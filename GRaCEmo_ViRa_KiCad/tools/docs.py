import json, csv, os, subprocess, collections
OUT = "/home/claude/out/GRaCEmo_ViRa_KiCad"
M = json.load(open("/home/claude/out/model.json"))
PRE = json.load(open("/home/claude/out/precheck.json"))
D = OUT + "/docs"

parts = [p for p in M["parts"] if p["in_bom"]]
# ---------------------------------------------------------------- BOM
cols = ["Reference", "Sheet", "Symbol", "Value", "Manufacturer", "MPN", "Function", "Voltage", "Current", "Connector", "Datasheet", "Footprint", "Selection_status", "Sim_class", "Notes"]
with open(D + "/BOM.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for p in sorted(parts, key=lambda p: (p["sheet"], p["ref"].rstrip("0123456789"), int("".join(c for c in p["ref"] if c.isdigit())))):
        m = p["meta"]
        w.writerow([p["ref"], p["sheet"], p["sym"], p["value"], m.get("manufacturer", ""), m.get("mpn", ""), m.get("function", ""),
                    m.get("voltage", ""), m.get("current", ""), "yes" if p["ref"].startswith("J") else "", p["ds"], p["fp"],
                    m.get("status", ""), m.get("sim_class", ""), m.get("notes", "")])
print("BOM rows", len(parts))

# ---------------------------------------------------------------- pinouts
skip = {"R", "C", "CP", "FUSE", "TESTPOINT", "PWR_FLAG", "DIODE", "JUMPER", "NETTIE", "TVS", "SW_SPST", "PUSHBUTTON_NO"}
status = {
    "NUCLEO_F746ZG_IF": "LOGICAL index - NOT a Morpho/Arduino pin; map from UM1974/CubeMX",
    "JETSON_CARRIER_IF": "LOGICAL index - carrier not selected; no Jetson pin numbers claimed",
    "CAN_XCVR_SN65HVD230": "From memory of TI datasheet - UNVERIFIED (datasheet not fetched)",
    "OPTO_PC817": "From memory of standard PC817 pinout - UNVERIFIED",
}
with open(D + "/Interface_and_Connector_Pinouts.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Sheet", "Reference", "Symbol", "Pin_number", "Pin_name", "Net", "Electrical_type", "Verification"])
    for sh, ref, pn, num, net, et, sym in M["conns"]:
        if sym in skip or ref.startswith("#"):
            continue
        w.writerow([sh, ref, sym, num, pn, net, et, status.get(sym, "UNVERIFIED - provisional pin (part/vendor pinout pending)")])

# ---------------------------------------------------------------- net list summary
nets = collections.defaultdict(set)
for sh, ref, pn, num, net, et, sym in M["conns"]:
    if net != "NC":
        nets[net].add(sh)
with open(D + "/Net_List_Summary.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["Net", "Sheets"])
    for n in sorted(nets):
        w.writerow([n, "; ".join(sorted(nets[n]))])

# ---------------------------------------------------------------- precheck/ERC report
open(D + "/ERC_Report.md", "w").write(f"""# ERC / validation report

**KiCad ERC was NOT run.** KiCad is not installed in the generation environment, and the environment could not download it.
No sheet has been opened in KiCad. Do not treat this project as KiCad-validated.

## What was actually run
`check.py` (included in `tools/`) parsed all {PRE['files']} `.kicad_sch` files with the independent `kiutils` parser and rebuilt connectivity from geometry
(wire end points, global labels, pin end points, no-connect markers). This is **not** a substitute for KiCad ERC.

| Check | Result |
|---|---|
| Files parse with kiutils | {PRE['files']} / {PRE['files']} |
| Distinct nets found | {PRE['nets']} |
| Pins explicitly marked no-connect | {PRE['nc']} |
| Unconnected pins without NC marker | {len([e for e in PRE['errors'] if 'unconnected' in e])} |
| Duplicate reference designators | {len([e for e in PRE['errors'] if 'duplicate' in e])} |
| Multiple power_out / output drivers on a net | {len([e for e in PRE['errors'] if 'multiple' in e])} |
| power_in nets with no power_out / PWR_FLAG | {len([e for e in PRE['errors'] if 'power_in' in e])} |
| Dangling labels | {len([e for e in PRE['errors'] if 'dangling' in e])} |
| Errors total | {len(PRE['errors'])} |
| Warnings total | {len(PRE['warnings'])} |

## Expected KiCad ERC findings you should still check
* **PWR_FLAG usage** is intentional on nets that are fed through fuses/switches/relay contacts (passive pins only): `VBATT_BMS, VBATT_PROT, VBATT_MAIN, VBATT_COMP, VBATT_LOGIC, VBATT_MOT, V_SAFE_FUSED, GND_LOGIC, GND_AUDIO, 3V3_LOGIC, VMOT, K1_COIL_P, STO_A, STO_B`. Review each.
* **Global labels are used everywhere** (no hierarchical labels/sheet pins). KiCad will treat same-name labels as one net across sheets.
* **Off-grid / library warnings**: custom symbols embed in every sheet and are also in `libs/GRaCEmo.kicad_sym`. KiCad may warn about library cache differences on first open.
* **Footprints**: only passives carry standard KiCad footprint names (`Resistor_SMD:R_0603_1608Metric`, `Capacitor_SMD:C_0603_1608Metric`, `Fuse:Fuse_1812_4532Metric`) and these were not verified against an installed library. All other parts have no footprint. **Do not generate a PCB yet.**
* Dual-voltage-domain nets (e.g. `MOTOR_PWR_ON_N`) are optocoupler-isolated at the source.
* Nets with only two pins both on stub labels are normal in this label-based style.
""")

# ---------------------------------------------------------------- simulation
open(D + "/Simulation_Classification.md", "w").write("""# Simulation classification

KiCad cannot execute Jetson Linux, NVIDIA inference, OAK-D Pro image processing, real LiDAR scans or STM32 firmware here. No separate simulator is claimed.

| Component / group | Class |
|---|---|
| R, C, CP (generic passives) | Native KiCad symbol class; ideal ngspice models usable once `Sim.*` fields are added (not added in this draft) |
| Fuses, switches, relays, contactors, safety relay, E-stop | Custom symbol required / hardware represented by interface only; ngspice only with behavioural models you add |
| Diodes / TVS | Symbol available, no model assigned (needs vendor SPICE model) |
| BMS, battery pack | Custom symbol; electrochemical behaviour needs external model |
| DC-DC converters (5 provisional blocks) | Custom symbol; ngspice only after a real converter is chosen and a vendor model exists |
| PC817 optocouplers | Custom symbol; generic opto ngspice models exist but none assigned |
| NPN driver | Custom symbol; ngspice model requires chosen part |
| SN65HVD230 CAN transceiver | Custom symbol, vendor SPICE model not applied; requires real-hardware validation of bus |
| INA228-class monitor | Symbol only; requires real-hardware validation |
| NUCLEO-F746ZG | Hardware represented by interface only; firmware requires separate emulator or HIL |
| Jetson carrier (Cfg A/B) | Hardware represented by interface only; needs real hardware |
| OAK-D Pro, LiDAR, IMU, mic array, DAC, amp, speaker | Interface only / requires real-hardware validation |
| Wheel/arm drives and encoders | Connector/interface only |

Suitable ngspice candidates once parts are chosen: reverse-polarity block, precharge, input surge/TVS clamp, DC-DC input filter, opto input/pull-up levels, K1/K2 coil flyback, CAN termination network.
""")

# ---------------------------------------------------------------- power budget
open(D + "/Power_Budget.md", "w").write("""# Power budget (assumptions first)

Status: **incomplete by design.** Only figures with a stated source are used; everything else is `TBD`. Do not size fuses/converters from this draft.

## Assumptions
* Battery nominal 24V class. 6S Li-ion = 25.2V full; 7S = 29.4V full. Cutoff assumed 3.0V/cell (6S 18V, 7S 21V) - **verify with BMS/cell datasheet**.
* Converter efficiency assumed **90%** (assumption, not a part value).
* Jetson module power uses NVIDIA module power modes: AGX Orin 64GB 15-60W; Orin NX 16GB 10-25W (**module only**, carrier/fan/peripherals excluded; verify on current NVIDIA docs).

## Compute rail (module only)
| Config | P_module | I @ 24V nominal, 90% eff. | I @ 18V worst case |
|---|---|---|---|
| A: AGX Orin 64GB | 15-60 W | 0.69-2.78 A | 0.93-3.70 A |
| B: Orin NX 16GB | 10-25 W | 0.46-1.16 A | 0.62-1.54 A |

Formula: `I = P / (V_batt * 0.90)`.

## Other loads
| Load | Power | Source |
|---|---|---|
| NUCLEO-F746ZG | TBD | measure |
| OAK-D Pro | TBD | Luxonis datasheet (not fetched) |
| LiDAR | TBD | model pending |
| IMU, proximity, bumpers | TBD | parts pending |
| Audio amp + DAC + mic | TBD | parts pending |
| Wheel drives (4x), upper body | TBD | motor/drive selection |
| Fan | TBD | thermal design |
| Safety coils (K1, K2, relay) | TBD | parts pending |

## Fixed calculations performed in the schematic
| Item | Calculation | Result |
|---|---|---|
| K1 feedback opto LED resistor 4.7k at 29.4V | (29.4 - 1.2) / 4.7k | 6.0 mA; dissipation (28.2^2)/4.7k = 0.17 W, use >= 0.25 W (preferably 0.5 W) |
| Same at 21V | (21 - 1.2) / 4.7k | 4.2 mA |
| Enable opto LED 1k from 3.3V | (3.3 - 1.2) / 1k | 2.1 mA (check CTR vs drive input) |
| CAN bus termination | two 120 ohm ends | 60 ohm differential |

## Fuse/wire sizing method (to run when currents known)
1. Continuous current per branch I_c; peak I_p and duration from motor/drive datasheets.
2. Fuse: rated >= 1.25 * I_c, rated voltage >= max pack voltage (29.4V for 7S), breaking capacity >= BMS/pack prospective short-circuit current, time-current curve tolerates I_p.
3. Wire: ampacity (insulation temperature, bundling, ambient) > fuse rating; voltage drop = I * R_wire(L) <= 2% of VBATT_MIN for motor feeds.
4. Connector: contact rating > fuse rating with derating.
""")

# ---------------------------------------------------------------- wiring
open(D + "/Wiring_and_Grounding.md", "w").write("""# Wiring and grounding specification (draft)

## Grounds
| Net | Contains | Notes |
|---|---|---|
| GND_PWR | battery negative, DC-DC GND pins, drives, K1/K2 coil returns, safety relay A2 | Power star point |
| GND_LOGIC | Jetson, NUCLEO, sensors, encoders, CAN transceivers, optocoupler secondary | Returns to star point via NT1 (sheet 02) |
| GND_AUDIO | amp, DAC analog ground | Returns to GND_LOGIC via net tie (sheet 07) |
| CHASSIS | not defined | **TBD**: single bond point and any RC/Y-cap; not designed here |

Non-isolated converters tie input and output negatives physically at the converter; the net tie documents the intended single-point star, which must be matched in layout/harness.

## Power rails
VBATT_RAW/BMS -> main fuse -> disconnect -> reverse-polarity block -> shunt -> VBATT_MAIN -> branch fuses (compute, logic, motor, safety) -> converters / K1 (VMOT).
Motor current path never passes through GND_LOGIC. Encoders and sensors return on GND_LOGIC only.

## Emergency-stop behaviour
* Dual channel E-stop (and optional external loop) -> safety relay.
* Safety relay opens K1 (VMOT off) and removes STO_A/STO_B.
* K2 (software stop) has two NC contacts in series with each channel: software can only add a stop.
* DRV_EN is an optocoupled enable for non-safety operation. It cannot override STO or K1.
* **Not certified.** Needs PL/SIL determination, certified relay/contactor, EDM/feedback loop and proof tests.

## Harness rules
Twisted pairs for CAN (120 ohm); separate motor power looms from signal; shield CAN bus at one end; keep USB cable length within spec; strain relief on all connectors; label every wire to the net names in `Interface_and_Connector_Pinouts.csv`.
""")

# ---------------------------------------------------------------- unresolved
open(D + "/Unresolved_Decisions.md", "w").write("""# Unresolved engineering decisions / specifications needed

1. Battery: chemistry, cell count (6S/7S?), capacity, peak current, cutoff voltages. BMS part and communication interface.
2. Jetson carrier board model for Config A and Config B; real connector pinouts; input voltage range; USB VBUS budgets; 3.3V logic confirmation; CAN pins.
3. Riva/speech decision does not affect this schematic but affects carrier/module (see earlier proposal).
4. STM32: real pin assignment on NUCLEO-F746ZG (CN7/CN8/CN9/CN10, Arduino) from UM1974/CubeMX; power-source jumpers; ST-LINK/SWD usage; encoder timer pin choices and 5V tolerance. Note `STM32F746Z6T6` is not a part number confirmed here: this design uses the NUCLEO-F746ZG (STM32F746ZG).
5. Motor drives/motors: models, whether four independently driven wheels, CAN protocol, STO/enable terminals and levels, peak currents.
6. Actuators for arms/hands/head: count, voltage, protocol.
7. LiDAR model: supply voltage, Ethernet speed/pairs, sync.
8. OAK-D Pro variant (USB vs PoE), current draw, cable.
9. IMU, proximity sensors, bumper switches, microphone array, USB DAC/amp, speaker.
10. Safety: certified safety relay/controller, E-stop device, K1 contactor rating, EDM wiring, required performance level.
11. Reverse-polarity topology, TVS rating, shunt value, fuse ratings, DC-DC part numbers and ratings, precharge circuit.
12. CAN: bus topology/ends for termination; whether CAN-FD is required (needs different MCU or external controller).
13. Chassis bonding / EMC strategy.
14. Footprints for all non-passive parts; verify standard-library footprints exist in the target KiCad version before PCB work.
15. Datasheet verification: every pin map marked UNVERIFIED must be checked against the manufacturer document.
""")

# ---------------------------------------------------------------- readme
open(OUT + "/README.md", "w").write(f"""# GRaCEmo ViRa - KiCad hardware overview (DRAFT 0.1)

## Read this first
* **Not validated in KiCad.** KiCad was not available where this was generated. Files were generated programmatically, parsed with an independent parser (kiutils) and checked by a custom script. KiCad ERC has not been run.
* **File format.** The request named `GRaCEmo_ViRa_Hardware_Overview.sch`. That is KiCad's legacy (v5) format. Modern KiCad (6+) uses `.kicad_sch`, so the native root schematic is `GRaCEmo_ViRa_Hardware_Overview.kicad_sch`. No legacy file was produced, because a fake or mis-converted `.sch` would be invalid. If you need legacy, open in KiCad 5.1 is not possible; use the modern file.
* **Format target.** KiCad 7 file format (`version 20230121`); KiCad 7, 8 and 9 should open it (newer versions upgrade the format on save). Not tested.
* **Pin data.** Most pin-level data is provisional or from memory. See `docs/Interface_and_Connector_Pinouts.csv` (Verification column) and `docs/Unresolved_Decisions.md`.

## Contents
| Path | Purpose |
|---|---|
| `GRaCEmo_ViRa_Hardware_Overview.kicad_pro` | project |
| `GRaCEmo_ViRa_Hardware_Overview.kicad_sch` | root sheet 00_System_Overview with 10 sheet symbols |
| `01_...10_*.kicad_sch` | hierarchical sheets |
| `libs/GRaCEmo.kicad_sym`, `sym-lib-table` | custom symbols ({len(__import__('json').load(open('/home/claude/out/model.json'))['parts'])} parts total placed) |
| `docs/` | BOM, pinouts, net list, power budget, wiring/grounding, simulation classes, ERC report, unresolved decisions |
| `tools/` | generator and checker scripts |

## Opening
1. Open `GRaCEmo_ViRa_Hardware_Overview.kicad_pro` in KiCad 7 or newer.
2. If prompted for the symbol library, project table `sym-lib-table` points to `${{KIPRJMOD}}/libs/GRaCEmo.kicad_sym`. Symbols are also embedded in every sheet.
3. Navigate from the root sheet into each sheet.

## Validation you must do
1. Inspect > Electrical Rules Checker, run, and review against `docs/ERC_Report.md` expectations.
2. Check every sheet loads; open Symbol Editor to confirm library resolves.
3. Replace provisional symbols with real library parts as selections are made; verify pin numbers against datasheets.
4. Do not annotate-reset: references are already unique (`Tools > Annotate` with 'reset' will renumber).
5. Add footprints and `Sim.*` fields before PCB/simulation work.

## Style
Connectivity uses global labels at pin stubs rather than long drawn wires, so symbols are arranged for readability, not as a classic drawn schematic. Rewire as desired while keeping net names.
""")
print("docs done")
