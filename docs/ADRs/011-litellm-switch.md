# ADR-011. Switch from LiteLLM to Bifrost and custom portal

Date: 2026-04-08
Status: Proposed

## Context
Currently, LiteLLM is less than desirable as a user portal. The following issues have occured:

### 1. Globally unique key aliases

Key aliases are enforced as unique across the entire instance. If one user names their key "default", no other user can use that name. There is no per-user namespace, so alias collisions become inevitable as the user base grows.

### 2. Forced team selection

Users are required to select a team when creating a key. This makes no sense for individual researchers who just want a personal API key — it adds friction and confusion to a task that should be trivial.

### 3. Broken internal API calls

The UI makes requests to internal paths like `/config/pass_through_endpoint` and `/health/readiness` that are legitimately blocked by any hardened nginx configuration. This means the UI only works reliably via SSH tunnel to localhost, not through the public-facing reverse proxy. Even after reworking auth to selective path-based gating, the UI's internal call patterns remain fragile.

### 4. No separation between admin and user views

There is no "user mode". The UI is a single admin panel — you either give someone full administrative access or nothing useful. There's no scoped view where a user can manage only their own keys and see only their own usage.

### 5. SSO requires an enterprise licence

Institutional authentication (e.g. Raven/CRSID at Cambridge) cannot be integrated without a paid LiteLLM enterprise licence. The only alternatives are manual user creation by an admin or setting `disable_generic_signup: false`, which allows anyone who can reach the UI to create an account.

### 6. UI auth conflicts with reverse proxy auth

The browser-based UI cannot attach Bearer tokens to its own internal API calls. This fundamentally conflicts with any nginx-level auth layer. In practice, this was the root cause of a fail2ban self-lockout loop: the UI polled unauthenticated endpoints, generating 401 responses that fail2ban interpreted as brute-force login attempts.

### 7. No user-friendly key metadata

Users cannot set meaningful display names or descriptions for their keys. The only mechanism is the alias field, which is globally namespaced (see issue 1) and not designed for user-facing labelling.


## Decision
A custom user portal built over LiteLLM's management API is the identified long-term architecture. The API provides everything needed for key creation, usage queries, and model listing — the portal just needs to present it with proper per-user scoping, sensible defaults, and no admin footguns (feetguns?).

We will switch to Bifrost, an API gateway written in Go (as opposed to LiteLLM which is written in Python). We will then build a frontend around 

## Consequences
What are the tradeoffs?