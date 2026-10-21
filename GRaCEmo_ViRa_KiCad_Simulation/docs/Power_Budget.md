# Power budget (assumptions first)

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
