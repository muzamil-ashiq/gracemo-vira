# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 00: Executive Summary

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Working Trees Inspected:**  
1. Workspace Root: `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`
2. Integrated Prototype Root: `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1`
3. Parent Reference Repository: `/home/sabarishchandrasekaran/projects/VIRA`  
**Audit Scope:** Read-Only Exhaustive Static Architecture & Codebase Investigation  
**Safety Mandate:** Zero code modification, physical actuation locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`)

---

## 1. High-Level Audit Findings

A rigorous static analysis was performed across the complete GRaCEmo ViRa codebase, covering Python sources, ROS 2 packages, Gazebo simulation environments, launch files, URDF/Xacro models, Rust cognitive kernel crates, configuration files, shell utilities, and test suites.

| Metric | Workspace Tree (`VIRA-agent-bridge-migration`) | Prototype Tree (`prototypes/gracemo_integrated_v1`) | Combined Total |
| :--- | :--- | :--- | :--- |
| **Total Files Inspected** | 4,191 files | 2,626 files | **6,817 files** |
| **Maintained Source Files** | 629 files | 133 files | **762 files** |
| **Generated / Build Artifacts** | 3,562 files (`build/`, `install/`, `.pyc`, `.o`) | 2,493 files (`log/`, `build/`, `.pyc`) | **6,055 files** |
| **Exact Duplicate File Clusters** | 56 clusters (138 identical files by SHA256) | Included in cluster count | **56 clusters** |
| **Functional Duplicate Groups** | 18 major functional subsystems | — | **18 groups** |
| **ROS 2 Overlapping Packages** | 5 workspace pkgs vs 7 prototype pkgs | — | **7 duplicate/split packages** |
| **Configuration Divergences** | 8 conflicting parameters (wheelbase, radius, speed) | — | **8 conflicts** |
| **Orphaned / Staging Subtrees** | 3 major subtrees (`staging_blender_integration`, `backup_pre_blender`, legacy clone) | — | **>120 MB redundant data** |

---

## 2. Key Audit Conclusions

### 1. Dual-Package Split Between Workspace and Prototype V1
The repository currently maintains two competing naming conventions for core ROS 2 packages:
- **Workspace Stack:** `gracemo_nav2`, `gracemo_description`, `gracemo_gazebo`, `gracemo_hardware`, `gracemo_bridge`.
- **Prototype V1 Stack:** `gracemo_navigation`, `gracemo_robot_description`, `gracemo_simulation`, `gracemo_hardware`, `gracemo_command_coordinator`, `gracemo_bringup`, `gracemo_interaction`.
Both stacks contain overlapping launch files, world files, and parameters, creating ambiguity regarding which package is authoritative.

### 2. Triplicate 3D Mesh and Robot Description Assets
Complete sets of 15 `.obj` and `.mtl` robot visual meshes (e.g., `base_link_visual.obj`, `left_arm_visual.obj`) exist identically across three locations:
1. `ros2_ws/src/gracemo_description/meshes/` (active workspace)
2. `staging_blender_integration/meshes/` (staging copy during Blender mesh migration)
3. `ros2_ws/src/gracemo_robot_description/meshes/` (prototype v1 copy)
Similarly, URDF xacro files are replicated across `backup_pre_blender_integration/`, `staging_blender_integration/`, and `ros2_ws/`.

### 3. Multiple Competing Voice & Interaction Stacks
Three separate speech-to-text (STT) and text-to-speech (TTS) architectures exist in parallel:
1. **`vira_interaction/`:** Active Pygame-based facial avatar, Whisper/Groq STT, `pyttsx3` TTS, and state machine.
2. **`adapters/voice/gracemo_voice/`:** Isolated Faster-Whisper, Kokoro TTS, and Vosk adapter library.
3. **`gracemo_interaction` (prototype):** In-tree ROS 2 node using `speech_adapters.py` with EdgeTTS and OpenAI Whisper.

### 4. Critical Safety Bypass in Standalone Navigation Scripts
While the authoritative autonomous pipeline strictly routes motor commands through:
$$\text{Nav2} \longrightarrow \text{velocity\_smoother} \longrightarrow \text{collision\_monitor} \longrightarrow \text{terrain\_monitor} \longrightarrow \text{/cmd\_vel} \longrightarrow \text{ros\_gz\_bridge} / \text{mcu\_bridge}$$
several standalone exploration and test scripts (`scripts/closed_loop_nav.py`, `scripts/auto_explore.py`, `scripts/smart_explore.py`, `scripts/mission_control.py`) publish velocity commands **directly to `/cmd_vel`**, completely bypassing collision monitoring and terrain safety stops.

### 5. Critical Physical Configuration Discrepancies
- **Wheel Separation (Wheelbase):** Configured as `0.32 m` in `config/robot.yaml`, but defined as `0.34 m` in `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml` and `gracemo_vira.urdf.xacro`.
- **Robot Collision Radius:** Configured as `0.22 m` in `gracemo_nav2` vs `0.23 m` in `gracemo_navigation`.
- **Max Linear Speed:** Defined as `0.8 m/s` in `config/robot.yaml`, `0.65 m/s` in `nav2_params.yaml`, `0.5 m/s` in prototype `nav2_params.yaml`, and clamped to `0.35 m/s` in `mcu_transport.py`.
- **Room Destinations Format:** `config/destinations.json` (authoritative dictionary with aliases and coordinates) conflicts with `config/places.json` and `vira_interaction/config/places.json` (4-element list format).

---

## 3. Top Architectural Risks

1. **Safety Gate Bypass (High Risk):** Standalone scripts publishing to `/cmd_vel` can drive the robot into obstacles if run during navigation tests.
2. **Odometry & Dead Reckoning Error (High Risk):** The 20 mm discrepancy in wheel separation ($0.32\text{ m}$ vs $0.34\text{ m}$) causes systematic rotational error during in-place turns if differential drive kinematics use divergent constants.
3. **Ghost Node / Stale Launch Conflicts (Medium Risk):** Launching both `vira_complete.launch.py` and `prototype.launch.py` starts conflicting navigation coordinators and bridges.
4. **Maintenance Overhead (Medium Risk):** Over 120 MB of unreferenced backup/staging files inflate Git clone sizes and confuse automated test discovery.

---

## 4. Report Navigation

| Document | Title & Focus Area |
| :--- | :--- |
| [01_COMPLETE_FILE_INVENTORY.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/01_COMPLETE_FILE_INVENTORY.md) | Exhaustive directory and file inventory distinguishing maintained code from generated artifacts |
| [02_EXACT_DUPLICATES.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/02_EXACT_DUPLICATES.md) | Catalog of all 56 SHA-256 identical duplicate file clusters with evidence tables |
| [03_FUNCTIONAL_DUPLICATES.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/03_FUNCTIONAL_DUPLICATES.md) | Deep inspection of 18 functional duplication groups across perception, speech, and motion |
| [04_ROS2_ARCHITECTURE_AUDIT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/04_ROS2_ARCHITECTURE_AUDIT.md) | ROS 2 node registry, topic topology, and `/cmd_vel` velocity arbitration pipeline mapping |
| [05_CONFIGURATION_AND_DEPENDENCY_AUDIT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/05_CONFIGURATION_AND_DEPENDENCY_AUDIT.md) | Audit of parameter conflicts, multiple sources of truth, and dependency overlaps |
| [06_ENTRY_POINTS_AND_EXECUTION_MAP.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/06_ENTRY_POINTS_AND_EXECUTION_MAP.md) | Map of all application entry points, launch scripts, and process conflict hazards |
| [07_LEGACY_UNUSED_AND_ORPHANED_CODE.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/07_LEGACY_UNUSED_AND_ORPHANED_CODE.md) | Inventory of staging directories, pre-blender backups, and abandoned utility scripts |
| [08_RISK_AND_IMPACT_ASSESSMENT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/08_RISK_AND_IMPACT_ASSESSMENT.md) | Comprehensive risk matrix assessing safety, reliability, build, and maintenance impacts |
| [09_RECOMMENDED_CONSOLIDATION_PLAN.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/09_RECOMMENDED_CONSOLIDATION_PLAN.md) | Phased, non-destructive consolidation roadmap awaiting human operator approval |
| [10_AUDIT_EVIDENCE_AND_METHODS.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/architecture_audit/10_AUDIT_EVIDENCE_AND_METHODS.md) | Methodological documentation, static analysis scripts, and reproducible evidence logs |
