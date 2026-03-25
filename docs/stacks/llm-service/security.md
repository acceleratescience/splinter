# LLM Inference Service Security

## Overview

The LLM service attempts to use a defence-in-depth model with five distinct security layers. Each layer operates independently so that a failure in one (hopefully) does not compromise the system. The service exposes a single public endpoint serving an OpenAI-compatible API to authenticated researchers.

```
Internet → Firewall → Fail2ban → Nginx → LiteLLM → vLLM
              ↕            ↕          ↕         ↕        ↕
          Ports 22,    IP bans    Auth,     API keys,  Internal
          80, 443     on abuse   filtering  rate limits  only
```

## Layer 1: Network (Firewall + SSH)

The host firewall restricts inbound traffic to three ports:

| Port | Service | Access |
|------|---------|--------|
| 22   | SSH     | Key-based authentication only, password auth disabled |
| 80   | HTTP    | Redirects to 443 after TLS setup |
| 443  | HTTPS   | Public API endpoint |

SSH is the only administrative access path. The LiteLLM admin UI (`/ui`) and the Grafana dashboard are accessible exclusively via SSH tunnel — it is blocked at both the Nginx and LiteLLM layers. Root login is disabled.

## Layer 2: Fail2ban

Two custom jails monitor Nginx access logs and issue temporary IP bans:

| Jail | Trigger | Threshold | Ban Duration |
|------|---------|-----------|--------------|
| `nginx-llm-blocked` | Requests returning 444 or 403 (attack vector paths, malformed probes) | 5 hits in 60s | 24 hours |
| `nginx-llm-auth` | Requests returning 401 (missing or invalid auth) | 10 hits in 60s | 1 hour |

This catches both automated scanners (which tend to hit blocked paths rapidly) and brute-force key guessing attempts.

## Layer 3: Nginx

Nginx is the primary security boundary. It handles all external traffic before anything reaches the Python application layer.

### Authentication Gate

A `map` directive validates the `Authorization` header format on every request. Requests without a valid header are rejected with 401 before reaching LiteLLM. This is a format check, not key validation — LiteLLM handles actual key verification. The purpose is to drop obviously invalid requests cheaply at the C level.

### Hostname Validation

A default server block drops connections to unrecognised hostnames or direct IP access:

```
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
    return 444;
}
```

This prevents host header injection and reduces noise from scanners that enumerate IP ranges.

### Rate Limiting

| Control | Value | Purpose |
|---------|-------|---------|
| Request rate | 10 req/s per IP | Prevents rapid-fire abuse |
| Burst allowance | 50 requests | Accommodates legitimate spikes |
| Connection limit | 20 per IP | Mitigates slowloris-style attacks |

These are safety backstops — LiteLLM enforces per-user rate limits as the primary mechanism.

### Timeouts

| Timeout | Value | Protects Against |
|---------|-------|------------------|
| `client_header_timeout` | 10s | Slowloris (slow header delivery) |
| `client_body_timeout` | 30s | Stalled uploads |
| `send_timeout` | 30s | Clients that stop reading |
| `keepalive_timeout` | 65s | Idle connection accumulation |
| `proxy_read_timeout` | 300s | Long LLM inference times |
| `proxy_send_timeout` | 300s | Long streaming responses |

### Path Blocking

Blocked paths are defined in a security snippet (`/etc/nginx/snippets/llm-security.conf`):

| Path Pattern | Response | Reason |
|--------------|----------|--------|
| `/ui` | 404 | Admin interface — SSH tunnel only |
| `/redoc`, `/docs`, `/openapi.json`, `/swagger`, `/test` | 404 | API documentation disclosure |
| `/config` | 404 | Configuration disclosure |
| `/health/liveliness`, `/health/readiness` | 404 | Internal health sub-endpoints |
| `.php`, `.asp`, `.env`, `.git`, `.sql`, `.bak` etc. | 444 | Common attack vectors |
| `wp-admin`, `wp-login`, `xmlrpc.php` | 444 | WordPress probes |

Returning 444 (drop connection silently) for attack vectors avoids giving scanners any information. Returning 404 for blocked application paths mimics "doesn't exist" rather than "forbidden".

### Security Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

These are standard hardening headers. Primarily relevant if any browser-based access occurs.

### Request Size

`client_max_body_size` is set to 10M. The service currently handles text-only inputs, so this is generous — it prevents abuse via oversized payloads while leaving headroom for future multimodal support.

## Layer 4: LiteLLM

LiteLLM provides application-level security as a second line of defence:

| Setting | Effect |
|---------|--------|
| API key authentication | Every request must carry a valid key issued via the admin panel |
| Per-user and per-team rate limits | Granular usage control beyond Nginx's IP-based limits |
| `ui_access_mode: "admin_only"` | Restricts admin UI to master key holders |
| `disable_generic_signup: true` | Prevents self-registration |
| `block_robots: true` | Prevents search engine indexing |
| `NO_DOCS` / `NO_REDOCS` env vars | Disables Swagger and ReDoc at application level |
| `drop_params: true` | Silently drops unsupported parameters instead of erroring |
| `set_verbose: false` | Prevents sensitive information leaking into logs |

The localhost-only port binding (`127.0.0.1:${LITELLM_PORT}:4000`) ensures LiteLLM is unreachable from the network — only Nginx on the same host can proxy to it.

## Layer 5: Docker Network Isolation

Services are isolated within the Docker network:

| Service | External Access | Internal Access |
|---------|----------------|-----------------|
| PostgreSQL | None | LiteLLM only (via Docker DNS) |
| vLLM | None (no port mapping) | LiteLLM only (via Docker DNS) |
| LiteLLM | localhost:${LITELLM_PORT} only | Nginx (on host) |

vLLM has no authentication of its own — security relies entirely on network isolation. It is never exposed outside the Docker network.

## TLS

TLS is provisioned post-deployment via Certbot:

```bash
sudo certbot --nginx -d ${DOMAIN}
```

Certbot modifies the Nginx config to listen on 443, redirect HTTP to HTTPS, and manage certificate renewal automatically. Until TLS is configured, API keys are transmitted in cleartext on port 80 which is not ideal.

## Redundancy Summary

Several controls are deliberately duplicated across layers:

| Control | Nginx | LiteLLM | Rationale |
|---------|-------|---------|-----------|
| Auth required | Header format check | Full key validation | Cheap rejection before Python |
| Admin UI blocked | `location /ui` returns 404 | `ui_access_mode: admin_only` | Defence in depth |
| Docs disabled | Path blocks return 404 | `NO_DOCS`, `NO_REDOCS` | Defence in depth |
| Rate limiting | IP-based at connection level | Per-user at application level | Different threat models |
| Robot blocking | No `robots.txt` served | `block_robots: true` | Defence in depth |

## Known Limitations (probably should sort these out...)

- **`/health` requires authentication**: External monitoring tools cannot hit the health endpoint without a valid API key. Consider exempting `/health` from the auth map if uptime monitoring is needed.
- **vLLM image uses `latest` tag**: A bad upstream release could break inference. Pin to a specific version for production stability.
- **No Docker network segmentation**: All three services share the default Docker network. vLLM can reach PostgreSQL despite having no reason to. Custom networks would tighten this.
- **No container resource limits**: A memory leak in LiteLLM or PostgreSQL could starve the GPU process. Consider adding `mem_limit` and `cpus` constraints.
- **No centralised logging**: Container logs rotate locally but are not shipped to the monitoring stack. Important for incident response and audit trails.
- **Window of cleartext before TLS**: Between deployment and Certbot execution, API keys transit over HTTP.