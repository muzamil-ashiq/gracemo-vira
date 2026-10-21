# Six ngspice simulation decks

These `.cir` files are standalone SPICE decks intended to be run with ngspice and are included beside the KiCad project. They are **not yet native KiCad Simulator saved setups** because KiCad/ngspice is not installed in the build environment, so model assignment and simulator execution could not be verified here. Open the deck in a text editor and run `ngspice filename.cir` on a system with ngspice installed. The `.control` blocks print key nodes; transient decks can be plotted with `plot v(node)` in an interactive ngspice session.

- `01_battery_protection.cir`: source/fixed fuse resistance/diode protection/TVS approximation/switch/filter/load. Fuse is not a fuse-opening model; TVS is a generic avalanche approximation.
- `02_dc_dc_buck_educational.cir`: averaged ideal buck equivalent, not a switching converter or manufacturer IC model. Includes input step and load step.
- `03_estop_motor_enable.cir`: behavioral active-high enable; E-stop state and logic-power loss force output low.
- `04_can_physical_layer_equivalent.cir`: simplified dominant/recessive bus voltage model and termination; not a transceiver model or CAN protocol test.
- `05_sensor_conditioning.cir`: configurable sinusoidal sensor input, RC filter, ideal gain-of-2 conditioner and ADC input equivalent.
- `06_voltage_current_monitoring.cir`: divider and shunt current-sense equivalent.

All parameter values are educational test assumptions only. They do not qualify real components or establish safety, thermal, EMC, transient, or production performance.
