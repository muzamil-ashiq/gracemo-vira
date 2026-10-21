# Simulation / Hardware Parity Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. Parity Philosophy
To prevent software divergence between development environments (e.g. macOS workstations, CI runners) and physical hardware deployments (Linux / ROS 2 Jazzy onboard compute), GRaCEmo ViRa establishes a strict configuration boundary:

```bash
VIRA_MODE=simulation   # Local kinematic simulation or Gazebo Harmonic
VIRA_MODE=hardware     # Physical robot base with CAN/Serial motor drivers
```

The interaction tier, cognitive brain, event contracts, safety gate rules, and command validators are **100% identical** across both modes. Only the low-level motor actuation backend changes.

---

### 2. Contract Equivalence Matrix

| Layer | `VIRA_MODE=simulation` | `VIRA_MODE=hardware` | Parity Guarantee |
|---|---|---|---|
| **Dialogue & Brain** | `InteractionGateway` / `FastPathMatcher` | `InteractionGateway` / `FastPathMatcher` | **Identical** |
| **Safety Validation** | `SafetyGate` & `SafetyAdapter` | `SafetyGate` & `SafetyAdapter` | **Identical** ($[-100, 100]$ bounds, battery interlock, $< 3\text{ s}$ freshness) |
| **Command Envelope** | `contracts/robot-command.schema.json` | `contracts/robot-command.schema.json` | **Identical** |
| **Event Envelope** | `contracts/event-envelope.schema.json` | `contracts/event-envelope.schema.json` | **Identical** (`trace_id` preserved across all events) |
| **Feedback Events** | `contracts/robot-event.schema.json` | `contracts/robot-event.schema.json` | **Identical** (`NavigationStarted`, `Progress`, `Arrived`, `Failed`) |
| **Actuator Authority** | Gazebo `/cmd_vel` (diff-drive plugin) | Base motor controller (differential drive) | Velocity saturation limits ($0.35\text{ m/s}, 0.75\text{ rad/s}$) |

---

### 3. Coordinate Frame & Sensor Parity

The physical sensor coordinate frames defined in [`ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro) strictly match the hardware sensor mounts:

| Frame Name | Sensor Type | Physical Position | Parity Verification |
|---|---|---|---|
| `base_footprint` | Robot Footprint | $(0.0, 0.0, 0.0)$ on ground plane | Ground contact reference |
| `base_link` | Chassis Center | $(0.0, 0.0, 0.05)$ above footprint | Mass center reference |
| `lidar_link` | 2D LiDAR | $(+0.12, 0.0, +0.18)$ | Matches 360° planar scanner |
| `imu_link` | 6-DOF IMU | $(0.0, 0.0, +0.08)$ | Aligned with rotational center |
| `camera_link` | RGB-D Optics Housing | $(+0.15, 0.0, +0.65)$ | Center of head display assembly |
| `camera_optical_link` | Optical Axis | Optical roll-pitch-yaw offsets | ROS optical standard (Z-forward, X-right) |

---

### 4. Continuous Integration & Cross-Platform Execution
- **macOS / Linux Host**: Full unit, contract, safety, navigation, and end-to-end integration tests execute natively using the high-fidelity kinematic backend in `RobotBridge`.
- **Docker Simulation Container**: Master launch file (`ros2 launch gracemo_gazebo vira_complete.launch.py`) executes Gazebo Harmonic, Nav2, and ROS 2 nodes under NVIDIA container runtime.
- **Physical Robot**: Launches physical sensor drivers (`sensor_bridge`), Nav2 costmaps, and `RobotBridge` bound to hardware serial ports with identical semantic command handling.
