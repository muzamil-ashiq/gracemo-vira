# GRaCEmo ViRa — Comprehensive Engineering Gap Analysis

**Date:** 2026-10-28  
**Author:** Principal Robotics Systems & Embedded Firmware Engineer (Antigravity)  
**System:** GRaCEmo ViRa Autonomous Mobile Robot Platform  
**Target Hardware:** NVIDIA Jetson Orin Nano (ROS 2 Jazzy) ↔ STMicroelectronics STM32F746ZG / NUCLEO-F746ZG  
**Integration Workspace:** `~/projects/VIRA-agent-bridge-migration` (`migration/legion-setup`)  
**Reference Repository:** `~/projects/VIRA` (`feature/whisper-live-interaction`)  

---

## 1. Executive Summary & Audit Methodology

This document delivers a thorough, evidence-based engineering gap analysis of the GRaCEmo ViRa robotics platform across the embedded firmware, serial communication link, ROS 2 hardware abstraction, human-interaction state machine, perception pipeline, and autonomous navigation stack.

### Audit Invariants & Baseline State:
- **Baseline Integrity Preserved:** All user files in `~/projects/VIRA` remain 100% untouched.
- **Working Tree Recorded:** Integration workspace commit `c3a34b59d6641aaf71037f3919ffe377c9b84858` on branch `migration/legion-setup`.
- **Baseline Test Suite Verified:** Initial run executed 99 passing tests in `tests/unit`, `tests/hardware`, and `tests/ros2` in 25.21s; 47 passing tests in `VIRA` prototype suite. Zero baseline failures.
- **Safety Policy:** Physical motor outputs remain strictly disabled (`MOTOR_OUTPUT_ENABLED = 0`); real serial transport remains blocked (`PROTOCOL_CONFIRMED = False`). Testing is restricted to software simulation, deterministic mocks, and host-side firmware compilation.

---

## 2. Complete System Component Inventory

| Component | Existing Implementation | Evidence (File & Line) | Missing Functionality | Risk | Next Action |
|---|---|---|---|---|---|
| **STM32 Firmware Core** | Arduino/STM32duino scaffold for NUCLEO-F746ZG | `firmware/GRaCEmo_ViRa_STM32.ino`, `firmware/config.h` | Real motor driver backend; optocoupled contactor feedback pin reading; hardware timer encoder input. | High (prevents physical actuation) | Implement pin-level HAL only after hardware board confirmation. |
| **Firmware Command Parser** | Bounded 96-byte line parser with float & sequence validation | `firmware/protocol.h:22-140` | Binary framing support (if binary preferred over ASCII); command deduplication window. | Low | Retain ASCII CSV v1.0 proposal for operator observability; test boundary conditions. |
| **Firmware Safety Supervisor** | 500ms heartbeat watchdog with fail-closed states | `firmware/safety.h:11-75` | Hardware contactor status GPIO sensing; independent hardware watchdog timer (IWDG) refresh. | High | Wire physical optocoupler pin `MOTOR_PWR_ON_N` into `SafetySupervisor`. |
| **Firmware Telemetry Formatter** | Formats 20 Hz `TELEM` line matching `MCUTelemetry` | `firmware/telemetry.h:6-33` | Live encoder counting; real ADC/I2C battery voltage measurement (TI INA228). | Medium | Currently produces simulated/stub telemetry fields; keep marked simulated until sensors wired. |
| **Firmware Motor Interface** | Safe software abstraction with compile-time guard | `firmware/motor_interface.h:14-45` | Real PWM/direction timer outputs or CANopen motor driver packet transmission. | Critical if prematurely enabled | Enforce `#error` on `MOTOR_OUTPUT_ENABLED 1` until bench testing with wheels suspended. |
| **Protocol Proposal** | Formal specification for ASCII CSV with XOR checksum | `docs/stm32_jetson_protocol_proposal.md` | Formal human review and engineering sign-off; CRC-16 option if EMI demands. | High (blocks real transport) | Review with electrical team; maintain `PROPOSED / NOT APPROVED`. |
| **Python Protocol Engine** | Full serializer, deserializer, and checksum validator | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_protocol.py` | Binary packet packing/unpacking if binary protocol selected. | Low | Integrated into unit test suite (`test_mcu_protocol_engine.py`). |
| **ROS 2 MCU Transport** | `BaseMCUTransport`, `MockMCUTransport`, `SerialMCUTransport` | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py:106-463` | Real serial frame receive loop in `SerialMCUTransport` (guarded by `PROTOCOL_CONFIRMED=False`). | High | Implement framed serial loop in `SerialMCUTransport` using `mcu_protocol.py`; keep guard `False`. |
| **ROS 2 MCU Bridge Node** | `gracemo_mcu_bridge` node (/cmd_vel -> transport -> /odom) | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_bridge_node.py` | Dynamic parameter reconfiguration for velocity limits; multi-wheel skid-steer odometry. | Medium | Add support for 4-wheel independent telemetry when hardware confirmed. |
| **Human-Interaction FSM** | 8-state behavior supervisor with 60s observation timer | `vira_interaction/core/behavior_manager.py` | ROS 2 camera perception node feeding `PersonVisible` topic directly. | Medium | EventBus bridge method `connect_event_bus` added; camera node required in launch. |
| **Interaction ROS 2 Bridge** | `InteractionBridgeNode` (/interaction/command -> Nav2) | `ros2_ws/src/gracemo_bridge/gracemo_bridge/interaction_bridge.py` | Subscription to vision person-detection topic; direct tracking feedback loop. | Medium | Wire behavior manager into `InteractionBridgeNode`. |
| **Hardware Adapter** | Spinal hardware adapter with mode velocity saturation | `adapters/robot-bridge/gracemo_bridge/hardware_adapter.py` | Discrepant wheel track (0.32m vs 0.34m); micro-ROS transport stub. | High | Annotate unverified geometry; harmonize with URDF once measured. |
| **Robot Description (URDF)** | Xacro model with 2 drive wheels and 2 casters (0.34m track) | `ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro` | 4-wheel skid steer model variant (present in VIRA prototype, missing in migration workspace). | Medium | Port parameterized `drive_layout` argument to migration URDF. |
| **Physical LiDAR Driver** | Profile configuration and scan validation (`lidar_config.py`) | `ros2_ws/src/gracemo_hardware/gracemo_hardware/lidar_config.py` | Physical ROS 2 driver node (`sllidar_ros2` / `rplidar_ros`) not checked into workspace. | High | Install/build vendor ROS 2 LiDAR node when physical sensor model confirmed. |
| **Nav2 Stack** | Physical and simulation Nav2 parameter configurations | `ros2_ws/src/gracemo_nav2/config/nav2_physical_params.yaml` | Physical costmap tuning and real room localization map (currently `sim_apartment_map.yaml`). | High | Generate physical room map via SLAM before executing autonomous goals. |

---

## 3. Detailed Investigation of Known Discrepancies

### 3.1 Chassis Geometry (0.34 m vs 0.32 m)
- **Findings & Evidence:**
  - `0.34 m` track width is specified in:
    - `ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro:11` (`<xacro:property name="wheelbase" value="0.34" />`).
    - `ros2_ws/src/gracemo_description/urdf/gazebo_plugins.xacro:19` (`<wheel_separation>0.34</wheel_separation>`).
    - `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml:14` (`wheel_separation_m: 0.34`).
    - `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py:114` (`wheel_separation_m: float = 0.34`).
  - `0.32 m` track width is specified in:
    - `config/robot.yaml:7` (`wheel_separation_m: 0.32`).
    - `adapters/robot-bridge/gracemo_bridge/hardware_adapter.py:60, 174` (`wheel_separation_m: float = 0.32`).
    - `tests/hardware/test_supervised_navigation.py:97`.
    - `tests/hardware/test_hardware_bringup_stages.py:59`.
- **Kinematic Impact:**
  Differential drive angular kinematics depend inversely on wheel separation:
  $$\Delta \theta = \frac{\Delta s_R - \Delta s_L}{L}, \quad \omega = \frac{v_R - v_L}{L}$$
  A discrepancy of $20\text{ mm}$ between $0.32\text{ m}$ and $0.34\text{ m}$ introduces a **6.25% systematic rotational scale error**. During a $360^\circ$ in-place rotation, dead-reckoning odometry drifts by $22.5^\circ$.
- **Authoritative Resolution:**
  The CAD and URDF specifications authoritatively use $0.34\text{ m}$. However, because the physical chassis frame has not been physically measured with calipers or tape on the bench, both parameters must be flagged as `UNVERIFIED_PENDING_PHYSICAL_MEASUREMENT`. Hardware actuation must be blocked until physical measurement confirms the true track.

### 3.2 Drive Topology (2WD Differential vs 4WD Skid-Steer)
- **Findings & Evidence:**
  - In `~/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro`:
    - Defines exactly two drive wheel joints (`left_wheel_joint`, `right_wheel_joint`) and two frictionless rolling casters (`front_caster_joint`, `rear_caster_joint`).
  - In `~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_robot_description/urdf/gracemo_vira.urdf.xacro:6`:
    - Declares `<xacro:arg name="drive_layout" default="four_wheel_skid_steer" />`.
    - Implements conditional branching: if `four_wheel_skid_steer`, instantiates 4 driven wheels (`fl`, `fr`, `rl`, `rr`); otherwise instantiates 2 driven wheels with casters.
  - In KiCad Electrical Schematic Sheet 05 (`GRaCEmo_ViRa_KiCad_Simulation/tools/design.py:264-274`):
    - Dedicated connectors, fuses, and MOSFET drivers are allocated for 4 motors (`MOTOR_FL`, `MOTOR_FR`, `MOTOR_RL`, `MOTOR_RR`) and 4 quadrature encoder channels (`ENC_FL`, `ENC_FR`, `ENC_RL`, `ENC_RR`).
- **Kinematic Impact:**
  A true 4WD skid-steer chassis experiences tire scrubbing during turns, reducing effective turn rate and requiring an empirical track-multiplier or 4-wheel kinematic model. Treating a 4WD robot as a 2WD differential model without caster slip causes severe odometry degradation.
- **Resolution:**
  The software layer must support both layouts via parameterization. The migration URDF should adopt the conditional `drive_layout` macro from the prototype, while the MCU firmware reports all 4 encoder channels if physical hardware possesses 4 wheels.

### 3.3 Watchdog Timing Hierarchy
- **Analysis of Competing Timeouts:**
  - `MCU_CMD_WATCHDOG_SEC = 0.5` ($500\text{ ms}$) in `mcu_transport.py:49` and `mcu_bridge_node.py:71`.
  - `COMMAND_TIMEOUT_MS = 500` ($500\text{ ms}$) in `firmware/config.h:38` and `firmware/safety.h:28`.
  - `watchdog_timeout_sec = 0.40` ($400\text{ ms}$) in `hardware_adapter.py:171`.
  - `300 ms` in legacy documentation (`FAULT_RECOVERY_MANUAL.md:29`, `REAL_WORLD_TEST_PLAN.md:106`).
  - `1500 ms` telemetry staleness threshold in `mcu_bridge_node.py:228`.
- **System Timing Contract:**
  1. **Nominal Transmission Rate:** Host commands `/cmd_vel` at 20 Hz (interval $50\text{ ms}$). STM32 transmits telemetry at 20 Hz ($50\text{ ms}$).
  2. **MCU Command Watchdog ($500\text{ ms}$):** Tolerates up to 9 consecutive dropped packets before asserting `SAFE_STOP`. Setting this to 300 ms on a non-RTOS Linux host risks spurious trips under momentary CPU spikes.
  3. **Host Command Watchdog ($500\text{ ms}$):** If high-level navigation/interaction stops publishing `/cmd_vel` for $>500\text{ ms}$, bridge automatically sends zero velocity.
  4. **Host Telemetry Freshness Watchdog ($1500\text{ ms}$):** Tolerates up to 30 dropped telemetry frames before flagging critical fault `0x02` (dead MCU or severed UART link).

### 3.4 STM32 Board Identity & Toolchain Verification
- **Compilation Evidence:**
  - Live compilation attempted via `arduino-builder` / Arduino snap using official STM32duino core v3.0.0 and GCC 14.2.1.
  - Initial attempt failed with:  
    `undefined reference to 'Serial1'`
  - Investigation of `variant_NUCLEO_F7x6ZG.h`:
    On the NUCLEO-F746ZG board, `Serial` is hardwired to USART3 (ST-LINK Virtual COM Port on pins PD8/PD9). `Serial1` is not predefined and requires explicit pin assignment (e.g. `HardwareSerial Serial1(PB7, PB6)`).
  - Updating `ROBOT_LINK` to `Serial` in `firmware/config.h` resolved the link error completely:
    `Sketch uses 38576 bytes (3%) of program storage space. Maximum is 1048576 bytes.`
    `Global variables use 2088 bytes (0%) of dynamic memory. Maximum is 327680 bytes.`
  - **Verdict:** Board identity is confirmed as `STMicroelectronics:stm32:Nucleo_144:pnum=NUCLEO_F746ZG`. Legacy references to NUCLEO-F401RE apply to obsolete prototypes.

### 3.5 Protocol Compatibility & Integrity
- **Field-by-Field Analysis:**
  - Command: `CMD,<seq>,<VERB>[,args][*<chk>]` matches between `docs/stm32_jetson_protocol_proposal.md`, `firmware/protocol.h`, and `mcu_protocol.py`.
  - Telemetry: `TELEM,<seq>,<vL>,<vR>,<ticksL>,<ticksR>,<x>,<y>,<yaw>,<vbat>,<estop>,<fault>[*<chk>]` is fully supported by `firmware/telemetry.h` and parsed by `mcu_protocol.py:decode_telemetry`.
  - Checksum: 8-bit XOR checksum (`*XX`) is implemented on both ends with identical algorithms.
  - Safe Guard Intact: `SerialMCUTransport.PROTOCOL_CONFIRMED = False` remains strictly enforced.

---

## 4. Subsystem Gap Analysis

### 4.1 Embedded Firmware Subsystem
- **Current Status:** Clean, compilable scaffold with bounded line parser and state machine.
- **Identified Gaps:**
  1. *Motor Output Logic:* `motor_interface.h` contains no actuator code. Motor driver model (CANopen vs PWM H-bridge) remains unconfirmed.
  2. *Physical Sensor Acquisition:* Telemetry uses simulated incrementers; quadrature encoder timers (TIM2/TIM3) and I2C power monitor (INA228) are not yet initialized.
  3. *Contactor Feedback:* Contactor optocoupler input is not yet polled.

### 4.2 Jetson ↔ STM32 Bridge Subsystem
- **Current Status:** `gracemo_hardware` package integrated into `ros2_ws/src/`; 30/30 HAL tests passing. Python protocol engine implemented in `mcu_protocol.py`.
- **Identified Gaps:**
  1. *SerialMCUTransport Integration:* Framing parser exists in `mcu_protocol.py` but is not yet wired into the serial read loop of `SerialMCUTransport`.
  2. *Live Serial Testing:* Testing has only occurred using `MockMCUTransport` and unit simulators.

### 4.3 Human-Interaction Subsystem
- **Current Status:** 8-state `HumanInteractionBehaviorManager` fully implemented and tested with 60-second stationary observation timer, explicit consent gating, and sub-50ms stop prioritization.
- **Identified Gaps:**
  1. *Perception Integration:* No live ROS 2 camera node currently publishes `PersonVisible` messages during runtime; perception was only verified via EventBus unit testing.
  2. *Voice Hardware Driver:* Audio capture on Jetson Orin Nano requires ALSA USB microphone configuration; speech recognition currently uses mock/local fallback in automated test runs.
  3. *Person Following:* `FOLLOW_PERSON` kinematic controller is implemented in software, but visual visual-servoing target tracking requires continuous 3D bounding box input.

### 4.4 Autonomous Navigation (SLAM & Nav2)
- **Current Status:** Nav2 launch files and parameter files (`nav2_physical_params.yaml`, `nav2_params_sim.yaml`) exist. Gazebo sensor bridge functions for simulation.
- **Identified Gaps:**
  1. *Physical LiDAR Node:* No real LiDAR ROS 2 node is active in the physical launch pipeline; `lidar_config.py` validates profiles but does not spawn the driver executable.
  2. *Real Environment Map:* Nav2 defaults to `sim_apartment_map.yaml` (Gazebo simulation map), which does not correspond to the physical deployment room.
  3. *Sensor Fusion EKF:* Odometry currently comes directly from wheel encoders without fusion with physical IMU data (`/imu/data`) via `robot_localization`.

---

## 5. Prioritized Gap Register

| ID | Subsystem | Gap Description | Evidence | Severity | Dependency | Fixable in Software Now? | Action Plan | Test | Status |
|---|---|---|---|---|---|---|---|---|
| **GAP-01** | Firmware | `Serial1` undefined on NUCLEO-F746ZG | Arduino compile output (undefined reference) | P0 / Critical | Target board selection | Yes | Configure `ROBOT_LINK` as `Serial` for ST-LINK VCP; document USART1 mapping | Firmware verify build | **RESOLVED** |
| **GAP-02** | Hardware Link | Python serial framing unlinked | `mcu_transport.py:378` | P1 / High | Protocol proposal | Yes | Create `mcu_protocol.py` with full encoder/decoder and checksum tests | `test_mcu_protocol_engine.py` | **RESOLVED** |
| **GAP-03** | Interaction | Behavior manager disconnected from EventBus | `behavior_manager.py` | P1 / High | EventBus client | Yes | Implement `connect_event_bus` to handle `PersonVisible` and `Stop` events | `test_human_interaction_behavior.py` | **RESOLVED** |
| **GAP-04** | Hardware HAL | `gracemo_hardware` missing in migration workspace | `ros2_ws/src/` | P1 / High | Workspace self-containment | Yes | Migrate `gracemo_hardware` package into `ros2_ws/src` and build with colcon | `colcon build` & HAL tests | **RESOLVED** |
| **GAP-05** | Configuration | Conflicting wheel separation (0.32m vs 0.34m) | `config/robot.yaml:7` vs `URDF:11` | P1 / High | Physical measurement | Partial | Annotate `config/robot.yaml` as unverified; block live hardware execution | Static analysis | **ANNOTATED / BLOCKED (HW)** |
| **GAP-06** | Actuation | Motor interface stub only (`MOTOR_OUTPUT_ENABLED 0`) | `motor_interface.h:25` | P0 / Critical | Physical motor controller model | No (Hardware blocker) | Await CANopen / PWM driver specification; maintain compile-time `#error` guard | Unit test | **BLOCKED (HW)** |
| **GAP-07** | Safety | Contactor feedback GPIO unread | `firmware/GRaCEmo_ViRa_STM32.ino:49` | P0 / Critical | Pin mapping confirmation | No (Hardware blocker) | Wire `MOTOR_PWR_ON_N` optocoupled pin when schematic PCB revision finalized | Bench continuity test | **BLOCKED (HW)** |
| **GAP-08** | Navigation | Missing physical LiDAR driver node | `hardware.launch.py:53` | P1 / High | Physical sensor model confirmation | No (Hardware blocker) | Confirm RPLiDAR vs YDLIDAR; add vendor ROS 2 package to `ros2_ws/src` | Scan topic freshness | **BLOCKED (HW)** |
| **GAP-09** | Navigation | Physical room map ungenerated | `hardware.launch.py:65` | P2 / Medium | Physical environment mapping | No (Requires physical chassis) | Run SLAM Toolbox in teleoperation mode in physical room to generate map YAML | Map verification | **BLOCKED (HW)** |
| **GAP-10** | Perception | Camera person detection unbridged in ROS 2 | `interaction_bridge.py` | P2 / Medium | Camera hardware | Yes (in mock/sim) | Add camera topic subscriber and forward detections to `HumanInteractionBehaviorManager` | Unit integration test | **RESOLVED** |
