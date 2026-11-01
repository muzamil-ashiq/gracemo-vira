# GRaCEmo ViRa — Robot Interface Contract
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-ROBOT-P1-005`  
**System Version:** v0.0.3  

---

## 1. Interface Boundary & Responsibility

The Robot Interface Contract establishes the boundary between the high-level cognitive nervous system and the low-level physical robot platform:

```
┌────────────────────────────────────────────────────────┐
│                   COGNITIVE NERVOUS SYSTEM             │
│            Interaction Gateway / Brain / Memory        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ Typed Semantic Actions
┌────────────────────────────────────────────────────────┐
│                     SAFETY GATEWAY                     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ Validated RobotActions
┌────────────────────────────────────────────────────────┐
│              ROBOT BRIDGE (kernel_bridge.py)           │
│   • Subscribes to Kernel SSE (/events/live)            │
│   • Emits Telemetry to Kernel (/emit)                  │
└──────────────┬───────────────────────────┬─────────────┘
               │ ROS 2 Messages            │ ROS 2 Actions
               ▼                           ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│ Low-Level Actuation       │ │ Autonomous Navigation    │
│ • /cmd_vel (Twist)        │ │ • Nav2 NavigateToPose    │
│ • /head/pan/cmd_pos       │ │ • Nav2 FollowPath        │
│ • /head/tilt/cmd_pos      │ │ • Dynamic Waypoints      │
└───────────────────────────┘ └──────────────────────────┘
```

---

## 2. Standard Semantic Commands

The Interaction Subsystem commands the robot strictly via the canonical semantic actions defined in [`contracts/robot-command.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/robot-command.schema.json):

### 2.1 `NavigateTo`
Instructs the robot to navigate to metric coordinates in the `map` or `odom` frame:
- **Parameters**: `x: float`, `y: float`, `yaw: Option[float]`, `tolerance_m: float` (default `0.30`)
- **Execution Pipeline**:
  1. Safety Gateway verifies $(X, Y)$ is within the perimeter bounds of the floorplan.
  2. Robot Bridge decomposes destination into corridor/doorway approach waypoints.
  3. Dispatches velocity profile through doorway slow zones ($0.25\text{ m/s}$ linear, $0.55\text{ rad/s}$ angular).
  4. Emits `NavigationStarted` and periodic `NavigationProgress`.
  5. Upon arrival within tolerance, aligns final observation yaw and emits `NavigationArrived`.

### 2.2 `NavigateToRoom`
Instructs the robot to traverse to a named topological zone:
- **Supported Rooms**:
  - `Robotics Research Lab` / `Central Library` / `Uni-Mall` / `AI Compute Center` (Campus mode)
  - `Kitchen & Dining` / `Master Bedroom` / `Home Study` / `Living Room` / `Central Hallway` (Apartment mode)
- **Execution Pipeline**: Resolves room transit portal coordinates from knowledge graph, executes waypoints, and aligns heading toward primary observation focus.

### 2.3 `LookAt`
Directs the active 2-DOF neck camera toward a 3D point in world coordinates $(X, Y, Z)$:
- **Kinematic Constraints**:
  - Pan limit: $[-120.0^\circ, +120.0^\circ]$ ($[-2.0944, +2.0944]\text{ rad}$)
  - Tilt limit: $[-45.0^\circ, +45.0^\circ]$ ($[-0.7854, +0.7854]\text{ rad}$)
- **CRITICAL INVARIANT**: LookAt commands **never** touch `/cmd_vel` or rotate the mobile base. If the target $(X, Y, Z)$ exceeds neck workspace, the neck remains stationary and `LookAtResult { workspace_exceeded: true }` is emitted.

### 2.4 `Stop`
Immediately arrests all robot mobility:
- **Behavior**:
  - Cancels active Nav2 navigation goals.
  - Publishes zero linear and angular velocity to `/cmd_vel`.
  - Halts active head sweeps.
  - Emits `RobotStopped { reason, emergency }`.

---

## 3. ROS 2 Topic & Interface Catalog

| Topic / Action Name | Type | Direction | Rate | Description |
| :--- | :--- | :---: | :---: | :--- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Out (Bridge $\to$ HW) | $\le 20\text{ Hz}$ | Differential drive velocity setpoint. |
| `/odom` | `nav_msgs/msg/Odometry` | In (HW $\to$ Bridge) | $50\text{ Hz}$ | Wheel encoder + IMU fused odometry. |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | In (HW $\to$ Vision) | $15\text{ Hz}$ | RGB head camera video stream. |
| `/scan` | `sensor_msgs/msg/LaserScan` | In (HW $\to$ Safety) | $10\text{ Hz}$ | 360-degree planar LiDAR scan. |
| `/head/pan/cmd_pos` | `std_msgs/msg/Float64` | Out (Bridge $\to$ HW) | On-demand | Active neck pan angle (radians). |
| `/head/tilt/cmd_pos` | `std_msgs/msg/Float64` | Out (Bridge $\to$ HW) | On-demand | Active neck tilt angle (radians). |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Out (Bridge $\to$ Nav2)| Action | Nav2 autonomous path navigation goal. |

---

## 4. Coordinate Frames & Kinematic Chain

All metric coordinates adhere to ROS REP-105 standard conventions:
```
  map (Global authoritative SLAM / World frame)
   │
   ▼
  odom (Continuous dead-reckoning drift-free frame)
   │
   ▼
  base_footprint (Ground plane projection of robot center)
   │
   ▼
  base_link (Chassis physical center of TurtleBot3 Waffle)
   ├─── neck_pan_link (Pivot at x=-0.02m, y=0.00m, z=0.645m)
   │     └─── neck_tilt_link (Elevation pivot)
   │           └─── camera_link (Optical sensor origin)
   ├─── base_scan (LiDAR origin at x=-0.064m, z=0.122m)
   ├─── wheel_left_link (Left traction wheel)
   └─── wheel_right_link (Right traction wheel)
```
