# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 11: Duplicate Removal & Archival Log

**Audit & Consolidation Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Branch:** `feature/gracemo-unified-control-center`  
**Safety Status:** Physical Actuation Locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`)  
**Recovery Branch:** `backup/pre-consolidation-checkpoint`  
**Rollback Archive:** `scratch/backup_removed_files/pre_blender_staging_archive.tar.gz`

---

## 1. Executive Summary

This document provides the authoritative, evidence-based log of all duplicate, redundant, obsolete, and staging files removed, archived, or remediated during the Architectural Consolidation phase. Every removal follows the strict protocol:
$$\text{Verify} \longrightarrow \text{Backup / Archive} \longrightarrow \text{Migrate} \longrightarrow \text{Test} \longrightarrow \text{Retire}$$

### Summary of Actions:
- **Exact Duplicate Files Retired from Active Tree:** 48 staging/backup files + 2 repository root/duplicate files.
- **Disk Space Reclaimed:** Over **124 Megabytes** removed from the active working tree.
- **Rogue Direct-Drive Scripts Gated:** 3 scripts remediated to route motion exclusively through Nav2 velocity smoother and collision monitor.
- **ROS 2 Package Duality Resolved:** Autonomy coordinator and terrain safety monitor migrated to canonical workspace package `gracemo_nav2`.
- **Zero Loss of Functionality:** All Pygame facial avatar, UARCC engineering console, cognitive kernel, and ROS 2 autonomy features verified operational.

---

## 2. Removal and Archival Audit Registry

| Index | Original Path | SHA-256 Checksum | Category | Reason for Removal | Canonical Replacement | Dependencies Verified | Recovery Location |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REM-01** | `blender_deep_inventory.json` | `994e2f054af49a37...` | Staging Inventory | Duplicate copy of Blender model inventory in root folder. | `docs/blender_gazebo_integration/blender_model_audit.md` | No runtime imports; static audit file. | `scratch/backup_removed_files/pre_blender_staging_archive.tar.gz` & Git commit `f628205` |
| **REM-02** | `docs/blender_gazebo_integration/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md` | `9b89aae44705bd29...` | Documentation | 100% byte-for-byte exact duplicate of root docs report. | `docs/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md` | Referenced by `docs/UARCC_V1_BASELINE_AUDIT.md`. | `scratch/backup_removed_files/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md` |
| **REM-03** | `scripts/kitchen_arrival_frame.jpg` | `75317e651e94119f...` | Test Artifact | Byte-for-byte exact duplicate of `scripts/kitchen_visual_observation.jpg`. | `scripts/kitchen_visual_observation.jpg` | Verified `scripts/test_live_visual_perception.py` calls `kitchen_visual_observation.jpg`. | `scratch/backup_removed_files/kitchen_arrival_frame.jpg` |
| **REM-04** | `staging_blender_integration/` (38 files, 15 `.obj` meshes, materials, reports) | Directory tree (60.2 MB) | Staging Directory | Temporary staging folder used during Blender mesh integration; all meshes promoted to `gracemo_description`. | `ros2_ws/src/gracemo_description/meshes/` | All launch files and URDF Xacros reference `gracemo_description`. Zero callers to staging. | `scratch/backup_removed_files/pre_blender_staging_archive.tar.gz` |
| **REM-05** | `backup_pre_blender_integration/` (9 files, 2 world backups, 7 URDF Xacro backups) | Directory tree (63.8 MB) | Historical Backup | Historical pre-mesh geometry snapshots superseded by CAD mesh URDF and Gazebo world models. | `ros2_ws/src/gracemo_description/urdf/` and `ros2_ws/src/gracemo_gazebo/worlds/` | Zero runtime references; superseded by active `gracemo_description`. | `scratch/backup_removed_files/pre_blender_staging_archive.tar.gz` |
| **REM-06** | `adapters/robot-bridge/gracemo_bridge/interaction_bridge.py` | `a34bfbfe09a6ec46...` | Bridge Node | Duplicate source file between Python adapters and ROS 2 workspace package. | `ros2_ws/src/gracemo_bridge/gracemo_bridge/interaction_bridge.py` | Converted to authoritative relative symlink. Tested with `test_interaction_bridge.py` (5/5 PASS). | Symlink to canonical package file. |

---

## 3. Direct-Drive Remediation Registry

The following scripts were identified as bypassing Nav2 safety layers by publishing directly to `/cmd_vel`. They were remediated to enforce safety routing:

| Script Path | Original Behavior | Remediated Behavior | Safety Gate Enforced |
| :--- | :--- | :--- | :--- |
| `scripts/auto_explore.py` | Published raw velocity directly to `/cmd_vel` | Parameterized `cmd_topic` defaulting to `/cmd_vel_teleop` | Routes through Nav2 `velocity_smoother` and `collision_monitor` |
| `scripts/closed_loop_nav.py` | Published raw velocity directly to `/cmd_vel` | Parameterized `cmd_topic` defaulting to `/cmd_vel_teleop` | Routes through Nav2 `velocity_smoother` and `collision_monitor` |
| `scripts/smart_explore.py` | Published raw velocity directly to `/cmd_vel` | Parameterized `cmd_topic` defaulting to `/cmd_vel_teleop` | Routes through Nav2 `velocity_smoother` and `collision_monitor` |

---

## 4. Subsystem Migrations

| Subsystem | Source Component | Destination Component | Build / Integration Action |
| :--- | :--- | :--- | :--- |
| **Autonomous Coordinator** | `prototypes/.../coordinator_node.py` | `ros2_ws/src/gracemo_nav2/gracemo_nav2/coordinator_node.py` | Integrated into `gracemo_nav2`, registered in `CMakeLists.txt` and `package.xml`, added to `vira_complete.launch.py`. |
| **Terrain Safety Gate** | `prototypes/.../terrain_monitor_node.py` | `ros2_ws/src/gracemo_nav2/gracemo_nav2/terrain_monitor_node.py` | Integrated into `gracemo_nav2`, registered in `CMakeLists.txt` and `package.xml`, added to `vira_complete.launch.py`. |
| **Frontier Explorer** | `prototypes/.../frontier_exploration_node.py` | `ros2_ws/src/gracemo_nav2/gracemo_nav2/frontier_explorer.py` | Canonicalized inside `gracemo_nav2` as the authoritative autonomous explorer. |

---

## 5. Rollback and Recovery Instructions

If any removed file or historical snapshot is required for comparison, rollback can be executed instantly through two independent mechanisms:

### Method A: Extract from Local Backup Archive
```bash
# To inspect the pre-blender and staging archive:
tar -ztvf scratch/backup_removed_files/pre_blender_staging_archive.tar.gz

# To restore specific files into scratch or workspace:
tar -zxvf scratch/backup_removed_files/pre_blender_staging_archive.tar.gz <path_to_file>
```

### Method B: Restore from Git Safety Branch
```bash
# The entire pre-consolidation workspace state is preserved at:
git checkout backup/pre-consolidation-checkpoint -- <path_to_file>
```
