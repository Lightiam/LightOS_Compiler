# JLCPCB PCB Layout Order - Technical Requirements
## LightRail AI NCE Neural Computing Engine Motherboard

**Project Name:** LightRail AI NCE - PCB Layout Design  
**Submission Date:** 2026-07-21  
**Schematic Status:** Complete (6 subsystem sheets)  
**Target Timeline:** Phase 2 Completion (60% - July 2026)  

---

## 1. BOARD SPECIFICATIONS

### 1.1 Physical Dimensions & Mechanical
| Parameter | Specification |
|-----------|---|
| Board Size | 267 mm × 111 mm (dual-slot PCIe form factor) |
| Board Thickness | 2.4 mm |
| Aspect Ratio | ~2.4:1 (long and narrow for slot insertion) |
| Edge Connector Type | PCIe x16 164-pin edge connector (J1) |
| Mounting Holes | 4× mounting locations (per PCIe x16 spec) |
| Keep-out Areas | 5 mm margin around PCIe connector J1 |

### 1.2 Layer Stack-Up Configuration
**IMPORTANT:** Current design specifies **10-layer stack**, but **32-layer stack recommended for optimal SI/PI**.

#### Current 10-Layer Stack (to be confirmed):
```
Layer 1:  F.Cu         - Signal (0.035 mm Cu)
Layer 2:  In1.Cu       - Vcore Power Plane (0.035 mm Cu)
Layer 3:  In2.Cu       - Signal (0.035 mm Cu)
Layer 4:  In3.Cu       - GND Plane (0.035 mm Cu)
Layer 5:  In4.Cu       - Signal (0.035 mm Cu)
Layer 6:  In5.Cu       - Vmem Power Plane (0.035 mm Cu)
Layer 7:  In6.Cu       - Signal (0.035 mm Cu)
Layer 8:  In7.Cu       - GND Plane (0.035 mm Cu)
Layer 9:  In8.Cu       - Signal (0.035 mm Cu)
Layer 10: B.Cu         - Signal (0.035 mm Cu)
```

#### Dielectric Specifications:
- Material: FR-4 (Tg ≥170°C recommended)
- Epsilon_r: 4.5 ±0.2
- Loss Tangent: 0.02 ±0.003
- Core thickness between power/GND: 0.1 mm
- Prepreg thickness: 0.15 mm
- Copper Weight: 1 oz (0.035 mm) on all layers

#### Manufacturing Preference:
- Copper Finish: **HASL (Hot Air Solder Leveling)** or ENIG (lead-free preferred)
- Solder Mask Color: **Green** (standard, best visibility for assembly)
- Silkscreen Color: **White** (high contrast for component markings)
- Surface Treatment: **RoHS-compliant** (no lead)

---

## 2. COMPONENT PLACEMENT GUIDELINES

### 2.1 Critical Component Locations

| Reference | Component | Package | Placement Requirement | Priority |
|-----------|-----------|---------|----------------------|----------|
| **J1** | PCIe x16 Edge Connector | 164-pin | Board right edge, flush with connector teeth | **CRITICAL** |
| **J2** | 8-pin PEX Power Connector | Molex 5559 | Bottom side, accessible for power cabling | **CRITICAL** |
| **J3** | 14-pin JTAG Header | 0.1" pitch | Top-left corner for test access | **HIGH** |
| **U27** | LR-GEN3-NPU-5NM (Main ASIC) | BGA-3136 (50×50mm) | Center-left area, surrounded by HBM3 stacks | **CRITICAL** |
| **U28-U39** | HBM3 Memory Stacks (12×) | BGA-1024 (8×8mm) | 6 stacks left of ASIC, 6 stacks right; symmetric arrangement | **CRITICAL** |
| **U1-U2** | MP5949 PWM Controllers (2×) | QFN-48 | Near J2 power input; close to phase inductors L1-L12 | **HIGH** |
| **U3-U26** | CSD95481RWJ MOSFETs (24×) | PK 8×8 | 12 phases around MP5949; minimize trace length to gates | **HIGH** |
| **L1-L12** | Phase Inductors (0.47µH) | 1210 | Distributed across PDM area; close to MOSFET collectors | **HIGH** |
| **U40** | INA3221 Power Monitor | TSSOP-20 | Near U27 ASIC for rail monitoring | **MEDIUM** |
| **U41** | NCT6798D Thermal Controller | QFN-48 | Near heatspreader area; accessible for thermal sensor routing | **MEDIUM** |
| **U42-U43** | 40mm Cooling Fans (2×) | Connector mount | Rear edge; airflow path to ASIC heatspreader | **MEDIUM** |
| **U44** | SG-531S TCXO (27 MHz) | 7×5mm | Near U27 CLK pin; minimize clock trace length <5 mm | **HIGH** |
| **C1-C700** | Decoupling Capacitors (600×) | 0402-1206 | Distributed per power rail; <5 mm from IC power pins | **CRITICAL** |

### 2.2 Power Plane Allocation
- **In1.Cu (Vcore):** Dedicated plane for 0.9V, 210A core supply; full plane coverage
- **In3.Cu (GND):** Reference plane; continuous coverage with via stitching every ~25 mm
- **In5.Cu (Vmem):** Dedicated plane for 1.2V, 75A memory supply; full plane coverage  
- **In7.Cu (GND):** Secondary reference plane; continuous coverage with via stitching

### 2.3 Heatspreader Area
- Aluminum 6061-T6 heatspreader: 50 mm × 50 mm (mounted on top of U27)
- Thermal interface material (Arctic MX-4): 0.5 mm gap
- Thermal vias under heatspreader: 0.3 mm diameter, 25 mm spacing (via array)
- Connect thermal vias to In3.Cu and In7.Cu GND planes

---

## 3. SIGNAL ROUTING SPECIFICATIONS

### 3.1 PCIe Differential Pairs (J1 → U27)
| Parameter | Specification | Notes |
|-----------|---|---|
| Total Pairs | 32 (16 TX + 16 RX) | Gen3/Gen4 compatible |
| Impedance | **100 Ω ±10%** differential | Tuned for PCIe Gen4 5GT/s |
| Trace Width | 0.15 mm (each) | Track on F.Cu or In2.Cu |
| Pair Spacing | 0.15 mm (gap) | Edge-to-edge |
| Length Matching | ±20 mils (±0.5 mm) | Within each lane group |
| Via Count | <2 per signal | Minimize inductance |
| Max Skew | <100 ps | Between TX and RX pairs |
| Routing Layer | Preferably In2.Cu (over In3.Cu GND) | For impedance control |

### 3.2 HBM3 Clock Distribution (U27 → U28-U39)
| Parameter | Specification | Notes |
|-----------|---|---|
| Clock Pairs | 2 (CLK / CLK#) | Differential at 2.4 GHz |
| Impedance | **100 Ω ±10%** differential | Matched to PCIe pairs |
| Trace Width | 0.2 mm (each) | Wider than PCIe for lower loss |
| Pair Spacing | 0.2 mm (gap) | Slightly increased spacing |
| Length Matching | ±100 ps skew max | Between 12 stacks |
| Via Count | <4 per line | Allow for escape routing |
| Guard Traces | GND on both sides | Shielding for EMI immunity |
| Route to Each Stack | Length-matched tree from PLL | Ensure <100 ps core-to-core skew |

### 3.3 HBM3 Data Bus (U27 → U28-U39)
| Parameter | Specification | Notes |
|-----------|---|---|
| Data Width | 1,024 bits total | 128 bits per stack × 8 groups |
| Signal Voltage | 1.2V LVCMOS | Referenced to Vmem plane |
| Trace Width | 0.15-0.2 mm | Dependent on layer/spacing |
| Via Density | ~50% of signal area | Escape routing critical for BGA |
| Strobe Lines | 16 total (2 per stack) | Treat as differential pairs if possible |
| Max Trace Length | 30 mm per group | Avoid excessive skew between stacks |

### 3.4 Reference Clock (27 MHz TCXO → U27)
| Parameter | Specification | Notes |
|-----------|---|---|
| Source | SG-531S TCXO (U44) | 27 MHz ±50 ppm |
| Impedance | **50 Ω single-ended** | Standard CMOS clock |
| Trace Width | 0.25 mm | Impedance-controlled on F.Cu |
| Distance to ASIC | <5 mm | Minimize jitter coupling |
| Via Count | 1 only | Keep L low |
| Decoupling | 10µF + 0.1µF at U44 supply | <5 mm away |

### 3.5 Power Distribution Traces
| Rail | Max Current | Trace Width | Via Diameter | Notes |
|------|---|---|---|---|
| Vcore (12-phase PDM) | 210A | 0.5-1.0 mm per phase | 1.0 mm | Distributed around ASIC |
| Vmem | 75A | 0.5 mm | 0.8 mm | Direct to HBM3 stack group supplies |
| V5 (auxiliary) | 20A | 0.4 mm | 0.6 mm | For PDM input stage |
| V3.3 (logic) | 2.5A | 0.25 mm | 0.4 mm | For thermal controller, monitoring ICs |
| V1.8 (I/O) | 1.5A | 0.15 mm | 0.3 mm | For JTAG, I2C signaling |

---

## 4. DESIGN RULE SPECIFICATIONS

### 4.1 Electrical Design Rules (for JLCPCB standard)

| Parameter | Minimum | Recommended | Our Target |
|-----------|---------|-------------|-----------|
| Trace Width (signal) | 0.09 mm | 0.15 mm | **0.15 mm** |
| Trace Spacing (signal) | 0.09 mm | 0.15 mm | **0.15 mm** |
| Via Diameter (through) | 0.25 mm | 0.3-0.4 mm | **0.3 mm** |
| Via Drill | 0.15 mm | 0.2 mm | **0.15-0.2 mm** |
| Annular Ring | 0.075 mm | 0.125-0.25 mm | **0.125 mm** |
| Pad-to-Mask Clearance | N/A | 0.05-0.1 mm | **0.05 mm** |
| Edge Clearance | 0.3 mm | 0.5 mm (recommended) | **0.5 mm** |
| Silkscreen Width | 0.15 mm | 0.2 mm | **0.2 mm** |
| Silkscreen Height | 0.8 mm min | 1-2 mm | **1.2 mm** |
| Min Hole Size | 0.2 mm | - | **0.3 mm** |

### 4.2 Impedance Control Rules

| Pair Type | Impedance | Trace Width | Gap | Over Reference | Tolerance |
|-----------|-----------|---|---|---|---|
| PCIe Differential | 100 Ω | 0.15 mm | 0.15 mm | In3.Cu GND | ±10% |
| HBM3 Clock | 100 Ω | 0.2 mm | 0.2 mm | In3.Cu GND | ±10% |
| TCXO Reference | 50 Ω | 0.25 mm | N/A | In3.Cu GND | ±10% |

### 4.3 Via Stitching Specification

- **GND Plane Stitching:** 0.3 mm via diameter, ~25 mm spacing (one via per 25×25 mm square)
- **Power Plane Stitching:** 0.3 mm via diameter, ~35 mm spacing around high-current areas
- **Via Array Density:** Especially around U27 ASIC (3136 pins) and power delivery area
- **Connection Points:** Vias connect all power/GND planes; no floating connections

---

## 5. THERMAL MANAGEMENT SPECIFICATIONS

### 5.1 Power Dissipation Budget
| Component | Typical Power | Peak Power | Thermal Notes |
|-----------|---|---|---|
| LR-GEN3-NPU (U27) | 150W | 200W | Requires heatspreader + active cooling |
| 12-Phase PDM | 25W | 50W | Inductor + MOSFET losses |
| HBM3 Stacks (12×) | 30W | 40W | Distributed thermal load |
| Thermal Controller (U41) | <1W | <2W | Low dissipation |
| **Total System** | **~205W** | **~290W** | Design margin for 225W spec |

### 5.2 Heatspreader Specifications
- **Material:** Aluminum 6061-T6 (k = 160 W/mK)
- **Size:** 50 mm × 50 mm × 3 mm
- **Thermal Interface:** Arctic MX-4 (k = 5 W/mK, 0.5 mm layer)
- **Expected Θ:** <0.4 °C/W (ASIC junction to ambient)
- **Mounting:** Thermal vias on PCB + adhesive backing
- **Via Thermal Path:** 0.3 mm via array every 25 mm connecting to GND planes

### 5.3 Active Cooling System
- **Fans:** 2× 40 mm DC axial fans (Delta PFB0412SHN or Noctua NF-A4x20)
- **Airflow:** 2× 20 CFM = 40 CFM total (heatspreader-to-ambient)
- **Noise:** <35 dB(A) @ full speed
- **Control:** PWM via GPIO from U27 (duty cycle 0-100%)
- **Thermal Thresholds:**
  - Normal operation: 65-75 °C
  - Fan ramp: Linear from 25°C (0%) to 75°C (100%)
  - Soft throttle: 85 °C (reduce core frequency)
  - Hard shutdown: 95 °C
  - Absolute max: 100 °C (die damage threshold)

### 5.4 Temperature Sensor Placement
| Sensor | Type | I2C Address | Location | Purpose |
|--------|------|---|---|---|
| U45 | LM75 | 0x48 | On U27 die (internal) | Core temperature |
| U46 | LM75 | 0x49 | Heatspreader area | Local thermal measurement |
| U47 | LM75 | 0x50 | Rear of board | Ambient temperature reference |
| NCT6798D (U41) | Integrated | 0x2E | External sensor inputs | Fan controller |

---

## 6. POWER DELIVERY NETWORK (PDN) REQUIREMENTS

### 6.1 Vcore Rail (0.9V @ 210A peak)
- **Phases:** 12 phases (MP5949 × 2 controllers, 6 phases each)
- **Phase Inductors:** 0.47 µH (TDK or Murata) × 12
- **Decoupling Strategy:**
  - Bulk: 24× 100 µF/6.3V MLCC (1206)
  - Mid-frequency: 200× 10 µF/6.3V MLCC (0805)
  - High-frequency: 150× 2.2 µF/6.3V MLCC (0603)
  - Ultra-high frequency: 150× 0.47 µF/6.3V MLCC (0603)
- **Placement:** <5 mm from U27 power pins; distributed equally across BGA
- **Target Impedance:** <10 mΩ @ 1-10 MHz
- **Voltage Droop:** <50 mV on 50A transient
- **Soft-Start:** 100 Ω resistor, 500 ms ramp (on MP5949)

### 6.2 Vmem Rail (1.2V @ 75A)
- **Regulation:** Linear dropout regulator or dedicated MP5949 phase (2-4 phases)
- **Decoupling:**
  - Bulk: 12× 10 µF (near memory stack groups)
  - Local: 2× 2.2 µF + 4× 0.47 µF per stack (96 capacitors total)
- **Per-Stack Capacitor Placement:** <5 mm from BGA micro-bumps
- **Target Impedance:** <5 mΩ @ 10-100 MHz
- **Voltage Tolerance:** ±3% (1.164V - 1.236V)

### 6.3 Auxiliary Rails (V5, V3.3, V1.8)
- **V5:** LDO regulator from 12V input; <500 mA for PDM bias
- **V3.3:** LDO for logic (thermal controller, monitors); <2.5A
- **V1.8:** LDO for I/O (JTAG, I2C); <1.5A
- **Bypass Caps:** 10µF bulk + 0.1µF local per rail

---

## 7. ASSEMBLY & MANUFACTURING REQUIREMENTS

### 7.1 Component Sourcing
| Category | Component Type | Quantity | Source | Lead Time |
|----------|---|---|---|---|
| **Custom** | LR-GEN3-NPU-5NM (U27) | 1 | LightRail AI internal | TBD (internal supply) |
| **High-Value** | H58M16ABHX HBM3 (U28-U39) | 12 | SK Hynix distributor | 4-8 weeks |
| **Standard** | MP5949, MOSFETs, passives | 600+ | JLCPCB / LCSC | In stock |

### 7.2 Assembly Service Requirements
- **Assembly Confidence:** JLCPCB can handle standard components; custom ASIC and HBM3 stacks require special handling
- **BGA Assembly:** BGA-3136 (ASIC) and 12× BGA-1024 (memory) require precision X-ray inspection
- **Thermal Interface:** Manual application of Arctic MX-4 between heatspreader and ASIC
- **Fan Assembly:** Manual integration of 40mm fans into mounting brackets
- **Test:** Recommend ICT (In-Circuit Test) + functional burn-in at 50°C-80°C for 24-48 hours
- **Rework Capability:** ASIC rework requires BGA rework station; HBM3 stacks are non-repairable

### 7.3 Pick & Place Considerations
- **Rotation Offsets:** Provide precise rotation data for polarized components (capacitors, MOSFETs)
- **Fiducials:** 3× tooling marks (0.5 mm holes) at corners for vision alignment
- **Component Clearance:** 2 mm min between component tops for reflow oven belt
- **Test Access:** Leave 5 mm clearance around TP1-TP50 test points

---

## 8. DESIGN VERIFICATION CHECKLIST

### 8.1 Pre-Layout Verification (Schematic Complete ✓)
- [x] Schematic ERC clean (all connections verified)
- [x] All component part numbers assigned
- [x] Datasheets reviewed and available
- [x] Power tree design validated
- [x] Signal integrity specs documented
- [x] Thermal budget calculated (205W typical, 290W peak)

### 8.2 Post-Layout Verification (JLCPCB to perform)
- [ ] DRC 100% clean (0 violations)
- [ ] All footprints correctly assigned to symbols
- [ ] Component placement optimized for thermal/signal integrity
- [ ] All critical signals routed to impedance spec
- [ ] Via stitching complete across all planes
- [ ] Copper pour generated and verified
- [ ] Gerber files validated (no artifacts)
- [ ] Drill file verified (correct hole sizes/locations)
- [ ] Assembly drawing generated (component locations + values)

### 8.3 Manufacturing Readiness
- [ ] BOM converted to LCSC part numbers (for JLCPCB pricing)
- [ ] Pick & Place file generated with rotation data
- [ ] Thermal simulation run (optional, recommended)
- [ ] Signal integrity simulation for PCIe/HBM3 (optional)
- [ ] Cost estimate <$10k/unit including assembly
- [ ] Lead time estimate <12 weeks

---

## 9. SPECIAL NOTES & CONSTRAINTS

### 9.1 High-Speed Signal Integrity
- **PCIe Gen4 Equalization:** Some signals may require inline equalization near U27; verify during routing
- **HBM3 Source-Sync Clock:** On-die PLL must lock to 27 MHz reference within 10 µs; jitter budget <2 ps RMS
- **Memory Data Eye:** Simulation recommended to verify 1,024-bit data bus margin

### 9.2 Power Integrity Concerns
- **Transient Response:** 50A current step on Vcore must settle within 500 ns; peak droop <50 mV
- **Ripple:** Target <30 mV peak-peak during steady-state operation
- **Soft-Start:** MP5949 must ramp Vcore from 0V to 0.9V over 500 ms to avoid inrush current spike

### 9.3 EMI / Signal Integrity
- **Ground Plane Continuity:** No splits in GND plane; all signals reference continuous plane
- **Layer Transitions:** Use paired vias (signal via near reference via) for layer changes
- **Return Path:** Ensure all high-speed signals have immediate GND return path within 3× trace height
- **Via Stitching:** Particularly dense around PCIe connector (every 10 mm) and ASIC (every 15 mm)

### 9.4 Mechanical Constraints
- **Slot Insertion:** Board must fit standard PCIe x16 slot with <0.2 mm clearance per side
- **Component Height:** Max component height 8 mm (including heatspreader)
- **Solder Fillet Clearance:** 2 mm from board edge to prevent solder shorts on connector
- **Mounting Hole Alignment:** Verify ±0.1 mm tolerance with mechanical drawings

### 9.5 Testing & Validation
- **Functional Test:** Verify 27 MHz clock, PLL lock, and all supply voltages before ASIC power-on
- **Burn-In:** 48-72 hour soak test at Tj = 70°C ±5°C, 50% clock speed
- **Thermal Validation:** Run full-load thermal test; verify Tj <85°C with dual fans at 75% duty
- **Signal Integrity:** Oscilloscope capture of PCIe TX/RX eyes; verify >200 mV vertical margin

---

## 10. MANUFACTURING RECOMMENDATIONS

### 10.1 Suggested Timeline (Phase 2 completion)
1. **Layout Design:** 2-3 weeks (JLCPCB standard service) or 1 week (express service)
2. **DRC Review & Iteration:** 1 week
3. **Gerber Generation & Validation:** 1 week
4. **Prototype PCB Manufacturing:** 2-3 weeks (lead time from fab)
5. **Component Procurement:** 4-8 weeks (especially HBM3 stacks)
6. **Assembly & Testing:** 2-3 weeks
7. **Thermal Validation:** 1-2 weeks

**Total Path to First Unit:** ~12-14 weeks (parallel sourcing recommended)

### 10.2 Risk Mitigation
- **ASIC Sourcing:** Confirm LR-GEN3-NPU availability and supply chain ASAP
- **HBM3 Availability:** Contact SK Hynix or authorized distributors now; long lead item
- **Assembly Complexity:** Pre-negotiate thermal and BGA rework rates with assembly house
- **Testing:** Plan ICT fixture design in parallel with layout phase

---

## 11. CONTACT & CHANGE MANAGEMENT

**Project Lead:** LightRail AI Engineering  
**JLCPCB Point of Contact:** (To be assigned by JLCPCB)  
**Design Files Location:** `/home/user/LightOS_Compiler/LightRail_NCE_Schematic/`

**Change Log:**
- **2026-07-21:** Initial layout requirement submission
- **v1.0** - Complete specification for Phase 2 PCB design

---

## 12. DELIVERABLES CHECKLIST (For JLCPCB Submission)

- [x] Requirement document (this file)
- [x] KiCAD schematic files (8 files: main + 6 subsystems)
- [x] KiCAD PCB file (skeleton, ready for layout)
- [x] Bill of Materials (CSV format)
- [ ] **JLCPCB to provide:** Routed PCB file + Gerber files
- [ ] **JLCPCB to provide:** Pick & Place file
- [ ] **JLCPCB to provide:** Assembly drawing
- [ ] **JLCPCB to provide:** Cost estimate & lead time

---

**Document Version:** 1.0  
**Status:** Ready for JLCPCB Layout Quote  
**Next Step:** Submit to design.jlcpcb.com/quote with all supporting files
