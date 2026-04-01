## 002 — LiteLLM admin UI unusable through public domain

**Date discovered:** 2026-03-20  
**Severity:** Functional  
**Components:** nginx, security.conf.template, nginx.conf.template, LiteLLM admin UI

**Symptoms:**
Creating pass-through endpoints or virtual API keys via the LiteLLM admin UI fails with `SyntaxError: Unexpected token '<', "<html> <h"... is not valid JSON`. Browser dev tools show `POST /config/pass_through_endpoint` returning 404 and `GET /health/readiness` returning 404. Users cannot self-service their own API keys through the public-facing UI.

**Root cause:**
The nginx security snippet applied blanket Bearer token authentication to all requests and explicitly blocked paths the UI depends on (`/config` → 404, `/health/readiness` → 404, `/health/liveliness` → 404). When the browser-based admin panel made internal API calls to these endpoints, nginx rejected them before they reached LiteLLM. The HTML error pages returned by nginx were not valid JSON, causing the frontend parse error.

**Fix applied:**
Replaced the blanket auth-everything approach with selective Bearer auth using an nginx `map` directive on `$uri`. API-facing paths (`/v1/`, `/chat/`, `/completions`, `/embeddings`, `/audio/`, `/models`, `/health`, `/hpc`) require a valid Bearer token at the nginx layer. All other paths (UI, config, key management) pass through to LiteLLM, which handles its own authentication via session cookies and master key validation. The `/config`, `/health/readiness`, and `/health/liveliness` block directives were removed from the security snippet.

**Considered but deferred:**
Restricting the UI to SSH tunnel access only (`allow 127.0.0.1; deny all;` on `/ui`) was considered but rejected because it defeats the purpose of users self-servicing their own API keys. An allowlist of specific UI-related paths was considered but deemed fragile — any LiteLLM update adding new internal endpoints would break again.

**Lesson:**
When proxying an application that serves both an API and a web UI, apply ingress auth selectively by endpoint type rather than globally. The web UI has its own auth flow that breaks when an upstream proxy demands credentials the browser cannot provide. Prefer allowlisting paths that need proxy-level auth over blocklisting paths that don't.