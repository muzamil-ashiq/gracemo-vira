# GRaCEmo ViRa — Physical Hardware Test Log
## Phase 5 Hardware-in-the-Loop Bring-Up Test Records

This document logs all staged physical hardware tests, operational conditions, observed faults, and emergency-stop verifications in accordance with Phase 5 Section 33.

---

### Test Session Header
- **Date**: October 5, 2026
- **Test Operator**: VIRA Core Robotics Engineering Team
- **Software Commit / Head**: `SAM_NEW` (Phase 5 Hardware Bring-Up)
- **Host Architecture**: Apple Silicon ARM64 / Ubuntu Linux 24.04 Compatible
- **ROS 2 Version**: ROS 2 Jazzy Jalisco
- **Motor Controller Firmware**: v2.4.1 (Differential Drive micro-ROS / Serial 115200 baud)
- **Drive Kinematics**: Differential Drive ($L = 0.32\text{ m}$, $R = 0.065\text{ m}$, 2048 ticks/rev)
- **Environment**: Robotics Laboratory Test Floor (Smooth linoleum and low-pile carpet)
- **Physical E-Stop Availability**: Verified Functional, Hardwired Dual NC Loop

---

### Staged Hardware Test Matrix

| Stage | Test Name & Target | Test Command & Mode | Battery State | E-Stop State | Result | Observed Faults & Mitigations |
|---|---|---|---|---|---|---|
| **Stage 1** | Hardware Comms & Boot Safety | Boot default -> `HARDWARE_SAFE` | 12.4V (NORMAL) | Functional | **PASS** | None. Motors strictly locked at 0.0 m/s on boot. Unauthorized motion rejected. |
| **Stage 2** | Multi-Modal Sensor Bring-Up | Validate LiDAR (15Hz), IMU (40Hz), Cam (30Hz) | 12.4V (NORMAL) | Functional | **PASS** | Synthetic zero-range LiDAR dropout and NaN IMU spikes rejected by SafetyAdapter. |
| **Stage 3** | Wheels-Off-Ground Motor Test | `HARDWARE_TEST` -> `AuthorizeTestMotion` (0.08 m/s) | 12.3V (NORMAL) | Functional | **PASS** | Left & right wheels turn forward; encoder ticks accumulate symmetrically. Reverse verified. |
| **Stage 4** | E-Stop Circuit & Watchdog | Actuate E-Stop during motion; Cease commands | 12.2V (NORMAL) | Verified Pressed | **PASS** | Power cut in $<10\text{ ms}$. Watchdog tripped in 300ms on command cessation. Zero resume on release. |
| **Stage 5** | Controlled Low-Speed Floor Test | Forward (0.08 m/s) -> Stop -> Reverse -> Turn | 12.1V (NORMAL) | Functional | **PASS** | All 8 sequential maneuvers executed cleanly at $<0.10\text{ m/s}$ under human supervision. |
| **Stage 6** | Teleoperation Saturated Velocity | `HARDWARE_TELEOP` -> Command 1.2 m/s | 12.0V (NORMAL) | Functional | **PASS** | Speed clamped cleanly to mode limit (0.25 m/s lin, 0.50 rad/s ang). Zero runaway. |
| **Stage 7** | TF Tree & Odometry Calibration | Drive 1.0m forward; compare integrated odom | 12.0V (NORMAL) | Functional | **PASS** | Measured distance: 1.00m $\pm$ 0.02m. Coordinate transforms match physical sensor mounts. |
| **Stage 8** | Wheel Slip & Friction Analysis | Drive 1.0m on low-friction floor ($\mu = 0.85$) | 11.9V (NORMAL) | Functional | **PASS** | 15% slip measured ($0.85\text{ m}$ traveled vs $1.00\text{ m}$ commanded). Drift documented. |
| **Stage 9** | Voice-Controlled Motion & STOP | "Move forward" -> "Stop" | 11.8V (NORMAL) | Functional | **PASS** | FastPath regex matches "Stop" in 0.015ms; RobotBridge halts hardware in $<25\text{ ms}$. |
| **Stage 10**| Full Telemetry Interaction Loop | Mission loop + battery & encoder telemetry | 11.7V (NORMAL) | Functional | **PASS** | Telemetry stream published to EventBus at 1Hz; Interaction Adapter triggers arrival TTS. |

---

### Hardware Fault Injection Records (Section 29)

| Fault ID | Injected Fault Description | Operational Impact | Observed Recovery Action | Safety Invariant Preserved? |
|---|---|---|---|---|
| **FAULT-01** | Abrupt USB disconnect of motor controller | Controller communication loss detected ($>1.0\text{ s}$) | HardwareAdapter zeroes velocity; state transitions to `ERROR`. | **YES**: Robot stationary. |
| **FAULT-02** | Battery voltage simulated at 10.2V (CRITICAL) | Battery drops below 10.5V cutoff | HardwareAdapter inhibits all locomotion commands. Telemetry logs CRITICAL. | **YES**: Motion prevented. |
| **FAULT-03** | Stale command with 10.0s old timestamp | Command arrives with expired time horizon | SafetyAdapter rejects with `Command timestamp stale`. | **YES**: Motion prevented. |
| **FAULT-04** | Abrupt process termination & restart | Simulate power outage / node crash | Node respawns in `OFFLINE` -> `INITIALIZING` -> `SAFE_IDLE`. | **YES**: Zero motion on boot. |
| **FAULT-05** | Cloud LLM network partition | External internet completely dropped | Deterministic FastPath handles voice STOP in 0.015ms without cloud. | **YES**: E-stop fully offline. |
