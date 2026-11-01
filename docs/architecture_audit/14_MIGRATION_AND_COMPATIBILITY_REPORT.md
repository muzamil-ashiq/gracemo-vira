# GRaCEmo ViRa — Migration and Compatibility Report
# Document 14: Subsystem Migration & Interface Compatibility

**Consolidation Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Status:** Verification of Backward Compatibility & Migration Integrity

---

## 1. Executive Summary

This report documents the migration of critical prototype nodes, launch entry points, and interfaces into the canonical repository architecture. The consolidation achieved 100% preservation of functional capabilities while eliminating redundant packages, duplicate meshes, and competing direct-drive controllers.

All external ROS 2 topic contracts, action server definitions, and HTTP APIs remain strictly preserved and backwards-compatible.

---

## 2. Subsystem Migration Details

### 2.1 Autonomous Navigation Coordinator
- **Previous Location:** `~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_command_coordinator/`
- **Canonical Location:** `ros2_ws/src/gracemo_nav2/gracemo_nav2/coordinator_node.py`
- **Executable Alias:** Installed as `gracemo_coordinator` via `ros2_ws/src/gracemo_nav2/CMakeLists.txt`.
- **Interface Compatibility:**
  - Subscribes to `/coordinator/command` (`std_msgs/msg/String`)
  - Publishes to `/coordinator/feedback` (`std_msgs/msg/String`)
  - Sends Nav2 Action Goals to `/navigate_to_pose` (`nav2_msgs/action/NavigateToPose`)
- **Compatibility Status:** Fully verified; seamless drop-in for UARCC and automated test runners.

### 2.2 Terrain Safety Gate (Inclinometer)
- **Previous Location:** `~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_navigation/scripts/terrain_monitor_node.py`
- **Canonical Location:** `ros2_ws/src/gracemo_nav2/gracemo_nav2/terrain_monitor_node.py`
- **Executable Alias:** Installed as `terrain_monitor` via `ros2_ws/src/gracemo_nav2/CMakeLists.txt`.
- **Interface Compatibility:**
  - Subscribes to `/imu/data` (`sensor_msgs/msg/Imu`)
  - Subscribes to `/cmd_vel_collision` (or smoothed velocity)
  - Publishes to final hardware/simulation `/cmd_vel` (`geometry_msgs/msg/Twist`)
  - Serves Emergency Stop topic `/terrain/emergency_stop`
- **Compatibility Status:** Integrated directly into the canonical velocity pipeline.

### 2.3 Consolidated Launch Architecture
- **Previous State:** Fragmented across multiple independent launchers (`sim.launch.py`, `navigation.launch.py`, `coordinator.launch.py`).
- **Canonical Location:** `ros2_ws/src/gracemo_gazebo/launch/vira_complete.launch.py`
- **Components Orchestrated:**
  1. Gazebo Harmonic Apartment Simulation & World Physics
  2. Robot State Publisher (`gracemo_description`)
  3. ROS-Gz Bridge for camera, LiDAR, IMU, clock, and odometry
  4. Nav2 Stack with AMCL localization and costmaps (`gracemo_nav2`)
  5. Terrain Safety Monitor Node
  6. Autonomous Command Coordinator Node
- **Compatibility Status:** Single authoritative launch command brings up the complete verified stack.

---

## 3. Interface Compatibility Matrix

| Interface Identifier | Type / Protocol | Canonical Publisher / Owner | Canonical Subscriber / Client | Compatibility Status |
| :--- | :--- | :--- | :--- | :--- |
| `/cmd_vel_teleop` | `geometry_msgs/Twist` | UARCC Manual Teleop, Exploration Scripts | Nav2 `velocity_smoother` | **Preserved:** Gated through smoother and collision monitor. |
| `/cmd_vel` | `geometry_msgs/Twist` | `terrain_monitor_node` | Gazebo ROS-Gz Bridge / MCU Transport | **Preserved:** Single-owner pipeline. |
| `/coordinator/command` | `std_msgs/String` | UARCC Mission Control / Scripts | `coordinator_node` | **Preserved:** Full JSON command schema supported. |
| `/coordinator/feedback`| `std_msgs/String` | `coordinator_node` | UARCC Mission Control, Interaction Bridge | **Preserved:** JSON status updates (`NAVIGATING`, `ARRIVED`, `FAILED`). |
| `/scan` | `sensor_msgs/LaserScan`| Gazebo LiDAR Bridge / SLLidar | Nav2 Costmaps, Collision Monitor, UARCC | **Preserved:** 360-sample planar scan. |
| `/camera/image_raw` | `sensor_msgs/Image` | Gazebo Camera Bridge | YOLO Perception, UARCC Camera View | **Preserved:** RGB8 640x480 frame format. |
| `/terrain/emergency_stop`| `std_msgs/Bool` | UARCC Safety View, E-Stop Button | `terrain_monitor_node` | **Preserved:** Immediate zero-velocity latch. |
| Cognitive HTTP API | HTTP REST (Port 7780) | Rust Kernel (`gracemo-kernel`) | UARCC Cognitive View, Python Reasoner | **Preserved:** Standardized on port 7780. |

---

## 4. Regression Prevention Strategy

1. **Colcon Symlink Installation:** Clean isolation of Python executables in `ros2_ws/install/`.
2. **Automated Unit & Integration Tests:** 30 UARCC suite tests and 5 ROS 2 bridge tests run on every pull request.
3. **Safety Clamp Locking:** Firmware invariants cannot be toggled via GUI or scripts; requires manual engineer sign-off.
