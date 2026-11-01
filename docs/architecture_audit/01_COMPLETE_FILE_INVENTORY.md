# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 01: Complete File Inventory

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Scope:** Complete repository inventory distinguishing maintained source code from generated and external artifacts.

---

## 1. Directory Tree & Structural Inventory

```
VIRA-agent-bridge-migration/ (Workspace Root: 4,191 files)
├── adapters/                        # Hardware and service adapters (Python)
│   ├── brain/                       # Cognitive reasoning and mission planning
│   ├── gemini_robotics/             # Gemini Multimodal semantic grounding tools
│   ├── motion/                      # Base, arm, and hand controllers
│   ├── perception/                  # YOLO/ONNX object detection and world model
│   ├── robot-bridge/                # Bridge adapters (navigation, safety, feedback)
│   ├── sdk/                         # Client SDK and workflow engine
│   ├── vision/                      # Computer vision adapters
│   └── voice/                       # Audio engine, Faster-Whisper, Kokoro TTS
├── agent_bridge/                    # FastMCP server for AI agent task management
│   ├── approvals/                   # Approval state files
│   ├── inbox/                       # Ingestion queues
│   ├── logs/                        # Agent interaction logs
│   ├── results/                     # Task outcome reports
│   └── tasks/                       # MCP tasks and locks
├── backup_pre_blender_integration/  # [LEGACY BACKUP] Pre-Blender mesh and URDF files (63 MB)
├── bin/                             # Auxiliary compiled binaries
├── config/                          # Central configuration files (YAML, JSON, TOML)
├── contracts/                       # JSON Schemas for event contracts
├── data/                            # Persistent runtime storage and database files
├── docs/                            # Comprehensive architectural documentation
│   ├── architecture_audit/          # Current comprehensive audit deliverables
│   └── screenshots/                 # 20 UARCC verification screenshots across resolutions
├── firmware/                        # STM32 embedded firmware sources & protocols
├── gracemo_control_center/          # PySide6 Unified Autonomous Robotics Control Center (UARCC)
│   ├── config/                      # UI settings and topic registry
│   ├── core/                        # Central event bus, health monitor, ROS manager
│   ├── modules/                     # 11 functional modules (Overview, Sim, Nav, etc.)
│   ├── resources/styles/            # Tokens and master QSS stylesheet
│   ├── tests/                       # Comprehensive integration test suite (30 tests)
│   ├── widgets/                     # Reusable UI component library (11 widgets)
│   └── workers/                     # Host system monitor background thread
├── kernel/                          # Rust neural-symbolic cognitive architecture
│   ├── gracemo-k/                   # K-Language compiler, parser, AST, runtime
│   ├── gracemo-kernel/              # Context compiler, ledger, graph memory, REST daemon
│   └── gracemo-types/               # Shared Rust type definitions
├── prototypes/                      # Prototype integration symlinks
│   └── gracemo_integrated_v1/       # Symlink to gracemo_control_center
├── requirements/                    # Pinned Python requirements files
├── ros2_ws/                         # ROS 2 Jazzy workspace
│   └── src/
│       ├── gracemo_bridge/          # Interaction, kernel, and sensor bridges
│       ├── gracemo_description/     # Active URDF, Xacro, and 3D visual meshes
│       ├── gracemo_gazebo/          # Gazebo Harmonic worlds, plugins, launch files
│       ├── gracemo_hardware/        # STM32 serial MCU transport, status, LiDAR config
│       ├── gracemo_moveit_config/   # MoveIt 2 manipulation kinematics configuration
│       └── gracemo_nav2/            # Nav2 costmaps, planner/controller parameters
├── scripts/                         # Operational launchers, exploration, and verification scripts
├── simulation/                      # Docker simulation definitions
├── staging_blender_integration/     # [STAGING] Blender export models, meshes, reports (60 MB)
├── tests/                           # Workspace test suites (unit, integration, safety, E2E)
├── tools/                           # Development and maintenance utilities
├── unified_control_center           # Workspace symlink to gracemo_control_center
├── vira_interaction/                # Pygame voice interaction engine & facial avatar
└── workflows/                       # Continuous integration definitions
```

---

## 2. Maintained Source Code vs Generated Artifacts

Out of the 4,191 files in the primary workspace:
- **Maintained Source Code:** **629 files** (15.0%)
- **Generated / Build Artifacts:** **3,562 files** (85.0%)

### 2.1 Inventory Breakdown by Extension (Maintained vs Generated)

| Extension | Category | Maintained Count | Generated / Build Count | Description / Role |
| :--- | :--- | :---: | :---: | :--- |
| `.py` | Python Sources | 290 | 0 | ROS 2 nodes, adapters, UI widgets, test suites |
| `.pyc` | Python Bytecode | 0 | 212 | Cached bytecode in `__pycache__` |
| `.rs` | Rust Sources | 24 | 0 | MNSE/K cognitive kernel and parser |
| `.rmeta` / `.rlib` | Rust Build Objects | 0 | 289 | Cargo build artifacts in `kernel/target/` |
| `.o` / `.d` | C/C++ Object Files | 0 | 1,111 | Colcon build artifacts in `build/` |
| `.cmake` / `.make` | CMake Build Rules | 0 | 135 | Colcon-generated CMake artifacts |
| `.timestamp` / `.stamp` | Build Markers | 0 | 268 | Build pipeline synchronization stamps |
| `.json` | Data / Config / Schema | 48 | 224 | Configuration, contracts, and build metadata |
| `.yaml` / `.yml` | Configuration | 36 | 0 | Nav2, hardware, MoveIt, and safety parameters |
| `.xacro` / `.urdf` | Robot Description | 16 | 2 | Robot kinematics, joint geometry, Gazebo plugins |
| `.obj` / `.mtl` | 3D Visual Meshes | 30 | 56 | CAD/Blender robot visual meshes |
| `.sh` | Shell Scripts | 71 | 0 | Launchers, test runners, Distrobox setup |
| `.md` | Documentation | 85 | 0 | Architectural specs, audit reports, manuals |
| `.jpg` / `.png` | Visual Artifacts | 46 | 0 | Verification screenshots and camera frames |
| `[no_ext]` | Shell / Binaries | 44 | 587 | Executable wrappers and compiler targets |
| **Total** | | **629** | **3,562** | **4,191 Primary Workspace Files** |

---

## 3. Integrated Prototype Tree (`prototypes/gracemo_integrated_v1`)

The prototype reference directory at `/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1` contains 2,626 files:
- **Maintained Source Files:** **133 files**
- **Generated Log / Build Artifacts:** **2,493 files** (primarily in `ros2_ws/log/` and `ros2_ws/build/`)

### Key Subsystems in Prototype Tree
1. `ros2_ws/src/gracemo_command_coordinator/` (Autonomous multi-room coordinator)
2. `ros2_ws/src/gracemo_interaction/` (Speech adapters and intent parser)
3. `ros2_ws/src/gracemo_navigation/` (Mapping, Nav2 params, terrain monitor)
4. `ros2_ws/src/gracemo_bringup/` (Prototype unified launch file)
5. `ros2_ws/src/gracemo_hardware/` (Duplicated hardware node and MCU bridge)
6. `ros2_ws/src/gracemo_simulation/` (Duplicated apartment world and simulation launch)
7. `ros2_ws/src/gracemo_robot_description/` (Duplicated URDF and visual meshes)
8. `unified_control_center/` (Duplicated baseline UARCC control center)

---

## 4. Staging, Backup, and Legacy Trees

Three large auxiliary subtrees reside in the primary workspace that represent historical milestones:

1. **`staging_blender_integration/` (60.2 MB):**
   - Created during the migration from primitive geometric shapes to Blender-modeled CAD meshes.
   - Contains a complete duplicate set of 15 `.obj` files, expanded URDFs, and audit reports.
2. **`backup_pre_blender_integration/` (63.8 MB):**
   - Created as a safety snapshot prior to executing the Blender mesh integration.
   - Contains duplicate Gazebo worlds (`apartment_floor_vira.world.bak`), URDFs, and mesh configurations.
3. **`graceemo_interaction` (Symlink in workspace):**
   - Points to `vira_interaction/` in the workspace, but exists as a complete 432 KB standalone clone with its own `.venv` and test files in `/home/sabarishchandrasekaran/projects/VIRA/graceemo_interaction/`.
