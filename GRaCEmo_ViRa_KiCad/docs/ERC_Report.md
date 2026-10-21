# ERC / validation report

**KiCad ERC was NOT run.** KiCad is not installed in the generation environment, and the environment could not download it.
No sheet has been opened in KiCad. Do not treat this project as KiCad-validated.

## What was actually run
`check.py` (included in `tools/`) parsed all 11 `.kicad_sch` files with the independent `kiutils` parser and rebuilt connectivity from geometry
(wire end points, global labels, pin end points, no-connect markers). This is **not** a substitute for KiCad ERC.

| Check | Result |
|---|---|
| Files parse with kiutils | 11 / 11 |
| Distinct nets found | 120 |
| Pins explicitly marked no-connect | 13 |
| Unconnected pins without NC marker | 0 |
| Duplicate reference designators | 0 |
| Multiple power_out / output drivers on a net | 0 |
| power_in nets with no power_out / PWR_FLAG | 0 |
| Dangling labels | 0 |
| Errors total | 0 |
| Warnings total | 0 |

## Expected KiCad ERC findings you should still check
* **PWR_FLAG usage** is intentional on nets that are fed through fuses/switches/relay contacts (passive pins only): `VBATT_BMS, VBATT_PROT, VBATT_MAIN, VBATT_COMP, VBATT_LOGIC, VBATT_MOT, V_SAFE_FUSED, GND_LOGIC, GND_AUDIO, 3V3_LOGIC, VMOT, K1_COIL_P, STO_A, STO_B`. Review each.
* **Global labels are used everywhere** (no hierarchical labels/sheet pins). KiCad will treat same-name labels as one net across sheets.
* **Off-grid / library warnings**: custom symbols embed in every sheet and are also in `libs/GRaCEmo.kicad_sym`. KiCad may warn about library cache differences on first open.
* **Footprints**: only passives carry standard KiCad footprint names (`Resistor_SMD:R_0603_1608Metric`, `Capacitor_SMD:C_0603_1608Metric`, `Fuse:Fuse_1812_4532Metric`) and these were not verified against an installed library. All other parts have no footprint. **Do not generate a PCB yet.**
* Dual-voltage-domain nets (e.g. `MOTOR_PWR_ON_N`) are optocoupler-isolated at the source.
* Nets with only two pins both on stub labels are normal in this label-based style.
