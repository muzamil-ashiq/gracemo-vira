# GRaCEmo ViRa - KiCad hardware overview (DRAFT 0.1)

## Read this first
* **Not validated in KiCad.** KiCad was not available where this was generated. Files were generated programmatically, parsed with an independent parser (kiutils) and checked by a custom script. KiCad ERC has not been run.
* **File format.** The request named `GRaCEmo_ViRa_Hardware_Overview.sch`. That is KiCad's legacy (v5) format. Modern KiCad (6+) uses `.kicad_sch`, so the native root schematic is `GRaCEmo_ViRa_Hardware_Overview.kicad_sch`. No legacy file was produced, because a fake or mis-converted `.sch` would be invalid. Use the modern file.
* **Format target.** KiCad 7 file format (`version 20230121`); KiCad 7, 8 and 9 should open it (newer versions upgrade the format on save). Not tested.
* **Pin data.** Most pin-level data is provisional or from memory. See `docs/Interface_and_Connector_Pinouts.csv` (Verification column) and `docs/Unresolved_Decisions.md`.

## Contents
| Path | Purpose |
|---|---|
| `GRaCEmo_ViRa_Hardware_Overview.kicad_pro` | project |
| `GRaCEmo_ViRa_Hardware_Overview.kicad_sch` | root sheet 00_System_Overview with 10 sheet symbols |
| `01_...10_*.kicad_sch` | hierarchical sheets |
| `libs/GRaCEmo.kicad_sym`, `sym-lib-table` | custom symbols (137 parts total placed) |
| `docs/` | BOM, pinouts, net list, power budget, wiring/grounding, simulation classes, ERC report, unresolved decisions |
| `tools/` | generator and checker scripts |

## Opening
1. Open `GRaCEmo_ViRa_Hardware_Overview.kicad_pro` in KiCad 7 or newer.
2. If prompted for the symbol library, project table `sym-lib-table` points to `${KIPRJMOD}/libs/GRaCEmo.kicad_sym`. Symbols are also embedded in every sheet.
3. Navigate from the root sheet into each sheet.

## Validation you must do
1. Inspect > Electrical Rules Checker, run, and review against `docs/ERC_Report.md` expectations.
2. Check every sheet loads; open Symbol Editor to confirm library resolves.
3. Replace provisional symbols with real library parts as selections are made; verify pin numbers against datasheets.
4. Do not annotate-reset: references are already unique (`Tools > Annotate` with 'reset' will renumber).
5. Add footprints and `Sim.*` fields before PCB/simulation work.

## Style
Connectivity uses global labels at pin stubs rather than long drawn wires, so symbols are arranged for readability, not as a classic drawn schematic. Rewire as desired while keeping net names.
