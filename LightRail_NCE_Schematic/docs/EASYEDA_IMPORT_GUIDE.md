# EasyEDA Import Guide - LightRail NCE Schematic & PCB

## ⚠️ Important Pre-Import Notes

1. **Import Complete Package**: Always import the **zipped KiCAD project** (both schematic + PCB), not just the schematic files alone
   - This ensures proper footprint binding and design integrity
   - Schematic-only import requires manual footprint linking

2. **Font Family Differences**: EasyEDA uses different font families than KiCAD
   - Text may appear slightly different after import
   - Check and adjust text placement if needed

3. **Format Conversion Differences**: Due to file format differences:
   - Some elements may require refinement
   - Review all layers and components carefully
   - Verify power planes and trace routing

4. **Disclaimer**: EasyEDA is not responsible for losses caused by format conversion differences

---

## 📦 File Package Contents

```
LightRail_NCE_Schematic.zip
├── kicad_project/
│   ├── LightRail_NCE.kicad_pro          (Main project file)
│   ├── LightRail_NCE.kicad_sch          (Top-level schematic)
│   ├── LightRail_NCE.kicad_pcb          (PCB layout)
│   ├── PDN.kicad_sch                    (Power Delivery sheet)
│   ├── PCIe_Interface.kicad_sch         (PCIe Interface sheet)
│   ├── HBM3_Memory.kicad_sch            (Memory sheet)
│   ├── Clock_Distribution.kicad_sch     (Clock sheet)
│   ├── Thermal_Management.kicad_sch     (Thermal sheet)
│   └── Debug_Interface.kicad_sch        (Debug sheet)
├── easyeda_project/
│   ├── project.json
│   └── LightRail_NCE_Main.json
├── docs/
│   ├── LightRail_NCE_BOM.csv
│   ├── EASYEDA_IMPORT_GUIDE.md          (This file)
│   └── IMPORT_CHECKLIST.md
└── README.md                             (Main documentation)
```

---

## 🚀 Step-by-Step Import Process

### Option A: Import from ZIP File (Recommended)

**Step 1: Download & Prepare**
- Download `LightRail_NCE_Schematic.zip` from the repository
- Keep it as a ZIP file (do not extract first)

**Step 2: Log in to EasyEDA**
1. Go to https://easyeda.com
2. Sign in with your account (create one if needed)
3. Go to **Dashboard** → **Projects**

**Step 3: Create New Project**
1. Click **"Create New Project"**
2. Enter project name: `LightRail AI NCE Motherboard`
3. Select **"EDA"** (Electronic Design Automation)
4. Click **"Create"**

**Step 4: Import KiCAD Files**
1. In the project editor, go to **File** → **Import** → **Import EDA**
2. Select **"KiCAD"** as the import format
3. Choose the ZIP file: `LightRail_NCE_Schematic.zip`
4. EasyEDA will automatically detect and import:
   - All schematic sheets
   - PCB layout
   - Footprint associations
   - Net connectivity

**Step 5: Wait for Processing**
- Processing may take 2-5 minutes depending on file size
- EasyEDA will show import progress
- You'll receive notification when complete

---

### Option B: Manual File Import

If ZIP import fails, manually import files:

**Step 1: Extract the ZIP File**
```bash
unzip LightRail_NCE_Schematic.zip
cd kicad_project/
```

**Step 2: Import Project in EasyEDA**
1. Go to **File** → **Import EDA**
2. Select **"KiCAD Project"** (not individual files)
3. Upload `LightRail_NCE.kicad_pro`
4. EasyEDA will prompt to import associated files

**Step 3: Import PCB Separately (if needed)**
1. Go to **File** → **Import PCB**
2. Select **"KiCAD PCB"**
3. Upload `LightRail_NCE.kicad_pcb`

**Step 4: Link Schematics & PCB**
1. In schematic editor: **Tools** → **Design Rules** → **Footprint Library**
2. Ensure all symbols have footprints assigned
3. In PCB editor: **Tools** → **Design Rules** → **Check**
4. Verify all components are placed

---

## ✅ Post-Import Verification Checklist

### Schematic Review

- [ ] All 6 sheets imported successfully
  - [ ] Main schematic (system overview)
  - [ ] PDN sheet (power delivery)
  - [ ] PCIe Interface sheet
  - [ ] HBM3 Memory sheet
  - [ ] Clock Distribution sheet
  - [ ] Thermal Management sheet
  - [ ] Debug Interface sheet

- [ ] Component symbols visible and correct
  - [ ] MP5949 PWM controller appears correctly
  - [ ] LR-GEN3-NPU BGA symbol complete
  - [ ] HBM3 memory stacks shown (12x)
  - [ ] Connectors (J1: PCIe, J2: PEX, J3: JTAG) present

- [ ] Nets and connections preserved
  - [ ] Power nets (Vcore, Vmem, V5, V3.3, V1.8) connected
  - [ ] GND connections complete
  - [ ] Signal paths intact (PCIe TX/RX, memory data, clock)

- [ ] Text and labels readable
  - [ ] Component designators visible
  - [ ] Net names clear
  - [ ] Adjust font sizes if text appears distorted

### PCB Review

- [ ] PCB dimensions correct: 267mm × 111mm ✓
- [ ] Board outline (Edge.Cuts layer) is square perimeter ✓
- [ ] 10-layer stackup properly configured
  - [ ] F.Cu (signal)
  - [ ] In1.Cu (Vcore plane)
  - [ ] In2.Cu (signal)
  - [ ] In3.Cu (GND plane)
  - [ ] In4.Cu (signal)
  - [ ] In5.Cu (Vmem plane)
  - [ ] In6.Cu (signal)
  - [ ] In7.Cu (GND plane)
  - [ ] In8.Cu (signal)
  - [ ] B.Cu (signal)

- [ ] Major components placed:
  - [ ] LR-GEN3-NPU (U27) at center-left
  - [ ] 12 HBM3 stacks (U28-U39) in two rows
  - [ ] MP5949 controllers (U1-U2) for PDM
  - [ ] PCIe connector (J1) at right edge
  - [ ] PEX power connector (J2)
  - [ ] JTAG header (J3)

- [ ] Traces routed:
  - [ ] Differential pairs for PCIe (100Ω impedance)
  - [ ] Memory data and clock lines
  - [ ] Power distribution network
  - [ ] Vias properly placed for power return

- [ ] Test points visible:
  - [ ] 50+ power rail monitoring pads
  - [ ] Signal observation points
  - [ ] JTAG access verified

### Component Footprints

- [ ] All footprints properly linked
  - [ ] QFN packages for controllers
  - [ ] BGA packages for ASIC and memory
  - [ ] 0603/0805 for passives
  - [ ] Edge connector footprint correct

- [ ] No missing or mismatched footprints
  - [ ] Run **Tools** → **Design Rules** → **Check**
  - [ ] Resolve any ERC/DRC errors

- [ ] Pad sizes appropriate:
  - [ ] PCIe connector pads for high current
  - [ ] BGA micro-bumps (40µm pitch for HBM3)
  - [ ] Power MOSFETs (PK 8×8 package)

---

## 🔧 Common Post-Import Adjustments

### Issue 1: Text Appearance Distorted
**Solution:**
1. Select affected text objects
2. Adjust font size to 1.5-2mm for clarity
3. Check alignment (left/center/right)
4. Use sans-serif fonts for better rendering

### Issue 2: Footprints Not Linked
**Solution:**
1. In schematic: Right-click symbol → **Edit Footprint**
2. Select correct footprint from library
3. Verify package size matches BOM
4. Update PCB layout if footprint changed

### Issue 3: Power Planes Not Imported
**Solution:**
1. In PCB editor: Go to **Layers** panel
2. Verify plane layers (In1, In3, In5, In7) are visible
3. If missing, manually recreate:
   - Select **"Polygon"** tool
   - Draw rectangle on plane layer
   - Set to "Solid Fill" for entire area
   - Assign net (Vcore, GND, Vmem, etc.)

### Issue 4: Differential Pair Impedance Not Set
**Solution:**
1. Select differential pair traces
2. In **Trace Properties**, set:
   - Impedance Type: **"Differential Pair"**
   - Impedance: **100 Ohms ±10%**
   - Track width: **0.15mm** (PCIe) or **0.2mm** (Memory)
   - Gap: **0.15mm** (PCIe) or **0.2mm** (Memory)

### Issue 5: Via Stitching Missing
**Solution:**
1. For ground plane via stitching:
   - Use **Via Array** tool
   - Spacing: ~25mm (1 via per square inch)
   - Diameter: 0.3mm
   - Via type: Through-hole
2. Place around high-current components (PDM, ASIC)

---

## 📊 Post-Import Design Rules

After successful import, verify these critical specifications:

### Power Delivery
- [ ] Vcore rail: 0.9V ±3% with <50mV droop on 50A transient
- [ ] Vmem rail: 1.2V ±3%
- [ ] All supply decoupling capacitors placed (<5mm from components)

### Signal Integrity
- [ ] PCIe TX/RX differential pairs: 100Ω impedance
- [ ] Memory clock pairs: 100Ω differential
- [ ] Length matching: ±20 mils within lane group
- [ ] Via count limited: <4 per signal

### Thermal
- [ ] Heatspreader copper area >50×50mm
- [ ] Thermal vias to ground planes under high-power components
- [ ] Fan connectors located at rear edge

### Manufacturing
- [ ] Solder mask clearance: 0.1mm minimum
- [ ] Silkscreen line width: 0.2mm minimum
- [ ] Copper-to-edge clearance: 0.3mm (12mil)
- [ ] Trace width minimum: 0.15mm for signals, 0.25mm for power

---

## 💾 Saving & Exporting

### Save Project in EasyEDA
1. **File** → **Save** (auto-saves continuously)
2. **File** → **Save as** to create version

### Export for Fabrication

**Gerber Files (for JLCPCB/PCB Fab):**
1. **File** → **Export** → **Gerber**
2. Include all layers:
   - F.Cu, B.Cu, F.Mask, B.Mask, F.SilkS, B.SilkS, Edge.Cuts, F.Fab
3. Generate drill file (Excellon format)
4. Create ZIP archive with all files

**Schematic PDF:**
1. **File** → **Export** → **PDF**
2. Include all sheets
3. Set scale for printing (1:1 or A3/A4)

**BOM for Assembly:**
1. Generate from schematic: **Tools** → **Generate BOM**
2. Cross-reference with `LightRail_NCE_BOM.csv`
3. Update part numbers and supplier information

---

## 📞 Support & Resources

### EasyEDA Resources
- **Official Tutorials**: https://docs.easyeda.com/
- **KiCAD Import Guide**: https://docs.easyeda.com/en/api/guide/easyeda-import-easyeda-format
- **Community Forum**: https://forum.easyeda.com/
- **Support Email**: support@easyeda.com

### LightRail AI Resources
- **Reference Design**: `LightRail_NCE_Reference_Design.html`
- **Main Documentation**: `README.md`
- **Bill of Materials**: `LightRail_NCE_BOM.csv`

### PCB Fabrication
- **JLCPCB**: https://jlcpcb.com/quote
- **Requirements**: See `DESIGN_SPECIFICATIONS.md`

---

## ⚠️ Troubleshooting

### Import Fails
- Verify ZIP file is not corrupted: `unzip -t LightRail_NCE_Schematic.zip`
- Try extracting and importing individual `.kicad_sch` files
- Contact EasyEDA support with error message

### Missing Components After Import
- Check **Component Library** in EasyEDA
- Manually add from library: **Tools** → **Component Library** → **Search**
- For custom parts (LR-GEN3-NPU, HBM3), create placeholder symbols

### Footprint Mismatches
- Review **Design Rules Check**: **Tools** → **Design Rules** → **Check**
- Update footprints using provided BOM reference
- Export footprint changes back to KiCAD if editing in EasyEDA

### Performance Issues with Large Design
- For 10-layer boards with 3000+ components:
  - Use **Layers** panel to hide/show layers as needed
  - Enable **Smart Refresh** to improve responsiveness
  - Consider splitting into multiple projects if needed

---

## 📋 Final Checklist Before Export

- [ ] All schematics reviewed and verified
- [ ] All footprints linked correctly
- [ ] PCB layout complete with all components placed
- [ ] All traces routed (or verify design is ready for layout)
- [ ] Design Rules Check passed with no errors
- [ ] BOM generated and verified
- [ ] Gerber files exported and tested in viewer
- [ ] Drill file included (Excellon format)
- [ ] Silkscreen and labels placed
- [ ] Documentation updated

---

**Version**: 1.0  
**Last Updated**: 2026-07-19  
**Status**: Ready for EasyEDA Import

For questions or issues with this import guide, refer to the main README.md or contact LightRail AI Engineering.
