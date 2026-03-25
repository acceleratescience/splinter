# System Architecture
Included here is a full overview of the bare server specifications.

## Server Overview

**Model:** Dell PowerEdge R760XA Server  
**Form Factor:** 2U Rack Server  
**Configuration:** PowerEdge R760XA - Full Configuration - [EMEA_R760XA]  

---

## Compute Resources

### Processors
- **Model:** Intel Xeon Gold 6548N
- **Specifications:** 2.8 GHz, 32C/64T, 20GT/s, 60M Cache, Turbo, HT (250W)
- **Memory Support:** DDR5-5200
- **Quantity:** 2 processors
- **Total Cores:** 64 physical cores
- **Total Threads:** 128 logical processors

### Memory
- **Type:** RDIMM (Registered DIMM)
- **Speed:** 5600MT/s
- **Capacity per DIMM:** 32GB Dual Rank
- **Quantity:** 32 DIMMs
- **Total Memory:** 1024GB (1TB)
- **Configuration:** Performance Optimized

---

## GPU Acceleration

### Graphics Processing Units
- **Model:** NVIDIA H100 NVL
- **Interface:** PCIe
- **Power:** 350W-400W
- **Memory per GPU:** 94GB
- **Form Factor:** Passive, Double Wide, Full Height
- **Quantity:** 4 GPUs
- **Total GPU Memory:** 376GB

### GPU Interconnect
- **Technology:** NVLINK Bridge
- **Quantity:** 2x NVLINK Bridge (for multi-GPU communication)
- **PCIe Riser:** Config 0, 4x16 FH Slots (Gen5), 4x16 FH DW GPU Capable Slots (Gen5) with Bridge Board

---

## Storage

### Primary Storage
- **Type:** SSD SAS
- **Capacity:** 1.92TB per drive
- **Performance:** Read Intensive, up to 24Gbps
- **Format:** 512e, 2.5in Hot-Plug, AG Drive
- **Quantity:** 2 drives
- **Total Primary Storage:** 3.84TB

### Boot Storage
- **Controller:** BOSS-N1 (Boot Optimized Storage Solution)
- **Type:** M.2 NVMe
- **Capacity:** 480GB per drive
- **Configuration:** RAID 1
- **Quantity:** 2 M.2 drives

### RAID Controller
- **Model:** PERC H965i Controller, Front
- **Configuration:** Unconfigured RAID (flexible configuration)
- **Backplane:** SAS/SATA Backplane

### Chassis
- **Storage Bays:** 2.5" Chassis with up to 8 SAS/SATA Drives, Front PERC 12

---

## Networking

### OCP Network Adapter
- **Model:** Broadcom 57414
- **Ports:** Dual Port 10/25GbE SFP28
- **Standard:** OCP NIC 3.0

---

## Power and Cooling

### Power Supply Units
- **Configuration:** Dual, Redundant (1+1), Hot-Plug
- **Capacity:** 2800W per PSU
- **Efficiency:** Titanium (ONLY FOR 200-240Vac)
- **Connector:** C22 Connector
- **Total Available Power:** 2800W (with 1+1 redundancy)

### Power Cords
- **Type:** Jumper Cord - C20/C21
- **Length:** 2.5M
- **Rating:** 250V, 16A (MultiNational)
- **Quantity:** 2

### Cooling
- **Type:** Gen 2 Fan
- **Thermal Config:** Heatsink for 2 CPU Configuration with OCP

---

## Management and Monitoring

### Remote Management
- **Platform:** iDRAC9, Enterprise 16G
- **Features:** Full remote management capabilities
- **Password:** Factory Generated Password for OCP cards

### Systems Management
- **Software:** OpenManage Enterprise Advanced
- **Connectivity:** Dell Connectivity Module

### Security
- **Boot Mode:** UEFI BIOS Boot Mode with GPT Partition
- **TPM:** No Trusted Platform Module

---

## Physical Configuration

### Chassis and Mounting
- **Bezel:** PowerEdge 2U Standard Bezel
- **Rails:** ReadyRails Sliding Rails (B25)
- **Form Factor:** 2U rack-mountable

### Operating System
- **Pre-installed OS:** No Operating System
- **Boot Configuration:** Bare metal, ready for OS installation

---

## Power Management

### BIOS Settings
- **Configuration:** Power Saving Dell Active Power Controller