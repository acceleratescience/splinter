# Product Requirements Document: Splinter LLM Infrastructure

> **Status:** Draft  
> **Author:** R. K. Daniels  
> **Last updated:** 2026-03-31  
> **Version:** 0.3  

---

## 1. Executive Summary

Splinter is a self-hosted LLM inference and serving platform built on GPU server hardware by the Accelerate Programme for Scientific Discovery. It provides researchers at Cambridge with secure, low-latency access to open-weight language models – including text generation, embeddings, speech, and image generation – without dependence on commercial API providers.

The platform serves two distinct purposes: (1) an operational research service for the Cambridge community, and (2) an open-source reference implementation for small research groups wishing to safely self-host LLMs. Both purposes are documented within this repository.

---

## 2. Problem Statement

### 2.1 Context

There is strong demand from the research community for local, open-source LLM access. Researchers are already self-hosting models for their individual groups, but the default behaviour of many serving frameworks leaves systems open to security vulnerabilities. At the same time, guidance on how to operate such systems safely at scale is scarce and scattered across blog posts, subreddits, technical documentation, and tribal knowledge.

Given this, the Accelerate Programme is positioned to offer two things:

1. A free, secure LLM service for the Cambridge research community
2. An open-source infrastructure repository for small research groups to safely serve LLMs

### 2.2 Pain Points

**General LLM Use**

- Researchers who need LLMs must sign up to commercial API platforms, which carry a financial cost. Even modest costs are a barrier to experimentation for many academics.
- High-throughput use cases (many requests, large output token counts) generate significant bills on commercial platforms, despite not requiring frontier-level model capabilities.

**Local LLM Deployment**

- Small research groups that self-host typically lack the infrastructure expertise to do so securely. Default configurations often expose unauthenticated endpoints to the internet.
- Operational knowledge – inference engine selection, monitoring, access management, security hardening – is fragmented across sources and not easily synthesised.

---

## 3. Goals & Success Criteria

### 3.1 Goals

**Primary goals:**

- Provide on-demand LLM inference to ≥ 100 concurrent users at acceptable latency.
- Provide an open-source, documented framework for others to replicate this deployment.

**Secondary goals:**

- Provide access to open-weight image generation and speech models.
- Produce Architecture Decision Records (ADRs) so replicators understand the reasoning behind choices, not just the choices themselves.

### 3.2 Non-Goals

- Not a general-purpose HPC cluster or batch compute facility.
- Not intended for training foundation models from scratch.
- Not a replacement for commercial cloud services for frontier-model use cases (e.g. coding agents requiring GPT-4-class capability).
- Not a managed service; users who require guaranteed SLAs should use commercial APIs.
- Not scoped to support external collaborators or public internet access beyond the Cambridge research community at this stage.

### 3.3 Success Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Inference latency (P95 TTFT, 7B-class model) | ≤ 500 ms | Prometheus / Grafana |
| Concurrent users supported | ≥ 100 | Load testing |
| Model availability (during supported hours) | ≥ 99.5% | Uptime monitoring |
| Time to onboard a new model | ≤ 4 hours | Operational log |
| User satisfaction | ≥ 4/5 | Periodic survey |

*Note: latency and concurrency targets should be validated against actual load testing results and revised accordingly.*

---

## 4. Users & Personas

### 4.1 Primary Users

| Persona | Description | Key Needs |
|---|---|---|
| **Research user** | Postdoc or PhD student using LLMs for their domain (e.g. NLP, bioinformatics, materials science) | Simple OpenAI-compatible API, good documentation, model variety, no cost |
| **Workshop participant** | Researcher attending a training session requiring temporary GPU-backed compute | Time-limited API key, JupyterHub environment, minimal friction |
| **Platform operator** | MLE team member responsible for keeping the stack running | Monitoring dashboards, alerting, Ansible-driven deployment, security auditability |

### 4.2 Secondary Stakeholders

- **Group leadership** — cost justification, usage reporting, research impact
- **Institutional leadership** — demonstration that this is possible
- **Information security** — compliance, vulnerability management, audit trails
- **Peer institutions and homelab operators** — documentation quality; this repository is itself a product for this audience

---

## 5. System Architecture

### 5.1 Hardware

The platform runs on a single bare-metal server. The specification was chosen to support tensor parallelism via NVLink, MIG for concurrent workloads, and sufficient VRAM to serve very large models without quantisation compromises.

| Component | Specification |
|---|---|
| Server | Dell PowerEdge R760XA (2U rack-mounted) |
| GPUs | 4× NVIDIA H100 NVL (94 GB HBM3 each; 376 GB total GPU memory) |
| GPU Interconnect | 2× NVLink bridges |
| CPU | 2× Intel Xeon Gold 6548N (32C/64T each, 2.8 GHz, DDR5-5200) |
| RAM | 1 TB DDR5 (32× 32 GB RDIMMs at 5600 MT/s) |
| Storage | 2× 1.92 TB NVMe SSDs (read-intensive); 2× 480 GB M.2 NVMe (OS, RAID 1 via BOSS-N1) |
| Network | Broadcom 57414 OCP NIC 3.0 (dual-port 10/25 GbE SFP28) |
| Power | 2× 2800 W PSU (Titanium efficiency, 1+1 redundancy) |
| Remote Management | iDRAC9 Enterprise 16G |
| OS | Ubuntu 22.04 LTS (UEFI/GPT) |

The four H100 GPUs are named `leo`, `raph`, `dona`, and `mike`.

### 5.2 Software Stack


**Layer descriptions:**

| Layer | Tool | Purpose | Why chosen |
|---|---|---|---|
| Reverse proxy | Nginx | TLS termination, auth pre-check, rate limiting, path blocking | Ubiquitous, well-understood, extensive security configuration options |
| API gateway | LiteLLM | OpenAI-compatible routing, API key lifecycle, usage metering | OpenAI API compatibility, per-user spend tracking, minimal ops overhead |
| Text inference | vLLM | LLM serving with continuous batching and PagedAttention | Team familiarity, strong community, OpenAI compatibility, best-in-class throughput |
| Image / multimodal inference | SGLang | Diffusion model serving | Better support for non-transformer architectures than vLLM |
| Speech | Speaches | Whisper STT and Kokoro TTS | Lightweight; co-located on GPU 3 with embeddings |
| Database | PostgreSQL 16 | LiteLLM backing store (keys, usage, teams) | Required by LiteLLM; minimal operational overhead |
| IaC / deployment | Ansible | Reproducible server configuration and deployments | Team expertise; playbook-driven operations enable auditability and replication |
| Container runtime | Docker Compose | Service orchestration | Lower complexity than Kubernetes for a single-node deployment |

Kubernetes/Proxmox were considered and explicitly rejected in favour of bare-metal Docker Compose to maximise GPU performance and preserve native NVLink support (see ADR-009).

### 5.3 Models Currently Served

| Model | Endpoint | GPUs | Use Case |
|---|---|---|---|
| `openai/gpt-oss-120b` | vllm-openai:8000 | 0, 1 (tensor parallel) | General-purpose chat; tool calling enabled |
| `Qwen/Qwen3.5-27B-FP8` | vllm-qwen:8001 | 2 | Reasoning tasks |
| `Qwen/Qwen3-Embedding-4B` | vllm-embedding:8002 | 3 | Text embeddings |
| `z-image-turbo` | sglang-diffusion:8003 | 3 | Image generation |
| `Qwen/Qwen-Image-Edit-2511` | sglang-image-edit:8004 | 3 | Image editing |
| `whisper-1` (faster-whisper-large-v3) | speaches (internal) | 3 | Speech-to-text |
| `tts-1` (Kokoro-82M) | speaches (internal) | 3 | Text-to-speech |

### 5.4 Supporting Services

| Service | Tool | Configuration highlights |
|---|---|---|
| Metrics collection | Prometheus | 15 s scrape interval; 30-day retention; scrapes vLLM, LiteLLM, Node Exporter, DCGM, Fail2ban |
| Dashboards | Grafana | Pre-provisioned: Node Exporter (1860), NVIDIA DCGM (12239), LiteLLM usage (custom), Fail2ban geo (custom) |
| Host metrics | Node Exporter | CPU, RAM, disk, network |
| GPU metrics | NVIDIA DCGM Exporter | Utilisation, memory, temperature, power draw per GPU |
| Intrusion detection | Fail2ban | 4 jails: SSH, Nginx blocked/auth/login |
| Ban geo-analytics | Custom fail2ban-geo-exporter | Parses nginx logs; exports ban metrics with GeoIP enrichment |
| Certificate management | Certbot | Auto-renewal via systemd timer |
| Secrets | Environment file (`.env`) | Not committed; example provided as `.env.example` |
| Documentation | MkDocs (planned) | ADRs, operational runbooks |

### 5.5 Network & Security Architecture

The platform uses a five-layer defence-in-depth model:

```
Internet → Firewall → Fail2ban → Nginx → LiteLLM → Docker isolation
```

**Layer 1 — Network / SSH**
- SSH: key-based authentication only; password authentication disabled; root login disabled.
- HTTP (80): redirects to HTTPS only.
- HTTPS (443): sole public API endpoint.

**Layer 2 — Fail2ban**

| Jail | Trigger | Threshold | Ban Duration |
|---|---|---|---|
| `sshd` | Auth failures | 3 in 3600 s | 24 h (24× incremental) |
| `nginx-llm-blocked` | HTTP 444/403 responses | 3 in 60 s | 24 h |
| `nginx-llm-auth` | HTTP 401 (missing/invalid token) | 5 in 60 s | 1 h |
| `nginx-llm-login` | POST `/login` / `/sso` failures | 5 in 300 s | 1 h |

**Layer 3 — Nginx**
- Bearer token format pre-validation (regex: `^Bearer\s+sk-.{10,}$`); invalid tokens rejected at HTTP layer.
- Rate limiting: 1000 req/s per IP (burst: 5000); 500 concurrent connections per IP.
- Path blocking: attack vector probes (`.php`, `.env`, `.git`, `wp-admin`), documentation endpoints (`/docs`, `/redoc`, `/openapi.json`), and admin UI (`/ui`) all blocked or silently dropped.
- Security headers: HSTS (1 year, includeSubDomains), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`.
- Unrecognised hostnames rejected with TLS handshake rejection (`ssl_reject_handshake on`) and HTTP 444.
- Streaming and SSE supported (proxy buffering disabled).

**Layer 4 — LiteLLM**
- All requests require a valid API key.
- Per-user and per-team rate limits enforced.
- Documentation endpoints, generic signup, and robots disabled.
- Bound to `127.0.0.1:4000` only; not reachable from outside the host.

**Layer 5 — Docker isolation**
- All monitoring services and inference backends bound to `127.0.0.1`; no external port exposure.
- PostgreSQL accessible only to the LiteLLM container.
- Monitoring stack on an isolated Docker network; accessible only via SSH tunnel.

**TLS:** Managed by Certbot with auto-renewal. Certificate paths injected via environment variables.

**Access to infrastructure (SSH/admin):** Restricted to the MLE team via Ansible playbooks from a control machine. No interactive shell access for researchers or collaborators (see ADR-005).

**Service access (API keys):** Issued by the MLE team via LiteLLM; tied to individual users or teams; rate-limited and revocable. No self-service key issuance currently. Access models being evaluated: workshop (time-limited), project-based calls, standing access for affiliated groups (see ADR-006).

---

## 6. Functional Requirements

### 6.1 Inference

| ID | Requirement | Priority |
|---|---|---|
| FR-INF-01 | System shall expose an OpenAI-compatible chat completions API | Must have |
| FR-INF-02 | System shall support concurrent requests from ≥ 100 users | Must have |
| FR-INF-03 | System shall support streaming responses (SSE) | Must have |
| FR-INF-04 | System shall support model selection per request | Must have |
| FR-INF-05 | System shall support structured output / JSON mode | Should have |
| FR-INF-06 | System shall support tool calling / function calling | Should have |
| FR-INF-07 | System shall support text embeddings via OpenAI-compatible embeddings API | Must have |
| FR-INF-08 | System shall support speech-to-text (Whisper-compatible API) | Should have |
| FR-INF-09 | System shall support text-to-speech | Should have |
| FR-INF-10 | System shall support image generation | Should have |

### 6.2 Fine-Tuning

| ID | Requirement | Priority |
|---|---|---|
| FR-FT-01 | System shall support LoRA / QLoRA fine-tuning workflows | Should have |
| FR-FT-02 | Users shall be able to submit training jobs via a defined interface | Should have |
| FR-FT-03 | System shall track fine-tuning runs with experiment metadata | Nice to have |

### 6.3 Model Management

| ID | Requirement | Priority |
|---|---|---|
| FR-MM-01 | Operators shall be able to add or remove models without full service downtime | Must have |
| FR-MM-02 | System shall support quantised models (e.g. FP8, AWQ, GPTQ) | Must have |
| FR-MM-03 | System shall maintain a model registry with version history | Nice to have |

### 6.4 Access Management

| ID | Requirement | Priority |
|---|---|---|
| FR-AM-01 | Operators shall be able to issue, revoke, and rate-limit API keys per user or team | Must have |
| FR-AM-02 | System shall track per-user usage (tokens, requests, spend equivalent) | Must have |
| FR-AM-03 | Workshop participants shall receive time-limited keys that expire automatically | Should have |

### 6.5 Observability

| ID | Requirement | Priority |
|---|---|---|
| FR-OBS-01 | System shall expose request latency, throughput, and error rate metrics | Must have |
| FR-OBS-02 | System shall expose GPU utilisation, memory, temperature, and power metrics | Must have |
| FR-OBS-03 | System shall provide per-user usage dashboards | Should have |
| FR-OBS-04 | System shall alert operators on service degradation | Must have |
| FR-OBS-05 | System shall log and visualise security events (Fail2ban bans, geographic origin) | Should have |

### 6.6 Workshop Support

| ID | Requirement | Priority |
|---|---|---|
| FR-WS-01 | System shall support a JupyterHub-based workshop environment | Should have |
| FR-WS-02 | System shall support GPU reallocation between inference and workshop modes | Should have |

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Availability** | Target ≥ 99.5% uptime during supported hours (08:00–20:00 UK time, Monday–Friday) |
| **Performance** | P95 time-to-first-token ≤ 500 ms for 7B-class models under normal load |
| **Scalability** | Architecture should support adding GPU nodes via Ansible without re-architecture; currently single-node |
| **Security** | All traffic encrypted in transit (TLS 1.2+); API keys rotated on request or on departure of key holders; 5-layer defence-in-depth enforced |
| **Maintainability** | All configuration managed via Ansible IaC; changes version-controlled; no manual configuration drift |
| **Data handling** | No user prompts or completions stored beyond LiteLLM usage metadata (token counts, model, timestamps); no plaintext prompt logging |
| **Disaster recovery** | RTO ≤ 4 hours; documented rebuild procedure via Ansible; all configuration version-controlled in this repository |
| **Auditability** | All infrastructure changes made via Ansible playbooks; all API usage logged in LiteLLM/Prometheus |

---

## 8. Deployment & Operations

### 8.1 Deployment Model

All configuration is managed as Infrastructure-as-Code via Ansible playbooks. The standard workflow is:

1. Clone this repository on a control machine.
2. Set required environment variables in `stacks/llm-service/.env` (from `.env.example`).
3. Run `ansible-playbook ansible/playbooks/setup.yml` to configure the host (drivers, Docker, NVIDIA toolkit).
4. Run `ansible-playbook ansible/playbooks/monitoring.yml` to deploy the monitoring stack.
5. Run `ansible-playbook ansible/playbooks/llm-service.yml` to deploy the inference stack.

Rollback: re-run the relevant Ansible playbook with a pinned image version. Full environment teardown is available via `ansible-playbook ansible/playbooks/nuke-from-orbit.yml`.

Environment management: currently single environment (production). No staging environment; changes should be tested locally via Docker Compose before deployment.

### 8.2 Operational Responsibilities

| Responsibility | Owner | Frequency |
|---|---|---|
| OS patching | MLE team | Monthly |
| Model updates | MLE team | As needed |
| Certificate renewal | Certbot (automated) + MLE team (verify) | Before expiry |
| Security review | MLE team | Quarterly |
| Capacity planning | MLE team | Quarterly |
| Prometheus data backup | MLE team | TBD — RAID1 recommended (ADR-007) |
| API key issuance / revocation | MLE team | On request |
| Fail2ban rule review | MLE team | Quarterly |

### 8.3 Support Model

- **Documentation:** This repository, including ADRs, setup guides, and operational runbooks.
- **Bug reports / feature requests:** GitHub Issues at `acceleratescience/splinter`.
- **User support:** Via the Accelerate Programme's existing support channels (to be defined per access programme — workshop, project call, standing access).

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GPU hardware failure | Low | High | Dell vendor warranty; iDRAC9 remote management; documented rebuild procedure via Ansible |
| Security breach via exposed API | Medium | High | 5-layer defence-in-depth (Firewall → Fail2ban → Nginx → LiteLLM → Docker isolation); API key required for all requests |
| Single point of failure (single server) | High | High | Documented and automated rebuild via Ansible; all config in version control; no stateful data outside Prometheus metrics and LiteLLM usage logs |
| Key person dependency | Medium | Medium | ADRs document all decisions; Ansible playbooks encode all operational knowledge; open-source for community contribution |
| Model licensing changes | Low | Medium | Preference for permissively licensed open-weight models; licensing reviewed at model onboarding |
| GPU contention between workloads | Medium | Medium | GPU allocation defined per service in Docker Compose; workshop mode requires explicit reconfiguration and playbook re-run |
| Runaway inference costs (compute) | Low | Low | Rate limiting enforced at LiteLLM and Nginx layers; GPU utilisation dashboards in Grafana |

---

## 10. Roadmap

### Phase 1: Foundation (Complete)

- Core inference stack operational (vLLM, LiteLLM, Nginx, PostgreSQL)
- Monitoring and alerting in place (Prometheus, Grafana, DCGM, Fail2ban geo)
- Initial user onboarding via API keys (workshop participants)
- Security hardening (5-layer defence-in-depth)
- IaC for reproducible deployment (Ansible)

### Phase 2: Hardening (In Progress)

- Formalise access model for project-based and standing-access users (ADR-006)
- Backup strategy for Prometheus and LiteLLM database (ADR-007)
- Pin all container image versions (known gap)
- Implement Docker network segmentation between services (known gap)
- Consider security certification (e.g. Cyber Essentials)
- Fine-tuning workflows available to power users

### Phase 3: Scale (Planned)

- Multi-node GPU support via distributed inference
- Self-service model onboarding (operator tooling)
- Integration with institutional HPC scheduler
- Formalised SLA / support offering

---

## 11. Appendices

### A. Architecture Diagram

![Architecture diagram](./assets/imgs/arch.png)

### B. Architecture Decision Records

| ADR | Decision | Date | Status |
|---|---|---|---|
| ADR-000 | Hardware: Dell PowerEdge R760XA with 4× H100 NVL | 2025-11-01 | Accepted |
| ADR-001 | License: GNU GPLv3 | 2025-12-03 | Accepted |
| ADR-002 | Server naming convention (splinter / TMNT GPUs) | 2025-12-05 | Accepted |
| ADR-003 | Inference engine: vLLM (+ SGLang for diffusion) | 2026-01-25 | Proposed |
| ADR-004 | Metrics and stress testing approach | 2026-01-25 | Proposed |
| ADR-005 | Infrastructure access: MLE team only, key-based SSH, Ansible-driven | 2026-02-09 | Accepted |
| ADR-006 | Service access: LiteLLM API keys; access models TBD | 2026-02-09 | Proposed |
| ADR-007 | Backup strategy: RAID1 for Prometheus DB | TBD | Proposed |
| ADR-008 | Monitoring stack: Prometheus + Grafana + DCGM + Fail2ban geo | 2025-12-09 | Accepted |
| ADR-009 | Deployment: bare-metal Ubuntu + Docker Compose (no Kubernetes) | 2026-01-21 | Proposed |
| ADR-010 | Fair use policy | 2026-01-29 | Proposed |

Full ADR text: [docs/ADRs/](./ADRs/)

### C. Glossary

| Term | Definition |
|---|---|
| ADR | Architecture Decision Record — a short document capturing a significant architectural decision, its context, and rationale |
| DCGM | NVIDIA Data Centre GPU Manager — toolkit for monitoring and managing GPUs in data centre environments |
| IaC | Infrastructure-as-Code — managing infrastructure through machine-readable configuration files rather than manual processes |
| LiteLLM | Open-source API gateway that provides a unified OpenAI-compatible interface over multiple LLM backends |
| LoRA / QLoRA | Low-Rank Adaptation / Quantised LoRA — parameter-efficient fine-tuning techniques |
| MIG | Multi-Instance GPU — NVIDIA feature allowing a single GPU to be partitioned into multiple isolated instances |
| NVLink | NVIDIA's high-bandwidth GPU-to-GPU interconnect, enabling tensor parallelism across GPUs |
| PagedAttention | vLLM's memory management technique that enables efficient KV cache handling for concurrent requests |
| SGLang | Structured Generation Language — an inference framework with strong support for diffusion and multimodal models |
| TTFT | Time-to-First-Token — latency from request submission to first token returned; key user-facing performance metric |
| vLLM | An open-source LLM inference and serving engine with high-throughput continuous batching |

### D. References

- [vLLM documentation](https://docs.vllm.ai)
- [LiteLLM documentation](https://docs.litellm.ai)
- [NVIDIA DCGM documentation](https://docs.nvidia.com/datacenter/dcgm/latest/)
- [Fail2ban documentation](https://www.fail2ban.org/wiki/index.php/Main_Page)
- [Accelerate Programme for Scientific Discovery](https://acceleratescience.github.io)
- [Project repository](https://github.com/acceleratescience/splinter)

---

*This document is a living artefact. Update it as the system evolves.*
