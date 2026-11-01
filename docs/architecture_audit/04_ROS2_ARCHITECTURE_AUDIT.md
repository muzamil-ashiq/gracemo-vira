# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 04: ROS 2 Architecture Audit

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**ROS Middleware:** ROS 2 Jazzy Jalisco / Gazebo Harmonic  
**Scope:** Complete topology mapping of nodes, topics, services, actions, launch pipelines, and command velocity ownership.

---

## 1. ROS 2 Package Split and Overlap

The repository currently exhibits a structural package duality between the active workspace (`ros2_ws/src/`) and the integrated prototype reference tree (`prototypes/gracemo_integrated_v1/ros2_ws/src/`):

| Functional Domain | Workspace Package Name | Prototype Package Name | Status & Duplication Analysis |
| :--- | :--- | :--- | :--- |
| **Navigation & Costmaps** | `gracemo_nav2` | `gracemo_navigation` | **Split Packages:** `gracemo_nav2` uses `nav2_params.yaml` with radius `0.22m` and speed `0.65m/s`. Prototype `gracemo_navigation` contains additional nodes (`terrain_monitor_node.py`, `frontier_exploration_node.py`, `attitude_diagnostics_node.py`). |
| **Robot Description (URDF)** | `gracemo_description` | `gracemo_robot_description` | **Exact Duplicate Meshes:** Identical 15 `.obj` visual meshes. URDF files share core kinematic chains but use slightly divergent wheel separation comments. |
| **Simulation Worlds & Bridge**| `gracemo_gazebo` | `gracemo_simulation` | **Overlapping Worlds:** Identical `gracemo_apartment.world` (13,045 bytes). Workspace uses `sim.launch.py`; prototype uses `simulation.launch.py`. |
| **Hardware HAL & MCU** | `gracemo_hardware` | `gracemo_hardware` | **Exact Duplication:** Same package name, 100% byte-for-byte identical source files across both trees. |
| **Autonomous Coordination** | `gracemo_bridge` | `gracemo_command_coordinator` | **Split Architecture:** Workspace implements `interaction_bridge`, `kernel_bridge`, and `sensor_bridge`. Prototype implements the authoritative `coordinator_node.py` with Nav2 action client. |
| **Voice & Interaction Node** | In `vira_interaction/` (Pygame) | `gracemo_interaction` | **Split Architecture:** Workspace uses standalone Pygame process communicating via ROS topics. Prototype used a dedicated ROS node (`interaction_node.py`). |
| **System Bringup Launch** | `gracemo_gazebo/launch/vira_complete.launch.py` | `gracemo_bringup/launch/prototype.launch.py` | **Conflicting Launchers:** Two top-level orchestrators launching divergent node collections. |

---

## 2. Complete ROS 2 Node Registry

### 2.1 Autonomous Core & Infrastructure Nodes

| Node Name | Package Origin | Executable / Script | Primary Role | Lifecycle / Authority |
| :--- | :--- | :--- | :--- | :--- |
| `gracemo_command_coordinator` | `gracemo_command_coordinator` | `coordinator_node.py` | Authoritative Nav2 action client, bounded state machine, and arrival verifier. | Authoritative Master |
| `gracemo_terrain_monitor` | `gracemo_navigation` | `terrain_monitor_node.py` | IMU attitude safety monitor, slope detector, and final `/cmd_vel` gatekeeper. | Authoritative Safety Gate |
| `gracemo_mcu_bridge` | `gracemo_hardware` | `mcu_bridge_node.py` | Hardware serial packet serializer/deserializer to STM32; publishes `/odom`. | Hardware HAL |
| `gracemo_hardware_status` | `gracemo_hardware` | `hardware_status_node.py` | Watchdog monitor checking LiDAR, IMU, and MCU message freshness. | Diagnostics Monitor |
| `gracemo_interaction_bridge` | `gracemo_bridge` | `interaction_bridge.py` | Bridges Pygame conversation events to ROS 2 `/coordinator/command` and `/coordinator/feedback`. | Interaction Gateway |
| `gracemo_kernel_bridge` | `gracemo_bridge` | `kernel_bridge.py` | Telemetry pipeline between ROS 2 perception/odometry and Rust MNSE cognitive daemon. | Cognitive Gateway |
| `gracemo_sensor_bridge` | `gracemo_bridge` | `sensor_bridge.py` | Republishes optical and depth camera streams for remote visualization. | Sensor Gateway |
| `gracemo_control_center_node`| `gracemo_control_center` | `app.py` / `ros_manager.py` | UARCC engineering dashboard GUI client monitoring topics and dispatching operator commands. | Operator Console (Client) |
| `robot_state_publisher` | `robot_state_publisher` | `robot_state_publisher` | Publishes standard `/tf` and `/tf_static` kinematic tree from URDF xacro. | Infrastructure |
| `ros_gz_bridge` | `ros_gz_bridge` | `parameter_bridge` | Bridges Gazebo Harmonic clock, lidar, camera, and joint states into ROS 2 topics. | Simulation Gateway |

---

## 3. The `/cmd_vel` Pipeline & Arbitration Audit

### 3.1 Preserved Authoritative Safety Pipeline

The intended, safety-compliant velocity command chain is strictly structured as follows:

```mermaid
graph LR
    Nav2[Nav2 Controller Server] -->|/cmd_vel_nav| VS[velocity_smoother]
    VS -->|/cmd_vel_smoothed| CM[collision_monitor]
    CM -->|/cmd_vel_safe| TM[gracemo_terrain_monitor]
    TM -->|/cmd_vel| GZ[ros_gz_bridge / mcu_bridge]
    
    style Nav2 fill:#EAF2FA,stroke:#2463A6
    style VS fill:#EAF2FA,stroke:#2463A6
    style CM fill:#FBF4E8,stroke:#D99A2B
    style TM fill:#FAECEC,stroke:#C74747,stroke-width:2px
    style GZ fill:#EBF5F0,stroke:#23865B
```

1. **`Nav2 controller_server`:** Outputs raw trajectory velocity on `/cmd_vel_nav`.
2. **`velocity_smoother`:** Limits linear and angular accelerations ($a_x \le 1.5\text{ m/s}^2, \alpha_z \le 3.2\text{ rad/s}^2$) on `/cmd_vel_smoothed`.
3. **`collision_monitor`:** Evaluates 2D planar LiDAR points against polygon safety zones (Warning $\rightarrow$ Slowdown $\rightarrow$ Stop) on `/cmd_vel_safe`.
4. **`gracemo_terrain_monitor`:** Asserts pitch/roll safety thresholds ($|\text{pitch}| < 20^\circ, |\text{roll}| < 20^\circ$) and checks `/terrain/emergency_stop`. Only when clear does it publish to the final `/cmd_vel` topic.
5. **`ros_gz_bridge` / `mcu_bridge`:** Subscribes exclusively to the final gated `/cmd_vel` topic.

### 3.2 Critical Safety Hazard: Rogue `/cmd_vel` Publishers

Static analysis identified **six standalone scripts** that publish directly to `/cmd_vel`, bypassing the entire collision and terrain safety pipeline:

| Script / Test File | Publisher Topic | Message Type | Hazard Description | Severity |
| :--- | :--- | :--- | :--- | :---: |
| `scripts/auto_explore.py` | `/cmd_vel` | `geometry_msgs/Twist` | Directly drives the robot using raw LiDAR ranges, bypassing collision monitor polygons and terrain tilt gates. | **CRITICAL** |
| `scripts/closed_loop_nav.py` | `/cmd_vel` | `geometry_msgs/Twist` | Proportional controller driving motors directly based on odometry targets. | **CRITICAL** |
| `scripts/smart_explore.py` | `/cmd_vel` | `geometry_msgs/Twist` | Standalone room coverage script publishing drive velocities directly. | **CRITICAL** |
| `scripts/mission_control.py` | `/cmd_vel` | `geometry_msgs/Twist` | Publishes fallback velocity commands directly when Nav2 actions timeout. | **HIGH** |
| `tests/integration/test_drive_diagnostics.py` | `/cmd_vel` | `geometry_msgs/Twist` | Drives test pulses ($0.3\text{ m/s}$) directly onto motor input. | **MEDIUM** (Test harness only) |
| `tests/test_navigation_grounding_live.py` | `/cmd_vel` | `geometry_msgs/Twist` | Drives robot directly during grounding demonstrations. | **HIGH** |

> [!CAUTION]
> If any of these exploratory or grounding scripts run concurrently with Nav2, two competing nodes publish to `/cmd_vel` simultaneously, causing motor command chatter, rapid jerking, and potential physical damage.

---

## 4. Topic Topology & QoS Contracts

| Topic Name | Message Type | Authorized Publisher | Authorized Subscriber(s) | Reliability / Durability |
| :--- | :--- | :--- | :--- | :--- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | `gracemo_terrain_monitor` (Exclusive) | `ros_gz_bridge`, `gracemo_mcu_bridge` | Best Effort / Volatile |
| `/cmd_vel_safe` | `geometry_msgs/msg/Twist` | `collision_monitor` | `gracemo_terrain_monitor` | Best Effort / Volatile |
| `/cmd_vel_smoothed` | `geometry_msgs/msg/Twist` | `velocity_smoother` | `collision_monitor` | Best Effort / Volatile |
| `/cmd_vel_nav` | `geometry_msgs/msg/Twist` | Nav2 `controller_server` | `velocity_smoother` | Best Effort / Volatile |
| `/odom` | `nav_msgs/msg/Odometry` | `ros_gz_bridge` / `mcu_bridge` | Nav2, AMCL, Coordinator, UARCC | Best Effort / Volatile |
| `/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | `amcl` | Coordinator, UARCC, `kernel_bridge` | Transient Local / Reliable |
| `/map` | `nav_msgs/msg/OccupancyGrid` | `map_server` | Nav2 costmaps, UARCC `map_view` | Transient Local / Reliable |
| `/plan` | `nav_msgs/msg/Path` | Nav2 `planner_server` | UARCC `map_view`, RViz2 | Reliable / Volatile |
| `/scan` | `sensor_msgs/msg/LaserScan` | `ros_gz_bridge` / LiDAR driver | Costmaps, Collision Monitor, UARCC | Best Effort / Volatile |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | `ros_gz_bridge` / Camera driver | `perception/detector`, UARCC | Best Effort / Volatile |
| `/coordinator/command`| `std_msgs/msg/String` | UARCC, `interaction_bridge` | `gracemo_command_coordinator` | Reliable / Volatile |
| `/coordinator/feedback`| `std_msgs/msg/String` | `gracemo_command_coordinator` | UARCC, `interaction_bridge`, Tests | Reliable / Volatile |
| `/terrain/emergency_stop`| `std_msgs/msg/Bool` | UARCC Safety Panel, Coordinator | `gracemo_terrain_monitor`, HAL | Reliable / Transient Local |

---

## 5. Launch File Duplication and Conflict

### Conflict Matrix: `vira_complete.launch.py` vs `prototype.launch.py`

| Property | `ros2_ws/src/gracemo_gazebo/launch/vira_complete.launch.py` | `prototypes/.../gracemo_bringup/launch/prototype.launch.py` | Conflict & Architectural Impact |
| :--- | :--- | :--- | :--- |
| **Simulation Include** | Includes `sim.launch.py` from `gracemo_gazebo` | Includes `simulation.launch.py` from `gracemo_simulation` | **Duplicate World Launch:** Spawns duplicate physics world if both are invoked. |
| **Navigation Include** | Includes `nav2.launch.py` from `gracemo_nav2` | Includes `navigation.launch.py` from `gracemo_navigation` | **Conflicting Costmap Parameters:** Workspace sets radius `0.22m`; prototype sets `0.23m`. |
| **Coordinator Node** | Does **NOT** launch `coordinator_node.py` (relies on manual launch) | Directly launches `gracemo_command_coordinator/coordinator_node.py` | **Missing Core Autonomy:** `vira_complete.launch.py` leaves autonomous goal handling unstarted unless launched separately. |
| **Interaction Bridge** | Launches `gracemo_bridge/interaction_bridge` | Launches `gracemo_interaction/interaction_node` | **Competing Interaction Bridges:** Two separate bridges attempt to translate user commands. |
