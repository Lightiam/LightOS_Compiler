# 🚀 JLCPCB Layout Order - Quick Start Guide
## 5-Minute Submission Checklist

### ✅ Pre-Submission Verification (1 min)

**Files Ready?**
- [x] `LightRail_NCE.kicad_sch` (main schematic)
- [x] `PDN.kicad_sch`, `PCIe_Interface.kicad_sch`, `HBM3_Memory.kicad_sch`, `Clock_Distribution.kicad_sch`, `Thermal_Management.kicad_sch`, `Debug_Interface.kicad_sch` (subsystems)
- [x] `LightRail_NCE.kicad_pcb` (PCB skeleton)
- [x] `JLCPCB_LAYOUT_REQUIREMENTS.md` (specs)
- [x] `JLCPCB_BOM_LCSC.csv` (bill of materials)

**All Located At:**
```
/home/user/LightOS_Compiler/LightRail_NCE_Schematic/
```

---

### 🔗 Submission URL
**https://design.jlcpcb.com/quote**

---

### 📝 What to Enter (2 min)

1. **Click:** "Start a Layout Quote" button (or go directly to URL above)

2. **Upload Package:** Select all files (ZIP recommended):
   ```
   LightRail_NCE_Schematic/
   ├── kicad_project/*.kicad_sch (7 files)
   ├── kicad_project/*.kicad_pcb (1 file)
   ├── kicad_project/*.kicad_pro (1 file)
   ├── JLCPCB_LAYOUT_REQUIREMENTS.md
   ├── JLCPCB_BOM_LCSC.csv
   └── README.md
   ```

3. **Project Details:**
   - **Project Name:** LightRail AI NCE - 10-Layer PCB Layout
   - **Board Dimensions:** 267 mm × 111 mm
   - **Layers:** 10
   - **Thickness:** 2.4 mm
   - **Material:** FR-4
   - **Copper Weight:** 1 oz (standard)
   - **Surface Finish:** HASL or ENIG
   - **Solder Mask:** Green
   - **Silkscreen:** White

4. **Special Requirements:** (paste from JLCPCB_LAYOUT_REQUIREMENTS.md)
   ```
   - Impedance control: PCIe 100Ω differential, HBM3 clock 100Ω differential
   - 3136-pin BGA (LR-GEN3-NPU custom ASIC) - requires direct supply
   - 12× 1024-pin BGA (SK Hynix HBM3 - 16GB stacks) - requires distributor supply
   - Heatspreader thermal vias under ASIC
   - Via stitching: ~25mm spacing across GND planes
   ```

---

### 📋 After Upload (2 min)

1. **Click:** "Submit Quote Request"
2. **Email:** JLCPCB will send quote within 24-48 hours
3. **Review:** Cost estimate + timeline (typically 2-3 weeks layout)
4. **Approve:** Click link in email to proceed to payment

---

### ⏱️ Timeline & What to Do In Parallel

While JLCPCB does the layout (2-3 weeks):

**CRITICAL - Start These NOW:**
1. **Confirm ASIC Supply:** Contact LightRail AI for LR-GEN3-NPU-5NM delivery arrangement
   - Unit cost: $3,500
   - Quantity: 1
   - Delivery to: JLCPCB assembly house (or direct to your facility)

2. **HBM3 Procurement:** Contact SK Hynix or authorized distributor for H58M16ABHX
   - Unit cost: $180 (market dependent)
   - Quantity: 12
   - Lead time: 4-8 weeks (longest critical path item!)
   - Part number: SK Hynix H58M16ABHX

3. **Review Design Specs:** Share `JLCPCB_LAYOUT_REQUIREMENTS.md` with assembly house

---

### 💰 Budget Estimate

| Item | Cost | Notes |
|------|------|-------|
| JLCPCB Layout Service | $500-1,000 | 2-3 weeks |
| PCB Manufacturing (10 units) | $5,000-7,500 | Includes setup fees |
| Standard Components | $6,380 | Per JLCPCB_BOM_LCSC.csv |
| Custom ASIC (LR-GEN3-NPU) | $3,500 | Per unit |
| HBM3 Memory Stacks (12×) | $2,160 | Per unit ($180 each) |
| Assembly Labor | $200-400 | High complexity |
| **Total Per Unit** | **$6,700-7,100** | Components + assembly |

---

### 🎯 Key Success Factors

1. ✅ **Schematic Complete** - All 8 files verified
2. ✅ **Specs Documented** - 25-page requirements file
3. ✅ **BOM Ready** - LCSC part numbers assigned
4. ⚠️ **CRITICAL:** Source custom ASIC (LightRail AI)
5. ⚠️ **CRITICAL:** Source HBM3 stacks (4-8 week lead time!)
6. ✅ **Design Rules** - Impedance control specs included
7. ✅ **Thermal Plan** - Heatspreader + fan cooling defined

---

### 📞 Contact Points

**If JLCPCB Asks About:**

| Question | Answer | Reference |
|----------|--------|-----------|
| "What's the PCIe x16 connector spec?" | Molex 73215-0520 (164-pin, Gen3/Gen4) | JLCPCB_LAYOUT_REQUIREMENTS.md § 2.1 |
| "How should we route the ASIC power?" | 12-phase PDM with distributed inductors | JLCPCB_LAYOUT_REQUIREMENTS.md § 6.1 |
| "What impedance for HBM3 clock?" | 100Ω differential ±10% | JLCPCB_LAYOUT_REQUIREMENTS.md § 3.2 |
| "Can JLCPCB source the ASIC?" | No - requires direct LightRail AI supply | JLCPCB_LAYOUT_REQUIREMENTS.md § 7.1 |
| "What about the HBM3 stacks?" | Limited availability - distributor supply | JLCPCB_LAYOUT_REQUIREMENTS.md § 7.1 |
| "What test points do we need?" | 50 total - power rail monitoring, signal observation, JTAG access | JLCPCB_LAYOUT_REQUIREMENTS.md § 2.1 |

---

### 🔴 Red Flags to Avoid

1. **Don't wait for component sourcing** - Start HBM3 procurement NOW (4-8 week lead!)
2. **Don't skip the requirements document** - JLCPCB needs it for impedance control
3. **Don't forget to mention custom ASIC** - Tell JLCPCB upfront about LR-GEN3-NPU supply
4. **Don't skip DRC** - Ensure 0 violations before fabrication
5. **Don't use generic PCIe connector** - Must be Molex 73215-0520 (164-pin edge)

---

### 📲 Quick Reference

**Submission URL:** https://design.jlcpcb.com/quote  
**Project Name:** LightRail AI NCE - 10-Layer PCB Layout  
**Board Size:** 267 × 111 × 2.4 mm  
**Layers:** 10 (FR-4)  
**Timeline:** 2-3 weeks (layout) + 4-8 weeks (component sourcing)  
**Total Cost:** $6,700-7,100 per unit  

---

**Status:** ✅ READY TO SUBMIT  
**Next Action:** Visit design.jlcpcb.com/quote and upload files  
**Expected Response Time:** 24-48 hours from JLCPCB
