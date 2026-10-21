# GRaCEmo ViRa — simulation guide (engineering draft)

## Important status
The existing multi-sheet KiCad design is preserved. Six ngspice-oriented circuit decks are added under `simulation/`. The environment used to build this package did not contain KiCad or ngspice, so the project has **not** been opened in KiCad, native simulator models have not been verified, and no waveform execution is claimed. These decks are standalone SPICE inputs, not native KiCad saved simulator configurations.

## Open the KiCad project
Open `GRaCEmo_ViRa_Hardware_Overview.kicad_pro` using KiCad 7+ (format target is KiCad 7). Custom symbols are in `libs/GRaCEmo.kicad_sym`; project table is `sym-lib-table`. Original system sheets remain interface/design documentation, not fully simulated circuits.

## Run the six decks with ngspice
Install ngspice on your machine, open a terminal in the `simulation` folder, then run `ngspice 01_battery_protection.cir` (replace filename for each circuit). In interactive mode use `plot v(out)` or `plot v(vout_c)` etc. Some ngspice builds run `.control` blocks in batch mode and print the listed values. If a deck errors, do not assume the result is valid; use the error text to correct syntax and re-run.

## Test cases and probes
| Deck | Main variables / nodes | Changeable condition |
|---|---|---|
| Battery | `v(src)`, `v(prot)`, `v(out)`, `i(Vbat)` | `.param VBAT=24`; switch delay at 5 ms |
| DC-DC equivalent | `v(vin)`, `v(vout_c)`, `i(Vinput)` | `.param VIN=24`, `DUTY=0.2083`; input step and load switch at 10 ms |
| E-stop | `v(vlogic)`, `v(estop)`, `v(enable)` | Change PWL E-stop and logic supply intervals |
| CAN equivalent | `v(tx1)`, `v(tx2)`, `v(canh)`, `v(canl)`, `v(canh,canl)` | TX pulse timing |
| Sensor | `v(sensor)`, `v(filt)`, `v(adc_pin)` | `.param SENSOR=1.2`, sine amplitude/frequency |
| Monitor | `v(supply)`, `v(load_in)`, `v(vmon)`, `v(imon)`, `i(Vsup)` | `.param VSUP=24`, `ILOAD=2` |

## Component simulation classification
- Battery, fuse, reverse-protection diode, TVS, switch, passives: generic/idealized models in standalone deck; not exact production component models.
- DC-DC: averaged educational equivalent, not a vendor regulator IC model.
- E-stop: behavioral logic equivalent, not certified safety hardware.
- CAN: behavioral electrical-layer equivalent, not a transistor-level vendor transceiver and not protocol simulation.
- Sensor conditioner and monitor amplifier: ideal controlled-source equivalents.
- Jetson AGX Orin / Orin NX, NUCLEO-F746ZG, OAK-D Pro, LiDAR, IMU, encoders, motors/drives, microphone array and audio amplifier: interface-only in the main project unless a specific validated vendor model is added. Firmware/AI/ROS 2 is not simulated in KiCad.

## Provisional selections
Jetson carrier and motor controller remain pending. 24 V nominal is an initial configurable assumption, not final battery/cell/chemistry approval.
