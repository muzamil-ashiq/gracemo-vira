# Coordinate Frames and TF Hierarchy

This document specifies the coordinate frames, transform conventions, and kinematic origins of the integrated GRaCEmo ViRa robot model according to ROS standards (REP-103: Standard Units of Measure & Coordinate Conventions, REP-105: Coordinate Frames for Mobile Platforms).

---

## 1. Full TF Tree Hierarchy

```
map
 └── odom (Published by AMCL / SLAM / Odometry Bridge)
      └── base_footprint (Ground plane projection, Z=0)
           └── base_link (Axle height, Z=0.115m)
                ├── front_left_wheel_link   (xyz="0.220  0.285  0.0")
                ├── front_right_wheel_link  (xyz="0.220 -0.285  0.0")
                ├── rear_left_wheel_link    (xyz="-0.220  0.285  0.0")
                ├── rear_right_wheel_link   (xyz="-0.220 -0.285  0.0")
                │
                └── torso_link (Waist pitch axis, xyz="0.0 0.0 0.205", Z=0.320m world)
                     ├── left_arm_link (xyz="0.0 0.215 0.485")
                     ├── right_arm_shoulder_pan_link (xyz="0.0 -0.215 0.485")
                     │    └── ... [7-DOF Arm & Gripper Links]
                     │
                     └── neck_pan_link (Neck yaw axis, xyz="0.0 0.0 0.585", Z=0.905m world)
                          └── head_link (Head tilt axis, xyz="0.0 0.0 0.0")
                               ├── lidar_link (Crown mount, xyz="0.0 0.0 0.270", Z=1.175m world)
                               ├── camera_link (Head lens bar, xyz="0.112 0.0 0.115", Z=1.020m world)
                               └── camera_optical_frame (xyz="0.112 0.0 0.115", rpy="-1.5708 0 -1.5708")
```

---

## 2. Frame Specifications & Kinematic Offsets

| Frame ID | Parent Frame | Origin $(x, y, z)$ [m] | Orientation $(r, p, y)$ [rad] | Purpose / Attached Geometry |
|---|---|---|---|---|
| `map` | World | Origin $(0, 0, 0)$ | $0, 0, 0$ | Global fixed navigation frame |
| `odom` | `map` | Dynamic pose | Dynamic | Odometric estimation frame (continuous) |
| `base_footprint` | `odom` | Dynamic pose | Yaw only $(0, 0, \theta)$ | 2D ground projection under center of axle base |
| `base_link` | `base_footprint` | $(0.0, 0.0, 0.115)$ | $(0, 0, 0)$ | Physical robot chassis frame at axle height ($115\text{ mm}$) |
| `front_left_wheel_link` | `base_link` | $(+0.220, +0.285, 0.0)$ | Continuous ($Y$-axis) | Front left drive wheel (tire, ring, hub) |
| `front_right_wheel_link`| `base_link` | $(+0.220, -0.285, 0.0)$ | Continuous ($Y$-axis) | Front right drive wheel (tire, ring, hub) |
| `rear_left_wheel_link`  | `base_link` | $(-0.220, +0.285, 0.0)$ | Continuous ($Y$-axis) | Rear left drive wheel (tire, ring, hub) |
| `rear_right_wheel_link` | `base_link` | $(-0.220, -0.285, 0.0)$ | Continuous ($Y$-axis) | Rear right drive wheel (tire, ring, hub) |
| `torso_link` | `base_link` | $(0.0, 0.0, 0.205)$ | Revolute ($Y$-axis, $\pm 30^\circ$) | Deck and upper body assembly ($Z=0.320\text{ m}$ world) |
| `neck_pan_link` | `torso_link` | $(0.0, 0.0, 0.585)$ | Revolute ($Z$-axis, $\pm 90^\circ$) | Neck rotation bracket ($Z=0.905\text{ m}$ world) |
| `head_link` | `neck_pan_link` | $(0.0, 0.0, 0.0)$ | Revolute ($Y$-axis, $-30^\circ$ to $+45^\circ$) | Head casing, OLED screen, ears, antennae |
| `lidar_link` | `head_link` | $(0.0, 0.0, 0.270)$ | $(0, 0, 0)$ | 360° Planar LiDAR optical focal center ($Z=1.175\text{ m}$ world) |
| `camera_link` | `head_link` | $(0.112, 0.0, 0.115)$ | $(0, 0, 0)$ | RGB & Depth optical sensor mount ($Z=1.020\text{ m}$ world) |
| `camera_optical_frame`| `camera_link` | $(0.0, 0.0, 0.0)$ | $(-\pi/2, 0, -\pi/2)$ | Standard ROS optical frame ($Z$ forward, $X$ right, $Y$ down) |

---

## 3. Sensor Frame Clearance & Line-of-Sight Verification

1. **Planar LiDAR (`lidar_link`):**
   - Positioned at the apex of the head crown at $Z = 1.175\text{ m}$ world level.
   - The head antenna is positioned behind the scan plane ($X < 0$), guaranteeing an unobstructed $360^\circ$ field of view with zero self-reflection in the laser raytrace.
2. **Perception Cameras (`camera_link`):**
   - Positioned at $X = +0.112\text{ m}$ forward, protruding ahead of the head bezel shell.
   - Zero occlusion from the face display or nose bezel across the full horizontal FOV ($80^\circ$) and vertical FOV ($60^\circ$).
