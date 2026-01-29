# ADR-001. Adopt GNU GPLv3 for Server Infrastructure Code and Documentation

Date: 2025-12-03  
Status: Accepted  
Status change: 2026-01-21

## Context
We're building and documenting infrastructure for our 4x H100 NVL server, including:

- GPU server deployment and configuration (H100 NVL setup)
- vLLM deployment for serving LLMs to the research community
- Infrastructure automation and provisioning scripts
- Operational documentation and runbooks

This work will serve researchers across the University. We want to maximize openness and ensure that any improvements or derivatives remain open source, creating a commons that benefits the entire research community.

We need a license that enforces reciprocal openness -- if someone takes our work, improves it, and deploys it, those improvements should flow back to the community rather than becoming proprietary.

## Decision
We will license all infrastructure code, configuration, and documentation under GNU General Public License v3.0 (GPLv3).
This means:

- All code remains free and open source
- Anyone can use, modify, and distribute our work
- Any modified versions that are distributed must also be released under GPLv3
- Users must provide source code when they distribute the software
- Clear attribution to the University of Cambridge Accelerate Programme

## Consequences
### Benefits
- Enforces openness - improvements can't be taken proprietary
- Builds a genuine commons for small-scale HPC infrastructure in academia
- Aligns with the spirit of major successful projects (Linux kernel, etc.)
- Ensures long-term community benefit from publicly-funded work
- Discourages parasitic commercial use without contribution

### Tradeoffs
- Some institutions with proprietary infrastructure management may be hesitant to adopt
- Cannot be easily mixed with proprietary tooling (by design)
- Slightly more complex license than permissive alternatives
- May reduce adoption compared to MIT/Apache in commercial/mixed environments

Accepted tradeoff: We're prioritizing community benefit and enforced openness over maximum adoption. **This is infrastructure for research, therefore it should remain open**.