# GRaCEmo ViRa — Physical Hardware Deployment Architecture
## Phase 5 Hardware-in-the-Loop & Hardware Bring-Up Specification

### 1. Hardware Architecture Overview
The physical GRaCEmo ViRa Autonomous Robot is an interactive mobile service robot designed with a hierarchical two-tier compute and actuation architecture:
1. **High-Level Cognitive Compute**: Host/Onboard compute (Apple Silicon / Linux ARM64 Jetson) running Python 3.11 interaction services, EventBus, SafetyGate, RobotBridge, and Nav2.
2. **Low-Level Motor Control / MCU Substrate**: Micro-ROS / STM32 / Serial Microcontroller executing 50Hz closed-loop motor velocity control, quadrature encoder sampling, battery telemetry, and hardware command watchdog.

---

### 2. Physical Subsystems & Verified Specifications

| Subsystem | Verified Hardware Component | Physical Parameter / Specification | Communication Interface |
|---|---|---|---|
| **Onboard Computer** | Host ARM64 Compute (e.g. Jetson Orin / Workstation) | Ubuntu Linux 24.04 / macOS Darwin / ROS 2 Jazzy | USB 3.0 / PCIe / Loopback Ethernet |
| **Microcontroller (MCU)**| STM32 / micro-ROS Controller Board | 32-bit Cortex MCU running micro-ROS / custom firmware | USB Serial (`/dev/ttyUSB0` at 115200 baud) |
| **Drive Kinematics** | Differential Drive Chassis | Track Width $L = 0.32\text{ m}$ (wheel separation) | High-torque dual planetary drive |
| **Drive Wheels** | Dual High-Traction Solid Rubber Wheels | Wheel Radius $R = 0.065\text{ m}$ (Diameter $0.13\text{ m}$) | Direct keyed axle coupling |
| **Drive Motors** | Dual DC Brushed/BLDC Gear Motors | Integrated hall/optical quadrature encoders | Motor Controller H-bridge / CAN / PWM driver |
| **Wheel Encoders** | Incremental Optical Quadrature Encoders | 2048 ticks/revolution resolution | Dual-channel A/B interrupt pins on MCU |
| **Planar LiDAR** | 360° Planar Scanning LiDAR | Scan rate: 15Hz, Range: 0.12m – 12.0m | USB-UART (`/dev/ttyUSB1`, frame `lidar_link`) |
| **Inertial Measurement Unit**| 6-DOF IMU (Accelerometer + Gyroscope) | Sample rate: 40Hz, Noise density: $< 0.02\text{ deg/}\sqrt{\text{s}}$ | I2C / SPI on MCU (frame `imu_link`) |
| **Vision Sensor** | RGB-D Depth Camera (Intel RealSense / Orbbec) | RGB: 640x480 @ 30Hz, Depth: 320x240 @ 15Hz | USB 3.0 (frame `camera_optical_link`) |
| **Head Display & Neck** | 2-DOF Pan/Tilt Neck with Expressive Face | Pan: $[-90°, +90°]$, Tilt: $[-30°, +45°]$ | Dual smart bus servos (50Hz) |
| **Power System** | 12V LiFePO4 / Li-Ion Rechargeable Battery | Nominal: 12.4V, Full: 12.6V, Low: 11.5V, Cutoff: 10.5V | ADC voltage divider to MCU telemetry |
| **Emergency Stop Circuit** | Hardware Normally-Closed (NC) E-Stop Switch | Physical mushroom button on chassis | Direct hardware interlock line to MCU / power gate |

---

### 3. Hardware Operational Modes & Velocity Envelopes

The physical robot strictly operates under four gated hardware modes plus simulation mode:

| Mode Name | Operational State | Max Linear Speed | Max Angular Speed | Preconditions / Safety Invariant |
|---|---|---|---|---|
| **`HARDWARE_SAFE`** | Stationary Default | **0.00 m/s** | **0.00 rad/s** | **Default Boot Mode**. All wheel motion locked. Motors unpowered. |
| **`HARDWARE_TEST`** | Bench / Low-Speed Test | **0.10 m/s** | **0.25 rad/s** | Requires explicit `authorize_test_motion()`. Human operator present. |
| **`HARDWARE_TELEOP`**| Manual Remote Teleop | **0.25 m/s** | **0.50 rad/s** | Teleop controller actively streaming. Watchdog enforced (<400ms). |
| **`HARDWARE_AUTONOMOUS`**| Supervised Autonomous Nav| **0.35 m/s** | **0.75 rad/s** | Requires valid LiDAR, IMU, AMCL localization, and battery > 15%. |
| **`SIMULATION`** | Gazebo Harmonic / SITL | 0.45 m/s | 0.85 rad/s | Software emulation backend in simulated physics. |

---

### 4. ROS 2 Hardware Nodes & Launch Architecture

```text
Physical Hardware Architecture:

[ Physical Sensors & Actuators ]
         │
         ├──► Serial (/dev/ttyUSB0) ──► gracemo_bridge/hardware_adapter
         ├──► LiDAR (/dev/ttyUSB1)  ──► sllidar_ros2 / ros2_ws/sensor_bridge ──► /scan
         └──► USB Camera            ──► v4l2_camera / ros2_ws/sensor_bridge  ──► /camera/image_raw
                                                     │
                                                     ▼
                                          [ ROS 2 Middleware ]
                                                     │
                                                     ▼
                                      [ adapters/robot-bridge ]
                                          ├── HardwareAdapter (Watchdog, E-Stop, Mode Limits)
                                          ├── SafetyAdapter (Sensor health, Battery interlocks)
                                          ├── CommandHandler (Priority, Velocity routing)
                                          └── NavigationAdapter (Nav2 Action Client)
                                                     │
                                                     ▼
                                            [ VIRA EventBus ]
                                                     ▲
                                                     │
                                      [ graceemo_interaction Gateway ]
                                          (FastPath, Speech, State Machine)
```

### 5. Multi-Tier Safety & Watchdog Architecture
1. **Hardware Command Watchdog**:
   - The low-level `HardwareAdapter` checks command freshness at 50Hz.
   - If `/cmd_vel` or velocity requests cease for $> 300\text{ ms}$, the hardware adapter immediately writes 0.0 m/s to both wheels and halts locomotion.
2. **Physical E-Stop Circuit**:
   - Depressing the physical E-stop immediately breaks motor authority.
   - Releasing the physical switch **NEVER resumes motion automatically**; the state machine remains latched in `SAFE_IDLE` until an explicit software reset command is issued.
3. **Battery Voltage Interlock**:
   - $V > 11.5\text{ V}$: `NORMAL` status; all operations permitted.
   - $10.5\text{ V} \le V \le 11.5\text{ V}$: `LOW` status; visual/auditory warnings broadcast.
   - $V < 10.5\text{ V}$: `CRITICAL` status; hardware locomotion is unconditionally inhibited.
4. **Sensor Fault Lockout**:
   - If 2D LiDAR, IMU, or wheel odometry streams drop or report corrupt data ($NaN$, $Inf$, zero ranges), `SafetyAdapter` immediately rejects autonomous locomotion goals.
