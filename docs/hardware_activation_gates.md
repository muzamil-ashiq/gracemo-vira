# GRaCEmo ViRa — Hardware Activation Gates & Laboratory Safety Protocol

**Document ID:** `VIRA-GATE-HW-001`  
**Classification:** Mandatory Operational Safety Standard  
**Date:** 2026-10-28  

---

## 1. Cardinal Safety Statement

> [!CAUTION]
> **PASSING AUTOMATED SOFTWARE TESTS AND MOCK SIMULATIONS DOES NOT AUTHORIZE HARDWARE ACTIVATION.**
> 
> Motor power activation (`MOTOR_OUTPUT_ENABLED = 1`) and live serial transport (`SerialMCUTransport.PROTOCOL_CONFIRMED = True`) are strictly prohibited until all 8 sequential gates in this document have been physically verified, measured, and signed off in the laboratory.

---

## 2. Sequential Hardware Activation Gates

```
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   GATE 0    │ ──> │   GATE 1    │ ──> │   GATE 2    │ ──> │   GATE 3    │
  │ Pre-Power   │     │ Logic Power │     │ UART Link   │     │ Hardwired   │
  │ Inspection  │     │ & Firmware  │     │ Loopback    │     │ E-Stop Test │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                     │
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐            ▼
  │   GATE 7    │ <── │   GATE 6    │ <── │   GATE 5    │ <── ┌─────────────┐
  │ Supervised  │     │ Low-Speed   │     │ Odometry &  │     │   GATE 4    │
  │ Autonomous  │     │ Teleop      │     │ Roll-Out    │     │ Wheels-Off- │
  │ Navigation  │     │ Tether      │     │ Measurement │     │ Ground Spin │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

### Gate 0: Pre-Power Mechanical & Electrical Inspection
- **Objective:** Prevent dead shorts, reverse polarity, and mechanical binding before applying any power.
- **Prerequisites:**
  1. Measure DC resistance across main 12V/24V battery terminal connectors ($R > 100\ \Omega$ with main switch open).
  2. Inspect wiring harness for chafing against aluminium chassis frame.
  3. Verify fuse ratings match electrical design (Main fuse: 30A, Motor fuses: 15A per channel).
  4. Measure physical wheel track width with vernier caliper to resolve $0.34\text{ m}$ vs $0.32\text{ m}$.
- **Sign-off Condition:** Zero short-circuits; track width documented in [`hardware_params.yaml`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/config/hardware_params.yaml).

---

### Gate 1: Logic Power & STM32 Firmware Flashing
- **Objective:** Verify low-voltage rails and load confirmed safety firmware.
- **Prerequisites:**
  1. Power Jetson Orin Nano (19V DC supply) and STM32 (via ST-LINK USB). Main motor power remains OFF.
  2. Measure 3.3V logic rail ($3.30\text{ V} \pm 0.05\text{ V}$) and 5V peripheral rail ($5.00\text{ V} \pm 0.10\text{ V}$).
  3. Flash firmware with Arduino CLI / OpenOCD using board `STMicroelectronics:stm32:Nucleo_144:pnum=NUCLEO_F746ZG`.
  4. Confirm boot message over ST-LINK VCP: `READY,MOTOR_OUTPUT_DISABLED`.
- **Sign-off Condition:** Firmware version `0.1.0-proposed` verified with motor outputs locked.

---

### Gate 2: UART Communications Loopback & Protocol Handshake
- **Objective:** Verify bi-directional framing, XOR checksums, and sequence handling across physical cable.
- **Prerequisites:**
  1. Connect Jetson USB to STM32 ST-LINK VCP (`/dev/gracemo_mcu`).
  2. Run host-side protocol test script sending `CMD,1,HEARTBEAT*68\n` at 20 Hz.
  3. Verify STM32 responds with `ACK,1,HEARTBEAT` and broadcasts `TELEM` frames at 20 Hz.
  4. Inject corrupted checksum `CMD,2,HEARTBEAT*FF\n` and confirm STM32 drops frame without crashing.
  5. Pause Jetson transmission for $>500\text{ ms}$ and confirm STM32 raises `FAULT_HEARTBEAT_TIMEOUT` (code `1`).
- **Sign-off Condition:** Zero frame drop across 10,000 consecutive packets; watchdog triggers deterministically.

---

### Gate 3: Hardwired Emergency-Stop & Contactor Trip Verification
- **Objective:** Prove independent hardware safety circuit cuts motor power without software intervention.
- **Prerequisites:**
  1. Energize main contactor coil via latching circuit.
  2. Monitor main motor power rail with calibrated oscilloscope / digital multimeter.
  3. Depress physical red mushroom E-stop button.
  4. Measure de-energization time from button hit to motor voltage $< 0.5\text{ V}$ ($T_{trip} < 20\text{ ms}$).
  5. Verify auxiliary contact feedback pin (`PE0`) transitions to HIGH, reflecting `physical_estop_pressed = 1` in serial telemetry.
  6. Release button: verify contactor remains open until explicit manual reset push-button is pressed.
- **Sign-off Condition:** Hardwired isolation proven; zero software dependence.

---

### Gate 4: Wheels-Off-Ground Motor Spin & Direction Verification
- **Objective:** Validate motor driver pin mapping, rotation polarity, and velocity clamping without ground contact.
- **Prerequisites:**
  1. Elevate robot chassis on solid laboratory workbench stands so all 4 wheels rotate freely in the air.
  2. Set `MOTOR_OUTPUT_ENABLED = 1` in [`firmware/config.h`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/config.h) and reflash.
  3. Set `SerialMCUTransport.PROTOCOL_CONFIRMED = True`.
  4. Send forward command: `CMD,10,DRIVE,0.100,0.000`.
  5. Inspect wheel rotation: both wheels MUST rotate in forward driving direction.
  6. Send over-speed command: `CMD,11,DRIVE,1.500,0.000` and confirm firmware clamps velocity to $\le 0.35\text{ m/s}$.
  7. Hit E-stop while wheels are spinning: verify immediate motor power cut within $<20\text{ ms}$.
- **Sign-off Condition:** Polarity confirmed; overspeed clamped; E-stop halts rotation instantly.

---

### Gate 5: Odometry Calibration & Physical Roll-Out Test
- **Objective:** Reconcile encoder CPR, wheel radius, and wheel track scaling against physical distance.
- **Prerequisites:**
  1. Place robot on flat floor with laser distance meter aligned along a 5.000 meter marked track.
  2. Command forward travel at $0.20\text{ m/s}$ for exactly 5.000 meters.
  3. Measure actual physical travel with laser meter vs `/odom` pose $x$.
  4. Calculate wheel roll-out factor: $k_{wheel} = D_{measured} / D_{odom}$.
  5. Command pure in-place rotation for 10 full revolutions ($20\pi\text{ rad}$).
  6. Measure orientation error vs gyro/survey compass to calibrate effective wheel track ($W_{eff}$).
- **Sign-off Condition:** Odometry error $\le 1.0\%$ linear, $\le 2.0\%$ rotational.

---

### Gate 6: Low-Speed Teleoperation with Physical Tether
- **Objective:** Validate manual control and collision avoidance in controlled environment.
- **Prerequisites:**
  1. Operator holds dedicated wireless deadman switch / physical tether cable.
  2. Test joystick teleoperation up to $0.35\text{ m/s}$.
  3. Walk in front of robot: confirm LiDAR/bumper collision layer halts robot at $\ge 0.25\text{ m}$ clearance.
- **Sign-off Condition:** Zero contact with test obstacles; deadman release stops robot immediately.

---

### Gate 7: Supervised Autonomous Navigation
- **Objective:** Authorize production Nav2 missions in mapped facility.
- **Prerequisites:**  
  1. Complete 2D SLAM mapping of target area.
  2. Verify costmap footprint and inflation layers.
  3. Execute 50 consecutive waypoint missions under human supervisor observation.
- **Sign-off Condition:** Mission reliability $\ge 98\%$; zero safety violations.
