# ADR-011. Fine-Tuning Service

Date: 2026-04-20
Status: Proposed

## Context

The PRD (FR-FT-01, FR-FT-02) identifies LoRA/QLoRA fine-tuning as a "Should have" for Phase 2. The primary motivation is to allow researchers to adapt open weight models to domain-specific tasks (e.g. biology, materials science) without requiring cloud API access or local GPU hardware.

Several constraints shaped this design:

- **One GPU available**: At the time of writing, all four H100s are currently allocated to inference services. One GPU can be provisioned for fine-tuning, but it must be treated as a shared, serialised resource - concurrent training jobs are not feasible.
- **No file upload infrastructure**: The existing Nginx configuration restricts `client_max_body_size` to 10MB and there is no file storage layer. Building one would add significant operational complexity and security risk for little gain.
- **API compatibility**: The rest of the stack is OpenAI API compatible via LiteLLM. Users and tooling already expect this interface. Breaking from it for fine-tuning would increase friction.
- **No per-user adapter serving**: Serving a fine-tuned adapter for a single user would require either dedicated GPU capacity or a hot-swap mechanism on a shared inference instance. Neither is practical at this scale. Adapters must be returned to users via Hugging Face rather than hosted.
- **Security posture**: User supplied credentials (HuggingFace tokens) must not be persisted in logs or the LiteLLM database beyond what is strictly necessary. This is the point requiring the most consideration.

### Considered approaches for dataset delivery

**File upload via `/v1/files`**: LiteLLM routes this endpoint and it reaches the service (returning a 500 indicating `files_settings` is not configured, rather than a 404). However, enabling file storage requires configuring a backing store, raises questions about retention and quotas, and adds attack surface. Rejected.

**HuggingFace Hub reference**: Users provide a HF dataset repository path and a scoped HF token. The training service pulls the dataset directly from the Hub at job start. This avoids any file storage infrastructure on our side and is well-matched to how researchers already manage data. Selected.

### Considered approaches for adapter delivery

**Serve locally via vLLM LoRA**: vLLM supports dynamic LoRA adapter loading via `--enable-lora` and a `/v1/load_lora_adapter` endpoint. However, this means hosting a persistent model endpoint for one user's adapter, which is not a scalable use of GPU memory. Rejected.

**Push to user's HuggingFace Hub**: The training service uses the user's HF token (which must be write-scoped) to push the completed adapter back to their Hub. The user then has full ownership of the artifact and can load it however they choose. Selected.

## Decision

We implement a fine-tuning service as a custom Docker container added to the `llm-service` stack, exposed through the existing LiteLLM proxy using a passthrough route.

### API surface

Because the fine-tuning service uses a LiteLLM passthrough route (see below), LiteLLM forwards the request body entirely unmodified, i.e. it does not validate or transform it. This means **the request schema is fully under our control** and is not constrained by the OpenAI fine-tuning spec.

This opens a design decision that is unresolved at the time of writing:

---

**Option A: Custom schema, called via `httpx`/`requests`**

Define a clean, purpose-built schema with no inherited awkwardness from the OpenAI spec. The HF token is a top-level field, not buried in `hyperparameters`. Users call the endpoint directly using standard HTTP libraries:

```
POST /v1/fine_tuning/jobs
{
  "model": "Qwen/Qwen3.5-27B-FP8",
  "hf_dataset": "org/my-dataset",
  "hf_token": "hf_...",
  "suffix": "my-experiment",
  "n_epochs": 3,
  "batch_size": 4,
  "learning_rate_multiplier": 1.0,
  "lora_rank": 16,
  "lora_alpha": 32,
  "lora_target_modules": ["q_proj", "v_proj"],
  "quantization": "qlora"
}
```

*Pros*: clean schema, no spec contortion, no additional dependency for users.
*Cons*: users cannot use the OpenAI Python SDK (which enforces `training_file` as a required field client-side); they must use raw HTTP.

---

**Option B: OpenAI-compatible schema, called via the OpenAI SDK**

Conform to the OpenAI fine-tuning spec so users can use the OpenAI Python SDK without installing anything extra. `training_file` is repurposed to carry the HF dataset path (e.g. `hf://org/my-dataset`), and the HF token is passed inside `hyperparameters` — the only extensible field the spec provides:

```
POST /v1/fine_tuning/jobs
{
  "model": "Qwen/Qwen3.5-27B-FP8",
  "training_file": "hf://org/my-dataset",
  "suffix": "my-experiment",
  "hyperparameters": {
    "n_epochs": 3,
    "batch_size": 4,
    "learning_rate_multiplier": 1.0,
    "hf_token": "hf_...",
    "lora_rank": 16,
    "lora_alpha": 32,
    "lora_target_modules": ["q_proj", "v_proj"],
    "quantization": "qlora"
  }
}
```

*Pros*: works with `openai` Python SDK out of the box; consistent with the rest of the stack.
*Cons*: `training_file` semantics are misleading; HF token as a "hyperparameter" is awkward; `drop_params: true` in LiteLLM may strip unknown `hyperparameters` fields (requires empirical verification).

---

**Option C: Thin Splinter SDK**

Publish a small Python package (`splinter-client` or similar) that wraps the custom schema from Option A and provides a clean, documented interface. Users `pip install` it alongside their existing `openai` client:

```python
from splinter import SplinterClient

client = SplinterClient(base_url="https://<domain>", api_key="sk-...")
job = client.fine_tuning.jobs.create(
    model="Qwen/Qwen3.5-27B-FP8",
    hf_dataset="org/my-dataset",
    hf_token="hf_...",
    n_epochs=3,
    lora_rank=16,
)
```

*Pros*: clean schema and ergonomic interface; can add Splinter-specific features (queue position, estimated wait time) without spec constraints; sets a foundation for future platform-specific tooling.
*Cons*: additional package to maintain and distribute; users must install it (minor friction, but non-zero).

---

**Recommendation**: ???

*This decision should be made before implementation begins.*

---

In all options, the endpoint structure is:

```
POST /v1/fine_tuning/jobs        — submit job, returns job ID + queued status
GET  /v1/fine_tuning/jobs/{id}   — poll status
GET  /v1/fine_tuning/jobs        — list user's jobs
POST /v1/fine_tuning/jobs/{id}/cancel
```

Job submissions return immediately with a job ID and `queued` status. All training is asynchronous.

### LiteLLM routing

Rather than using LiteLLM's native fine-tuning model mode (which expects strict OpenAI schema and is less battle-tested than the inference routing), we use a passthrough route. LiteLLM validates the user's Bearer token and forwards the full request body unmodified to the fine-tuning container:

```yaml
general_settings:
  passthrough_endpoints:
    - path: "/v1/fine_tuning/jobs"
      target: "http://finetuning-service:8005/v1/fine_tuning/jobs"
```

This preserves the existing auth model (all requests require a valid LiteLLM API key) without requiring the service to reimplement authentication.

### Training framework

[Axolotl](https://docs.axolotl.ai/) is used as the training framework, invoked as a subprocess by the service. It provides LoRA and QLoRA support, handles model loading from the HF Hub, and has stable support for the model families we serve (Qwen).

### Job queue and state

The service maintains a job queue backed by a SQLite database on a named Docker volume. This provides:

- Serialisation of jobs against the single available GPU
- Crash recovery: jobs that were `running` at startup are marked `failed` on restart, rather than hanging indefinitely
- Status polling without in-memory state

A future migration to the existing PostgreSQL instance is possible if cross-service visibility becomes a requirement.

### Training time limits

Each job has a configurable maximum wall clock duration (default: 4 hours). The service enforces this by terminating the axolotl subprocess after the limit is reached and marking the job as `failed`. This prevents a single user from monopolising the GPU indefinitely.

### HF token handling

The HF token is used at job execution time to pull the dataset and push the completed adapter. It is:

- Not written to disk beyond what the HF Hub client requires transiently
- Not persisted to the job state database after the job completes

Users are responsible for supplying a token with appropriate scope (read access to the dataset repository, write access to the adapter destination repository). This requirement is documented; the service validates token validity at job submission time and fails fast if the token is invalid or insufficiently scoped.

Note: LiteLLM logs request bodies to PostgreSQL. The HF token will therefore appear in the LiteLLM request log for the submission call. This is could be an acceptable risk given that: (a) the PostgreSQL instance is not externally accessible, (b) HF tokens are revocable, and (c) the alternative (a pre-registration flow) adds significant implementation complexity. 

### Monitoring

The service exports Prometheus metrics on a `/metrics` endpoint, scraped by the existing Prometheus instance:

- Job queue depth (by status: `queued`, `running`, `failed`, `succeeded`)
- Job duration (histogram)
- GPU utilisation during training (via DCGM, already instrumented)
- HF pull and push durations

### GPU allocation

The fine-tuning service is allocated one H100 via `CUDA_VISIBLE_DEVICES`. The specific GPU to allocate is TBD pending a review of current GPU 3 utilisation (which currently runs four services: embedding, speech and two image generation models).

## Consequences

**Benefits:**

- Researchers can fine-tune domain adapted models without cloud API access or local hardware, fulfilling FR-FT-01 and FR-FT-02.
- No file storage infrastructure required: datasets live on Hugging Face, adapters are returned there. The service itself is stateless with respect to artifacts.
- Full OpenAI API compatibility means existing tooling and client libraries work without modification.
- The existing auth layer (LiteLLM API keys, Bearer token validation, fail2ban) covers fine-tuning requests with no additional work.
- Crash recovery via DB backed job state prevents ghost jobs.
- Training time limits protect the shared GPU from runaway jobs.

**Tradeoffs and limitations:**

- The API schema decision (Options A/B/C above) is unresolved. Option B's OpenAI compatibility comes with schema awkwardness; Options A and C are cleaner but require users to use raw HTTP or install an additional package.
- Single GPU, serialised queue: a busy period could mean significant wait times for users who submit large jobs. We have no current mechanism for estimating or communicating queue wait time to users. This is a known gap.
- HF tokens appear in LiteLLM's PostgreSQL request log.
- Adapter serving is out of scope. Users who want to run inference against their fine-tuned model must load it themselves (e.g. locally, or via a future self-service model onboarding workflow described in Phase 3 of the PRD).
- If Option B is selected, `drop_params: true` in `litellm_config.yaml` may strip unknown `hyperparameters` fields before they reach the container. This must be verified empirically; the fix is to exempt the passthrough route from parameter dropping.
