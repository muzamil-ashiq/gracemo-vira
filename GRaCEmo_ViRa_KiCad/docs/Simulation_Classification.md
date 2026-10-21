# Simulation classification

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
