# ADR-011. Fine-Tuning Service

Date: 2026-04-22
Status: Proposed

## Context

The PRD (FR-FT-01, FR-FT-02) identifies LoRA/QLoRA fine-tuning as a "Should have" for Phase 2. The primary motivation is to allow researchers to adapt open weight models to domain-specific tasks (e.g. biology, materials science) without requiring cloud API access or local GPU hardware.

Several constraints shaped this design:

- **One GPU available**: At the time of writing, all four H100s are currently allocated to inference services. One GPU can be provisioned for fine-tuning, but it must be treated as a shared, serialised resource (concurrent training jobs are not feasible).
- **No file upload infrastructure**: The existing Nginx configuration restricts `client_max_body_size` to 10MB and there is no file storage layer. Building one would add significant operational complexity and security risk for little gain.
- **No per-user adapter serving**: Serving a fine-tuned adapter for a single user would require either dedicated GPU capacity or a hot-swap mechanism on a shared inference instance. Neither is practical at this scale. Adapters must be returned to users via Hugging Face rather than hosted.
- **Access control**: LiteLLM has no mechanism to restrict fine-tuning access to a subset of users. A separate whitelist is required; fine-tuning cannot simply inherit the existing API key auth layer without granting all key holders access to submit training jobs.
- **Security posture**: User-supplied credentials (HuggingFace tokens) must not be persisted in logs or the database beyond what is strictly necessary.

### Considered approaches for dataset delivery

**File upload via `/v1/files`**: LiteLLM routes this endpoint and it reaches the service (returning a 500 indicating `files_settings` is not configured, rather than a 404). However, enabling file storage requires configuring a backing store, raises questions about retention and quotas, and adds attack surface. Rejected.

**HuggingFace Hub reference**: Users provide a HF dataset repository path and a scoped HF token. The training service pulls the dataset directly from the Hub at job start. This avoids any file storage infrastructure on our side and is well-matched to how researchers already manage data. Selected.

### Considered approaches for adapter delivery

**Serve locally via vLLM LoRA**: vLLM supports dynamic LoRA adapter loading via `--enable-lora` and a `/v1/load_lora_adapter` endpoint. However, this means hosting a persistent model endpoint for one user's adapter, which is not a scalable use of GPU memory. Rejected.

**Push to user's HuggingFace Hub**: The training service uses the user's HF token (which must be write-scoped) to push the completed adapter back to their Hub. The user then has full ownership of the artifact and can load it however they choose. Selected.

### Considered approaches for client interface

Because fine-tuning access cannot be universally granted, and because the fine-tuning schema does not map cleanly onto the OpenAI fine-tuning spec (which requires a `file.id` to be submitted, mandating a file upload step we have rejected), we need a purpose-built client interface rather than relying on the OpenAI SDK alone. The design of that interface is covered in ADR-012.

## Decision

We implement a fine-tuning service as a custom Docker container added to the `llm-service` stack. Users interact with it via a Splinter SDK (see ADR-012), which handles authentication against LiteLLM API keys and a separate fine-tuning access whitelist.

The service exposes:

```
POST /v1/fine_tuning/jobs        — submit job, returns job ID + queued status
GET  /v1/fine_tuning/jobs/{id}   — poll status
GET  /v1/fine_tuning/jobs        — list user's jobs
POST /v1/fine_tuning/jobs/{id}/cancel
```

Job submissions return immediately with a job ID and `queued` status. All training is asynchronous.

### Training framework

[Axolotl](https://docs.axolotl.ai/) is used as the training framework, invoked as a subprocess by the service. It provides LoRA and QLoRA support, handles model loading from the HF Hub, and has stable support for the model families we serve (Qwen).

### Job queue and state

The service maintains a job queue backed by a SQLite database on a named Docker volume. This provides:

- Serialisation of jobs against the single available GPU
- Crash recovery: jobs that were `running` at startup are marked `failed` on restart, rather than hanging indefinitely
- Status polling without in-memory state

A future migration to the existing PostgreSQL instance is possible if cross-service visibility becomes a requirement.

### Training time limits

Each job has a configurable maximum wall clock duration (default: 4 hours). The service enforces this by terminating the Axolotl subprocess after the limit is reached and marking the job as `failed`. This prevents a single user from monopolising the GPU indefinitely.

### HF token handling

The HF token is used at job execution time to pull the dataset and push the completed adapter. It is:

- Not written to disk beyond what the HF Hub client requires transiently
- Not persisted to the job state database after the job completes

Users are responsible for supplying a token with appropriate scope (read access to the dataset repository, write access to the adapter destination). The service validates token validity at job submission time and fails fast if the token is invalid or insufficiently scoped.

Note: if requests pass through LiteLLM, the HF token will appear in its PostgreSQL request log. This is an acceptable risk given that the PostgreSQL instance is not externally accessible and HF tokens are revocable.

### Monitoring

The service exports Prometheus metrics on a `/metrics` endpoint, scraped by the existing Prometheus instance:

- Job queue depth (by status: `queued`, `running`, `failed`, `succeeded`)
- Job duration (histogram)
- GPU utilisation during training (via DCGM, already instrumented)
- HF pull and push durations

### GPU allocation

The fine-tuning service is allocated one H100 via `CUDA_VISIBLE_DEVICES`. The specific GPU to allocate is TBD pending a review of current GPU utilisation across the embedding, speech, and image generation services.

## Consequences

**Benefits:**

- Researchers can fine-tune domain-adapted models without cloud API access or local hardware, fulfilling FR-FT-01 and FR-FT-02.
- No file storage infrastructure required: datasets live on Hugging Face, adapters are returned there. The service itself is stateless with respect to artifacts.
- The existing auth layer (LiteLLM API keys, Bearer token validation, fail2ban) covers the request path; fine-tuning-specific access control is handled via the whitelist in the Splinter SDK layer.
- Crash recovery via DB-backed job state prevents ghost jobs.
- Training time limits protect the shared GPU from runaway jobs.

**Tradeoffs and limitations:**

- Single GPU, serialised queue: a busy period could mean significant wait times for users who submit large jobs. We have no current mechanism for estimating or communicating queue wait time to users. This is a known gap.
- HF tokens appear in LiteLLM's PostgreSQL request log.
- Adapter serving is out of scope. Users who want to run inference against their fine-tuned model must load it themselves, or wait for a future self-service model onboarding workflow (Phase 3 of the PRD).
