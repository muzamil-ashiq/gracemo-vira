# GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC) V1.0
## Architectural Specification and Interface Audit Report

**Platform:** Ubuntu 24.04 LTS (Noble Numbat) | ROS 2 Jazzy Jalisco | Gazebo Harmonic 8.15.0  
**Host Hardware:** NVIDIA GeForce RTX 5060 Laptop GPU (8151 MiB VRAM), AMD Ryzen / Intel x86_64 Host  
**GUI Framework:** Python 3.12 / PySide6 6.12.0 / pyqtgraph 0.14.0 / OpenCV / NumPy  
**Git Baseline Checkpoints:**  
- Migration Repository (`/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`):  
  `19560b3dc7e0e911451f6a82252ecf693ecaa9dc` (tag: `v1.0.0-accepted-baseline`)  
- VIRA Repository (`/home/sabarishchandrasekaran/projects/VIRA`):  
  `68b13499ed049df3df38c97d3b8fde14d34c6ea3` (tag: `v1.0.0-accepted-baseline`)  
**Development Feature Branch:** `feature/gracemo-unified-control-center`  
**Safety Locked Status:** `SerialMCUTransport.PROTOCOL_CONFIRMED = False` | `MOTOR_OUTPUT_ENABLED = 0`

---

## 1. Executive Architecture Overview

The **Unified Autonomous Robotics Control Center (UARCC)** is a production-grade, modular desktop engineering workstation interface designed for GRaCEmo ViRa. It sits directly atop the established ROS 2 Jazzy and Gazebo Harmonic simulation substrate without altering or duplicating existing autonomy, perception, voice, cognitive, or safety engines.

### Key Architectural Tenets
1. **Client Independence:** The UARCC desktop interface is strictly an engineering client. Autonomous navigation, localization, safety watchdogs, obstacle avoidance, and lifecycle managers execute independently in ROS 2 background nodes. Terminating, restarting, or crashing the GUI has **zero impact** on active robot motion or safety.
2. **Pygame Avatar Preservation:** The existing Pygame interaction engine (`vira_interaction/model.py`) remains completely independent. The UARCC does not replace Pygame or voice capture pipelines; it visualizes and interfaces with interaction events via established ROS 2 topics (`/interaction/spoken_feedback`, `/interaction/user_input`, `/interaction/voice_recognized`).
3. **Single Command Authority:** The GUI **never publishes directly to `/cmd_vel`** and never bypasses the authoritative command pipeline. All autonomous navigation commands are dispatched through the 11-state `gracemo_command_coordinator` (`/coordinator/command`).
4. **Safety Pipeline Invariant:** The command chain remains strictly preserved:
   $$\text{Nav2 BT} \xrightarrow{/cmd\_vel\_nav} \text{velocity\_smoother} \xrightarrow{/cmd\_vel\_smoothed} \text{collision\_monitor} \xrightarrow{/cmd\_vel\_safe} \text{terrain\_monitor} \xrightarrow{/cmd\_vel} \text{ros\_gz\_bridge}$$
5. **Zero Fabrication:** Subsystem states are derived purely from live ROS 2 telemetry. If data is missing or delayed, the GUI explicitly displays `NOT CONNECTED`, `INITIALIZING`, `STALE DATA`, or `ERROR`. `READY` is displayed only when empirical readiness conditions are met.

---

## 2. Authoritative ROS 2 Interface Registry

| Subsystem | Topic / Service / Action | Message / Service Type | QoS Profile | Authoritative Owner | Role in UARCC |
|---|---|---|---|---|---|
| **Clock** | `/clock` | `rosgraph_msgs/msg/Clock` | Sensor Data (Best Effort) | `ros_gz_bridge` | Simulation clock & synchronization |
| **LiDAR** | `/scan` | `sensor_msgs/msg/LaserScan` | Sensor Data (Best Effort) | `ros_gz_bridge` | 360° top-down polar/Cartesian point cloud |
| **Odometry** | `/odom` | `nav_msgs/msg/Odometry` | Sensor Data (Best Effort) | `ros_gz_bridge` | Linear/angular velocities & dead reckoning |
| **IMU** | `/imu/data` | `sensor_msgs/msg/Imu` | Sensor Data (Best Effort) | `ros_gz_bridge` | Roll, pitch, yaw, accelerations, angular rates |
| **RGB Camera** | `/camera/image_raw` | `sensor_msgs/msg/Image` | Sensor Data (Best Effort) | `ros_gz_bridge` | Live 30 FPS RGB vision feed |
| **Camera Info** | `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Reliable | `ros_gz_bridge` | Intrinsics & distortion parameters |
| **Depth Camera** | `/camera/depth_image` | `sensor_msgs/msg/Image` | Sensor Data (Best Effort) | `ros_gz_bridge` | Float32/16UC1 depth feed with colorization |
| **Joint States** | `/joint_states` | `sensor_msgs/msg/JointState` | Sensor Data (Best Effort) | `ros_gz_bridge` | Neck, waist, arm, and gripper joint angles |
| **Localization** | `/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Transient Local (Reliable) | `amcl` | 2D map pose & variance $(x, y, \theta)$ |
| **Particles** | `/particle_cloud` | `nav2_msgs/msg/ParticleCloud` | Sensor Data (Best Effort) | `amcl` | AMCL particle dispersion cloud |
| **Map** | `/map` | `nav_msgs/msg/OccupancyGrid` | Transient Local (Reliable) | `map_server` | Authoritative 2D static occupancy grid |
| **Global Path** | `/plan` | `nav_msgs/msg/Path` | Reliable | `planner_server` | Active Nav2 global path trajectory |
| **Costmaps** | `/global_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` | Transient Local | `planner_server` | Static & inflated costmap obstacles |
| **Local Costmap**| `/local_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` | Transient Local | `controller_server` | Dynamic obstacle sensor costmap |
| **Drive Motion** | `/cmd_vel` | `geometry_msgs/msg/Twist` | Reliable | `terrain_monitor` | Physical wheel velocity stream |
| **Safe Motion** | `/cmd_vel_safe` | `geometry_msgs/msg/Twist` | Reliable | `collision_monitor` | Pre-terrain obstacle-safe velocity |
| **E-Stop Cmd** | `/terrain/emergency_stop` | `std_msgs/msg/Bool` | Reliable | UARCC / Coord | Assert emergency stop into safety gate |
| **Safety Status**| `/terrain/safety_stop` | `std_msgs/msg/Bool` | Reliable | `terrain_monitor` | Dynamic obstacle / slope breach active |
| **Terrain Telemetry**| `/terrain/status` | `std_msgs/msg/String` (JSON) | Reliable | `terrain_monitor` | Slope grade, pitch/roll angles, speed factor |
| **Coord Cmd** | `/coordinator/command` | `std_msgs/msg/String` (JSON) | Reliable | UARCC / User | Dispatch navigation intents & actions |
| **Coord Feedback**| `/coordinator/feedback`| `std_msgs/msg/String` (JSON) | Reliable | `gracemo_command_coordinator` | 11-state FSM transitions & speech status |
| **User Speech** | `/interaction/user_input` | `std_msgs/msg/String` | Reliable | Text / Voice / Pygame | Natural language query dispatch |
| **Spoken Output**| `/interaction/spoken_feedback`| `std_msgs/msg/String` (JSON) | Reliable | `interaction_node` | TTS output text & avatar status |
| **Voice Recog** | `/interaction/voice_recognized`| `std_msgs/msg/String` | Reliable | Whisper Mic | Live recognized voice transcripts |
| **TF Transforms**| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | Dynamic / Transient Local | `robot_state_publisher`, GZ, AMCL | `map -> odom -> base_footprint -> lidar_link` |
| **Nav2 Action** | `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Action Protocol | `bt_navigator` | Low-level Nav2 action execution |
| **Nomotion Srv**| `/request_nomotion_update` | `std_srvs/srv/Empty` | Service Protocol | `amcl` | Force AMCL particle filter update |
| **Clear Costmaps**| `/global_costmap/clear_entirely_global_costmap` | `nav2_msgs/srv/ClearEntireCostmap` | Service Protocol | `planner_server` | Clear costmap obstacles during recovery |

---

## 3. Authoritative Destinations Registry

Loaded strictly from `config/destinations.json`:

```json
{
  "hallway":     {"name": "Central Hallway",       "x":  0.0, "y":  0.0, "yaw":  0.00},
  "living_room": {"name": "Living Room",           "x":  4.0, "y": -2.5, "yaw": -1.57},
  "kitchen":     {"name": "Kitchen & Dining",      "x": -5.0, "y": -2.5, "yaw": -1.57},
  "bedroom":     {"name": "Master Bedroom",        "x": -5.0, "y":  2.2, "yaw":  1.57},
  "study":       {"name": "Home Study",            "x":  4.5, "y":  3.0, "yaw":  1.57},
  "lab":         {"name": "Robotics Research Lab", "x":  2.5, "y":  2.0, "yaw":  0.00}
}
```

---

## 4. Hardware Safety Invariant Protocols

1. **Protocol Confirmation Guard:**
   ```python
   SerialMCUTransport.PROTOCOL_CONFIRMED = False
   ```
2. **Motor Output Guard:**
   ```c
   #define MOTOR_OUTPUT_ENABLED 0
   ```
3. **UI Safety Notice:**  
   Every hardware telemetry and motor interface within UARCC is permanently watermarked:  
   `SIMULATION ONLY — PHYSICAL ACTUATION DISABLED`

---

## 5. UARCC Application Modular Architecture

```text
gracemo_control_center/
├── main.py                     # Entry point (initializes PySide6 QApplication, starts lifecycle)
├── app.py                      # Main UARCC Application orchestration & Window management
│
├── config/
│   ├── settings.py             # User and application preferences (refresh rates, color tokens)
│   └── topic_registry.py       # Authoritative ROS topic and service definitions
│
├── core/
│   ├── application_manager.py  # Central application controller
│   ├── ros_manager.py          # ROS 2 node lifecycle & worker management
│   ├── ros_executor.py         # MultiThreadedExecutor running in dedicated QThread
│   ├── connection_manager.py   # Connection heartbeat & stale data watchdog
│   ├── health_monitor.py       # Subsystem health verification (11-stage readiness logic)
│   ├── event_bus.py            # Qt-signal-based decoupled event dispatch
│   └── lifecycle_manager.py    # Clean startup and zero-orphan shutdown handlers
│
├── ros/
│   ├── sensor_subscriber.py    # QoS-tuned sensor streams (/scan, /imu, /odom)
│   ├── camera_subscriber.py    # High-throughput RGB & Depth image transport (OpenCV bridging)
│   ├── lidar_subscriber.py     # LaserScan parser & polar-to-Cartesian conversion
│   ├── localization_client.py  # AMCL pose & TF tree query interface
│   ├── navigation_client.py    # Coordinator command publisher & feedback listener
│   ├── safety_client.py        # Terrain monitor status & E-stop assertion
│   └── diagnostics_client.py   # Topic rate, latency, and node status inspector
│
├── modules/
│   ├── overview/               # Module A: Live System Dashboard
│   ├── simulation/             # Module B: Gazebo Harmonic Status & Viewer Control
│   ├── sensors/                # Module C: RGB, Depth, LiDAR, IMU, Odometry Center
│   ├── navigation/             # Module D: Interactive Map, Destinations & Nav2 Controls
│   ├── localization/           # Module E: AMCL Covariance & TF Chain Monitor
│   ├── interaction/            # Module F: Voice, Whisper STT, TTS & Conversation Log
│   ├── cognitive/              # Module G: MNSE Kernel, K Language & Agent Bridge Status
│   ├── safety/                 # Module H: Collision, Terrain Grade & Emergency Stop Center
│   ├── diagnostics/            # Module I: ROS Graph, Node Lifecycle & Host CPU/GPU Telemetry
│   ├── logs/                   # Module J: Unified Multi-Source Filterable Event Log
│   └── settings/               # Module K: Display, Rendering & Refresh Rate Preferences
│
├── widgets/
│   ├── status_indicator.py     # Hardware-style LED / Badge status indicator
│   ├── camera_view.py          # Hardware-accelerated OpenGL / QPainter RGB viewer
│   ├── depth_view.py           # Colormapped depth visualization with distance probe
│   ├── lidar_view.py           # 360° real-time polar/Cartesian radar view with safety zone
│   ├── map_view.py             # 2D occupancy grid with zoom, pan, path, and robot pose
│   ├── robot_pose_widget.py    # X/Y/Yaw coordinates, compass, and covariance indicator
│   ├── telemetry_widget.py     # Real-time strip charts for velocities and attitude
│   └── log_viewer.py           # High-performance virtualized log table with search/filtering
│
├── workers/
│   ├── ros_worker.py           # Background executor worker
│   ├── image_worker.py         # Dedicated image decoding and colormapping worker
│   ├── system_monitor_worker.py# Host psutil & NVML GPU telemetry collector (1 Hz)
│   └── diagnostic_worker.py    # Periodic ROS graph & node probe worker
│
├── resources/
│   ├── styles/
│   │   ├── dark_theme.qss      # Dark engineering palette stylesheet
│   │   └── tokens.py           # Centralized color tokens (#101820, #17232D, #F28C28)
│   └── icons/                  # Scalable vector / SVG status icons
│
└── tests/                      # Comprehensive pytest test harness (30+ test cases)
```

---

## 6. Implementation Phases Roadmap

- **PHASE 0 (Completed):** Repository audit, interface discovery, safety confirmation, and architecture specification.
- **PHASE 1:** Core PySide6 application foundation, navigation sidebar, top status bar, theme tokens, and routing.
- **PHASE 2:** Thread-safe ROS 2 communication layer, background executor, connection heartbeat, and health monitors.
- **PHASE 3:** Live sensor visualization (RGB, Depth colormapping, 360° LiDAR radar, IMU attitude, and Odometry).
- **PHASE 4:** Interactive 2D occupancy grid navigation map, global path, destination selector, and coordinator client.
- **PHASE 5:** Voice & interaction center (Whisper live transcription, spoken responses, interaction events).
- **PHASE 6:** Cognitive MNSE/K status, safety control center (emergency stop, terrain grade), and system diagnostics (CPU/GPU/RAM).
- **PHASE 7:** Gazebo simulation viewer integration, Pygame interaction independence, and GUI closure resilience.
- **PHASE 8:** End-to-end integration testing and automated GUI verification suite.
- **PHASE 9:** Final acceptance verification, documentation, and engineering handoff report.
