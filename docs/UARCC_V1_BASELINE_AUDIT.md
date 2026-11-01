# GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC) V1.0
## Phase 0: Engineering Baseline and Repository Audit Report

**Audit Date:** 2026-10-31  
**Lead Architect:** Principal Robotics Software Architect & Release Engineer  
**Host Platform:** Ubuntu 24.04 LTS (Noble Numbat) | ROS 2 Jazzy | Gazebo Harmonic 8.15.0  
**Target Application:** GRaCEmo ViRa Unified Autonomous Robotics Control Center (`gracemo_control_center`)

---

## 1. Executive Summary

This engineering audit establishes the baseline status of the GRaCEmo ViRa software ecosystem prior to live simulation integration, regression testing, and release packaging of the **Unified Autonomous Robotics Control Center (UARCC) V1.0**.

The audit confirms:
1. The accepted autonomous robotics baseline tag `v1.0.0-accepted-baseline` is immutably preserved in both the migration repository and the primary VIRA repository.
2. The hardware safety invariants (`SerialMCUTransport.PROTOCOL_CONFIRMED = False` and `MOTOR_OUTPUT_ENABLED = 0`) remain strictly enforced across all firmware, HAL, and control center layers.
3. The 11 PySide6 GUI modules are fully implemented with their underlying ROS 2 background executors and signal-based EventBus.
4. All 30 automated UARCC unit and integration tests are passing (100% pass rate).
5. The 6 canonical apartment destinations in `config/destinations.json` are authoritatively linked and validated.

---

## 2. Repository State and Version Control Audit

### 2.1 Migration Repository (`~/projects/VIRA-agent-bridge-migration`)
- **Active Branch:** `feature/gracemo-unified-control-center`
- **Current HEAD Commit:** `19560b3dc7e0e911451f6a82252ecf693ecaa9dc`
- **Git Tag Target:** `v1.0.0-accepted-baseline`
- **Working Tree Status:** Clean baseline with newly staged UARCC application components:
  - `gracemo_control_center/` (11 view modules, widgets, core managers, config)
  - `scripts/run_control_center.sh`
  - `scripts/stop_control_center.sh`
  - `docs/GRACEMO_UARCC_ARCHITECTURE_REPORT.md`
  - `config/destinations.json` (authoritative symlink to verified dataset)

### 2.2 Main VIRA Repository (`~/projects/VIRA`)
- **Active Branch:** `feature/gracemo-unified-control-center`
- **Current HEAD Commit:** `68b13499ed049df3df38c97d3b8fde14d34c6ea3`
- **Git Tag Target:** `v1.0.0-accepted-baseline`
- **Working Tree Status:** Clean baseline with mirrored prototype control center files in:
  - `prototypes/gracemo_integrated_v1/unified_control_center/`
  - `prototypes/gracemo_integrated_v1/scripts/run_control_center.sh`
  - `prototypes/gracemo_integrated_v1/scripts/stop_control_center.sh`

---

## 3. Existing Implementation Audit

### 3.1 Eleven Module Architecture
| Module ID | Module Name | Primary Implementation File | ROS 2 Interfaces Subscribed / Advertised |
|:---:|---|---|---|
| **A** | Overview | `modules/overview/overview_view.py` | Aggregated telemetry, battery/power, overall health status |
| **B** | Simulation | `modules/simulation/simulation_view.py` | `/clock`, Gazebo lifecycle status, model presence |
| **C** | Sensors | `modules/sensors/sensors_view.py` | `/camera/image_raw`, `/camera/depth_image`, `/scan`, `/imu/data`, `/odom` |
| **D** | Navigation | `modules/navigation/navigation_view.py` | `/coordinator/command`, `/coordinator/feedback`, `/plan`, `/map`, `/cmd_vel` |
| **E** | Localization | `modules/localization/localization_view.py` | `/amcl_pose`, `/particle_cloud`, `/tf`, `/tf_static` |
| **F** | Voice & Interaction | `modules/interaction/interaction_view.py` | `/interaction/spoken_feedback`, `/interaction/user_input`, `/interaction/voice_recognized` |
| **G** | Cognitive | `modules/cognitive/cognitive_view.py` | Agent Bridge task queue, MNSE kernel state, approval gate |
| **H** | Safety | `modules/safety/safety_view.py` | `/terrain/emergency_stop`, `/terrain/safety_stop`, `/terrain/status`, `/cmd_vel_safe` |
| **I** | Diagnostics | `modules/diagnostics/diagnostics_view.py` | ROS 2 node graph, topic frequency monitor, host CPU/RAM/GPU telemetry |
| **J** | Logs | `modules/logs/logs_view.py` | Multi-source filtered log aggregator (ROS, GUI, Coordinator) |
| **K** | Settings | `modules/settings/settings_view.py` | UI preferences, refresh rates, theme tokens, safety banner |

### 3.2 Threading & Background ROS 2 Execution
- `RosManager` runs `rclpy`'s `MultiThreadedExecutor` on a dedicated Python thread (`QThread` decoupling).
- Signals and slots via `core/event_bus.py` prevent cross-thread GUI access and enforce thread safety.
- Frame rate bounding is configured for image streams (30 FPS max) to prevent UI thread starvation.

---

## 4. Safety Invariants Audit

The following non-negotiable safety locks have been verified across the codebase:
1. **Serial Hardware Protocol Lock:**
   ```python
   # gracemo_hardware/gracemo_hardware/mcu_transport.py:372
   PROTOCOL_CONFIRMED: bool = False
   ```
   Physical serial communication to STM32 is blocked.
2. **Firmware Motor Output Lock:**
   ```c
   // firmware/config.h:41
   #define MOTOR_OUTPUT_ENABLED 0
   ```
   Physical motor driver PWM/direction timers are disabled at compile time.
3. **Single Authoritative Velocity Command Chain:**
   $$\text{Nav2 BT} \xrightarrow{/cmd\_vel\_nav} \text{velocity\_smoother} \xrightarrow{/cmd\_vel\_smoothed} \text{collision\_monitor} \xrightarrow{/cmd\_vel\_safe} \text{terrain\_monitor} \xrightarrow{/cmd\_vel} \text{ros\_gz\_bridge}$$
   The UARCC GUI does **not** publish to `/cmd_vel` directly. All movement requests are issued via `/coordinator/command` to the `gracemo_command_coordinator` state machine.

---

## 5. Existing Test Results

### 5.1 UARCC Automated Test Suite
- Executed: `python3 -m pytest gracemo_control_center/tests/ -v`
- **Result:** **30 passed in 2.22s (100% pass rate)**
- Covered functionality:
  - Startup & shutdown lifecycle
  - ROS 2 node reconnection
  - Sensor freshness watchdogs
  - RGB & Depth image conversion
  - LiDAR coordinate transformation (polar to Cartesian)
  - IMU and Odometry packet parsing
  - 2D Occupancy Grid map rendering
  - 6-destination loading from `destinations.json`
  - Coordinator action dispatch and cancellation
  - Emergency stop trigger & safety stop display
  - Voice event reception and logging
  - GUI independence during autonomous navigation
  - Hardware safety invariant checks

### 5.2 Accepted Autonomous Robotics Baseline
- Baseline test report: `docs/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md`
- **Results:** 433 passed, 1 skipped (hardware bench test requiring physical MCU), 0 failed.
- 6/6 canonical destination navigation circuits passed with $\le 0.33\text{ m}$ precision.

---

## 6. Identified Incomplete Areas for Live Integration

The following areas require verification in live simulation:
1. **Live Gazebo Harmonic Telemetry:** Launching `run_prototype.sh` and verifying the GUI's connection to the live ROS 2 graph and Gazebo Harmonic bridge.
2. **Live Sensor Rate Measurement:** Measuring actual empirical update frequencies for `/scan`, `/camera/image_raw`, `/camera/depth_image`, `/imu/data`, and `/odom`.
3. **Live Closed-Loop Navigation:** Dispatching navigation goals via the UARCC GUI to the live `gracemo_command_coordinator` and Nav2 stack across the 6 apartment destinations.
4. **Live GUI Independence:** Closing and restarting the UARCC GUI while the robot is actively traversing a navigation goal to ensure zero mission interruption.
5. **Real-time System Performance:** Monitoring memory, CPU, and rendering framerate under concurrent simulation, Nav2, and GUI load.

---

## 7. Files Requiring Modification or Staging

1. `config/destinations.json` (Symlinked in migration repository for canonical reference).
2. `gracemo_control_center/` (Full application codebase).
3. `scripts/run_control_center.sh` and `scripts/stop_control_center.sh` (Shell execution helpers).
4. Documentation artifacts in `docs/`:
   - `UARCC_V1_BASELINE_AUDIT.md` (This document)
   - `UARCC_SENSOR_LIVE_ACCEPTANCE.md`
   - `UARCC_NAVIGATION_LIVE_ACCEPTANCE.md`
   - `UARCC_GUI_INDEPENDENCE_ACCEPTANCE.md`
   - `UARCC_V1_SAFETY_ACCEPTANCE.md`
   - `UARCC_V1_FINAL_REGRESSION_REPORT.md`
   - `UARCC_V1_FINAL_LIVE_ACCEPTANCE_REPORT.md`
   - `UARCC_V1_FINAL_ENGINEERING_HANDOFF.md`

---

## 8. Risk Management and Safeguards

| Risk | Likelihood | Impact | Mitigation |
|---|:---:|:---:|---|
| Accidental physical motor command | Low | Catastrophic | `PROTOCOL_CONFIRMED=False` and `MOTOR_OUTPUT_ENABLED=0` invariants locked. |
| GUI freeze during high sensor throughput | Medium | Moderate | Bounded queue, 30 FPS cap on OpenCV image conversions, dedicated QThread workers. |
| Duplicate ROS nodes on GUI restart | Low | High | Unique node naming, clean `QApplication.aboutToQuit` executor shutdown. |
| Nav2 preemption on GUI exit | Low | High | GUI operates strictly as a telemetry monitor and coordinator command client; navigation is managed independently by Nav2 and coordinator FSM. |

---

**Audit Sign-off:**  
Baseline verified. Proceeding directly to Phase 1 (Module Integration Verification) and Phase 2 (Live Gazebo & ROS Integration).
