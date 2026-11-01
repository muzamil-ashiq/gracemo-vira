# ROS 2 Integration Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. Overview
The ROS 2 subsystem provides the hardware abstraction, kinematic transformations, and autonomous navigation planning for the GRaCEmo ViRa mobile robot. It connects to the VIRA cognitive interaction tier strictly via the **Robot Bridge** and **EventBus**.

---

### 2. ROS 2 Workspace Structure
The workspace is located at `ros2_ws/src/` with the following packages:

| Package | Type | Description |
|---|---|---|
| `gracemo_description` | `ament_cmake` | URDF, Xacro 3D model, physical visual & collision meshes, inertia matrices, and kinematic joint limits. |
| `gracemo_gazebo` | `ament_cmake` | Gazebo Harmonic world (`apartment_floor.world`), spawn configurations, and master simulation launch files. |
| `gracemo_bridge` | `ament_python` | Physical sensor bridge (`sensor_bridge.py`) and Kernel EventBus bridge (`kernel_bridge.py`). |
| `gracemo_nav2` | `ament_cmake` | Navigation2 configuration (`nav2_params.yaml`), SLAM Toolbox mapping, and RViz2 navigation layouts. |
| `gracemo_moveit_config` | `ament_cmake` | 7-DOF arm trajectory planning and MoveIt 2 configuration. |

---

### 3. Node Architecture

```text
[Gazebo Harmonic Sim]
   │ (gz.transport13)
   ▼
[sensor_bridge] ────────────────────────────────────────────────────────┐
   │                                                                     │
   ├──► /scan (sensor_msgs/LaserScan, frame: lidar_link)                 │
   ├──► /odom (nav_msgs/Odometry, frame: odom -> base_footprint)        │
   ├──► /imu/data (sensor_msgs/Imu, frame: imu_link)                     │
   ├──► /camera/image_raw & camera_info (RGB)                            │
   ├──► /camera/depth_image & points (PointCloud2)                       │
   └──► /joint_states (sensor_msgs/JointState)                           │
                                                                         │
   ▲                                                                     ▼
   │ /cmd_vel                                                    [robot_state_publisher]
   │ (geometry_msgs/Twist)                                               │
   │                                                                     ▼
[kernel_bridge / RobotBridge] ◄──── /events/live (SSE) ──────── [TF Tree Broadcaster]
   │                                                              (map -> odom -> base_link)
   └──► /emit ──► [VIRA Kernel EventBus]
```

#### Active ROS 2 Nodes:
1. **`robot_state_publisher`**: Parses `gracemo_vira.urdf.xacro` and continuously broadcasts the forward kinematic TF tree at 50 Hz.
2. **`sensor_bridge`**: Native C++/Python transport bridge linking Gazebo Harmonic topics directly to standard ROS 2 message types.
3. **`kernel_bridge`**: Subscribes to Kernel EventBus `/events/live` for `ActionRequested` semantic commands and commands closed-loop waypoint tracking over `/cmd_vel` without touching GPIO or PWM.

---

### 4. Topic Graph

| Topic Name | Message Type | Rate | Purpose |
|---|---|---|---|
| `/scan` | `sensor_msgs/msg/LaserScan` | 20 Hz | 360° planar obstacle detection and 2D SLAM localization. |
| `/odom` | `nav_msgs/msg/Odometry` | 50 Hz | Continuous wheel odometry and linear/angular velocity estimation. |
| `/imu/data` | `sensor_msgs/msg/Imu` | 100 Hz | High-frequency angular acceleration and orientation estimation. |
| `/joint_states` | `sensor_msgs/msg/JointState` | 50 Hz | Real-time joint angles for wheels, 2-DOF neck, and arm links. |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | 30 Hz | Forward RGB vision (640x480, hfov=1.15 rad). |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | 30 Hz | Intrinsics calibration matrix for RGB optics. |
| `/camera/depth_image` | `sensor_msgs/msg/Image` | 30 Hz | Metric depth map for 3D spatial occupancy. |
| `/camera/depth/points` | `sensor_msgs/msg/PointCloud2` | 10 Hz | 3D point cloud for 3D obstacle avoidance. |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 50 Hz | Commanded differential drive velocities ($v_x, \omega_z$). |

---

### 5. Coordinate Frame Hierarchy (TF Tree)

```text
map
 └── odom
      └── base_footprint
           └── base_link
                ├── lidar_link (x=+0.12, z=+0.18)
                ├── imu_link (x=0.00, z=+0.08)
                ├── camera_link (x=+0.15, z=+0.65)
                │    └── camera_optical_link (rpy: -π/2, 0, -π/2)
                ├── left_wheel_link (y=+0.17)
                ├── right_wheel_link (y=-0.17)
                └── neck_pitch_link (z=+0.645)
```

---

### 6. Production Launch Files

1. **Complete Stack Launch**:
   ```bash
   ros2 launch gracemo_gazebo vira_complete.launch.py use_sim_time:=true launch_nav2:=true
   ```
2. **Simulation Only**:
   ```bash
   ros2 launch gracemo_gazebo sim.launch.py
   ```
3. **Autonomous Navigation (Nav2 + SLAM)**:
   ```bash
   ros2 launch gracemo_nav2 nav2.launch.py
   ```
