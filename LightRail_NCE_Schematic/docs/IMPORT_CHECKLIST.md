# EasyEDA Import Verification Checklist

**Project**: LightRail AI NCE Motherboard  
**File**: LightRail_NCE_Schematic.zip  
**Date Imported**: ___________  
**Reviewer**: ___________  

---

## Pre-Import Checklist

### File Preparation
- [ ] ZIP file downloaded successfully
- [ ] ZIP file integrity verified (not corrupted)
- [ ] File size: ~2-5 MB (typical for this project)
- [ ] Contains all required subdirectories:
  - [ ] kicad_project/
  - [ ] easyeda_project/
  - [ ] docs/

### System Requirements
- [ ] EasyEDA account created and logged in
- [ ] Browser compatible with EasyEDA (Chrome, Firefox, Edge)
- [ ] Sufficient storage quota in EasyEDA project
- [ ] Internet connection stable

---

## Import Process Verification

### Step 1: Create New Project
- [ ] Project created with name: "LightRail AI NCE Motherboard"
- [ ] Project type: "EDA" (Electronic Design Automation)
- [ ] Project access level set appropriately (Private/Public)

### Step 2: Import Files
- [ ] ZIP file selected for import
- [ ] Import format recognized as "KiCAD"
- [ ] File upload progress shows 100%
- [ ] No error messages during upload
- [ ] Processing notification received

### Step 3: Wait for Processing
- [ ] Import progress displayed
- [ ] No timeout errors (typical processing: 2-5 minutes)
- [ ] Completion notification received
- [ ] Project automatically opens after import

---

## Schematic Import Verification

### Main Schematic (LightRail_NCE.kicad_sch)
- [ ] File imported successfully
- [ ] System block diagram visible
- [ ] Text annotations readable
- [ ] Sheet reference notes present:
  - [ ] "1 - Power Delivery System"
  - [ ] "2 - PCIe Interface"
  - [ ] "3 - HBM3 Memory Subsystem"
  - [ ] "4 - Clock Distribution"
  - [ ] "5 - Thermal Management"
  - [ ] "6 - Debug Interface"

### Schematic Sheets (All 6 Subsystems)
- [ ] PDN.kicad_sch (Power Delivery)
  - [ ] MP5949 controller symbols visible
  - [ ] 12-phase configuration shown
  - [ ] Power rail labels (Vcore, Vmem, V5, V3.3, V1.8)
  - [ ] Decoupling network annotations present

- [ ] PCIe_Interface.kicad_sch
  - [ ] PCIe x16 edge connector shown
  - [ ] 16-lane differential pair indication
  - [ ] Power input protection circuit visible
  - [ ] OR-ing diode configuration shown

- [ ] HBM3_Memory.kicad_sch
  - [ ] 12 memory stack symbols present
  - [ ] Stack placement diagram included
  - [ ] 128-bit data path per stack shown
  - [ ] Decoupling capacitor annotations

- [ ] Clock_Distribution.kicad_sch
  - [ ] 27MHz TCXO symbol visible
  - [ ] On-chip PLL reference shown
  - [ ] 2.4 GHz output clock indicated
  - [ ] Clock distribution tree diagram present

- [ ] Thermal_Management.kicad_sch
  - [ ] Dual fan connectors shown
  - [ ] Temperature sensor symbols (5 total)
  - [ ] Heatspreader representation visible
  - [ ] Thermal control logic annotated

- [ ] Debug_Interface.kicad_sch
  - [ ] 14-pin JTAG header symbol
  - [ ] I2C bus connections shown
  - [ ] Temperature sensor I2C addresses
  - [ ] Current monitor ICs displayed

### Component Symbols
- [ ] MP5949 (PWM Controller)
  - [ ] Pin count: 48 (QFN)
  - [ ] Power pins: VIN, VDD, GND identified
  - [ ] Phase outputs: 12 phases labeled
  - [ ] Control pins: VREF, FB, etc. present

- [ ] LR-GEN3-NPU (Main ASIC)
  - [ ] BGA symbol (3136 pins)
  - [ ] Power domains: Vcore, Vmem
  - [ ] Data interfaces: HBM3, PCIe TX/RX
  - [ ] Clock input: CLK_27MHz
  - [ ] Debug: JTAG, Thermal sense

- [ ] HBM3 Memory Stacks (12x)
  - [ ] Symbol appears 12 times
  - [ ] Part number: H58M16ABHX
  - [ ] Power pin: VDDQ (1.2V)
  - [ ] Data pins: DQ[0:127]
  - [ ] Clock pins: CLK, CLK#

- [ ] Passive Components
  - [ ] Capacitors: Multiple values visible
  - [ ] Resistors: Pull-up, termination shown
  - [ ] Inductors: Power inductors identified
  - [ ] Diodes: Protection diodes visible

### Nets and Connectivity
- [ ] Net names imported and preserved:
  - [ ] +12V, +5V, +3.3V, +1.8V power nets
  - [ ] GND (multiple ground nets)
  - [ ] Vcore, Vmem (regulated supplies)
  - [ ] PCIe data nets (TX, RX lanes)
  - [ ] Memory data nets (DQ, strobes)
  - [ ] Clock nets (CLK, CLK_27MHz)
  - [ ] JTAG nets (TDI, TDO, TMS, TCK)

- [ ] No connectivity errors
- [ ] All connections show proper continuity
- [ ] No floating nets or unconnected pins

---

## PCB Layout Verification

### Basic Dimensions
- [ ] Board size imported: 267mm × 111mm ✓
- [ ] Thickness: 2.4mm ✓
- [ ] Edge cuts (outline) properly defined
- [ ] Mounting hole locations marked
- [ ] Board origin set correctly

### Layer Stack
- [ ] 10-layer board configured
- [ ] Layer order correct:
  - [ ] Layer 1 (F.Cu): Signal/GND
  - [ ] Layer 2 (In1.Cu): Vcore Power Plane
  - [ ] Layer 3 (In2.Cu): Signal
  - [ ] Layer 4 (In3.Cu): GND Reference Plane
  - [ ] Layer 5 (In4.Cu): Signal
  - [ ] Layer 6 (In5.Cu): Vmem Power Plane
  - [ ] Layer 7 (In6.Cu): Signal
  - [ ] Layer 8 (In7.Cu): GND Reference Plane
  - [ ] Layer 9 (In8.Cu): Signal
  - [ ] Layer 10 (B.Cu): Signal/GND

- [ ] Dielectric properties set:
  - [ ] Material: FR-4
  - [ ] Tg ≥ 170°C
  - [ ] Epsilon_r: 4.5
  - [ ] Loss tangent: 0.02

### Component Placement
- [ ] LR-GEN3-NPU (U27) placed at design center
- [ ] PCIe connector (J1) at right edge
- [ ] PEX power connectors (J2) accessible
- [ ] JTAG header (J3) positioned for test access
- [ ] Thermal management area clear
- [ ] All critical components placed

### HBM3 Memory Stacks
- [ ] 12 stacks total placed:
  - [ ] 6 stacks on left side (S0-S5)
  - [ ] 6 stacks on right side (S6-S11)
- [ ] Stack placement symmetrical
- [ ] Spacing optimal for thermal management
- [ ] Data routing accessible

### Power Distribution Network
- [ ] 12-phase layout arranged
- [ ] Phase inductors distributed for thermal balance
- [ ] Decoupling capacitors placed:
  - [ ] Bulk capacitors near PDM input
  - [ ] Local capacitors near ASIC/memory power pins
  - [ ] Via stitching to power planes visible

### Traces and Routing
- [ ] Differential pair routing present:
  - [ ] PCIe TX/RX pairs 100Ω impedance
  - [ ] Memory clock pairs 100Ω differential
  - [ ] Equal length traces within pairs
- [ ] High-speed signal traces appropriately routed
- [ ] Via density adequate for power delivery
- [ ] No shorts or design rule violations visible

### Silk Screen & Labels
- [ ] Component designators visible (U1, J1, etc.)
- [ ] Net names labeled on key signals
- [ ] Board title: "LightRail AI NCE Motherboard"
- [ ] Revision info: "Rev 1.0"
- [ ] Date stamp present
- [ ] Company mark/logo included

### Test Points
- [ ] 50+ test points visible:
  - [ ] Power rail monitoring pads
  - [ ] Signal observation points
  - [ ] JTAG access verification points
- [ ] Test point locations logical and accessible

---

## Design Rules Check

### Electrical Rules Check (ERC)
- [ ] Run: **Tools** → **Design Rules Check**
- [ ] Results:
  - [ ] Errors: **0** (expected)
  - [ ] Warnings: _____ (document if any)
  - [ ] Info messages: _____ (review for understanding)

### Design Rules (DRC) - PCB
- [ ] Minimum trace width: 0.15mm (met)
- [ ] Minimum spacing: 0.15mm (met)
- [ ] Via diameter: 0.3mm (met)
- [ ] Pad-to-edge clearance: 0.3mm (met)
- [ ] Solder mask clearance: 0.1mm (met)
- [ ] Copper-to-edge: 0.3mm (met)

### DRC Violations (if any)
- [ ] Count: _____ (should be 0)
- [ ] List violations found:
  1. _____________________________
  2. _____________________________
  3. _____________________________
- [ ] Resolution status: _____ (Resolved/Pending)

---

## Footprint Verification

### Critical Components
- [ ] MP5949 → QFN-48-1EP (correct ✓)
- [ ] LR-GEN3-NPU → BGA-3136 (correct ✓)
- [ ] H58M16ABHX → BGA-1024 (correct ✓, qty: 12)
- [ ] NCT6798D → QFN-48 (thermal controller)
- [ ] INA226 → TSSOP-20 (voltage monitor)
- [ ] LM75 → TSSOP-8 (temperature sensor, qty: 3)

### Passive Components
- [ ] Capacitors: 0603/0805 packages (600 total)
- [ ] Resistors: 0603/0805 packages (250 total)
- [ ] Inductors: 1210/1812 packages (50 total)
- [ ] No oversized or mismatched packages

### Connectors
- [ ] PCIe x16 (J1): Edge connector, 164-pin ✓
- [ ] 8-pin PEX (J2): Molex 5559 ✓
- [ ] JTAG (J3): 14-pin 0.1" header ✓

### Missing Footprints
- [ ] Count: _____ (should be 0)
- [ ] List any unlinked symbols: _________
- [ ] Resolution: _____ (Linked/Pending)

---

## Signal Integrity Verification

### PCIe Differential Pairs
- [ ] Number of pairs: 16 (TX) + 16 (RX) = 32 pairs ✓
- [ ] Impedance setting: 100Ω ±10%
- [ ] Track width: 0.15mm
- [ ] Pair spacing (gap): 0.15mm
- [ ] Length matching: ±20 mils ✓

### Memory Clock Distribution
- [ ] Differential pairs: 2 (CLK and CLK#)
- [ ] Impedance: 100Ω differential
- [ ] Track width: 0.2mm
- [ ] Via count: <2 per line
- [ ] Jitter spec: <3ps RMS

### Reference Clock (27 MHz)
- [ ] Impedance: 50Ω single-ended
- [ ] Jitter: <1ps RMS
- [ ] Decoupling: 10µF + 0.1µF present

---

## Thermal Verification

### Heatspreader
- [ ] Copper area allocated: 50×50mm minimum
- [ ] Thermal vias connected to ground planes
- [ ] Thermal pad thickness defined

### Thermal Management Traces
- [ ] Fan power traces routed (5V/12V to J2)
- [ ] Fan PWM signal lines (GPIO from ASIC)
- [ ] Temperature sensor connections:
  - [ ] Sensor 1: Internal die temp (on-chip)
  - [ ] Sensor 2-4: Ambient thermistors
  - [ ] All connected to ASIC I2C bus

### Power Dissipation Path
- [ ] ASIC → Heatspreader → Fans
- [ ] Thermal resistance: <0.4°C/W expected

---

## Manufacturing Readiness

### Design for Manufacturability (DFM)
- [ ] Silkscreen clearance: 0.2mm from solder mask
- [ ] Text size: >0.3mm height
- [ ] Smallest trace: 0.15mm (acceptable for JLCPCB)
- [ ] Smallest via: 0.3mm (acceptable)
- [ ] Solder mask alignment: ±0.05mm tolerance

### Assembly Considerations
- [ ] Component placement density: Moderate (suitable for JLCPCB)
- [ ] No overlapping footprints
- [ ] BGA escape routing present
- [ ] Rework areas accessible
- [ ] Test point access clear

### BOM Completeness
- [ ] Total components: ~900 (250 resistors + 600 capacitors + 50 inductors + 48 ICs)
- [ ] All parts have:
  - [ ] Part number
  - [ ] Manufacturer specified
  - [ ] Package designated
  - [ ] Quantity noted
- [ ] Cost estimate calculated
- [ ] Lead times reviewed

---

## Export & Fabrication Prep

### Gerber Export
- [ ] Gerber files generated:
  - [ ] F.Cu (top copper)
  - [ ] B.Cu (bottom copper)
  - [ ] F.Mask (top solder mask)
  - [ ] B.Mask (bottom solder mask)
  - [ ] F.SilkS (top silkscreen)
  - [ ] B.SilkS (bottom silkscreen)
  - [ ] Edge.Cuts (board outline)
  - [ ] F.Fab (front fabrication layer - optional)

- [ ] Drill file generated (Excellon format)
- [ ] All files compressed into ZIP archive
- [ ] File size: _____ MB
- [ ] Gerber preview checked (no anomalies)

### JLCPCB Submission Ready
- [ ] ZIP archive created with all Gerber files
- [ ] Drill file included
- [ ] Project settings:
  - [ ] PCB Thickness: 2.4mm ✓
  - [ ] Layers: 10 ✓
  - [ ] Surface Finish: HASL or ENIG
  - [ ] Solder Mask Color: (select - recommend green)
  - [ ] Silkscreen Color: (select - recommend white)
  - [ ] Copper Weight: 1 oz front/back, per layer stackup

### Documentation Package
- [ ] README.md included ✓
- [ ] BOM.csv included ✓
- [ ] EASYEDA_IMPORT_GUIDE.md included ✓
- [ ] Design specifications documented
- [ ] Reference design included

---

## Final Sign-Off

### Overall Status
- [ ] Schematic import: **COMPLETE**
- [ ] PCB import: **COMPLETE**
- [ ] Design verification: **COMPLETE**
- [ ] DRC/ERC: **PASSED**
- [ ] BOM: **VERIFIED**
- [ ] Ready for fabrication: **YES / NO**

### Sign-Off
- **Reviewed By**: ___________________________
- **Date**: ___________________________
- **Comments**: _______________________________
  ________________________________________
  ________________________________________

### Next Steps
- [ ] If issues found:
  - [ ] Document issues in Issues Log below
  - [ ] Assign resolution owner
  - [ ] Schedule review
  
- [ ] If approved:
  - [ ] Generate final Gerber files
  - [ ] Submit to fabrication
  - [ ] Send confirmation to LightRail AI team
  - [ ] Archive this checklist

---

## Issues Log (if any)

| Issue # | Description | Severity | Owner | Status |
|---------|-------------|----------|-------|--------|
| 1. | | | | |
| 2. | | | | |
| 3. | | | | |

---

**Document Version**: 1.0  
**Created**: 2026-07-19  
**Last Updated**: ___________  

*This checklist ensures complete verification of the LightRail NCE schematic and PCB design after EasyEDA import.*
