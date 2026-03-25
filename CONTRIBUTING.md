# Contributing to Splinter

Thanks for your interest in contributing to Splinter. This document covers the conventions and processes we use.

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/). Every commit message should follow this format:

```
type(scope): short description
```

**Types:**

- `feat` — A new feature or capability
- `fix` — A bug fix
- `docs` — Documentation changes (ADRs, READMEs, guides)
- `chore` — Maintenance tasks (dependency bumps, image version updates)
- `refactor` — Code restructuring with no behaviour change
- `ci` — Changes to CI/CD configuration
- `test` — Adding or updating tests or benchmarks

**Scope** is optional but encouraged. Use it to indicate the area of the codebase:

- `ansible` — Ansible playbooks and roles
- `monitoring` — Prometheus, Grafana, exporters
- `llm` — vLLM, LiteLLM, inference service
- `nginx` — Reverse proxy configuration
- `docker` — Docker Compose files and container configuration
- `adr` — Architecture Decision Records
- `workshop` — JupyterHub and workshop environments

**Examples:**

```
feat(monitoring): add GPU temperature alerting
fix(nginx): correct rate limit configuration
docs(adr): add ADR-007 service access
chore(docker): bump DCGM exporter to 3.3.6
refactor(ansible): extract common tasks into shared role
```

Keep the description lowercase, imperative mood ("add" not "added"), and under 72 characters.

## Branching and Pull Requests

- All changes go through pull requests. No direct pushes to `main`.
- PRs require at least one approval before merging.
- Resolve all review conversations before merging.
- Commits must be signed (GPG or SSH).

## Reporting Issues

Use GitHub Issues. For bugs, include: what you expected, what happened, and any relevant logs or configuration. For feature requests, describe the use case, not just the solution.

## Security

If you discover a security vulnerability, **do not** open a public issue. Email the maintainers directly. See the repository's security policy for contact details.
