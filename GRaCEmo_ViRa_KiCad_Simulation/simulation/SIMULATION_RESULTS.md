# Simulation results and validation status

## Execution status
No KiCad executable, `kicad-cli`, `eeschema`, or `ngspice` was available in the build environment. Consequently, no simulation was executed and no waveforms/results are claimed as measured. The six `.cir` decks are provided as ngspice-oriented source, but syntax and convergence still require execution in ngspice. They are **not certified as runnable** until tested.

## Expected qualitative behavior (not measured results)
1. Battery: nominal source is 24 V; diode drops a small amount; output switch turns on after 5 ms. The generic TVS clamp only approximates avalanche behavior.
2. Buck equivalent: averaged output tends toward duty × input (about 5 V at 24 V × 0.2083), with transient response affected by L/C/load; this is not a switching regulator design.
3. E-stop: enable should be high only when logic power is valid and the modeled E-stop input is in its normal state; it should go low during the E-stop interval and power-loss interval.
4. CAN equivalent: modeled dominant state creates a differential bus level; overlap is a simplified analog conflict and is not proof of protocol arbitration.
5. Sensor: RC filter attenuates high-frequency content; ideal gain block doubles the filtered input before ADC series RC.
6. Monitor: with 24 V and nominal 2 A assumption, shunt drop is approximately 0.1 V; ideal gain-of-20 sense output approximately 2 V; divider output about 2.17 V. These are analytical estimates, not simulation output.

## Required next validation
Run every deck in ngspice, correct any parser/model/convergence errors, inspect plots, then create matching native KiCad schematic symbols with `Sim.*` fields and test KiCad's integrated simulator. This project does not yet meet the user's full definition of done for opening each circuit in KiCad Simulator directly.
