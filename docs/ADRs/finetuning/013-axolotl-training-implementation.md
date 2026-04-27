# ADR-013. Axolotl Training Implementation

Date: 2026-04-27
Status: Proposed

## Context

With the service skeleton established in ADR-012, the next decisions concerned the actual training pipeline: how Axolotl is invoked, how GPU utilisation is maximised on H100 hardware, how evaluation is handled and how optional integrations (Weights & Biases) are exposed to users.

## Decision

### Axolotl invocation

Axolotl is invoked as a subprocess (`axolotl train <config.yaml>`) rather than imported as a library. This keeps Axolotl's CUDA environment self-contained.

A per job Axolotl config is generated at runtime by merging a service level base config (`config.yaml`, mounted read-only) with the user's job parameters. The result is written to a temp directory (`/tmp/finetuning/{job_id}/`) and cleaned up unconditionally in a `finally` block after the subprocess exits.

### Worker as a separate container

The worker runs in its own container using the Axolotl base image (`axolotlai/axolotl:main-py3.12-cu130-2.10.0`). The API uses a separate lightweight Python image. Merging them would require the API to carry the full Axolotl image (several GB) for no benefit.

### Flash Attention 4

The Axolotl image ships Flash Attention 2 (FA2). On CUDA 13 / H100 hardware, FA2 produced a `CUBLAS_STATUS_INVALID_VALUE` error in the RoPE computation during evaluation, crashing jobs before training began. Installing Flash Attention 4 (`flash-attn-4[cu13]==4.0.0b10`) resolved this. FA4 is the architecturally correct choice for Hopper GPUs (H100) and is explicitly recommended by Axolotl in its startup logs for this hardware. The `[cu13]` extra selects the CUDA 13 wheel.

FA4 is pinned to a specific beta version. Upgrading is a deliberate decision identical to how we pin the Axolotl base image.

### Sample packing

Sample packing is enabled by default (`sample_packing: true`) and disabled for evaluation (`eval_sample_packing: false`). Without it, sequences are padded individually to `sequence_len`, resulting in approximately 55% padding waste on typical instruction-tuning datasets. With sample packing, multiple conversations are packed end-to-end into each sequence slot using Flash Attention masking to prevent cross conversation attention. This improved trainable token density to ~65% and GPU throughput ~9x on our test dataset.

Sample packing is not applied during evaluation: the eval set is usually small and packing adds complexity without meaningfully improving evaluation speed.

### Default sequence length

The default `sequence_len` is 2048. The original default of 512 dropped approximately 37% of training samples from our representative dataset (max sequence length ~1716 tokens). 2048 retains all sequences and, combined with sample packing, allows more conversations per packed slot. Users may override this per job.

### Evaluation control

Evaluation is opt-in. Jobs default to `do_eval: false`, which injects `eval_strategy: "no"` into the generated Axolotl config, overriding the base config's `eval_strategy: epoch`. When `do_eval: true`, the `validation` split of the user's dataset is used and evaluation runs at the end of each epoch.

This is opt-in rather than opt-out because many Hugging Face datasets do not include a `validation` split; silently failing a job because the split is absent is a worse experience than requiring users to explicitly request evaluation. SDK documentation will specify that users must include a `validation` split if they set `do_eval: true`.

### Weights & Biases integration

Optional wandb logging is supported via three fields: `wandb_token`, `wandb_project`, and `wandb_entity`. The token is handled identically to the HF token: stored in the database, passed to the Axolotl subprocess as `WANDB_API_KEY` and cleared to `NULL` on job completion.

Validation rules:
- `wandb_project` and `wandb_token` must be provided together.
- `wandb_entity` (a team/organisation name) may be omitted; wandb defaults to the user's personal account.
- Providing `wandb_entity` without `wandb_project` is rejected.

`wandb_entity` alone being omitted is the only partially specified combination that is permitted, reflecting wandb's own behaviour.

## Consequences

- Training jobs on H100 / CUDA 13 hardware work with FA4.
- Sample packing significantly improves GPU utilisation but compresses the effective number of training steps per epoch. For small datasets, users should be aware that a large `micro_batch_size` relative to the dataset size can result in very few optimiser steps per epoch.
- Evaluation requires users to know their dataset structure. No automatic detection of available splits is performed.
- Wandb tokens are treated as sensitive credentials and cleared after use, consistent with the HF token policy established in ADR-011.
