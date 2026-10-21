# Wiring and grounding specification (draft)

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
