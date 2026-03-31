## 005 — Floating container tag pulled a broken nightly build

**Date discovered:** 2026-03-24  
**Severity:** Service outage  
**Components:** LiteLLM, Docker Compose, container image tagging

**Symptoms:**

After running `docker compose up -d`, the LiteLLM proxy entered a crash loop. Logs showed a Prisma engine failure — the ORM couldn't connect to its own internal query engine, with a `httpx.ConnectError: All connection attempts failed` traceback. The Postgres database was healthy, vLLM containers were running, but no API requests could be served.

**Root cause:**

The `docker-compose.yml` specified `ghcr.io/berriai/litellm:main-latest` as the image tag. On `docker compose up -d`, Docker pulled whatever image currently occupied that tag — which happened to be a nightly development build with a Python 3.13 / Prisma incompatibility. The previous working image was overwritten locally; `docker images` showed only the new broken one. There was no way to recover the previous version without knowing its specific tag or digest.

**Fix applied:**

Pinned the image to the latest stable release:

```yaml
image: ghcr.io/berriai/litellm:main-v1.81.12-stable.1
```

Then pulled and recreated:

```bash
docker compose pull litellm
docker compose up -d --force-recreate litellm
```

**Considered but rejected:**

- **Rolling back via image digest** - The old image was already overwritten locally. Without a prior record of the digest, there was nothing to roll back to.
- **Tracking `main-stable` instead of `main-latest`** - Better than `latest`, but still a floating tag that can change without warning. A pinned version is the only guarantee.

**Lesson:**

Floating tags like `latest`, `stable`, or `nightly` are aliases that can point to a different image at any moment. In production, they create a coupling between "when you happen to pull" and "what you get" - a form of non-determinism that's invisible until it breaks. Pin to a specific version tag. Upgrade deliberately by changing the tag, pulling, testing, and committing the change. This applies to every container in the stack.

Importantly, this has lead to us pinning all containers. And after the recent LiteLLM supply chain attack, pinned by hash.