# GraceEMO ViRa — System Architecture (LPU Digital Twin)

**Runtime truth (Command Center):** the browser at `:8888` talks to `virtual_space_node` (Python kinematics + Tornado). Gazebo Harmonic and Nav2 are **optional** packages, not the live twin loop. See `AUDIT_REPORT.md`.

## High-Level Architecture

```
                    ┌──────────────────────────┐
                    │    LPU DIGITAL TWIN      │
                    │                          │
                    │  200m x 200m Campus      │
                    │  8 Academic Blocks       │
                    │  Central Library (B37)   │
                    │  Uni-Mall, Hospital      │
                    │  Sports, Hostels         │
                    │  Roads, Paths, Gates     │
                    │  Dynamic Pedestrians     │
                    │  Vehicles, Weather       │
                    │  Semantic Navigation     │
                    └────────────┬─────────────┘
                                 │
                         ┌───────▼───────┐
                         │   GAZEBO      │
                         │  SIMULATION   │
                         │  (Harmonic)   │
                         └───────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │       ROBOT EDGE        │
                    │                         │
                    │ Vision (YOLO11n)        │
                    │ LiDAR (360°)            │
                    │ Depth Camera            │
                    │ SLAM (slam_toolbox)     │
                    │ Navigation (Nav2)       │
                    │ Voice (Whisper/Kokoro)  │
                    │ Brain (Gemini LLM)      │
                    │ Memory (SQLite)         │
                    │ ROS 2 Jazzy             │
                    └────────────┬────────────┘
                                 │
                              CAN-FD
                                 │
                    ┌────────────▼────────────┐
                    │       MCU LAYER         │
                    │                         │
                    │ Motor control           │
                    │ Encoders                │
                    │ PID                     │
                    │ Safety watchdog         │
                    │ Emergency stop          │
                    └────────────┬────────────┘
                                 │
                              MOTORS

                         ╔══════════════╗
                         ║ CENTRAL AI   ║
                         ║ GPU SERVER   ║
                         ║              ║
                         ║ LLM / VLM    ║
                         ║ Heavy AI     ║
                         ║ Knowledge    ║
                         ║ Fleet Mgmt   ║
                         ║ Analytics    ║
                         ╚══════╤═══════╝
                                │
                           ROS 2 / API
                                │
                    ┌───────────▼──────────┐
                    │ ROBOTICS COMMAND     │
                    │ CENTER (Web UI)      │
                    │                      │
                    │ 3D Campus View       │
                    │ Mission Builder      │
                    │ AI Decisions         │
                    │ Sensor Feeds         │
                    │ Server Status        │
                    │ Fault Injection      │
                    │ Research Mode        │
                    │ Analytics Dashboard  │
                    └──────────────────────┘
```

## ROS 2 Package Architecture

### Existing Packages (Phase 1 — Enhanced)
| Package | Purpose | Key Topics |
|---------|---------|-----------|
| `gracemo_gazebo` | Simulation engine, web studio, campus world | `/odom`, `/scan`, `/camera/image_raw` |
| `gracemo_description` | URDF robot model (chassis, sensors) | TF tree |
| `gracemo_navigation` | Nav2 + SLAM + human-aware nav | `/cmd_vel`, `/map` |
| `gracemo_perception` | YOLO detection + sensor fusion | `/gracemo/detections` |
| `gracemo_voice` | Wake word + STT + TTS | `/gracemo/speech_input`, `/gracemo/say` |
| `gracemo_brain` | LLM cognitive reasoning + VLM | `/gracemo/ai_decision` |
| `gracemo_memory` | SQLite episodic + semantic memory | Database |
| `gracemo_control` | Motor control abstraction | `/cmd_vel` |
| `gracemo_interfaces` | Custom messages, services, actions | `.msg`, `.srv` |
| `gracemo_bringup` | Master config + launch files | Config YAML |

### New Packages (Phase 2-6)
| Package | Purpose | Key Topics |
|---------|---------|-----------|
| `gracemo_scenarios` | Weather, crowd, traffic presets | `/gracemo/scenario_state` |
| `gracemo_pedestrians` | Dynamic pedestrian + vehicle agents | `/gracemo/dynamic_agents` |
| `gracemo_missions` | Mission planning, NL builder | `/gracemo/mission_state` |
| `gracemo_server` | Central AI server + fleet mgmt | `/gracemo/server_state` |
| `gracemo_network_sim` | Network condition simulation | `/gracemo/network_state` |
| `gracemo_fault_injection` | Fault injection engine | `/gracemo/fault_state` |
| `gracemo_research` | Research experiment framework | `/gracemo/research_state` |
| `gracemo_analytics` | Metrics, logging, replay | `/gracemo/analytics` |

## Network Architecture

```
ROBOT EDGE (Jetson / IPC equivalent)
        │
        │  ROS 2 DDS (configurable latency/loss)
        │
CENTRAL AI SERVER
        │
        │  WebSocket (live telemetry)
        │
WEB DASHBOARD (Browser)
```

### Edge/Cloud Failover States
- **ONLINE**: Full server connectivity, heavy AI tasks offloaded
- **PARTIAL**: Degraded connection, only critical tasks offloaded
- **OFFLINE**: No server, robot uses local fallback models + deterministic nav

## Safety Architecture

```
                    ┌─────────────────┐
                    │   AI / LLM      │
                    │   (Proposes)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ SAFETY LAYER    │
                    │ (Validates)     │
                    │                 │
                    │ Speed limits    │
                    │ Collision check │
                    │ Restricted zone │
                    │ E-stop          │
                    │ Watchdog        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ MOTOR CONTROL   │
                    │ (Executes)      │
                    └─────────────────┘
```

**CRITICAL**: AI/LLM may propose actions. The safety/controller layer VALIDATES and EXECUTES them. AI cannot bypass safety.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| OS | Ubuntu 24.04 (Docker) |
| Middleware | ROS 2 Jazzy |
| Simulator | Gazebo Harmonic (headless) |
| Navigation | Nav2 + SLAM Toolbox |
| Perception | YOLO11n + OpenCV |
| LLM | Gemini 2.0 Flash |
| STT | Faster-Whisper |
| TTS | Kokoro |
| Memory | SQLite + sqlite-vec |
| Server API | FastAPI + Tornado |
| Database | PostgreSQL 16 |
| Dashboard | Web (Three.js + vanilla JS) |
| Container | Docker + Docker Compose |

## Development Phases

| Phase | Status | Components |
|-------|--------|-----------|
| 1 | ✅ Enhanced | ROS 2 workspace, Gazebo, Robot, Campus, Sensors, Teleop |
| 2 | ✅ Built | Dynamic pedestrians, vehicles, scenarios, navigation upgrades |
| 3 | ✅ Built | Semantic campus, mission system, AI perception |
| 4 | ✅ Built | Central AI server, network simulation, failover |
| 5 | ✅ Built | Fault injection, research experiments, analytics |
| 6 | 🔧 Web UI | Professional dashboard (upgrading existing web studio) |
| 7 | 📋 Planned | Physical robot integration |
