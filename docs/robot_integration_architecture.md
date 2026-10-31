# GRaCEmo ViRa — Robot Integration Architecture

**Document ID:** `VIRA-ARCH-INT-001`  
**Classification:** Systems Architecture Specification  
**Platform:** NVIDIA Jetson Orin Nano + STM32F746ZG (NUCLEO-144)  
**ROS 2 Distribution:** Jazzy Jalisco  
**Date:** 2026-10-28  

---

## 1. System Overview & Division of Responsibilities

```
                                  JETSON ORIN NANO
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  Perception & Interaction                Autonomous Navigation (Nav2)       │
 │  ┌──────────────────────┐                ┌───────────────────────────────┐  │
 │  │ Camera / Person Det  │                │ Global & Local Costmaps       │  │
 │  │ Audio / Whisper Voice│                │ Path Planner & Controller     │  │
 │  │ Behavior Manager     │                │ Collision Monitor             │  │
 │  └──────────┬───────────┘                └───────────────┬───────────────┘  │
 │             │                                            │                  │
 │             ▼                                            ▼                  │
 │      Structured Action                         /cmd_vel (Navigation)        │
 │             │                                            │                  │
 │             └───────────────────┬────────────────────────┘                  │
 │                                 ▼                                           │
 │                   Command & Velocity Safety Gate                            │
 │                 (Clamping: 0.35 m/s, 0.75 rad/s; STOP Priority)             │
 │                                 │                                           │
 │                                 ▼                                           │
 │                        MCU Bridge Node                                      │
 │                                 │                                           │
 │                                 ▼                                           │
 │                     MCU Transport Abstraction                               │
 │             ┌───────────────────┴───────────────────┐                       │
 │             ▼                                       ▼                       │
 │       MockMCUTransport                     SerialMCUTransport               │
 │     (Default: Simulation)                 (Safety Gated: PROTOCOL_CONFIRMED)│
 └─────────────┬───────────────────────────────────────┬───────────────────────┘
               │ (Host Simulation)                     │ (ASCII CSV / UART)
               ▼                                       ▼
     [Simulated Kinematics]                    STM32F746ZG MCU
                                ┌──────────────────────────────────────────────┐
                                │ - Protocol Parser (Bounded 96B, XOR Checksum)│
                                │ - Safety Supervisor (Watchdog, E-Stop latch) │
                                │ - Motor Driver Stub (MOTOR_OUTPUT_ENABLED=0) │
                                │ - Telemetry Formatter (20 Hz TELEM frames)   │
                                └──────────────────────────────────────────────┘
```

### 1.1 Jetson Orin Nano (High-Level Robotics Computer)
- **Role:** Cognition, perception, high-level planning, dialogue, and operator safety supervision.
- **Responsibilities:**
  - Ingestion of live camera stream (OpenCV/V4L2) and person bounding-box estimation.
  - Ingestion of live microphone stream (PyAudio/ALSA) and structured voice command normalization (`VoiceCommandParser`).
  - Authoritative 8-state human-interaction state machine ([`BehaviorManager`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/behavior_manager.py)) enforcing a 60-second observation timer before interaction consent.
  - LiDAR scan acquisition and 2D obstacle costmap maintenance.
  - Nav2 navigation stack lifecycle management and trajectory generation.
  - Command velocity saturation ([`hardware_adapter.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/adapters/robot-bridge/gracemo_bridge/hardware_adapter.py)): clamping linear velocity to $\le 0.35\text{ m/s}$ and angular velocity to $\le 0.75\text{ rad/s}$.
  - Serial command encoding with sequence IDs and XOR checksums.
  - Telemetry freshness watchdog ($1.5\text{ s}$ timeout).

### 1.2 STM32F746ZG Microcontroller (Low-Level Real-Time Controller)
- **Role:** Deterministic hard real-time safety, motor commutation, encoder pulse counting, and contactor monitoring.
- **Responsibilities:**
  - Bounded input buffering (96 bytes max) and ASCII CSV parsing (`CMD,<seq>,<VERB>[,<args>][*<chk>]`).
  - Independent $500\text{ ms}$ command watchdog timer: automatically stops motors if the Jetson command stream stalls.
  - Hardwired emergency-stop input and auxiliary contactor feedback sense (`PE0`).
  - Dual-wheel quadrature encoder pulse accumulation (future hardware timer counter mode).
  - Periodic $20\text{ Hz}$ telemetry frame transmission (`TELEM,<seq>,<vL>,<vR>,<ticksL>,<ticksR>,<x>,<y>,<yaw>,<vbat>,<estop>,<fault>[*<chk>]`).
  - Compile-time motor output disable guard: `MOTOR_OUTPUT_ENABLED = 0` locks PWM timers and direction pins.

---

## 2. ROS 2 Package Relationships

| Package Name | Path | Core Role & Contents |
|---|---|---|
| `gracemo_hardware` | [`ros2_ws/src/gracemo_hardware`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware) | `mcu_bridge_node`, `mcu_transport` (`BaseMCUTransport`, `MockMCUTransport`, `SerialMCUTransport`), `mcu_protocol` encoder/decoder, hardware launch files, and `hardware_params.yaml`. |
| `gracemo_bridge` | [`ros2_ws/src/gracemo_bridge`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_bridge) | `interaction_bridge_node`, ROS 2 topic wrappers, and `kernel_bridge`. |
| `gracemo_description` | [`ros2_ws/src/gracemo_description`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description) | URDF/Xacro models ([`gracemo_vira.urdf.xacro`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro) and parameterized [`gracemo_vira_parameterized.urdf.xacro`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/urdf/gracemo_vira_parameterized.urdf.xacro)), materials, and Gazebo Harmonic simulation plugins. |
| `gracemo_nav2` | [`ros2_ws/src/gracemo_nav2`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_nav2) | Nav2 physical configuration ([`nav2_physical_params.yaml`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_nav2/config/nav2_physical_params.yaml)), costmap parameterization, recovery behaviors, and navigation bringup launch files. |
| `vira_interaction` | [`vira_interaction`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction) | Python cognitive substrate: [`BehaviorManager`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/behavior_manager.py), [`CameraDriverInterface`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/camera_driver.py), [`AudioDriverInterface`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/audio_driver.py), and `SafetyGate`. |

---

## 3. Data Flow & Sensor Pipelines

### 3.1 Outbound Command Pipeline (Jetson → Motors)
1. **Source:** Either Nav2 planner (`/cmd_vel_nav`), Voice manual command (`BehaviorManager.process_voice_command`), or Teleoperation.
2. **Safety Validation:** [`SafetyGate`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/safety_gate.py) enforces:
   - Nan and infinity rejection.
   - Low-battery interlock: inhibits forward locomotion if $V_{bat} < 10.5\text{ V}$.
   - Emergency-stop override: if E-stop is tripped, commands are immediately zeroed.
3. **Hardware Bridge Translation:** `MCUBridgeNode` maps linear/angular velocity to `MCUCommand(linear_vel_mps, angular_vel_rps, seq)`.
4. **Transport Layer:**
   - **Mock Mode:** [`MockMCUTransport`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py#L184) computes differential kinematics in software.
   - **Hardware Serial Mode:** [`SerialMCUTransport`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py#L359) serializes `CMD,<seq>,DRIVE,<lin>,<ang>*<chk>\n` over 115200 baud UART.
5. **Firmware Execution:** STM32 safety supervisor validates checksum, sequence freshness, and bounds, then dispatches to motor driver (guarded by `MOTOR_OUTPUT_ENABLED = 0`).

### 3.2 Inbound Telemetry Pipeline (STM32 → ROS 2)
1. **Firmware Output:** STM32 transmits `TELEM` frame at $20\text{ Hz}$ ($50\text{ ms}$ interval).
2. **Serial Receive:** `SerialMCUTransport.feed_bytes()` accumulates chunks into a bounded 1024-byte buffer, strips newlines, and rejects lines $>96$ characters.
3. **Protocol Decoding:** [`mcu_protocol.decode_telemetry()`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_protocol.py#L56) verifies XOR checksum and extracts velocity, encoder ticks, battery voltage, E-stop bit, and fault codes into `MCUTelemetry`.
4. **Odometry & TF Publishing:** `MCUBridgeNode` computes odometry integration and broadcasts `odom -> base_footprint` TF transform and `/odom` (`nav_msgs/msg/Odometry`).

---

## 4. Coordinate Frame (TF) Architecture

Following ROS REP-103 and REP-105 standards:

```
  map (Global fixed frame from SLAM / AMCL)
   │
   ▼
  odom (Continuous world-fixed odometry frame from wheel integration)
   │
   ▼
  base_footprint (2D ground projection, z=0.0)
   │
   ▼
  base_link (Center of physical robot chassis, z=wheel_radius=0.065m)
   ├── lidar_link (x=0.15m, y=0.0m, z=0.28m, rpy=0,0,0)
   ├── camera_link (x=0.18m, y=0.0m, z=0.45m)
   │    └── camera_optical_frame (REP-103: x-right, y-down, z-forward)
   ├── left_wheel_link (y=+0.17m, continuous joint)
   ├── right_wheel_link (y=-0.17m, continuous joint)
   ├── front_caster_link (x=+0.14m, fixed joint in differential layout)
   └── rear_caster_link (x=-0.14m, fixed joint in differential layout)
```

---

## 5. Mock vs Physical Transport Operational Modes

| Operational Characteristic | Mock Transport (`MockMCUTransport`) | Physical Transport (`SerialMCUTransport`) |
|---|---|---|
| **Safety Activation Gate** | Enabled by default; safe for automated testing and CI. | Blocked by `PROTOCOL_CONFIRMED = False`; raises `RuntimeError` if invoked. |
| **Physical Movement** | None. Motors are completely bypassed. | None until `MOTOR_OUTPUT_ENABLED = 1` in firmware and physical gates sign-off. |
| **Odometry Generation** | Forward Euler numerical integration from commanded velocities. | Deduced from wheel encoder tick accumulation. |
| **Fault Injection** | Supports programmatic `inject_estop()`, `inject_disconnect()`, `inject_timeout()`. | Reflects physical contactor state (`PE0`), UART line drops, and hardware faults. |
| **Diagnostic Metrics** | Command count, connection state. | `frames_received`, `checksum_errors`, `malformed_frames`, `buffer_overflows`. |
