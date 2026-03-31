## 0XX — LiteLLM's admin UI is not a user-facing portal

**Date discovered:** 2026-03-24  
**Severity:** Architectural  
**Components:** LiteLLM admin UI, key management, user self-service

**Symptoms:**

After exposing the LiteLLM admin UI to beta users so they could generate their own API keys, several issues emerged in rapid succession:

1. **Key names are globally unique.** When a second user tried to create a key, they got an error because the first user had already used that alias. Key aliases are enforced as unique across the entire system, not scoped per user or per team.
2. **Key name is mandatory in the UI.** The API treats `key_alias` as optional - omit it and the key generates fine. The UI won't let you submit without one.
3. **Team selection is forced.** Users couldn't create personal keys without a default team being pre-configured. The UI requires a team even when the API doesn't.
4. **Users can see all models.** The model dropdown shows every model on the proxy regardless of the user's team restrictions. Enforcement happens at request time, but the UI gives the impression of unrestricted access.
5. **Internal links are broken.** A "navigate to virtual keys" link pointed to `/public?login=success&page=api-keys`, which returned a 404.
6. **User-to-key mapping is opaque.** Finding which keys belong to which user requires navigating multiple admin pages or hitting the API directly.

None of these are security vulnerabilities. Every restriction is enforced correctly at the API layer. But the cumulative effect is an admin interface being pressed into service as a self-serve developer portal — a role it was perhaps never designed for.

**Root cause:**

LiteLLM is an API gateway, not a developer platform. Its admin UI was built for operators managing a proxy, not for end users managing their own access (despite having things like self-signup options in their docker container...). The key alias uniqueness constraint likely exists because aliases are used as lookup identifiers in the admin interface — a reasonable design decision for an operator managing a fleet of keys, but nonsensical for users who each expect their own namespace. The forced team selection, mandatory fields, and model visibility are all admin-first design choices that become UX obstacles when the audience changes.

This is not a bug. It's more of a category error, where I'm trying to use a tool outside its design intent.

**Fix applied (short term):**

- Instruct users to set their API key names as <crsid>-whatevername
- Accepted that the admin UI is an admin tool, not a user tool.

**Alternatives evaluated:**

For institutions wanting to offer an OpenAI-like self-serve experience on top of self-hosted models, LiteLLM is the right backend but the wrong frontend. The options fall into three categories:

**1. Thin custom portal over LiteLLM's API**

Build a lightweight web app (Flask/FastAPI + React, or even a single-page app) that calls LiteLLM's API with the master key server-side. Users authenticate with the portal, which manages display names in its own database and calls `/key/generate` without aliases. LiteLLM never sees the display name; the portal maps its own per-user-scoped names to LiteLLM's hashed key tokens.

- **Pros:** Full control over UX. LiteLLM handles all the hard parts (auth enforcement, rate limiting, model routing, spend tracking). Small codebase — four pages (login, key list, create key, usage).
- **Cons:** You have to build and maintain it. Another service in the stack. Auth is your problem.
- **Verdict:** Best option for institutions with even modest dev resource. The portal is simple because LiteLLM's API is solid.

**2. LiteLLM Enterprise**

Pay for the enterprise tier, which includes SSO, better RBAC, team admin roles, and presumably a more polished UI experience.

- **Pros:** No custom development. Supported product.
- **Cons:** Cost. Vendor dependency — which conflicts with the sovereignty motivation of self-hosting in the first place. Feature set is still oriented toward internal API management, not external developer portals.
- **Verdict:** Reasonable if budget exists and the UI improvements are sufficient. Check before buying.

**3. Replace LiteLLM entirely**

Evaluate alternatives that were designed from the start for multi-tenant developer access:

- **Kong / Tyk / Gravitee** — Full API management platforms with developer portals, self-serve key management, rate limiting, and analytics. But they have no concept of LLM-specific concerns (token budgets, model routing, prompt logging). You'd need to bolt that on yourself.
- **Helicone / LiteLLM alternatives** — Emerging LLM-specific proxies with better user-facing features. Evaluate maturity before committing.
- **Bifrost** — Currently know nothing about Bifrost, but it comes highly recommended. Though it may lack support for image and audio models.
- **Custom gateway** — Build the whole thing. Maximum control, maximum effort. Only justified at significant scale.

- **Verdict:** Unsure at this stage.

**Lesson:**

I'm not sure that there is a lesson. Perhaps I did not research alternatives, and the end need well enough before picking LiteLLM.