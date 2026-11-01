# GRaCEmo ViRa — Velocity Pipeline Remediation Report
# Document 17: Velocity Safety Chain & Command Arbitration Architecture

**Remediation Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Working Repository:** `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`  
**Branch:** `feature/gracemo-unified-control-center`  
**Safety Status:** Physical Actuation Locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`)  
**Status:** **TECHNICAL REMEDIATION COMPLETE — ALL 18 ACCEPTANCE CRITERIA SATISFIED**

---

## 1. Original Defects Identified in Pre-Commit Audit

During the independent pre-commit audit ([16_PRE_COMMIT_ACCEPTANCE_REPORT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/16_PRE_COMMIT_ACCEPTANCE_REPORT.md)), five critical velocity pipeline defects were uncovered:

1. **Defect A — Missing Velocity Smoother Configuration:**  
   `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` lacked the required `velocity_smoother` parameter block.
2. **Defect B — Missing Collision Monitor Configuration:**  
   `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` lacked the `collision_monitor` parameter block present in prototype v1.
3. **Defect C — Open-Circuit Velocity Topic:**  
   `terrain_monitor_node.py` subscribed to `/cmd_vel_safe`, but no active upstream node published to `/cmd_vel_safe`.
4. **Defect D — Dead-Ended Teleoperation:**  
   Exploration scripts (`auto_explore.py`, `closed_loop_nav.py`, `smart_explore.py`) published to `/cmd_vel_teleop`, but no active node consumed `/cmd_vel_teleop`.
5. **Defect E — Stale Hardware Launch Package References:**  
   `hardware.launch.py` referenced retired prototype packages `gracemo_command_coordinator`, `gracemo_navigation`, and `gracemo_robot_description`.

---

## 2. Root Cause Analysis

- When prototype packages were consolidated into `ros2_ws/src/`, `nav2_params.yaml` was migrated without copying the `velocity_smoother` and `collision_monitor` blocks from `gracemo_navigation`.
- In ROS 2 Nav2 Jazzy, `velocity_smoother` expects a single command stream (`cmd_vel`). Directly piping two separate command streams (`/cmd_vel_nav` and `/cmd_vel_teleop`) into `velocity_smoother` without arbitration was impossible without a dedicated command multiplexer.
- As a result, changing exploration scripts to publish to `/cmd_vel_teleop` prevented raw injection into `/cmd_vel` but dead-ended the teleoperation commands.

---

## 3. Previous Architecture vs Implemented Architecture

### Previous (Broken) Architecture
```text
NAV2 (controller_server) ──► /cmd_vel_nav (unconnected)
TELEOP / EXPLORATION ──────► /cmd_vel_teleop (unconnected)
                             (missing smoother & collision monitor)
                             /cmd_vel_safe (unconnected) ──► TERRAIN_MONITOR ──► /cmd_vel ──► SENSOR_BRIDGE
```

### Remediated Authoritative Architecture
```text
                    NAV2
                      │
                /cmd_vel_nav
                      │
                      ▼
              ┌────────────────┐
              │  COMMAND MUX   │ ◄─── /cmd_vel_teleop (TELEOP / EXPLORATION)
              │ / ARBITER      │
              └────────────────┘
                      │
                /cmd_vel_mux
                      │
                      ▼
             VELOCITY_SMOOTHER
                      │
                      ▼
               /cmd_vel_smoothed
                      │
                      ▼
              COLLISION_MONITOR
                      │
                      ▼
                 /cmd_vel_safe
                      │
                      ▼
               TERRAIN_MONITOR
                      │
                      ▼
                  /cmd_vel
                      │
                      ▼
                ROS GZ BRIDGE (sensor_bridge)
                      │
                      ▼
                 SIMULATION / GAZEBO HARMONIC
```

---

## 4. Command Velocity Multiplexer (`cmd_vel_mux_node.py`)

A minimal, dedicated ROS 2 node was implemented in `gracemo_nav2`:
- **File:** `ros2_ws/src/gracemo_nav2/gracemo_nav2/cmd_vel_mux_node.py`
- **Class:** `CommandVelocityMuxNode`
- **Subscribed Topics:**
  - `/cmd_vel_teleop` (`geometry_msgs/Twist`): High priority (teleoperation & exploration scripts).
  - `/cmd_vel_nav` (`geometry_msgs/Twist`): Low priority (autonomous Nav2 path tracking).
- **Published Topics:**
  - `/cmd_vel_mux` (`geometry_msgs/Twist`): Output unified command stream to `velocity_smoother`.
  - `/cmd_vel_mux/status` (`std_msgs/String`): Diagnostic JSON telemetry.
- **Arbitration Protocol:**
  - **Teleoperation Priority:** When `/cmd_vel_teleop` has published within `teleop_timeout_sec` (0.5s), it preempts `/cmd_vel_nav` immediately.
  - **Autonomous Fallback:** When teleoperation ceases for $>0.5\text{ s}$, the arbiter seamlessly falls back to `/cmd_vel_nav` if active.
  - **Safe-Zero Command:** When neither source is active or both time out, the node publishes a safe zero-velocity `Twist()` command to halt the robot and holds zero state.
  - **Deterministic Diagnostics:** Reports active owner (`TELEOP`, `NAV`, `NONE`), source ages, and latch state at 5 Hz.

---

## 5. End-to-End Topic Mapping

| Pipeline Stage | Input Topic | Node / Component | Output Topic | Safety Gate / Function |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1A: Autonomous** | Nav2 Goal | `controller_server` / `behavior_server` | `/cmd_vel_nav` | DWB local planner path following |
| **Stage 1B: Teleoperation** | Joystick / Scripts | Teleop / Exploration Scripts | `/cmd_vel_teleop` | Manual intervention / exploration |
| **Stage 2: Arbitration** | `/cmd_vel_nav`<br>`/cmd_vel_teleop` | `cmd_vel_mux` (`cmd_vel_mux_node.py`) | `/cmd_vel_mux` | Teleop priority, timeout fallback, zero halt |
| **Stage 3: Smoothing** | `/cmd_vel_mux` | `velocity_smoother` (`nav2_velocity_smoother`) | `/cmd_vel_smoothed` | Accel/decel ramp limits ($2.5\text{ m/s}^2$) |
| **Stage 4: Collision** | `/cmd_vel_smoothed` | `collision_monitor` (`nav2_collision_monitor`) | `/cmd_vel_safe` | 2D LiDAR polygon bubble slowdown/stop |
| **Stage 5: Terrain Authority**| `/cmd_vel_safe` | `terrain_monitor` (`terrain_monitor_node.py`) | `/cmd_vel` | IMU roll/pitch slope clamp, E-stop latch |
| **Stage 6: Simulation** | `/cmd_vel` | `sensor_bridge` (`gracemo_bridge`) | Gazebo Harmonic `diff_drive` | Physical physics simulation |

---

## 6. Configuration Enhancements in `nav2_params.yaml`

Added authoritative configurations to `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml`:

```yaml
velocity_smoother:
  ros__parameters:
    use_sim_time: True
    smoothing_frequency: 20.0
    scale_velocities: False
    feedback: "OPEN_LOOP"
    max_velocity: [0.5, 0.0, 1.5]
    min_velocity: [-0.5, 0.0, -1.5]
    max_accel: [2.5, 0.0, 3.2]
    max_decel: [-2.5, 0.0, -3.2]
    odom_topic: "odom"
    odom_duration: 0.1
    deadband_velocity: [0.0, 0.0, 0.0]
    velocity_timeout: 0.5

collision_monitor:
  ros__parameters:
    use_sim_time: True
    base_frame_id: "base_footprint"
    odom_frame_id: "odom"
    cmd_vel_in_topic: "cmd_vel_smoothed"
    cmd_vel_out_topic: "cmd_vel_safe"
    state_topic: "collision_monitor_state"
    transform_tolerance: 0.5
    source_timeout: 2.0
    base_shift_correction: True
    stop_pub_timeout: 2.0
    polygons: ["FootprintApproach"]
    FootprintApproach:
      type: "polygon"
      action_type: "approach"
      footprint_topic: "/local_costmap/published_footprint"
      time_before_collision: 0.20
      simulation_time_step: 0.1
      min_points: 6
      visualize: False
      enabled: True
    observation_sources: ["scan"]
    scan:
      type: "scan"
      topic: "/scan"
      min_height: 0.05
      max_height: 2.0
      enabled: True

cmd_vel_mux:
  ros__parameters:
    use_sim_time: True
    teleop_topic: "/cmd_vel_teleop"
    nav_topic: "/cmd_vel_nav"
    mux_topic: "/cmd_vel_mux"
    status_topic: "/cmd_vel_mux/status"
    teleop_timeout_sec: 0.5
    nav_timeout_sec: 0.5
    publish_rate_hz: 20.0
```

---

## 7. Launch Architecture Remediation

1. **`ros2_ws/src/gracemo_nav2/launch/navigation_launch.py`:**
   - Added authoritative Nav2 lifecycle launch with `velocity_smoother` remapped to `/cmd_vel_mux`.
   - `controller_server` and `behavior_server` remapped to `/cmd_vel_nav`.
   - `collision_monitor` included as managed lifecycle node.
2. **`ros2_ws/src/gracemo_nav2/launch/nav2.launch.py`:**
   - Includes `gracemo_nav2/launch/navigation_launch.py`.
   - Launches `cmd_vel_mux_node.py` with parameters from `nav2_params.yaml`.
3. **`ros2_ws/src/gracemo_hardware/launch/hardware.launch.py`:**
   - Stale package references resolved:
     - `gracemo_navigation` $\longrightarrow$ `gracemo_nav2`
     - `gracemo_robot_description` $\longrightarrow$ `gracemo_description`
     - `gracemo_command_coordinator` $\longrightarrow$ `gracemo_nav2` / `coordinator_node.py`
     - Default maps/params updated to `physical_lab_map.yaml` and `nav2_physical_params.yaml`.

---

## 8. Test Execution & Evidence

### Test Suite Execution
- **Unit & Pipeline Tests:** `tests/ros2/test_velocity_pipeline_and_mux.py` (10 tests)
  - `test_01_no_input_safe_zero`: **PASS**
  - `test_02_nav_only_arbitration`: **PASS**
  - `test_03_teleop_only_arbitration`: **PASS**
  - `test_04_teleop_preempts_nav_priority`: **PASS**
  - `test_05_teleop_timeout_fallback_to_nav`: **PASS**
  - `test_06_both_timeout_safe_stop`: **PASS**
  - `test_07_nav2_params_smoother_and_collision_blocks`: **PASS**
  - `test_08_hardware_launch_stale_package_remediated`: **PASS**
  - `test_09_navigation_launch_remappings`: **PASS**
  - `test_10_exploration_scripts_use_teleop`: **PASS**
- **Interaction Bridge Tests:** `tests/ros2/test_interaction_bridge.py` (5 tests) — **5/5 PASS**
- **UARCC Engineering Console Suite:** `gracemo_control_center/tests/test_uarcc_comprehensive.py` (30 tests) — **30/30 PASS**
- **Colcon Build:** All 5 workspace packages build cleanly in 1.60s with 0 warnings.
- **URDF Validation:** `xacro gracemo_vira.urdf.xacro | check_urdf` parsed 100% of links and joints.
- **Launch File Generation:** `nav2.launch.py` (5 entities), `vira_complete.launch.py` (9 entities), and `hardware.launch.py` (20 entities) all generate without error.

---

## 9. Safety Invariants & Physical Measurement Constraints

1. **Hardware Safety Locks:**
   - `MOTOR_OUTPUT_ENABLED = 0` (Confirmed active and locked).
   - `SerialMCUTransport.PROTOCOL_CONFIRMED = False` (Confirmed fail-closed).
2. **Velocity Limits:**
   - Hardware fail-safe clamp: $\le 0.35\text{ m/s}$ linear, $\le 0.75\text{ rad/s}$ angular.
   - Simulation velocity ceiling: $0.50\text{ m/s}$ linear, $1.50\text{ rad/s}$ angular.
3. **Unverified Physical Dimension:**
   - `wheel_separation_m` remains annotated as `[UNVERIFIED CONFLICT]` (0.34m in URDF vs 0.32m in `robot.yaml`). Physical caliper measurement is mandatory prior to live hardware power-on.

---

## 10. Rollback Instructions

Should rollback be required:
```bash
# Revert to pre-consolidation checkpoint:
git checkout backup/pre-consolidation-checkpoint -- ros2_ws/src/gracemo_nav2 ros2_ws/src/gracemo_hardware
```
