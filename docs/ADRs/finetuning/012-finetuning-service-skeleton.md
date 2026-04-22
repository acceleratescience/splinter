# ADR-013. Fine-Tuning Service Skeleton

Date: 2026-04-22
Status: Proposed

## Context

With the high level service design established in ADR-011, the skeleton implementation required a set of concrete technical decisions: stack layout, base image and service framework.

## Decision

**Separate stack.** The fine-tuning service lives in `stacks/finetuning-service/` rather than extending the llm-service stack. This mirrors the monitoring stack pattern and allows the service to be brought up and down independently.

**Base image.** `axolotlai/axolotl-uv:main-py3.12-cu130-2.10.0` is used and pinned. The `-uv` variant is consistent with the team's preference for uv across the project. The image is pinned to a specific tag; updates are a deliberate decision, identical to our LiteLLM versioning. 

**FastAPI** for the service framework, with **SQLite** backed by a named Docker volume for job queue state. This is sufficient for a single-worker serialised queue and avoids a dependency on the existing PostgreSQL instance.

**Networking** between the fine-tuning service and LiteLLM (for future API key validation) uses `host.docker.internal` rather than joining the llm-service Docker network as an external network. This keeps the stacks decoupled.

## Consequences

- Hyperparameter configuration for training jobs is deferred; the job submission schema carries only the fields needed to identify the job.
- SQLite is sufficient now but migration to PostgreSQL remains possible if cross-service visibility is needed later.
