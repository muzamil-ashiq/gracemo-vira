# Baseline Audit: GRaCEmo ViRa Blender-to-Gazebo Integration

**Date:** 2026-10-29  
**Platform:** Ubuntu 24.04.4 LTS (Noble Numbat)  
**ROS 2 Distribution:** ROS 2 Jazzy Jalisco (`/opt/ros/jazzy`)  
**Gazebo Simulator:** Gazebo Harmonic (Gazebo Sim 8.15.0)  
**Blender Installation:** Blender 5.2.2 LTS (Snap rev 7803)  
**Target Hardware:** NVIDIA GeForce RTX 5060 Laptop GPU (Driver 595.99.02, CUDA 13.2)  

---

## 1. Master Blender Source Integrity Check

Prior to any asset extraction or processing, the SHA-256 checksums of the candidate Blender files were computed:

| File Path | SHA-256 Checksum | Status |
|---|---|---|
| `/home/sabarishchandrasekaran/gracemo_gazebo/gracemo_blender_to_gazebo/robot.blend` | `8bece57adfed0a40560d19c2d8f4da380b5c5718ee903237ba2d01e54e57b12a` | Authoritative |
| `/home/sabarishchandrasekaran/robot.blend` | `8bece57adfed0a40560d19c2d8f4da380b5c5718ee903237ba2d01e54e57b12a` | Identical Replica |

Both sources are binary identical. Cheksums are verified before and after conversion to guarantee zero alteration of the original art asset.

---

## 2. Workspace Comparison & Architectural Roles

Three candidate workspaces were audited to establish their architectural roles and dependencies:

### Workspace 1: Migration Workspace (`projects/VIRA-agent-bridge-migration`)
- **Git Branch:** `migration/legion-setup`
- **Location:** `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`
- **Packages:** `gracemo_description`, `gracemo_gazebo`, `gracemo_hardware`, `gracemo_bridge`, `gracemo_moveit_config`, `gracemo_nav2`.
- **Architectural Role:** Primary migration workspace containing the Agent Bridge MCP adapter, MCU serial transport (`firmware/`), and hardware HAL.
- **Robot Description:** Maintained in `ros2_ws/src/gracemo_description/`. In this workspace, `gracemo_vira.urdf.xacro` was release-frozen for Phase 7/8 tests (`tests/test_active_neck_urdf.py`). The Blender-integrated model is deployed as `ros2_ws/src/gracemo_description/urdf/gracemo_vira_integrated.urdf.xacro`.

### Workspace 2: Standalone Integrated Prototype (`projects/VIRA/prototypes/gracemo_integrated_v1`)
- **Git Branch:** Untracked prototype tree under `projects/VIRA`
- **Location:** `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1`
- **Packages:** `gracemo_robot_description`, `gracemo_simulation`, `gracemo_navigation`, `gracemo_command_coordinator`, `gracemo_interaction`, `gracemo_bringup`, `gracemo_hardware`.
- **Architectural Role:** Complete end-to-end autonomous prototype. Houses the production launch pipeline (`prototype.launch.py`), Nav2 costmaps/planner (`gracemo_navigation`), voice interaction loop (`gracemo_interaction`), and command coordinator.
- **Robot Description:** Active runtime model is `ros2_ws/src/gracemo_robot_description/urdf/gracemo_vira.urdf.xacro`.

### Workspace 3: Core VIRA Repository (`projects/VIRA`)
- **Git Branch:** `feature/whisper-live-interaction`
- **Location:** `/home/sabarishchandrasekaran/projects/VIRA`
- **Packages:** `gracemo_bridge`, `gracemo_description`, `gracemo_gazebo`, `gracemo_moveit_config`, `gracemo_nav2`.
- **Architectural Role:** Upstream reference repository with Whisper ASR and Riva speech services.

---

## 3. World Files & Simulation Readiness

| Candidate World | Path | Findings | Decision |
|---|---|---|---|
| `gracemo_apartment.world` | `prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_simulation/worlds/` | Self-contained multi-room apartment SDF (hallway, bedroom, kitchen, living room, study, lab). Zero remote Fuel dependencies. Passes `gz sdf -k`. | **PRIMARY PRODUCTION WORLD** |
| `room.world` | `gracemo_simulation/worlds/` & `gracemo_gazebo/worlds/` | Single-room test facility without obstacle complexity. | Minimal fallback world |
| `apartment_floor.world` | `gracemo_gazebo/worlds/` | Multi-room world with embedded robot SDF referencing remote Fuel models (`model://bed`, `model://refrigerator`). | Legacy — Updated with integrated robot SDF and synchronized with `gracemo_apartment.world`. |

---

## 4. Pre-Integration Baseline Audit Summary

1. **Geometry Baseline:** Prior model used purely geometric primitives (boxes, cylinders, spheres) totaling 0 external meshes.
2. **Drive Baseline:** 4-wheel differential/skid-steer kinematics with active waist pitch joint stabilization.
3. **Sensor Baseline:** 2D LiDAR (`/scan`), RGB camera (`/camera/image_raw`), Depth camera (`/camera/depth_image`), IMU (`/imu/data`), `/joint_states`, `/odom`, `/tf`.
4. **Nav2 Baseline:** Navigation2 stack configured with costmap inflation, NavfnPlanner, and AMCL localization.
