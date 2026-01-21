# ADR-003. Bare metal approach

Date: 2026-01-21
Status: Proposed

## Context

The primary workload is continuous LLM inference via vLLM behind a LiteLLM proxy, monitored with Prometheus/Grafana. Secondary workloads include JupyterHub with VS Code Server for workshop participants, requiring Kubernetes orchestration.

We evaluated Proxmox as a virtualisation layer but identified concerns:
- GPU passthrough complexity with NVLink interconnects
- Additional abstraction layer impacting inference latency
- Team expertise gap in Proxmox administration
- Potential complications with vLLM's multi-GPU tensor parallelism

Our team has existing competency in Docker Compose and Ansible, with developing Kubernetes knowledge. The infrastructure-as-code approach we've been building assumes direct container deployment.

## Decision

Deploy directly on bare metal Ubuntu with containerised services, avoiding a hypervisor layer.

- **Primary stack**: Docker Compose for vLLM, LiteLLM proxy, and monitoring (Prometheus/Grafana)
- **Workshop stack**: Lightweight Kubernetes (k3s) for JupyterHub when needed, or containerised JupyterHub via Docker
- **GPU allocation**: All 4x H100s available to vLLM by default; reconfigure for workshops as needed
- **Configuration management**: Ansible playbooks for reproducible deployment

## Consequences

**Benefits**
- Full GPU performance with native NVLink communication for tensor parallelism
- Simpler debugging path—one fewer abstraction layer
- Aligns with team's existing skills
- Lower operational overhead for a small team

**Costs**
- No VM-level isolation between LLM service and workshop environments
- Workshop deployment requires either service interruption or careful resource partitioning
- Less flexibility for running heterogeneous OS environments
- Hardware maintenance requires full service downtime

**Mitigations**
- Use namespaces/cgroups for workload isolation where needed
- Schedule workshops during planned maintenance windows
- Document runbooks for switching between LLM-serving and workshop configurations
- Consider Proxmox for future multi-server deployments once team expertise develops