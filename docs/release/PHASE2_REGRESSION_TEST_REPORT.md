# GRaCEmo ViRa — Phase 2 Release Engineering
# Document 02: Complete Regression Test Report

**Execution Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Working Repository:** `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`  
**Active Branch:** `feature/gracemo-unified-control-center`  
**Commit Under Test:** `f41b234c9c45ea0f055038ec15904df9eb3e85bb`  
**Test Environment:** Linux 6.8.0, Ubuntu 24.04 LTS (Noble), Python 3.12.3, ROS 2 Jazzy Jalisco, Gazebo Harmonic, PySide6 6.7  
**Hardware Safety Invariant:** Physical Actuation Locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`)  

---

## 1. Executive Summary

This report documents the exhaustive regression testing suite executed against the feature branch commit `f41b234`. The regression suite encompasses ROS 2 workspace compilation, command arbitration, velocity pipeline smoother and collision monitoring, ROS bridge translation, PySide6 UARCC engineering console operations, social interaction behavior FSM, kinematic URDF validation, launch description execution, Python syntax verification, and package dependency audits.

A total of **65 automated tests** were executed across 6 test suites with **100% PASS** rate (65 passed, 0 failed, 0 skipped).

---

## 2. Regression Results Matrix

| # | Test Category | Target Component | Exact Command Executed | Tests | Result | Duration | Status |
| :-: | :--- | :--- | :--- | :-: | :-: | :-: | :-: |
| **1** | **ROS 2 Workspace Build** | All 5 workspace packages | `colcon build --symlink-install` | 5 pkgs | 5/5 Built | 1.18s | **PASS** |
| **2** | **ROS Bridge Tests** | Interaction bridge node | `pytest -v tests/ros2/test_interaction_bridge.py` | 5 | 5 Passed | 0.44s | **PASS** |
| **3** | **Command Mux Tests** | Priority arbitration & timeout | `pytest -v tests/ros2/test_velocity_pipeline_and_mux.py -k Mux` | 6 | 6 Passed | 0.18s | **PASS** |
| **4** | **Velocity Pipeline Tests** | Smoother, collision, hardware launch | `pytest -v tests/ros2/test_velocity_pipeline_and_mux.py -k Pipeline` | 4 | 4 Passed | 0.12s | **PASS** |
| **5** | **UARCC Engineering Suite** | 11 UI modules, event bus, safety watchdog | `QT_QPA_PLATFORM=offscreen pytest -v gracemo_control_center/tests/test_uarcc_comprehensive.py` | 30 | 30 Passed | 1.99s | **PASS** |
| **6** | **Interaction Engine Suite** | FSM, Behavior, Voice Pipeline | `pytest -v tests/unit/test_human_interaction_behavior.py tests/unit/test_interaction_fsm.py tests/integration/test_interaction_pipeline.py` | 20 | 20 Passed | 0.13s | **PASS** |
| **7** | **URDF / Xacro Validation** | Kinematic tree & CAD meshes | `xacro gracemo_vira.urdf.xacro \| check_urdf /dev/stdin` | 17 links | Parsed XML | 0.52s | **PASS** |
| **8** | **Launch Description Validation** | Gazebo, Hardware, Nav2, Navigation | Python AST & runtime entity tree generator | 4 launch | 45 entities | 0.38s | **PASS** |
| **9** | **Python Syntax Compilation** | Workspace Python sources | `python3 -m py_compile [sources]` | 13 files | 0 syntax err | 0.22s | **PASS** |
| **10**| **Package Dependency Audit** | Colcon & rosdep dependency trees | `rosdep check --from-paths ros2_ws/src` | 5 pkgs | System valid | 0.40s | **PASS (Obs)**|

---

## 3. Detailed Execution Logs

### 3.1 ROS 2 Colcon Build
```text
Summary: 5 packages finished [1.18s]
- gracemo_description: Built and installed (0.20s)
- gracemo_bridge: Built and installed (0.19s)
- gracemo_hardware: Built and installed (1.10s)
- gracemo_gazebo: Built and installed (0.07s)
- gracemo_nav2: Built and installed (0.07s)
```

### 3.2 Velocity Pipeline & Command Mux (`test_velocity_pipeline_and_mux.py`)
```text
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_01_no_input_safe_zero PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_02_nav_only_arbitration PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_03_teleop_only_arbitration PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_04_teleop_preempts_nav_priority PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_05_teleop_timeout_fallback_to_nav PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestCommandVelocityMux::test_06_both_timeout_safe_stop PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestVelocityPipelineConfiguration::test_07_nav2_params_smoother_and_collision_blocks PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestVelocityPipelineConfiguration::test_08_hardware_launch_stale_package_remediated PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestVelocityPipelineConfiguration::test_09_navigation_launch_remappings PASSED
tests/ros2/test_velocity_pipeline_and_mux.py::TestVelocityPipelineConfiguration::test_10_exploration_scripts_use_teleop PASSED
============================== 10 passed in 0.30s ==============================
```

### 3.3 ROS 2 Interaction Bridge (`test_interaction_bridge.py`)
```text
tests/ros2/test_interaction_bridge.py::TestInteractionBridgeNode::test_closed_loop_odometry_arrival PASSED
tests/ros2/test_interaction_bridge.py::TestInteractionBridgeNode::test_emergency_stop_halts_cmd_vel PASSED
tests/ros2/test_interaction_bridge.py::TestInteractionBridgeNode::test_greeting_command_via_ros_topic PASSED
tests/ros2/test_interaction_bridge.py::TestInteractionBridgeNode::test_initial_state_and_topics PASSED
tests/ros2/test_interaction_bridge.py::TestInteractionBridgeNode::test_navigation_dispatch_and_goal_pose PASSED
============================== 5 passed in 0.44s ===============================
```

### 3.4 UARCC Desktop Control Center Suite (`test_uarcc_comprehensive.py`)
```text
30/30 passed in 1.99s. All criteria validated:
- Application startup and graceful shutdown
- ROS disconnection & reconnection handling
- Sensor freshness decay & watchdog alerts
- Camera, depth, LiDAR polar-to-cartesian projection
- Nav2 action dispatch, cancel, goal acceptance, arrival
- Fail-safe emergency stop zeroing
- Collision monitor and terrain monitor telemetry
- Independent Pygame avatar operation
- Hardware safety invariant persistence: MOTOR_OUTPUT_ENABLED = 0, PROTOCOL_CONFIRMED = False
```

### 3.5 Interaction Behavior and State Machine Suite
```text
tests/unit/test_human_interaction_behavior.py: 9 passed
tests/unit/test_interaction_fsm.py: 6 passed
tests/integration/test_interaction_pipeline.py: 5 passed
============================== 20 passed in 0.13s ==============================
```

### 3.6 Kinematic Parser (`check_urdf`)
```text
robot name is: gracemo_vira
---------- Successfully Parsed XML ---------------
root Link: base_footprint has 1 child(ren) -> 17 links validated
```

### 3.7 Launch Description Evaluation
```text
OK: ros2_ws/src/gracemo_gazebo/launch/vira_complete.launch.py -> 9 entities
OK: ros2_ws/src/gracemo_hardware/launch/hardware.launch.py -> 20 entities
OK: ros2_ws/src/gracemo_nav2/launch/nav2.launch.py -> 5 entities
OK: ros2_ws/src/gracemo_nav2/launch/navigation_launch.py -> 11 entities
```

---

## 4. Observations & Environment Notes

1. **Classic Gazebo rosdep tags:** In Ubuntu 24.04 (Noble) with ROS 2 Jazzy, Gazebo Harmonic uses the modern `ros_gz_sim` and `ros_gz_bridge` packages. Legacy `gazebo_ros` tags in `gracemo_description/package.xml` are superseded by ROS 2 Jazzy `ros_gz` packages and do not affect build or runtime execution.
2. **Deterministic Mock vs Runtime Simulation:** Unit and pipeline tests verify arbitration timing, safety latching, and message routing deterministically without requiring physical robot actuation or live hardware.

---

## 5. Verdict

**STAGE B REGRESSION TESTING PASSED.** 65/65 automated tests passed with 0 failures, 0 regressions, and full hardware isolation.
