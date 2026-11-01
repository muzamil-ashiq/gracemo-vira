# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 09: Recommended Consolidation Plan

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Status:** **PROPOSAL ONLY — REQUIRES HUMAN APPROVAL BEFORE EXECUTION**  
**Mandate:** Zero modifications have been made during this audit. This document outlines the recommended, non-destructive path to consolidate duplicates, resolve conflicts, and establish authoritative sources of truth.

---

## 1. Principles of Consolidation

1. **Non-Destructive Transition:** No working code should be deleted without a proven canonical equivalent and full integration test validation.
2. **Preserve Autonomous & Safety Invariants:** Physical actuation remains permanently locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`). The single-owner velocity chain must never be weakened.
3. **Architectural Separation:** The Pygame user-facing voice/avatar interface must remain distinct from the PySide6 engineering monitoring center (UARCC).
4. **Single Source of Truth:** Every physical robot dimension, room coordinate, topic name, and launch pipeline must have exactly one authoritative definition.

---

## 2. Canonical Implementation Recommendations

| Functional Domain | Candidate Files | Recommended Canonical Implementation | Rationale |
| :--- | :--- | :--- | :--- |
| **ROS 2 Navigation Package** | `gracemo_nav2` vs `gracemo_navigation` | **`ros2_ws/src/gracemo_nav2`** | Standard ROS 2 naming convention (`_nav2`). Migrate `coordinator_node.py` and `terrain_monitor_node.py` into this package. |
| **Robot Description Package** | `gracemo_description` vs `gracemo_robot_description` | **`ros2_ws/src/gracemo_description`** | Actively tracked in workspace; contains verified URDF xacro and 3D visual meshes. |
| **Simulation Worlds Package** | `gracemo_gazebo` vs `gracemo_simulation` | **`ros2_ws/src/gracemo_gazebo`** | Actively configured for Gazebo Harmonic with standard `ros_gz_bridge`. |
| **Autonomous Goal Coordinator** | `prototype/.../coordinator_node.py` | **Promote to `ros2_ws/src/gracemo_nav2/scripts/coordinator_node.py`** | Authoritative bounded state machine executing Nav2 action goals. |
| **Voice & Avatar Interface** | `vira_interaction/` vs `adapters/voice/` vs `gracemo_interaction` | **`vira_interaction/`** | Proven Pygame facial avatar and Whisper STT / `pyttsx3` TTS pipeline. Retire `adapters/voice/`. |
| **Object / Person Detection** | `adapters/perception/detector.py` vs `adapters/vision/` | **`adapters/perception/detector.py`** | Accelerated ONNX/Ultralytics YOLO inference with NMS; robust person detection. |
| **Room Destination Config** | `config/destinations.json` vs `config/places.json` | **`config/destinations.json`** | Rich schema containing destination names, $(x,y,\text{yaw})$ coordinates, frame IDs, and search aliases. |
| **Top-Level Launch File** | `launch_full_simulation.sh` / `vira_complete.launch.py` | **`scripts/launch_full_simulation.sh`** invoking `vira_complete.launch.py` | Unified, modern launcher. Update `vira_complete.launch.py` to include `coordinator_node`. |
| **Hardware HAL & MCU Transport**| `ros2_ws/src/gracemo_hardware/` | **`ros2_ws/src/gracemo_hardware/`** | Canonical STM32 serial transport and status monitor. |
| **3D Visual Meshes** | 3 duplicate sets of 15 `.obj` files | **`ros2_ws/src/gracemo_description/meshes/`** | Sole canonical location for CAD meshes. |

---

## 3. Preserved Architectural Boundaries (Must Remain Separate)

The following components **must NOT be merged**, as their separation is an intentional architectural requirement:

1. **PySide6 UARCC Console vs Pygame Social Interface:**
   - `gracemo_control_center/` is an engineering diagnostic workstation.
   - `vira_interaction/` is a user-facing social robot face.
   - Merging Qt and Pygame into a single monolithic window degrades framerates and confuses operator vs social interaction contexts.
2. **Rust Cognitive Kernel vs Python Adapters:**
   - `kernel/gracemo-kernel` is a high-performance compiled graph memory and context compiler.
   - `adapters/brain/` provides lightweight Python bindings for ROS 2 nodes.
   - They must remain separate client-server processes over HTTP / IPC domain sockets.
3. **Planar Collision Monitor vs 3D Terrain Monitor:**
   - Nav2 `collision_monitor` guards the 2D $XY$ ground plane using 360° LiDAR polygons.
   - `terrain_monitor` guards the 3D inclination angle ($Z/\theta$) using IMU gyroscopes and emergency stop assertions.
   - Both must remain active sequentially in the velocity pipeline.

---

## 4. Five-Phase Phased Consolidation Roadmap

### Phase 1: Parameter & Configuration Unification
- Measure physical wheel separation on the robot chassis (resolve $0.32\text{ m}$ vs $0.34\text{ m}$).
- Measure physical wheel radius (resolve $0.065\text{ m}$ vs $0.066\text{ m}$).
- Standardize costmap radius to $0.22\text{ m}$ across all navigation configurations.
- Symlink `vira_interaction/config/places.json` to canonical `config/destinations.json` via a backward-compatible adapter.

### Phase 2: Navigation & Coordinator Integration
- Move `coordinator_node.py` and `terrain_monitor_node.py` into `ros2_ws/src/gracemo_nav2/`.
- Update `ros2_ws/src/gracemo_gazebo/launch/vira_complete.launch.py` to launch `coordinator_node` automatically.
- Re-route all test scripts (`auto_explore.py`, `closed_loop_nav.py`) through Nav2 action goals or a safe velocity multiplexer (`twist_mux`).

### Phase 3: Archive Legacy Subtrees
- Create an archive branch (`archive/pre-blender-snapshots`) in Git.
- Relocate `backup_pre_blender_integration/` (63.8 MB) and `staging_blender_integration/` (60.2 MB) to the archive branch, freeing over 124 MB in the active working tree.
- Remove redundant duplicate prototype tree in `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1`.

### Phase 4: Voice & Perception Streamlining
- Retire `adapters/voice/gracemo_voice/` to eliminate duplicate Whisper and Kokoro dependencies.
- Standardize perception on `adapters/perception/detector.py` and retire `adapters/vision/gracemo_vision/detector.py`.

### Phase 5: Comprehensive Regression Testing
- Execute full 30-test UARCC test suite (`test_uarcc_comprehensive.py`).
- Run end-to-end multi-room navigation acceptance test (`test_all_destinations_acceptance.py`).
- Validate voice command interpretation and Pygame avatar animation loop.

---

## 5. Items Requiring Human Engineering Decisions

Before executing any consolidation phase, the human engineering team must resolve:

1. **Wheelbase Caliper Measurement:** Physical measurement required on the hardware chassis to determine whether $0.32\text{ m}$ or $0.34\text{ m}$ is the true physical wheelbase.
2. **Speed Envelope Decision:** Confirm whether the maximum allowable linear speed on physical hardware is $0.35\text{ m/s}$ (firmware clamp) or $0.50\text{ m/s}$.
3. **Repository Consolidation Policy:** Authorize the archival and removal of `backup_pre_blender_integration/` and `staging_blender_integration/`.
4. **TTS Engine Preference:** Decide between `pyttsx3` (current zero-latency offline engine in `vira_interaction`) and `Kokoro` (higher quality neural voice in `adapters/voice`).
