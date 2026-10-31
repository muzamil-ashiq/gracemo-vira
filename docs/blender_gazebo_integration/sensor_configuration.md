# Sensor Configuration and Verification

This document specifies the sensor payload, frame attachments, ROS 2 topics, and live verified streaming parameters of the integrated GRaCEmo ViRa robot in Gazebo Harmonic.

---

## 1. Verified Sensor Matrix

| Sensor Type | ROS 2 Topic | Frame ID | Message Type | Update Rate | Verified Operating Range |
|---|---|---|---|---|---|
| **2D Planar LiDAR** | `/scan` | `lidar_link` | `sensor_msgs/msg/LaserScan` | 15 Hz | 360 beams, $0.10\text{ m} - 12.0\text{ m}$, $360^\circ$ scan plane at $Z=1.175\text{ m}$ |
| **RGB Camera** | `/camera/image_raw` | `camera_optical_frame` | `sensor_msgs/msg/Image` | 30 Hz | $640 \times 480$ resolution, `rgb8` encoding, $80^\circ$ H-FOV |
| **Camera Info** | `/camera/camera_info` | `camera_optical_frame` | `sensor_msgs/msg/CameraInfo` | 30 Hz | Calibrated pinhole camera intrinsic matrix |
| **Depth Camera** | `/camera/depth_image` | `camera_optical_frame` | `sensor_msgs/msg/Image` | 15 Hz | $640 \times 480$ resolution, `32FC1` metric depth ($0.2\text{ m} - 5.0\text{ m}$) |
| **6-DOF IMU** | `/imu/data` | `base_footprint` | `sensor_msgs/msg/Imu` | 50 Hz | Angular velocity ($\text{rad/s}$), Linear acceleration ($Z = +9.801\text{ m/s}^2$) |
| **Joint Telemetry** | `/joint_states` | `base_link` | `sensor_msgs/msg/JointState` | 50 Hz | Positions and velocities across all 16 robot joints |
| **Wheel Odometry** | `/odom` | `odom` $\to$ `base_footprint` | `nav_msgs/msg/Odometry` | 50 Hz | Integrated pose $(x, y, \theta)$ and body twist $(v_x, \omega_z)$ |

---

## 2. Sensor Placement and Line-of-Sight

### 1. Planar LiDAR (`lidar_link`)
- **Mount Pose:** Origin $(0, 0, 0.270)$ on `head_link` ($Z = 1.175\text{ m}$ world elevation).
- **Clearance:** Elevated above the head shell crown. Head antenna and ears are positioned below the laser horizontal scan plane.
- **Raytrace Test:** Verified zero link self-occlusion or phantom obstacles on `/scan`.

### 2. RGB-D Camera (`camera_link`)
- **Mount Pose:** Origin $(0.112, 0.0, 0.115)$ on `head_link` ($Z = 1.020\text{ m}$ world elevation).
- **Optical Orientation:** In Gazebo, sensor frame is rotated to standard optical convention (`rpy="-1.5708 0 -1.5708"`).
- **GPU Acceleration:** Leverages NVIDIA GeForce RTX 5060 Laptop GPU via Gazebo's Ogre2 render engine, streaming stable 30 FPS RGB frames with zero dropped frames.

### 3. Inertial Measurement Unit (`imu_sensor`)
- **Mount Pose:** Embedded in `base_footprint` at axle level.
- **Gravity Handling:** Correctly reports gravitational acceleration ($+9.801\text{ m/s}^2$ upwards reaction along $Z$-axis) when stationary on the floor.
