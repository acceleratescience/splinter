# ADR-014. Fine-Tuning Service Authentication

Date: 2026-04-28
Status: Proposed

## Context

The fine-tuning service exposes HTTP endpoints for submitting and managing training jobs. Without authentication, any user on the network could submit jobs, consuming GPU time and potentially exfiltrating model adapters. Splinter already operates a LiteLLM proxy that issues and manages API keys for all users, making it the natural authority for key validation.

## Decision

### LiteLLM key validation

All `/v1/fine_tuning/*` endpoints require a Bearer token. On each request the service calls LiteLLM's `/key/info` endpoint using the service's own master key to verify the token. A 200 response means the key is valid and active; anything else returns 401 to the caller. The `/health` endpoint is left unauthenticated.

This avoids maintaining a second credential store. Users present the same API key they already use for inference.

### FastAPI dependency injection

The auth logic is implemented as a FastAPI dependency (`verify_litellm_key`) applied at the router level rather than per-route. This ensures new routes are protected by default without any per-route ceremony.

### Inter-container networking

The API container reaches LiteLLM via a shared external Docker network (`finetuning_default`) rather than `host.docker.internal`. LiteLLM is bound to `127.0.0.1` on the host (loopback only), so `host.docker.internal` (which resolves to the Docker bridge gateway, not loopback) cannot reach it. Joining both containers to a shared network allows the API to address LiteLLM directly by container name (`http://litellm-proxy:4000`), the same pattern used by the monitoring stack.

### User allowlist

An optional `whitelist.txt` file (one LiteLLM user ID per line) can be placed alongside the compose file to restrict access to specific users. The user ID is extracted from the `/key/info` response. If `whitelist.txt` is absent, any valid LiteLLM key is accepted. The file is gitignored and never committed; `whitelist.txt.example` is committed as a template.

Reading the allowlist on every request (rather than at startup) means the list can be updated without restarting the service.

## Consequences

- Users must include `Authorization: Bearer <litellm-key>` on all fine-tuning requests.
- Each authenticated request incurs one additional HTTP call to LiteLLM. This is acceptable given that fine-tuning job submission is infrequent and not latency sensitive.
- The LiteLLM master key must be present in the finetuning service `.env` as `LITELLM_MASTER_KEY`.
