# ADR-000. Hardware

Date: 2025-11-01
Status: Accepted

## Context
The research group requires dedicated compute to move away from reliance on external SaaS providers and closed-source LLMs. Our goals include providing free, private model access for researchers, hosting workshops, and conducting fundamental AI research.

Several constraints and factors influenced this decision:

- **Physical Constraints**: Initial plans for desktop RTX 6000 Pro systems were rejected due to extreme heat output (600W per card), noise levels unsuitable for an office environment, and power draw risks (including the fire-prone 12VHPWR cable design).

- **Infrastructure**: The university department requires rack-mounted solutions for security, remote SSH access, and managed cooling.

- **Performance Requirements**: We need high VRAM and NVLink support for training foundation models and efficient inference.

- **Market Volatility**: During the evaluation, the price of DDR5 RAM and storage increased significantly (nearly 8x for RAM kits), necessitating a "buy now" approach to avoid further budget erosion.

- **Sustainability**: While H100s have a higher upfront cost, they are more power-efficient (300W) than the RTX 6000 Pro cards for the equivalent compute, easing the burden on the server room's power capacity.

## Decision
We have decided to purchase a Dell 2U Rack-mounted Server equipped with:

- 4x NVIDIA H100 NVL 94GB GPUs (chosen over L40/L40S for NVLink and VRAM capacity).

- 1TB System RAM (to facilitate Expert offloading in MoE models and prevent data bottlenecks).

- 2x 1.92TB NVMe SSDs for high-speed local caching.

- 2x Intel Xeon CPUs.

We opted for the 4x configuration immediately rather than a 2x system to mitigate the risk of H100s reaching End-of-Life before an upgrade could be funded, and to ensure full NVLink topology from day one.

## Consequences
### Positive
**Data Sovereignty**: We can offer researchers an endpoint that does not track inputs/outputs, fulfilling our privacy mission.

**Operational Efficiency**: Support for MIG (Multi-Instance GPU) allows us to partition the cards for simultaneous workshop use and background training.

**Reliability**: Choosing Dell as a supplier provides enterprise-grade support and hardware reliability favored by departmental sysadmins.

**Capacity**: 376GB of total HBM3 VRAM plus 1TB of system RAM allows for serving very large models with high throughput.

### Negative/Trade-offs
**High Initial Capital Outlay**: The final cost significantly exceeded the initial desktop projections.

**End-of-Life Risk**: As the H100 is later in its lifecycle, future hardware expansions may require a full system replacement rather than modular upgrades.

**Administrative Overhead**: Moving to a rack-mount system means we are dependent on the department’s server room schedule and SysAdmin availability for physical maintenance.

**Form factor**: The H100 has no HDMI output and does not support NVIDIA game-ready drivers. So it won't run Cyberpunk 2077. :(