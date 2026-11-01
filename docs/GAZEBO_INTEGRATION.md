# Gazebo Simulation Integration Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. Simulation Environment
- **Simulator**: Gazebo Sim Harmonic (Version 8)
- **Physics Engine**: DART with multi-contact LCP solver (1000 Hz physics step, 50 Hz ROS clock synchronization)
- **World File**: [`ros2_ws/src/gracemo_gazebo/worlds/apartment_floor.world`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_gazebo/worlds/apartment_floor.world)
- **Robot Model**: [`ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro)

---

### 2. Embedded World Topology
The simulation environment replicates a multi-room indoor facility aligned with the authoritative place database:

| Room / Zone | Center Coordinates (x, y) | Key Semantic Features |
|---|---|---|
| **Central Hallway** | $(0.00, 0.00)$ | Main transit corridor connecting all suites. |
| **Kitchen & Dining** | $(-5.00, -2.50)$ | Dining table, chairs, refrigerator, pantry. |
| **Master Bedroom** | $(-5.00, +2.20)$ | Bed, side tables, wardrobe. |
| **Home Study** | $(+4.50, +3.00)$ | Desk, office chair, computer, bookshelves. |
| **Living Room** | $(+4.00, -2.50)$ | Sectional sofa, coffee table, entertainment center. |
| **Robotics Research Lab** (Campus) | $(+2.50, +2.00)$ | Workbenches, electronic fixtures, compute racks. |
| **Central Library** (Campus) | $(+45.00, +20.00)$ | Book stacks, study carrels. |

---

### 3. Gazebo Plugins and Actuation

#### A. Differential Drive Plugin (`gz-sim-diff-drive-system`)
- Left Joint: `left_wheel_joint`
- Right Joint: `right_wheel_joint`
- Wheel Separation: $0.34\text{ m}$
- Wheel Radius: $0.065\text{ m}$
- Topic: `/cmd_vel` (`gz.msgs.Twist`) $\longleftrightarrow$ ROS 2 `/cmd_vel`

#### B. 2D Planar LiDAR Sensor (`gpu_lidar`)
- Link: `lidar_link`
- Samples: 720 (0.5° angular resolution across 360°)
- Range: $0.15\text{ m}$ to $12.0\text{ m}$
- Topic: `/scan` (`gz.msgs.LaserScan`) $\longleftrightarrow$ ROS 2 `/scan`

#### C. IMU Sensor (`imu`)
- Link: `imu_link`
- Rate: $100\text{ Hz}$
- Topic: `/imu/data` (`gz.msgs.IMU`) $\longleftrightarrow$ ROS 2 `/imu/data`

#### D. RGB-D Camera (`rgbd_camera`)
- Link: `camera_link` / `camera_optical_link`
- Optics: 640x480 RGB @ 30 Hz, 320x240 Depth @ 30 Hz
- Horizontal FOV: $1.15\text{ rad}$ ($65.8^\circ$)
- Depth Range: $0.20\text{ m}$ to $5.0\text{ m}$
- PointCloud2: `/camera/depth/points`

#### E. Active 2-DOF Neck Controllers
- Joint 1 (Pan): `head_pan_joint` (Range: $\pm 120^\circ$)
- Joint 2 (Tilt): `head_tilt_joint` (Range: $\pm 45^\circ$)
- Decoupled from mobile base: Gaze execution never generates `/cmd_vel` velocity commands.
