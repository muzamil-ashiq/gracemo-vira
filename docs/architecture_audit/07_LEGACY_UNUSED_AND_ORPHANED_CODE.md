# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 07: Legacy, Unused, and Orphaned Code

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Objective:** Identification and cataloging of superseded historical snapshots, dead adapters, unreferenced scripts, and dormant prototype branches.

---

## 1. Executive Summary of Orphaned & Legacy Code

Static analysis identified **over 124 Megabytes** of historical backups, redundant staging trees, unreferenced exploratory scripts, and legacy adapter prototypes that are no longer part of the primary runtime execution path:

| Subtree / Component | Path | Approximate Size | Maintained File Count | Status & Reason for Deprecation |
| :--- | :--- | :---: | :---: | :--- |
| **Pre-Blender Integration Backup** | `backup_pre_blender_integration/` | **63.8 MB** | 32 files | **Superseded Historical Backup:** Preserved geometric URDF and early SDF world files prior to Blender CAD mesh adoption. |
| **Blender Integration Staging** | `staging_blender_integration/` | **60.2 MB** | 38 files | **Superseded Staging Tree:** Temporary staging folder used while validating 15 Blender-exported `.obj` meshes and materials. |
| **Legacy Interaction Clone** | `~/projects/VIRA/graceemo_interaction/` | **432 KB** (excl venv) | 48 files | **Superseded Codebase:** Historical Pygame interaction interface replaced by unified `vira_interaction/`. |
| **Prototype Reference Stack** | `~/projects/VIRA/prototypes/gracemo_integrated_v1/` | **>15 MB** | 133 files | **Historical Prototype:** Prototype v1 integration stack whose components were partially migrated to the workspace root. |
| **Rogue Direct-Drive Scripts** | `scripts/auto_explore.py`, `scripts/closed_loop_nav.py`, `scripts/smart_explore.py` | $\sim 20\text{ KB}$ | 3 files | **Obsolete / Unsafe:** Bypasses Nav2 and collision monitoring. Superseded by Nav2 autonomous coordinator. |
| **Early Vision / ZMQ Bridges** | `adapters/vision/gracemo_vision/sim_camera_bridge.py`, `face_id.py` | $\sim 15\text{ KB}$ | 2 files | **Dead Code:** Superseded by standard `ros_gz_bridge` and YOLO ONNX perception service. |
| **Duplicate Static Screenshots** | `scripts/*.jpg` (18 image files) | $\sim 350\text{ KB}$ | 18 files | **Static Test Artifacts:** Static visual verification captures saved in code directory rather than `docs/`. |

---

## 2. Detailed Subsystem Deprecation Analysis

### 2.1 `backup_pre_blender_integration/` (63.8 MB)
- **Origin:** Snapshot created on October 29, 2026, before executing the Blender CAD mesh integration.
- **Contents:**
  - `apartment_floor_vira.world.bak` & `apartment_floor.world.bak` (81 KB each): Early Gazebo SDF worlds.
  - `gracemo_integrated_v1_urdf/`: 3 Xacro files referencing primitive geometric cylinders and boxes.
  - `gracemo_description_urdf/`: 4 Xacro files representing early parameterized chassis geometries.
- **Architectural Status:** Fully superseded by `ros2_ws/src/gracemo_description/urdf/` and `ros2_ws/src/gracemo_gazebo/worlds/`.
- **Runtime Dependency:** Zero runtime references in launch files, ROS nodes, or test suites.

### 2.2 `staging_blender_integration/` (60.2 MB)
- **Origin:** Staging workspace created on October 29, 2026, to hold Blender `.blend` exports and audit reports.
- **Contents:**
  - `meshes/`: 15 `.obj` files and `gracemo_palette.mtl` (100% byte-for-byte duplicate of `ros2_ws/src/gracemo_description/meshes/`).
  - `urdf/expanded_gracemo_vira.urdf` & `gracemo_vira.urdf.xacro`: Staging copy of robot description.
  - `reports/blender_deep_inventory.json` (98 KB): Duplicate of root file.
- **Architectural Status:** Successfully promoted to `ros2_ws/src/gracemo_description/`. Staging tree is now completely redundant.
- **Runtime Dependency:** Zero runtime references.

### 2.3 `~/projects/VIRA/graceemo_interaction/` (Legacy Interaction Directory)
- **Origin:** Early standalone voice and Pygame face repository.
- **Contents:**
  - Contains full standalone Python virtual environment (`.venv/`), `main.py`, `model.py`, and older Riva voice adapters.
- **Architectural Status:** In the primary workspace, `graceemo_interaction` is a symlink pointing to `vira_interaction/`. The standalone directory in `~/projects/VIRA` represents unmaintained legacy code.
- **Runtime Dependency:** Superseded by `vira_interaction/`.

### 2.4 Standalone Exploration Scripts in `scripts/`
- **`auto_explore.py` (4,313 B):** Simple wall-following explorer publishing velocities directly to `/cmd_vel`.
- **`closed_loop_nav.py` (6,102 B):** Proportional P-controller navigating between waypoints by checking `/odom` and publishing to `/cmd_vel`.
- **`smart_explore.py` (7,355 B):** Ad-hoc multi-room explorer bypassing Nav2 action servers.
- **Architectural Hazard:** These scripts do not subscribe to or respect the `/terrain/emergency_stop` topic or collision monitor safety envelopes. If executed by an operator, they can cause unpredictable physical or simulated collisions.
- **Recommendation:** Move to an `archive/legacy_scripts/` folder or deprecate with warning headers.

### 2.5 Dormant Adapters in `adapters/`
- **`adapters/motion/`:**
  - `arm_kinematics.py`, `gracemo_base_controller.py`, `hand_controller.py`, `arm_controller.py`: Early standalone mathematical controllers written prior to integrating ROS 2 MoveIt 2 and Nav2.
- **`adapters/vision/gracemo_vision/sim_camera_bridge.py`:**
  - Custom ZMQ/socket camera frame bridge superseded by standard `ros_gz_bridge`.
- **`adapters/vision/gracemo_vision/face_id.py`:**
  - Face recognition prototype using `face_recognition` library; dormant and uncalled in the active perception pipeline.
