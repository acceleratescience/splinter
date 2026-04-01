## 001 — Self lockout

**Date discovered:** 2026-03-30  
**Severity:** Functional  
**Components:** LiteLLM UI, all LLM endpoints

**Symptoms:**
A lock out of all inference services, and the LiteLLM UI.

**Root cause:**
The LiteLLM UI, running in the browser, polls /health/readiness in the background to check service status. This endpoint is protected by nginx bearer token auth, but the UI sends a session cookie instead — so nginx returns 401 on every poll. When you made a bad API call, the UI likely refreshed aggressively, accumulating 5 × 401s within 60 seconds and tripping the nginx-llm-auth fail2ban jail.

This was essentially caused by [`gotcha-001`](./gotcha-001.md)

**Fix applied:**
Added an `ignoreregex` to the `nginx-llm-`auth` filter so that 401s on `/health/readiness` don't count toward the ban threshold. The endpoint stays protected — auth is unchanged — fail2ban just ignores the noise from the UI's legitimate polling.

**Considered but deferred:**

- **Exclude `/health/readiness` from bearer auth in the nginx map** — would stop the 401s entirely, but makes the endpoint publicly accessible, leaking LiteLLM version and internal callback/middleware names.
- **Inject master key server-side via nginx `proxy_set_header`** —  keeps real health checks working and avoids client exposure of the key, but still leaves the endpoint publicly accessible with the same information leakage concern.
- **Return a static `{"status":"ok"}` from nginx** — eliminates all leakage, but means the service always appears healthy even if LiteLLM or the DB is down.
- **IP allowlist / dedicated health-check key / internal-only port** — valid mitigations for the exposure problem, but add operational complexity for what is ultimately a low-severity self-banning issue.


**Lesson:**
How to unban oneself:

```bash
sudo fail2ban-client set nginx-llm-auth unbanip your.ip.address.here
```

Obviously you will need to SSH into the machine.