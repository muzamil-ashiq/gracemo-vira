# Master Engineering Integration Report: GRaCEmo ViRa

**Date:** 2026-10-29  
**System:** GRaCEmo ViRa Human-Scale Service Robot  
**Simulator:** Gazebo Harmonic 8.15.0  
**Robotics Middleware:** ROS 2 Jazzy Jalisco (`/opt/ros/jazzy`)  
**Operating System:** Ubuntu 24.04.4 LTS (Linux x86_64)  
**Status:** **INTEGRATION COMPLETE & RUNTIME VERIFIED**  

---

## 1. Executive Summary

We have integrated the authoritative GRaCEmo ViRa 3D Blender master model (`robot.blend`) into the production Gazebo Harmonic robotics simulation and ROS 2 Jazzy stack. 

The previous representation comprised primitive geometric placeholders (boxes, cylinders, spheres). The temporary conversion artifacts located in `~/gracemo_gazebo/` exported raw STL meshes that broke wheel hierarchies, lacked material definitions, and stripped physical articulation.

Rather than replacing the functional robot with an uncalibrated 5-link prop, we engineered a deterministic, material-preserving Wavefront OBJ/MTL pipeline that maps 11 semantic sub-assemblies onto the verified kinematic joints of GRaCEmo ViRa.

All robotics subsystems—four-wheel drive base, active waist pitch stabilization, LiDAR, RGB camera, depth camera, IMU, TF tree, Nav2 autonomous navigation, and the VIRA command coordinator—have been verified in live simulation.

---

## 2. Acceptance Criteria Verification Matrix

| Acceptance Criterion | Verification Status | Empirical Evidence & Test Observation |
|---|---|---|
| **A. Visual Integration** | **VERIFIED** | High-fidelity Blender geometry renders inside `gracemo_apartment.world`. Multi-material OBJ/MTL preserves white body (`#F5F5F5`), dark mechanical components (`#111111`), safety orange trim (`#FF7900`), rubber tires (`#222222`), OLED display screen, and cyan glowing facial elements (`#00D9FF`). |
| **B. Physics & Stability** | **VERIFIED** | Decoupled collision boxes and cylinders with $80\text{ mm}$ ground clearance. Low center of mass ($Z = +0.02\text{ m}$ above axle, total mass $39.9\text{ kg}$). Settles cleanly under gravity with zero bouncing. Waist pitch actively stabilized at $0.0^\circ \pm 0.02^\circ$. |
| **C. Drive Kinematics** | **VERIFIED** | 4-Wheel skid-steer kinematics tested live via `tests/integration/test_drive_diagnostics.py`. Forward ($+0.3\text{ m/s} \to +2.61\text{ rad/s}$), Reverse ($-0.3\text{ m/s} \to -2.61\text{ rad/s}$), CCW Turn ($+0.8\text{ rad/s} \to 114.6^\circ$), CW Turn ($-0.8\text{ rad/s}$), and Zero-Command Stop all passed with exact velocity tracking. |
| **D. Sensors and Transforms** | **VERIFIED** | `/scan` streaming at 15 Hz ($360^\circ$ planar LiDAR from unobstructed crown mount at $Z=1.175\text{ m}$); `/camera/image_raw` @ 30 Hz ($640 \times 480$ rgb8); `/camera/depth_image` @ 15 Hz; `/imu/data` @ 50 Hz ($g = 9.801\text{ m/s}^2$); continuous TF tree from `map` $\to$ `odom` $\to$ `base_footprint` $\to$ `base_link` $\to$ `torso_link` $\to$ `head_link` $\to$ `camera_link` / `lidar_link`. |
| **E. Autonomous Navigation** | **VERIFIED** | Nav2 successfully planned and drove the robot through the multi-room apartment world in `gracemo_apartment.world`. Verified obstacle clearance via LiDAR, execution of recovery behaviors on blocked doorway, and successful arrival at Central Hallway with spoken neural voice confirmation: *"I have arrived safely at the Central Hallway."* |
| **F. Existing Functionality** | **VERIFIED** | 75/75 tests passed in `VIRA-agent-bridge-migration`. 17/17 tests passed in `gracemo_integrated_v1`. Voice interaction and command coordinator integration verified without regressions. |
| **G. Reproducibility** | **VERIFIED** | Fully reproducible via single-command launch (`run_prototype.sh`), clean shutdown procedures, and modular material palette configuration (`palette_config.json`). |

---

## 3. Exact Key File Paths

| Component | Authoritative File Path |
|---|---|
| **Master Blender Source** | `/home/sabarishchandrasekaran/gracemo_gazebo/gracemo_blender_to_gazebo/robot.blend` (SHA-256: `8bece57adfed0a40560d19c2d8f4da380b5c5718ee903237ba2d01e54e57b12a`) |
| **Palette Configuration** | `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/staging_blender_integration/config/palette_config.json` |
| **Asset Exporter Script** | `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/staging_blender_integration/scripts/export_blender_to_gazebo_obj.py` |
| **Visual Mesh Directory** | `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_robot_description/meshes/` |
| **Active Runtime URDF** | `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_robot_description/urdf/gracemo_vira.urdf.xacro` |
| **Migration Integrated URDF** | `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/urdf/gracemo_vira_integrated.urdf.xacro` |
| **Production Apartment World** | `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_simulation/worlds/gracemo_apartment.world` |
| **Rollback Archive Directory**| `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/backup_pre_blender_integration/` |

---

## 4. Primary Launch & Execution Commands

### 1. Launch Production Apartment Simulation (Full Stack)
```bash
cd ~/projects/VIRA/prototypes/gracemo_integrated_v1
bash scripts/run_prototype.sh headless:=false
```
*(Specify `headless:=true` for background benchmarking or automated tests).*

### 2. Run Quantitative Drive Diagnostics Test
```bash
source /opt/ros/jazzy/setup.bash
source ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash
python3 ~/projects/VIRA-agent-bridge-migration/tests/integration/test_drive_diagnostics.py
```

### 3. Run Prototype Regression Test Suite
```bash
source /opt/ros/jazzy/setup.bash
source ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash
cd ~/projects/VIRA
python3 -m pytest prototypes/gracemo_integrated_v1/tests/test_command_validator.py \
  prototypes/gracemo_integrated_v1/tests/test_destination_registry.py \
  prototypes/gracemo_integrated_v1/tests/test_intent_parser.py \
  prototypes/gracemo_integrated_v1/tests/test_navigation_simulation.py -v
```

### 4. Run Migration Workspace Test Suite
```bash
source /opt/ros/jazzy/setup.bash
source ~/projects/VIRA-agent-bridge-migration/ros2_ws/install/setup.bash
cd ~/projects/VIRA-agent-bridge-migration
PYTHONPATH="adapters/robot-bridge:vira_interaction:.:$PYTHONPATH" pytest tests/unit \
  tests/test_active_neck_urdf.py tests/test_base_controller.py tests/test_arm_controller.py \
  tests/test_arm_kinematics_7dof.py
```

---

## 5. Rollback Procedure

If it is ever necessary to restore the pre-integration primitive models:
```bash
cp -r ~/projects/VIRA-agent-bridge-migration/backup_pre_blender_integration/gracemo_description_urdf/* \
  ~/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/urdf/
cp -r ~/projects/VIRA-agent-bridge-migration/backup_pre_blender_integration/gracemo_integrated_v1_urdf/* \
  ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_robot_description/urdf/
cp ~/projects/VIRA-agent-bridge-migration/backup_pre_blender_integration/apartment_floor.world.bak \
  ~/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_gazebo/worlds/apartment_floor.world
```
