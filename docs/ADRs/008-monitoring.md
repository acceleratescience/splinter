# ADR-005. Monitoring Stack

Date: 2025-12-09  
Status: Accepted
Status Change: 2026-02-08

## Context

Once the GPU server is operational and serving LLM inference, we need visibility into both hardware health and service utilisation. This serves two purposes: operational (detecting failures, capacity planning, performance tuning) and strategic (demonstrating impact to funders and stakeholders).

Without monitoring, we are flying blind on questions like: how heavily are the GPUs being utilised? Is the system thermally throttling? How much disk space remains? Are we approaching memory limits under concurrent load? Furthermore, when hardware fails, we need to know before our users do.

Several constraints shaped this decision:

- **Security posture**: The server is internet-facing for LLM inference. Monitoring dashboards and metrics endpoints must not be exposed to the public internet, as they reveal detailed system internals (OS version, filesystem layout, GPU configuration) that would aid an attacker.
- **Operational overhead**: We are a small team, not a dedicated ops function. The monitoring stack needs to be deployable in minutes and largely self-maintaining.
- **GPU-specific requirements**: Standard system monitoring tools (CPU, RAM, disk) are well-established, but GPU telemetry requires NVIDIA-specific tooling that integrates with the NVIDIA driver and container runtime.
- **Data retention**: We need to retain metrics long enough to produce meaningful usage reports (e.g., monthly or quarterly), but do not require long-term archival.
- **Reproducibility**: Consistent with the Splinter project's goals, the monitoring stack should be fully codified and reproducible by anyone adopting the blueprint.

## Decision

We deploy a containerised monitoring stack using Docker Compose, consisting of four services:

**Prometheus** as the time-series database and scrape coordinator. Prometheus pulls metrics from exporters on a 15-second interval and retains data for 30 days. It was chosen over alternatives (InfluxDB, Victoria Metrics) for its maturity, native integration with Grafana, and widespread adoption in the self-hosting and datacentre community — meaning documentation and community support are excellent.

**Grafana** for visualisation and dashboarding. Grafana connects to Prometheus via internal Docker DNS (`http://prometheus:9090`) and provides pre-built community dashboards for both system (Dashboard 1860) and GPU (Dashboard 12239) metrics. This avoids the need to build dashboards from scratch.

**Node Exporter** (`prom/node-exporter`) for host-level system metrics: CPU, RAM, disk, and network. It reads from `/proc` and `/sys` on the host via read-only bind mounts, providing comprehensive hardware telemetry without requiring elevated privileges beyond filesystem access.

**NVIDIA DCGM Exporter** (`dcgm-exporter`) for GPU-specific metrics: utilisation, memory usage, temperature, and power draw. This requires the NVIDIA Container Toolkit and access to all GPU devices. We pin to a specific image version (`3.3.5-3.4.1-ubuntu22.04`) rather than `latest` to avoid breaking changes from upstream.

All four services bind exclusively to `127.0.0.1`, meaning no monitoring ports are accessible from the network. Remote access is via SSH tunnel only (e.g., `ssh -L 3000:localhost:3000 user@server`). This is a deliberate security decision: exposing Grafana or Prometheus to the internet unnecessarily increases the attack surface.

Persistent data (Prometheus TSDB and Grafana configuration) is stored in named Docker volumes (`prometheus_data`, `grafana_data`), surviving container restarts and redeployments.

The entire stack is deployed via a single shell script that performs pre-flight checks (Docker running, NVIDIA runtime configured, GPU accessible), pulls images, starts containers, and runs health checks against all four services before reporting status.

## Consequences

**Benefits:**

- Full hardware and GPU observability from a single `docker compose up -d` command.
- Zero ports exposed to the network. The SSH tunnel approach is simple and eliminates an entire class of security concerns.
- 30-day metric retention is sufficient for monthly reporting without consuming excessive disk space.
- The stack is entirely codified — anyone adopting the Splinter blueprint can deploy identical monitoring by running one script.
- Pre-flight checks in the deployment script catch common issues (missing NVIDIA runtime, Docker not running) before they become confusing runtime failures.

**Tradeoffs and limitations:**

- SSH tunnelling for dashboard access adds friction for non-technical users. If we need to provide dashboard access to people who cannot use SSH, we will need to revisit this, likely by placing Grafana behind the existing Nginx reverse proxy with authentication. This is a conscious deferral, as it seems unlikely to be a problem
- Grafana ships with default credentials (`admin/admin`). The deployment script notes this but does not enforce a password change. For a single-admin system this is acceptable; for multi-user access it would need hardening.
- DCGM Exporter is pinned to a specific version, which means we must manually update it to pick up new metrics or bug fixes. This is preferred over `latest` for stability but requires periodic review.
- Prometheus runs as a single instance with local storage. This is appropriate for a single server but would not scale to a multi-node deployment without moving to remote storage (e.g., Thanos, Cortex) or a federated Prometheus setup.
- We do not currently have alerting configured. Grafana supports alerts natively, but defining meaningful thresholds (e.g., GPU temperature > 85°C, disk usage > 90%) is deferred until we have baseline operational data from the production server.
- The 30-day retention window means we cannot produce year-over-year comparisons. If long-term trend analysis becomes a requirement, we would need to either extend retention (at the cost of disk) or periodically export summary metrics to an external store.