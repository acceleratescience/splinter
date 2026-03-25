# ADR-006. Service access management

Date: 2026-02-09  
Status: Proposed

## Context

The architecture already provides the mechanisms for managed service access. LiteLLM handles API key provisioning, user/team organisation, usage tracking, and rate limiting. Nginx provides SSL termination and request filtering. This means we can grant, meter, and revoke service access without exposing the underlying infrastructure.

However, the server was procured with programme funds for a specific purpose. It is not a general university computing resource. Capacity is finite -- VRAM, context windows, and concurrent request limits are all constrained. Every API key issued is a commitment of shared capacity.

We currently have one confirmed access pathway (workshop participants) and several potential models under consideration. The purpose of this ADR is to document the decision space honestly rather than prematurely commit to a model that may not survive contact with real demand.

## Decision

### What is decided

All service access is granted via LiteLLM API keys. Each key is tied to a named user or team, subject to rate limits and usage quotas, revocable at any time, and tracked for usage reporting. This is the mechanism regardless of which access model we adopt.

The MLE team approves all key issuance. There is no self-service provisioning at this stage.

### What is not yet decided

**Workshop participants.** Participants in Accelerate Programme workshops (e.g., LLM workshops, AI Winter School) will receive API keys for the duration of the workshop. The unresolved question is: does access persist after the workshop ends? Arguments exist in both directions. Persistent access builds a user community and generates usage data for funders. But it also commits finite capacity to users who may not have an active research need, and "workshop attendee" is not a strong signal of ongoing demand. A time-limited extension (e.g., 30 or 90 days post-workshop) with renewal on request is one possible middle ground, but this has not been tested.

**Project-based calls.** We are considering a model where researchers apply for API access in response to periodic calls, similar to how HPC allocations work. Applicants would describe their research use case, estimated usage (token volume, model requirements, duration), and expected outputs. This has the advantage of aligning access with demonstrable research need and producing a clear audit trail for funders. The risks are: bureaucratic overhead that deters adoption, a cadence that does not match research timelines (a researcher who needs access *now* cannot wait for the next call), and the fact that researchers are notoriously poor at estimating compute requirements in advance. We have no experience running this model and do not know whether demand justifies the overhead.

**Standing access for affiliated groups.** Some research groups may want persistent, always-on API access for ongoing projects (e.g., evaluation pipelines, agentic systems, data processing workflows). This is the most resource-intensive model and the hardest to reverse once granted. It is also potentially the highest-impact, as it enables integration of local LLM inference into research infrastructure rather than treating it as an ad-hoc tool.

**External collaborators.** The current assumption is university affiliation is required. Whether access extends to external collaborators on joint projects, visiting researchers, or partner institutions is unresolved.

## Consequences

**What we know:**

- The technical mechanism (LiteLLM key management) works and can support any of the above models without architectural changes.
- Usage tracking gives us the data to make informed decisions once we have real demand patterns. We do not need to solve the access model perfectly before launching — we need to launch, observe, and iterate.
- The MLE team as gatekeeper is sustainable at small scale but will not survive a large influx of requests without some automation or a clearer policy framework.

**What we need to learn:**

- What does actual demand look like? Workshop participants may never use their keys again, or they may become heavy users. We do not know yet.
- Is a call-based model worth the overhead, or does a simpler "request access, describe your use case, get a key" model achieve the same goals with less friction?
- What are reasonable rate limits and quotas? These need to be informed by benchmarking data (see ADR on benchmarking) and real usage patterns, not guesswork.
- How do we handle the inevitable request from a high-profile researcher or group that would consume disproportionate capacity? This is a political question as much as a technical one.

**Next steps:**

- Launch with workshop access as the initial pathway. Grant time-limited keys (duration TBD) and monitor usage.
- Draft a lightweight request process for non-workshop access. Keep it simple: name, affiliation, use case, estimated duration. Avoid building a formal allocation committee until demand warrants it.
- Revisit this ADR after 2 months of operational data.