"""Fail2ban Geo Exporter - Prometheus exporter for fail2ban with GeoIP enrichment."""

import gzip
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import geoip2.database
import requests
from prometheus_client import Gauge, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FAIL2BAN_LOG = os.environ.get("FAIL2BAN_LOG", "/var/log/fail2ban.log")
GEOIP_DB_PATH = os.environ.get("GEOIP_DB_PATH", "/data/geoip/dbip-city-lite.mmdb")
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9122"))
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "30"))  # seconds

# DB-IP Lite is free (CC-BY-4.0), no account required
GEOIP_DB_URL_TEMPLATE = (
    "https://download.db-ip.com/free/dbip-city-lite-{year}-{month:02d}.mmdb.gz"
)

# Regex for fail2ban log lines
# Matches: 2024-01-15 12:34:56,789 fail2ban.actions ... Ban 1.2.3.4
BAN_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+"
    r"fail2ban\.actions\s*\[.*?\]:\s*\w+\s+\[(\w[\w-]*)\]\s+Ban\s+(\S+)"
)
UNBAN_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}),\d+\s+"
    r"fail2ban\.actions\s*\[.*?\]:\s*\w+\s+\[(\w[\w-]*)\]\s+Unban\s+(\S+)"
)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
BANNED_IP = Gauge(
    "fail2ban_banned_ip",
    "Currently banned IP, value is ban timestamp in epoch ms",
    ["ip", "jail", "country", "city", "latitude", "longitude", "active"],
)
BANNED_IP_HISTORICAL = Gauge(
    "fail2ban_banned_ip_historical",
    "All IPs ever banned, value is ban timestamp in epoch ms",
    ["ip", "jail", "country", "city", "latitude", "longitude", "active"],
)
BAN_EVENT = Gauge(
    "fail2ban_ban_event",
    "Individual ban event, value is ban timestamp in epoch ms",
    ["ip", "jail", "country", "city", "latitude", "longitude", "event_id"],
)
BANS_PER_HOUR = Gauge(
    "fail2ban_bans_per_hour",
    "Ban events bucketed by hour, value is count. Label 'bucket' is epoch ms of hour start.",
    ["jail", "bucket"],
)
BANNED_CURRENT = Gauge(
    "fail2ban_banned_current",
    "Number of currently banned IPs per jail",
    ["jail"],
)

# ---------------------------------------------------------------------------
# GeoIP database management
# ---------------------------------------------------------------------------

def download_geoip_db(dest: str) -> bool:
    """Download the free DB-IP Lite City database."""
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        # Refresh monthly - check age
        age_days = (time.time() - dest_path.stat().st_mtime) / 86400
        if age_days < 35:
            log.info("GeoIP database is recent (%.0f days old), skipping download", age_days)
            return True

    now = datetime.now(timezone.utc)
    # Try current month, then previous month
    for month_offset in [0, -1]:
        month = now.month + month_offset
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        url = GEOIP_DB_URL_TEMPLATE.format(year=year, month=month)
        log.info("Downloading GeoIP database from %s", url)
        try:
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            gz_path = dest + ".gz"
            with open(gz_path, "wb") as f:
                shutil.copyfileobj(resp.raw, f)
            with gzip.open(gz_path, "rb") as f_in, open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(gz_path)
            log.info("GeoIP database downloaded successfully")
            return True
        except Exception as e:
            log.warning("Failed to download GeoIP DB for %d-%02d: %s", year, month, e)

    return False


class GeoResolver:
    """Resolve IP addresses to geographic coordinates using GeoIP2."""

    def __init__(self, db_path: str):
        self.reader = None
        self.cache: dict[str, dict] = {}
        try:
            self.reader = geoip2.database.Reader(db_path)
            log.info("GeoIP database loaded from %s", db_path)
        except Exception as e:
            log.error("Failed to load GeoIP database: %s", e)

    def lookup(self, ip: str) -> dict:
        if ip in self.cache:
            return self.cache[ip]

        result = {
            "country": "Unknown",
            "city": "Unknown",
            "latitude": "0",
            "longitude": "0",
        }

        if self.reader is None:
            return result

        try:
            resp = self.reader.city(ip)
            result = {
                "country": resp.country.name or "Unknown",
                "city": resp.city.name or "Unknown",
                "latitude": str(resp.location.latitude or 0),
                "longitude": str(resp.location.longitude or 0),
            }
        except Exception:
            pass  # Private IPs, unknown IPs, etc.

        self.cache[ip] = result
        return result


# ---------------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------------

class Fail2banLogParser:
    """Parse fail2ban log and track ban/unban state."""

    def __init__(self):
        # {jail: {ip: ban_epoch}} - currently active bans
        self.banned: dict[str, dict[str, float]] = {}
        # {jail: {ip: ban_epoch}} - all unique IPs ever banned
        self.all_banned: dict[str, dict[str, float]] = {}
        # Every individual ban event: (event_id, jail, ip, epoch_ms)
        self.ban_events: list[tuple[int, str, str, float]] = []
        self._next_event_id = 0
        self.last_position = 0
        self.last_inode = None

    @staticmethod
    def _parse_timestamp(ts: str) -> float:
        """Convert fail2ban log timestamp to unix epoch milliseconds."""
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").timestamp() * 1000

    def parse(self, log_path: str):
        """Read new lines from fail2ban log and update state."""
        try:
            stat = os.stat(log_path)
        except FileNotFoundError:
            log.warning("Fail2ban log not found: %s", log_path)
            return

        current_inode = stat.st_ino

        # Detect log rotation (inode change or file shrunk)
        if self.last_inode is not None and (
            current_inode != self.last_inode or stat.st_size < self.last_position
        ):
            log.info("Log rotation detected, resetting position")
            self.last_position = 0

        self.last_inode = current_inode

        if stat.st_size <= self.last_position:
            return

        with open(log_path, "r") as f:
            f.seek(self.last_position)
            for line in f:
                line = line.strip()
                ban_match = BAN_RE.match(line)
                if ban_match:
                    timestamp, jail, ip = ban_match.groups()
                    epoch = self._parse_timestamp(timestamp)
                    self.banned.setdefault(jail, {})[ip] = epoch
                    self.all_banned.setdefault(jail, {})[ip] = epoch
                    self.ban_events.append((self._next_event_id, jail, ip, epoch))
                    self._next_event_id += 1
                    continue

                unban_match = UNBAN_RE.match(line)
                if unban_match:
                    _, jail, ip = unban_match.groups()
                    if jail in self.banned:
                        self.banned[jail].pop(ip, None)

            self.last_position = f.tell()


# ---------------------------------------------------------------------------
# Metric updater
# ---------------------------------------------------------------------------

def update_metrics(parser: Fail2banLogParser, geo: GeoResolver):
    """Update Prometheus metrics from parsed state."""
    BANNED_IP._metrics.clear()
    BANNED_IP_HISTORICAL._metrics.clear()
    BAN_EVENT._metrics.clear()

    # Currently active bans - value is ban timestamp (epoch ms)
    for jail, ips in parser.banned.items():
        BANNED_CURRENT.labels(jail=jail).set(len(ips))
        for ip, epoch in ips.items():
            loc = geo.lookup(ip)
            BANNED_IP.labels(
                ip=ip,
                jail=jail,
                country=loc["country"],
                city=loc["city"],
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                active="Banned",
            ).set(epoch)

    # All unique IPs ever banned - value is ban timestamp (epoch ms)
    for jail, ips in parser.all_banned.items():
        currently_banned = parser.banned.get(jail, {})
        for ip, epoch in ips.items():
            loc = geo.lookup(ip)
            active = "Banned" if ip in currently_banned else "Unbanned"
            BANNED_IP_HISTORICAL.labels(
                ip=ip,
                jail=jail,
                country=loc["country"],
                city=loc["city"],
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                active=active,
            ).set(epoch)

    # Every individual ban event - value is ban timestamp (epoch ms)
    for event_id, jail, ip, epoch in parser.ban_events:
        loc = geo.lookup(ip)
        BAN_EVENT.labels(
            ip=ip,
            jail=jail,
            country=loc["country"],
            city=loc["city"],
            latitude=loc["latitude"],
            longitude=loc["longitude"],
            event_id=str(event_id),
        ).set(epoch)

    # Hourly histogram of ban events
    BANS_PER_HOUR._metrics.clear()
    hourly: dict[tuple[str, int], int] = defaultdict(int)
    ms_per_hour = 3_600_000
    for _, jail, _, epoch in parser.ban_events:
        bucket = int(epoch // ms_per_hour) * ms_per_hour
        hourly[(jail, bucket)] += 1
    for (jail, bucket), count in hourly.items():
        BANS_PER_HOUR.labels(jail=jail, bucket=str(bucket)).set(count)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("Starting fail2ban geo exporter on port %d", EXPORTER_PORT)
    log.info("Watching log: %s", FAIL2BAN_LOG)

    # Download / verify GeoIP database
    if not Path(GEOIP_DB_PATH).exists():
        if not download_geoip_db(GEOIP_DB_PATH):
            log.warning("Running without GeoIP - locations will show as Unknown")

    geo = GeoResolver(GEOIP_DB_PATH)
    parser = Fail2banLogParser()

    start_http_server(EXPORTER_PORT)
    log.info("Prometheus metrics server started on :%d", EXPORTER_PORT)

    while True:
        try:
            parser.parse(FAIL2BAN_LOG)
            update_metrics(parser, geo)
        except Exception as e:
            log.error("Error during scan: %s", e)
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
