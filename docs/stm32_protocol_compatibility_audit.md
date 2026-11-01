# STM32 ↔ Jetson Protocol Compatibility Audit

**GRaCEmo ViRa Autonomous Navigation Platform**  
**Document ID:** `VIRA-AUDIT-PROTO-001`  
**Status:** PROPOSED / VERIFIED IN SOFTWARE & TESTS / HARDWARE SILICON TESTING PENDING  
**Date:** 2026-10-28  

---

## 1. Executive Summary

This document performs an exhaustive, field-by-field protocol compatibility audit between:
1. **The Protocol Specification Proposal:** [`docs/stm32_jetson_protocol_proposal.md`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/stm32_jetson_protocol_proposal.md)
2. **The STM32 Embedded Firmware Implementation:** [`firmware/protocol.h`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/protocol.h), [`firmware/telemetry.h`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/telemetry.h), and [`firmware/GRaCEmo_ViRa_STM32.ino`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/GRaCEmo_ViRa_STM32.ino)
3. **The ROS 2 Hardware Bridge Driver:** [`ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_protocol.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_protocol.py) and [`ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py)

---

## 2. Framing, Framing Delimiters, and Checksum Mechanism

| Attribute | Protocol Proposal Specification | STM32 Firmware (`protocol.h`) | Python Bridge (`mcu_protocol.py`) | Compatibility Status |
|---|---|---|---|---|
| **Encoding** | 7-bit ASCII | ASCII `char` stream | ASCII UTF-8 bytes | **MATCH (Compatible)** |
| **Line Delimiter (TX)** | `\r\n` or `\n` | `\r\n` (via `Serial.println`) | `\n` | **MATCH (Compatible)** |
| **Line Delimiter (RX)** | `\n` (`\r` stripped) | Strips `\r`, dispatches on `\n` | Strips `\r\n` (`line.strip()`) | **MATCH (Compatible)** |
| **Field Delimiter** | Comma `,` | Comma `,` via `strtok_r` | Comma `,` via `split(",")` | **MATCH (Compatible)** |
| **Max Frame Length** | 96 bytes | 96 bytes (`buffer_[96]`) | 96 bytes (`MAX_FRAME_LENGTH = 96`) | **MATCH (Compatible)** |
| **Overflow Handling** | Drop buffer, emit `ERR,0,OVERFLOW` | Flags `overflow_`, emits `ERR,0,OVERFLOW` | Drops packet, returns `None` | **MATCH (Compatible)** |
| **Checksum Syntax** | Optional suffix `*<XX>` (2-digit hex) | Checked if `*` present; validated via `strtol(..., 16)` | Checked if `*` present; validates uppercase hex | **MATCH (Compatible)** |
| **Checksum Algorithm** | Bitwise 8-bit XOR over all characters from byte 0 up to `*` delimiter | Bitwise 8-bit XOR up to `*` (`uint8_t calc_chk ^= *p`) | Bitwise 8-bit XOR (`chk ^= ord(c)`) | **MATCH (Compatible)** |

---

## 3. Command Frames Audit (`Jetson` → `STM32`)

### 3.1 Packet Formats

#### Verb: `HEARTBEAT`
- **Proposal:** `CMD,<seq>,HEARTBEAT[*<chk>]\n`
- **Firmware (`protocol.h`):** Parses `CMD`, sequence `0..65535`, verb `HEARTBEAT`. Emits `ACK,<seq>,HEARTBEAT`.
- **Python Bridge (`mcu_protocol.py`):** Encodes `CMD,<seq>,HEARTBEAT[*<chk>]\n`.
- **Status:** **IDENTICAL & COMPATIBLE**.

#### Verb: `DRIVE`
- **Proposal:** `CMD,<seq>,DRIVE,<v_linear>,<v_angular>[*<chk>]\n`
- **Units:** Linear in meters/second ($m/s$), Angular in radians/second ($rad/s$).
- **Precision:** 3 decimal places (`%.3f`).
- **Firmware (`protocol.h`):**
  - Parses token 3 (`linear`) and token 4 (`angular`) using `strtof`.
  - Rejects NaN, $\pm\infty$ (`!isfinite()`).
  - Bounds checked against `HW_MAX_LINEAR_VEL_MPS` ($0.35\text{ m/s}$) and `HW_MAX_ANGULAR_VEL_RPS` ($0.75\text{ rad/s}$).
  - Rejects any extra tokens (`strtok_r != nullptr`).
- **Python Bridge (`mcu_protocol.py`):**
  - Formats: `CMD,{seq},DRIVE,{linear:.3f},{angular:.3f}`.
  - Clamps to safety bounds prior to serialization.
- **Status:** **IDENTICAL & COMPATIBLE**.

#### Verb: `STOP`
- **Proposal:** `CMD,<seq>,STOP[*<chk>]\n`
- **Firmware:** Sets motors to 0, invokes `safety.requestStop()`, responds `ACK,<seq>,STOP`.
- **Python Bridge:** Encodes `CMD,{seq},STOP[*<chk>]`.
- **Status:** **IDENTICAL & COMPATIBLE**.

#### Verb: `CLEAR_FAULT`
- **Proposal:** `CMD,<seq>,CLEAR_FAULT[*<chk>]\n`
- **Firmware:** Checks if motors stopped. If stopped, clears recoverable fault (`ACK,<seq>,CLEAR_FAULT`). If still rolling, rejects with `ERR,<seq>,CANNOT_CLEAR_WHILE_MOVING`.
- **Python Bridge:** Encodes `CMD,{seq},CLEAR_FAULT`.
- **Status:** **IDENTICAL & COMPATIBLE**.

#### Verb: `STATUS`
- **Proposal:** `CMD,<seq>,STATUS[*<chk>]\n`
- **Firmware:** Responds immediately with human-readable status frame `STATUS,fw=...,safety=...,motor_output=...,link=...,fault=...`.
- **Status:** **IDENTICAL & COMPATIBLE**.

---

## 4. Telemetry Frame Audit (`STM32` → `Jetson`)

### 4.1 Field Order and Data Types

Telemetry frame string format:  
`TELEM,<seq>,<vL>,<vR>,<ticksL>,<ticksR>,<odom_x>,<odom_y>,<odom_yaw>,<v_bat>,<estop_bit>,<fault_code>[*<chk>]\n`

| Index | Field Name | Unit | Range / Format | Firmware Representation (`telemetry.h`) | Python Decoder (`mcu_protocol.py`) | Bridge Dataclass (`MCUTelemetry`) | Alignment Status |
|---|---|---|---|---|---|---|---|
| 0 | Frame Header | None | Exact literal `"TELEM"` | Fixed string literal | Verified `parts[0] == "TELEM"` | Header identifier | **MATCH** |
| 1 | `seq` | Count | Integer `0 .. 65535` | `uint16_t` (`%u`) | `int(parts[1])` | `heartbeat_seq: int` | **MATCH** |
| 2 | `vL` | m/s | Float `%.3f` | `float left_wheel_vel_mps` | `float(parts[2])` | `left_wheel_vel_mps: float` | **MATCH** |
| 3 | `vR` | m/s | Float `%.3f` | `float right_wheel_vel_mps` | `float(parts[3])` | `right_wheel_vel_mps: float` | **MATCH** |
| 4 | `ticksL` | Pulses | Integer signed | `int32_t left_encoder_ticks` (`%ld`) | `int(parts[4])` | `left_encoder_ticks: int` | **MATCH** |
| 5 | `ticksR` | Pulses | Integer signed | `int32_t right_encoder_ticks` (`%ld`) | `int(parts[5])` | `right_encoder_ticks: int` | **MATCH** |
| 6 | `odom_x` | Meters | Float `%.3f` | `float odom_x` | `float(parts[6])` | `odom_x: float` | **MATCH** |
| 7 | `odom_y` | Meters | Float `%.3f` | `float odom_y` | `float(parts[7])` | `odom_y: float` | **MATCH** |
| 8 | `odom_yaw` | Radians | Float `%.3f` | `float odom_yaw` | `float(parts[8])` | `odom_yaw: float` | **MATCH** |
| 9 | `v_bat` | Volts | Float `%.2f` | `float battery_voltage_v` | `float(parts[9])` | `battery_voltage_v: float` | **MATCH** |
| 10 | `estop_bit` | Boolean | `0` or `1` | `uint8_t physical_estop_pressed` (`%u`) | `bool(int(parts[10]))` | `physical_estop_pressed: bool` | **MATCH** |
| 11 | `fault_code` | Enum | Integer `0 .. 255` | `uint8_t mcu_fault_code` (`%u`) | `int(parts[11])` | `mcu_fault_code: int` | **MATCH** |

---

## 5. Fault Codes Compatibility Matrix

| Code | Firmware Constant (`safety.h`) | Bridge Fault Code (`MCUFault`) | Description | Recovery Policy |
|---|---|---|---|---|
| `0` | `FAULT_NONE` | `0` | Nominal Operation | None required |
| `1` | `FAULT_HEARTBEAT_TIMEOUT` | `0x01` / `1` | Jetson Heartbeat silent > 500 ms | Resumes upon fresh `HEARTBEAT` or `DRIVE` |
| `2` | `FAULT_ESTOP_TRIPPED` | `0x02` / `2` | Hardware E-stop contactor opened | Manual button reset + `CLEAR_FAULT` |
| `3` | `FAULT_MOTOR_CONTROLLER` | `0x03` / `3` | Motor controller fault / overcurrent | Requires system power-cycle inspection |
| `4` | `FAULT_BAD_COMMAND` | `0x04` / `4` | Parsing error, velocity range violation, or NaN | Discard command, alert Jetson bridge |

---

## 6. Safety Guards & Latches

1. **Firmware Level:**
   - In [`firmware/config.h`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/config.h), `MOTOR_OUTPUT_ENABLED = 0`.
   - Actuation stub in [`firmware/motor_interface.h`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/firmware/motor_interface.h) completely locks out PWM/direction timer outputs and responds with `ACK,<seq>,DRIVE_ACCEPTED_OUTPUT_DISABLED`.
2. **ROS 2 Bridge Level:**
   - In [`ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py), `SerialMCUTransport.PROTOCOL_CONFIRMED = False`.
   - Attempting to connect or send commands over real serial raises `RuntimeError("Protocol not confirmed")`.
   - Automated tests and simulation utilize `MockMCUTransport` with high-fidelity kinematics simulation.

---

## 7. Audit Conclusion & Sign-Off Condition

The protocol definitions in the proposal, the STM32 firmware parser, and the ROS 2 Python bridge are **100% syntactically and semantically aligned**.

Before `PROTOCOL_CONFIRMED` can be transitioned from `False` to `True`:
1. Loopback testing across a physical USB-UART cable between the Jetson and NUCLEO-F746ZG must be performed.
2. Contactor feedback on pin `PE0` and E-stop button continuity must be verified.
3. Track width ($0.34\text{ m}$ vs $0.32\text{ m}$) must be confirmed by physical measurement.
