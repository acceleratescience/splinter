# ADR-005. Infrastructure access management

Date: 2026-02-09  
Status: Accepted

## Context

The Splinter server runs containerised services (vLLM, LiteLLM, Prometheus, Grafana) deployed via Docker Compose and managed through Ansible playbooks. Misconfiguration at this level, whether accidental or through a compromised account, could take down services, expose data, or create security vulnerabilities.

Every SSH-capable account on the server is an attack surface. The principle of least privilege applies: no one should have access they do not operationally require.

The question of whether to manage the server via direct SSH sessions or via Ansible from a local control machine also needed resolution. Both approaches have tradeoffs around auditability, reproducibility, and operational risk.

## Decision

Shell access (SSH) to the server is restricted to the MLE team only. No external researchers, collaborators, or stakeholders receive direct access to the machine. This is non-negotiable regardless of seniority or project affiliation.

Day-to-day server management is performed via Ansible from a local control machine rather than through interactive SSH sessions. Configuration changes are codified in playbooks, version-controlled in the Splinter repository, and reproducible. SSH is available for debugging and emergency intervention but is not the primary management interface.

SSH access is key-based only; password authentication is disabled. Keys are managed per-team-member and can be revoked individually.

## Consequences

**Benefits:**

- Minimal attack surface. Only operationally essential accounts exist on the server.
- Ansible-first management means all configuration changes are auditable, reproducible, and transferable. A new team member can understand the server's state by reading the repository rather than guessing from SSH history.
- The access model scales cleanly to the blueprint model: any institution adopting Splinter gets the same locked-down baseline.

**Tradeoffs and limitations:**

- Restricting infrastructure access to the MLE team creates a bus factor. If the team is unavailable, no one else can intervene. This is mitigated by the Ansible-as-code approach (anyone with the playbooks and appropriate credentials could take over), but succession planning should be documented.
- The Ansible-first approach requires discipline. The temptation to SSH in and fix something during an incident is real, and any manual changes not back-ported to playbooks create configuration drift. The team must treat playbooks as the source of truth.
- Denying infrastructure access to researchers accustomed to managing their own GPU resources may generate pushback. The response is straightforward: the service layer (see [ADR-006](./006-service-access.md)) provides everything needed for inference. Bare-metal access for training or custom workloads is a different use case requiring different infrastructure.