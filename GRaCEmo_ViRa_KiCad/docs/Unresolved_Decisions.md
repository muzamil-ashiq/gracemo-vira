# Unresolved engineering decisions / specifications needed

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
