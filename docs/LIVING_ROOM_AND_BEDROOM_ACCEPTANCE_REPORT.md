# GRaCEmo ViRa — Living Room & Bedroom Autonomous Navigation Engineering Report

**Role:** Principal ROS 2 Jazzy, Nav2, Gazebo Harmonic, and Autonomous Robotics Engineer  
**Workspace:** `~/projects/VIRA/prototypes/gracemo_integrated_v1`  
**ROS Workspace:** `~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws`  
**Test & Integration Workspace:** `~/projects/VIRA-agent-bridge-migration`  
**Platform:** Ubuntu 24.04 LTS | ROS 2 Jazzy Jalisco | Gazebo Harmonic 8.9.0 | NVIDIA RTX 5060 Laptop GPU  
**Date:** 2026-10-30  
**Status:** **PASSED & FULLY VERIFIED (Living Room Mission + Bedroom Long-Range Regression + 6-Stage Master Acceptance)**

---

## 1. Reproduction & Diagnostic Investigation of the Failure

### Observed Failure Modes in Historical Audits
1. **DDS Startup Race & Missing `/amcl_pose`:** Simultaneous initialization of localization and navigation lifecycle managers caused Fast-DDS discovery packet flooding. The `/map_server/change_state` transition timed out, leaving `map_server` inactive and `amcl` unconfigured. Stationary AMCL does not emit updates on default volatile subscriptions, causing test scripts to abort before navigation began.
2. **Missing Pre-Navigation Localization Readiness:** The coordinator transitioned directly from `VALIDATING_GOAL` to `PLANNING` without checking if the TF tree (`map -> odom -> base_footprint`) was connected. Nav2 rejected goals when costmaps timed out waiting for transforms.
3. **Narrow Corridor / Doorway Traversal Obstacle Trapping:** In previous configurations with continuous 1Hz replanning, when the robot entered narrow doorways ($1.3 - 1.4\text{m}$ width), transient cost inflation placed the robot center in a high-cost cell. SmacPlanner aborted with `"Start occupied"`, triggering recovery spins and backups into walls.
4. **Unreset Retry Counters:** In `coordinator_node.py`, `self.retry_count` was not reset upon receiving a new navigation goal. Once recovery was triggered on an earlier leg, subsequent goals immediately transitioned to `STATE_FAILED` with `"Path is completely blocked"` without attempting recovery.

### Detailed Telemetry Recorded During Controlled Diagnostics

| Parameter | Living Room Run 1 | Living Room Run 2 (From Bedroom) | Bedroom Regression Run |
| :--- | :--- | :--- | :--- |
| **Initial Pose** | $(0.000, 0.000, 0.0^\circ)$ | $(-4.805, 2.112, 119.4^\circ)$ | $(4.068, -2.226, -94.4^\circ)$ |
| **Requested Goal** | $(4.00, -2.50, 0.0^\circ)$ | $(4.00, -2.50, 0.0^\circ)$ | $(-5.00, 2.20, 0.0^\circ)$ |
| **Goal Frame** | `map` | `map` | `map` |
| **Nav2 Action Result** | `STATUS_SUCCEEDED` | `STATUS_SUCCEEDED` | `STATUS_SUCCEEDED` |
| **Duration** | $13.5\text{ s}$ | $33.2\text{ s}$ | $72.3\text{ s}$ |
| **Final Pose** | $(4.068, -2.226, -94.4^\circ)$ | $(4.156, -2.241, -88.2^\circ)$ | $(-4.805, 2.112, 119.4^\circ)$ |
| **Position Error** | $0.283\text{ m}$ (tol: $0.65\text{ m}$) | $0.301\text{ m}$ (tol: $0.65\text{ m}$) | $0.214\text{ m}$ (tol: $0.65\text{ m}$) |
| **Total Displacement** | $4.637\text{ m}$ | $9.963\text{ m}$ | $9.877\text{ m}$ |
| **Final Velocity** | $\text{lin}=0.000, \text{ang}=0.000$ | $\text{lin}=0.000, \text{ang}=0.000$ | $\text{lin}=0.000, \text{ang}=0.000$ |
| **Safety Pipeline** | `terrain_monitor` sole owner | `terrain_monitor` sole owner | `terrain_monitor` sole owner |
| **Arrival Verification** | **VERIFIED** | **VERIFIED** | **VERIFIED** |

---

## 2. Root Cause Analysis & Evidence-Based Fixes

1. **Goal Coordinate & Boundary Validation:**
   - Evaluated apartment map geometry ($18.0\text{ m} \times 13.0\text{ m}$, origin $[-9.0, -6.5]$).
   - Implemented strict boundary check $[-8.8 \le x \le 8.8, -6.3 \le y \le 6.3]$ and numeric validation in `coordinator_node.py`. Invalid or out-of-bounds destinations are rejected immediately with descriptive speech feedback.
2. **Lifecycle Manager Bond Timeouts:**
   - Configured `bond_timeout: 4.0` in `lifecycle_manager_localization` and `lifecycle_manager_navigation` (`nav2_params.yaml`), allowing Fast-DDS discovery to complete reliably across all 25 nodes without RMW timeout.
3. **AMCL Stationary Pose Availability:**
   - Configured `TRANSIENT_LOCAL` durability QoS on all AMCL subscribers.
   - Coordinator calls `/request_nomotion_update` service (`std_srvs/srv/Empty`) before dispatching any goal, forcing AMCL to evaluate scans and emit fresh poses on demand.
4. **Behavior Tree Doorway Traversal:**
   - Preserved `default_nav_to_pose_bt_xml: "navigate_w_recovery_and_replanning_only_if_path_becomes_invalid.xml"`. This prevents continuous 1Hz replanning from throwing `"Start occupied"` aborts when passing through tight doorways with inflated costs.
5. **Controller Goal Checkers:**
   - Configured `xy_goal_tolerance: 0.30` in both `general_goal_checker` and `FollowPath` DWB local planner. This prevents DWB from pruning the entire path to 0 poses before the goal checker declares arrival.

---

## 3. Improved Navigation Lifecycle Management in Command Coordinator

The coordinator (`coordinator_node.py`) was enhanced with production-grade FSM lifecycle controls:

```
[IDLE]
  │ (User command received)
  ▼
[VALIDATING_GOAL] ──(Invalid coords/bounds)──► [FAILED] ──► [IDLE]
  │ (Valid coords)
  ▼
[WAITING_FOR_LOCALIZATION] ──(TF dropout/high covariance)──► [FAILED] ──► [IDLE]
  │ (TF map->base connected, covariance bounded, nomotion update confirmed)
  ▼
[PLANNING]
  │ (Nav2 accepts goal)
  ▼
[NAVIGATING] ◄────────────────────────────────────────┐
  │                                                   │
  ├──► [Watchdog Timeout (>35s stagnant)]             │
  │         │                                         │
  ├──► [Nav2 Aborted/Failed]                          │
  │         │                                         │
  │         ▼                                         │
  │    (Retries < 2) ──► [RECOVERING] ────────────────┘
  │                         (Clear costmaps, wait 1.0s, resend goal)
  │    (Retries >= 2) ──► [SAFE_STOP] ──► [FAILED] ──► [IDLE]
  │
  ├──► (User Cancel) ──► [CANCELED] ──(Assert E-stop)──► [IDLE]
  │
  └──► (Nav2 Succeeded)
            │
            ▼
       [VERIFYING_ARRIVAL]
            │
            ├──► (dist <= 0.65m AND velocity <= 0.05 m/s) ──► [SUCCEEDED] ──► [IDLE]
            └──► (dist > 0.65m OR velocity > 0.05 m/s)   ──► [FAILED]    ──► [IDLE]
```

### Key Lifecycle Implementations:
- **Single Active Goal Policy:** Supersedes previous goals cleanly; cancels active goal handle, clears costmaps, and increments `current_goal_id` to invalidate in-flight async callbacks.
- **Reset of Recovery Counters:** Explicitly resets `self.retry_count = 0` on every new user navigation request.
- **Stagnation & Timeout Watchdog:** 1 Hz timer checks if robot displacement is $< 0.08\text{m}$ over $35\text{s}$ (or total navigation $> 180\text{s}$). Bounded recovery triggers costmap clearing and goal reissue; if exhausted, the robot halts safely.
- **Strict Arrival Verification:** Goal completion requires both Nav2 action success, TF distance to goal $\le 0.65\text{m}$, and verified zero velocity ($\le 0.05\text{ m/s}$).

---

## 4. Preservation of Safe Velocity Routing

The authoritative motion command pipeline remains intact and verified:

$$\text{Nav2 Controller} \xrightarrow{\text{/cmd\_vel\_nav}} \text{Velocity Smoother} \rightarrow \text{Collision Monitor} \rightarrow \text{Terrain Monitor} \xrightarrow{\text{/cmd\_vel}} \text{Gazebo Diff-Drive}$$

- **Sole Authoritative Publisher:** `terrain_monitor` is the single node publishing to `/cmd_vel`.
- **Sole Authoritative Subscriber:** `ros_gz_bridge` is the single node subscribing to `/cmd_vel` to drive Gazebo physics.
- **Coordinator Telemetry via Odometry:** The coordinator monitors robot physical velocity through `/odom` (`msg.twist.twist`), eliminating any extra subscription to `/cmd_vel` and preserving pipeline exclusivity.
- **Emergency Stop Safety Gate:** When cancellation or unrecoverable failure occurs, the coordinator publishes `Bool(True)` to `/terrain/emergency_stop`. `terrain_monitor` intercepts this and immediately zeroes `/cmd_vel`.

---

## 5. Verification Results

### Mission 1: Living Room Navigation
```text
================================================================================
  🏁 EXECUTING MISSION: NAVIGATE TO LIVING ROOM
================================================================================
  Initial Pose:         X=0.000, Y=0.000, Yaw=0.0°
  Target Goal:          X=4.000, Y=-2.500, Yaw=0.0° (Frame: map)
  Tolerance Allowed:    0.65 m
  Dispatching command:  'navigate to living room'
      [FEEDBACK] state=NAVIGATING: Navigation accepted. Starting motion to Living Room.
    T+  3.0s | Map=( 1.27, -0.56) | DistToGoal=3.35m | CmdVel=(lin:0.50, ang:0.10)
    T+  6.0s | Map=( 2.59, -0.79) | DistToGoal=2.22m | CmdVel=(lin:0.50, ang:-0.20)
    T+  9.0s | Map=( 3.68, -1.38) | DistToGoal=1.16m | CmdVel=(lin:0.50, ang:-0.50)
      [FEEDBACK] state=SUCCEEDED: Arrival confirmed. I have arrived safely at the Living Room.

  --- MISSION EXECUTION RESULTS ---
  Action Result:        SUCCEEDED
  Duration:             13.5 s
  Final Robot Pose:     X=4.068, Y=-2.226, Yaw=-94.4°
  Position Error:       0.283 m (Tolerance: 0.65 m)
  Total Displacement:   4.637 m
  Final Velocity:       Linear=0.000 m/s, Angular=0.000 rad/s
  Safe Stop Confirmed:  True
  Spoken Output:        ['Navigation accepted. Starting motion to Living Room.', 'Arrival confirmed. I have arrived safely at the Living Room.']
  ✅ VERIFICATION PASSED: Successfully navigated to living room safely and accurately.
```

### Mission 2: Bedroom Navigation (Long-Range Diagonal Regression Check)
```text
================================================================================
  🏁 EXECUTING MISSION: NAVIGATE TO BEDROOM
================================================================================
  Initial Pose:         X=4.068, Y=-2.226, Yaw=-94.4°
  Target Goal:          X=-5.000, Y=2.200, Yaw=0.0° (Frame: map)
  Tolerance Allowed:    0.65 m
  Dispatching command:  'navigate to bedroom'
      [FEEDBACK] state=NAVIGATING: Navigation accepted. Starting motion to Master Bedroom.
    T+  3.0s | Map=( 3.62, -2.12) | DistToGoal=9.64m | CmdVel=(lin:0.50, ang:-1.10)
    T+  6.0s | Map=( 3.27, -1.45) | DistToGoal=9.04m | CmdVel=(lin:0.19, ang:-0.90)
    T+ 18.0s | Map=( 3.05, -1.15) | DistToGoal=8.72m | CmdVel=(lin:0.50, ang:0.40)
    T+ 39.1s | Map=( 0.49, -0.31) | DistToGoal=6.03m | CmdVel=(lin:0.00, ang:-1.20)
    T+ 57.1s | Map=(-0.19, -0.07) | DistToGoal=5.32m | CmdVel=(lin:0.50, ang:-0.20)
    T+ 63.1s | Map=(-2.90,  0.61) | DistToGoal=2.63m | CmdVel=(lin:0.50, ang:-0.00)
    T+ 69.1s | Map=(-4.66,  2.12) | DistToGoal=0.35m | CmdVel=(lin:0.25, ang:0.10)
      [FEEDBACK] state=SUCCEEDED: Arrival confirmed. I have arrived safely at the Master Bedroom.

  --- MISSION EXECUTION RESULTS ---
  Action Result:        SUCCEEDED
  Duration:             72.3 s
  Final Robot Pose:     X=-4.805, Y=2.112, Yaw=119.4°
  Position Error:       0.214 m (Tolerance: 0.65 m)
  Total Displacement:   9.877 m
  Final Velocity:       Linear=0.000 m/s, Angular=0.000 rad/s
  Safe Stop Confirmed:  True
  Spoken Output:        ['Navigation accepted. Starting motion to Master Bedroom.', 'Arrival confirmed. I have arrived safely at the Master Bedroom.']
  ✅ VERIFICATION PASSED: Successfully navigated to bedroom safely and accurately.
```

### Full Regression Suite
- `test_motion_command_ownership.py`: **PASSED** (1 publisher `terrain_monitor`, 1 subscriber `ros_gz_bridge`).
- `test_localization_readiness.py`: **PASSED (8/8 checks)**.
- `test_live_full_acceptance.py`: **PASSED (ALL 6 STAGES)**, including cross-apartment navigation from Master Bedroom to Living Room ($9.963\text{m}$ displacement in $33.2\text{s}$, arrival confirmed, zero velocity).

---

## 6. Exact Files Modified & Code Summary

1. **[`coordinator_node.py`](file:///home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_command_coordinator/gracemo_command_coordinator/coordinator_node.py):**
   - Added `STATE_WAITING_FOR_LOCALIZATION`.
   - Added pre-navigation `check_localization_readiness()` gate with TF lookup, covariance bounds check, and `/request_nomotion_update` call.
   - Added numeric coordinate validation and map boundary bounds check $[-8.8 \le x \le 8.8, -6.3 \le y \le 6.3]$.
   - Added reset of `self.retry_count = 0` and progress tracking on new goal.
   - Implemented 1 Hz `_check_navigation_watchdog` detecting stagnation ($> 35\text{s}$) and timeout ($> 180\text{s}$).
   - Enhanced `on_nav_result` with physical arrival distance verification ($\le 0.65\text{m}$) and safe stop verification ($\le 0.05\text{ m/s}$) via odometry telemetry.
   - Added explicit handlers for `INITIALIZE_LOCALIZATION` and `LOCALIZATION_STATUS`.
2. **[`nav2_params.yaml` (ros2_ws)](file:///home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_navigation/config/nav2_params.yaml):**
   - Configured `bond_timeout: 4.0` for `lifecycle_manager_localization` and `lifecycle_manager_navigation`.
   - Adjusted `SmacPlanner2D` approach parameters (`tolerance: 0.25`, `max_on_approach_iterations: 10000`).
   - Adjusted goal tolerances: `general_goal_checker.xy_goal_tolerance: 0.30`, `FollowPath.xy_goal_tolerance: 0.30`.
3. **[`nav2_params.yaml` (root config)](file:///home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/config/nav2_params.yaml):**
   - Synchronized bond timeouts and goal tolerances.
4. **[`test_living_room_and_bedroom_acceptance.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/test_living_room_and_bedroom_acceptance.py):**
   - Automated living room navigation and bedroom regression test suite with quantitative pose error, velocity, and safety confirmation.
5. **[`test_localization_readiness.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/test_localization_readiness.py):**
   - 8-phase localization readiness test suite.
