# Terms of Service

> **Service status:** Beta 
> **Last updated:** 11th June 2026

---

## 1. What is Splinter?

Splinter is a self-hosted GPU inference platform operated by the [Accelerate Programme for Scientific Discovery](https://science.ai.cam.ac.uk) at the University of Cambridge. It runs on dedicated on-premises hardware (a Dell PowerEdge server with four NVIDIA H100 NVL GPUs) and provides Cambridge researchers with free access to open weight AI models without dependence on commercial API providers.

**Services currently available:**

| Service | Description                                                                      |
|---|----------------------------------------------------------------------------------|
| LLM inference | OpenAI-compatible chat completions and text generation API                       |
| Embeddings | Text embedding API for semantic search and similarity tasks                      |
| Image generation | Text-to-image and image-editing endpoints                                        |
| Speech | Speech-to-text (Whisper compatible) and text-to-speech                           |
| Compute pods | Isolated GPU compute environments for vetted users with custom workloads         |
| Engineer-mediated collaborations | Direct research partnership with an Accelerate engineer for substantive projects |

Access to **inference endpoints** is available to all eligible users. Access to **pods** and **engineer collaborations** requires a separate application via the Expression of Interest process.

This is an open-source project. The infrastructure code and documentation are publicly available at [github.com/acceleratescience/splinter](https://github.com/acceleratescience/splinter).

---

## 2. Eligibility

Splinter is intended for:

- Researchers, academic staff and PhD students at the University of Cambridge
- Staff and RSEs developing tools and services for the Cambridge research community
- Participants in Accelerate Programme-affiliated programmes (AI for Government cohort, AI ideas sprint, C2D3 and Accelerate awardees and similar)

Access is not open to the general public. All users must apply via the Expression of Interest form or be invited to a specific workshop. The Accelerate team reserves the right to decline or revoke access at its discretion.

---

## 3. Access and API keys

Access to Splinter's inference services is provided via API keys issued by the Accelerate team.

- **API keys are personal and non-transferable.** Do not share your key with others, inside or outside the university.
- **Workshop keys are time-limited** and will be revoked at the end of the workshop. Ongoing access requires a separate application.
- **Keys may be revoked** at any time for violations of this policy, sustained misuse or operational necessity.
- There is no self-service key issuance. Contact the Accelerate team to request, rotate or report a compromised key.

---

## 4. Beta service - what to expect

Splinter is currently a **beta service**. By using it, you acknowledge:

- The service runs on a best-effort basis. Planned and unplanned outages will occur. If you need guaranteed availability, use a commercial API provider.
- There is no formal service-level agreement. Support is provided by a small engineering team alongside other commitments.
- Models, endpoints and resource limits may be added, removed or altered without prior notice, though we will try to communicate changes via the user mailing list.
- The service is grant-funded and continuity beyond the current funding period is not guaranteed. We will provide advance notice to active users if the service is to be wound down or significantly curtailed.
- Disruptions are sometimes planned. Hands-on workshops and infrastructure work may require the service to be taken offline for periods of hours or days. These will be communicated via the mailing list where possible.

If you have a workload that is time-sensitive or cannot tolerate interruption, plan accordingly.

---

## 5. Data handling

**What we log:** Splinter logs request metadata (timestamps, model used, token counts and latency) per API key, for the purposes of capacity planning, fair-use enforcement and diagnosing issues.

**What we do not log:** We do not log or store the content of your prompts or completions.

**Splinter is not a certified secure environment.** It is not approved for processing restricted, sensitive, personal or otherwise regulated data (e.g. patient data, commercially confidential information, data subject to export controls). Do not send data to Splinter that you would not be comfortable processing on a shared, best-effort research system. If you are unsure whether your data is appropriate, contact us before using the service.

**User data in compute pods is not backed up.** If you have been granted a pod allocation, you are responsible for maintaining your own backups of any data, model weights or outputs you store there. We accept no liability for data loss due to hardware failure, accidental deletion or service disruption.

---

## 6. Acceptable use

By using Splinter, you agree to the [Splinter Fair Use Policy](fair-use-policy.md) and must read it in full before using the service. It covers:

- Permitted uses (research, teaching, prototyping, agentic workflows and more)
- Resource limits and our expectations of you as a user
- Prohibited uses (including harm, privacy violations, manipulation and academic dishonesty)
- Research exemptions for sensitive topics with appropriate ethics approval
- Monitoring and enforcement

### Agentic tools

Agentic coding tools (Claude Code, Cursor, GitHub Copilot Agent and similar systems) execute arbitrary commands on your behalf and can behave in ways that are difficult to anticipate or contain. If you use such tools against Splinter endpoints or within a pod environment:

- You are responsible for the actions those tools take using your API key or within your pod.
- Configure your tools to limit scope and avoid unintended side effects.
- Do not run agentic tools in a way that could affect other users' access (e.g. sustained high-volume generation that saturates shared resources).
- Within pod environments, do not use agentic tools in ways that attempt to escalate privileges beyond your pod boundary.

We reserve the right to revoke access for agentic misuse even where the underlying intent was benign.

---

## 7. Your responsibilities

As a Splinter user, you agree to:

1. **Use the service only for legitimate research, teaching and learning purposes** consistent with the Fair Use Policy.
2. **Keep your API key secure.** Treat it as you would a password.
3. **Maintain your own backups** of any data or outputs you cannot afford to lose.
4. **Not submit sensitive or restricted data** to Splinter without first confirming with the Accelerate team that it is appropriate.
5. **Report security concerns** promptly. If you believe your key has been compromised, or if you observe behaviour that suggests a security incident, contact us immediately.
6. **Be a considerate neighbour.** Sustained heavy use during peak hours affects everyone. Batch requests where possible; right-size your context windows; avoid unnecessary parallel requests.

---

## 8. Limitation of liability

Splinter is provided as-is, by a small research team, on a best-effort basis.

The Accelerate Programme and the University of Cambridge accept no liability for:

- Loss of data, outputs or work resulting from service outages, hardware failure or configuration changes
- Decisions made on the basis of model outputs
- Any indirect, consequential or incidental loss arising from use of the service

Nothing in these terms limits liability for death, personal injury or fraud caused by negligence.

---

## 9. Changes to these terms

We may update these terms as the service evolves. Changes will be communicated via the user mailing list and reflected in the version date at the top of this document. Continued use of the service after notification of changes constitutes acceptance.

---

## 10. Contact

- **Bug reports and feature requests:** [GitHub Issues](https://github.com/acceleratescience/splinter/issues)
- **Access requests and key management:** Email [accelerate-mle@cst.cam.ac.uk](mailto:accelerate-mle@cst.cam.ac.uk) or raise a GitHub Issue.
- **Security concerns:** Email [accelerate-mle@cst.cam.ac.uk](mailto:accelerate-mle@cst.cam.ac.uk) directly. Please do not open a public GitHub issue for security matters.

---

*Splinter is operated by the Accelerate Programme for Scientific Discovery, Department of Computer Science and Technology, University of Cambridge.*
