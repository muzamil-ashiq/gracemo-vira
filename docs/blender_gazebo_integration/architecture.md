# GRaCEmo ViRa Integration Architecture

This document details the multi-layer robotics architecture that bridges the high-fidelity 3D Blender master model into Gazebo Harmonic, ROS 2 Jazzy, and the VIRA autonomy stack.

---

## 1. End-to-End System Pipeline

```
[ robot.blend ] (Blender 5.2.2 LTS Master)
       │
       ▼  (export_blender_to_gazebo_obj.py + palette_config.json)
[ 11 Semantic Multi-Material OBJ Assets + gracemo_palette.mtl ]
       │
       ▼  (gracemo_vira.urdf.xacro + gazebo_plugins.xacro)
[ Integrated Robot Description (URDF / SDF Model) ]
       │
       ├──► Gazebo Harmonic 8.15.0 Simulation Server (Physics + World Sensors)
       │         │
       │         ▼  (ros_gz_bridge)
       ├──► ROS 2 Jazzy Transport Pipeline
       │         ├── /clock
       │         ├── /cmd_vel
       │         ├── /odom
       │         ├── /scan
       │         ├── /imu/data
       │         ├── /camera/image_raw
       │         └── /joint_states
       │
       ├──► robot_state_publisher (TF & TF Static Broadcaster)
       │
       ├──► Navigation2 Stack (AMCL, NavfnPlanner, Costmaps, Controller)
       │
       ├──► GRaCEmo Command Coordinator (/coordinator/command)
       │
       └──► GRaCEmo Interaction Node (/interaction/user_input, EdgeTTS)
```

---

## 2. Decoupled Physical Architecture

A core failure mode of the previous temporary conversion was treating visual meshes as collision and inertial bodies. Our production architecture strictly enforces **three decoupled layers**:

### Layer 1: Visual Representation
- **Format:** Wavefront OBJ with material libraries (`mtllib gracemo_palette.mtl`).
- **Granularity:** 11 semantic sub-assemblies (base chassis, 4 wheels, torso, neck bracket, head, left resting arm, right manipulator chain).
- **Scale:** Exact $1:1$ human scale ($1.240\text{ m}$ height).

### Layer 2: Collision Geometry
- **Format:** Analytical geometric primitives (boxes, cylinders, spheres).
- **Chassis (`base_link`):** Single bounding box $0.58\text{ m} \times 0.40\text{ m} \times 0.17\text{ m}$ elevated $80\text{ mm}$ above floor level. Eliminates ground snagging while accurately protecting interior electronics.
- **Drive Wheels:** Cylinders $R = 0.115\text{ m}$, width $0.100\text{ m}$.
- **Torso & Head:** Convex hull boxes and spheres protecting internal actuators.

### Layer 3: Inertial & Mass Properties
- **Total Robot Mass:** $39.9\text{ kg}$.
- **Base Chassis:** $22.0\text{ kg}$, center of mass placed low ($Z = +0.02\text{ m}$ above axle) to ensure dynamic rollover resistance.
- **Drive Wheels:** $1.8\text{ kg}$ each with positive-definite diagonal inertia tensors.
- **Waist Stabilization:** Active PID controller ($P=800, I=12, D=20$, effort max $80\text{ N}\cdot\text{m}$) maintaining upright neutral posture ($0.0^\circ \pm 0.02^\circ$).

---

## 3. Communication and Bridge Topology

The `ros_gz_bridge` (parameter_bridge) maps between Gazebo Harmonic native topics and ROS 2 Jazzy:

| ROS 2 Topic | ROS 2 Type | Direction | Gazebo Topic | Gazebo Type |
|---|---|---|---|---|
| `/clock` | `rosgraph_msgs/msg/Clock` | GZ $\to$ ROS | `/clock` | `gz.msgs.Clock` |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | ROS $\to$ GZ | `/cmd_vel` | `gz.msgs.Twist` |
| `/odom` | `nav_msgs/msg/Odometry` | GZ $\to$ ROS | `/odom` | `gz.msgs.Odometry` |
| `/scan` | `sensor_msgs/msg/LaserScan` | GZ $\to$ ROS | `/scan` | `gz.msgs.LaserScan` |
| `/imu/data` | `sensor_msgs/msg/Imu` | GZ $\to$ ROS | `/imu/data` | `gz.msgs.IMU` |
| `/tf` | `tf2_msgs/msg/TFMessage` | GZ $\to$ ROS | `/tf` | `gz.msgs.Pose_V` |
| `/joint_states` | `sensor_msgs/msg/JointState` | GZ $\to$ ROS | `/joint_states` | `gz.msgs.Model` |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | GZ $\to$ ROS | `/camera/image_raw` | `gz.msgs.Image` |
| `/camera/camera_info`| `sensor_msgs/msg/CameraInfo` | GZ $\to$ ROS | `/camera/camera_info` | `gz.msgs.CameraInfo` |
| `/camera/depth_image`| `sensor_msgs/msg/Image` | GZ $\to$ ROS | `/camera/depth_image` | `gz.msgs.Image` |
