# Changelog

All notable changes to **GRaCEmo ViRa** (Autonomous Robotics Nervous System) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 🔜 [0.0.2] — Semantic Knowledge Grounding & Vision-Nav2 Closed Loop
- **What**: Bridge simulated camera feed (`/camera/image_raw`) directly to YOLOv11 + ByteTrack and populate the MNSE Spatial Knowledge Graph in real-time.
- **Why**: Enable high-level natural language semantic queries (e.g. *"Where is the laptop?"*) and closed-loop task execution.

---

## [0.0.1] - 2026-08-31 (Unified Architecture, Modular Adapters & ROS 2 Humble Simulation Stack) 🏗️🤖🚀

### Added — Unified Configuration Engine & Schemas
- **`adapters/sdk/gracemo_sdk/config.py`**: Centralized `ConfigLoader` and `ConfigDict` providing type-safe dot-notation access (e.g., `config.stt.model_size`, `config.detector.engine`) with environment variable overrides and project root auto-discovery.
- **`config/perception.yaml`**: Schema-driven perception settings covering camera resolution, YOLOv11 weights, ByteTrack multi-object tracking thresholds, YuNet face recognition, and 3D spatial camera intrinsics.
- **`config/voice.yaml`**: Schema-driven audio settings covering Faster-Whisper STT model sizes, Silero VAD thresholds, Edge-TTS / Kokoro TTS voices, OpenWakeWord keywords, and 48kHz audio I/O.
- **`config/brain.yaml`**: Schema-driven cognitive configuration supporting multi-turn dialogue memory turns and swappable LLM backends (NVIDIA NIM, Google Gemini, local Ollama / vLLM).
- **`config/robot.yaml`**: Kinematics (0.32m wheelbase, 0.065m wheel radius, max velocity), head pan/tilt limits, and ESP32 micro-ROS serial parameters.

### Added — Modular Multi-Modal Voice Adapter
- **`adapters/voice/gracemo_voice/stt.py`**: Modular `BaseSTTEngine` and `FasterWhisperEngine` with Silero VAD speech segmentation and silence clipping.
- **`adapters/voice/gracemo_voice/tts.py`**: Modular `BaseTTSEngine` with `EdgeTTSEngine` (Neural cloud) and `KokoroTTSEngine` (local GPU synthesis).
- **`adapters/voice/gracemo_voice/wake_word.py`**: Modular `BaseWakeWordEngine` and `OpenWakeWordEngine` for low-CPU offline keyword activation.
- **`adapters/voice/gracemo_voice/audio_engine.py`**: Refactored `VoiceAdapter` orchestrating physical microphone hardware auto-detection (`sof-hda-dsp (hw:1,0)`) at 48kHz and non-blocking speech capture.

### Added — Modular Vision & Perception Adapter
- **`adapters/vision/gracemo_vision/detector.py`**: YOLOv11 object detector integrated with **ByteTrack** multi-object tracking to assign persistent `track_id` values across occlusions and frame boundaries.
- **`adapters/vision/gracemo_vision/face_id.py`**: Fast YuNet CNN face detector with identity matching against enrolled profile databases.
- **`adapters/vision/gracemo_vision/spatial.py`**: 3D spatial coordinate estimator calculating real-world lateral offset $(X)$, depth distance $(Y)$, and elevation $(Z)$ in meters from 2D bounding boxes.

### Added — Cognitive Brain & Multi-Turn Reasoner
- **`adapters/brain/gracemo_brain/reasoner.py`**: Multi-modal reasoning engine that fetches live world snapshots from the Kernel, injects multi-turn dialogue history, and dispatches structured `ActionRequested` events.

### Added — ROS 2 Humble & Modern Gazebo Simulation Platform (`ros2_ws/`)
- **Distrobox Container (`gracemo-ros2`)**: Isolated Ubuntu 22.04 LTS container with ROS 2 Humble Desktop Full, `ros_gz_sim` (Gazebo Fortress v6.18), and NVIDIA GPU passthrough on Arch Linux.
- **`gracemo_description`**:
  - `urdf/gracemo_vira.urdf.xacro`: Complete differential-drive robot model with 360° LiDAR, RGB camera, pan/tilt head, and driven wheels.
  - `urdf/gazebo_plugins.xacro`: Modern `ignition-gazebo-diff-drive-system`, `sensors-system`, and `imu-system` plugins.
  - `launch/display.launch.py`: RViz2 visual model inspection launch file.
- **`gracemo_gazebo`**:
  - `worlds/apartment_floor.world`: Full **16m × 12m, 4-room furnished apartment floorplan** (Master Bedroom, Kitchen & Dining, Living Room, Home Study, Central Hallway) with **1.4m spacious doorways** and self-contained SDFormat lighting and ground plane.
  - `launch/sim.launch.py`: Gazebo simulation launcher with `-r` auto-run physics and `ros_gz_bridge` parameter bridge.
- **`gracemo_bridge`**:
  - `gracemo_bridge/kernel_bridge.py`: Bidirectional ROS 2 $\leftrightarrow$ Kernel bridge routing `/camera/image_raw`, `/odom`, `/scan`, and translating Kernel `ActionRequested -> Move` into `/cmd_vel`.
- **`gracemo_nav2`**:
  - `config/nav2_params.yaml`: Nav2 configuration with DWB local trajectory planner, NavFn global planner, and local/global costmaps.
  - `launch/nav2.launch.py`: Unified bringup launching SLAM Toolbox live 2D mapping, Nav2 navigation, and RViz2.
  - `gracemo_nav2/frontier_explorer.py`: **Zero-hardcoded Dynamic SLAM Frontier Explorer** that mathematically detects boundaries between free space $(0)$ and unknown space $(-1)$ and dispatches Nav2 goals.

### Added — Mission Control & Exploration Scripts
- **`scripts/mission_control.py`**: Live terminal Mission Control UI with real-time room identification (Bedroom, Kitchen, Living Room, Study), mini ASCII 2D floorplan, coordinates, speed, and 1-key autonomous mission dispatch.
- **`scripts/start_sim.sh`**: One-command simulation launcher with automatic stale process cleanup and XWayland display configuration (`QT_X11_NO_MITSHM=1`).
- **`scripts/start.sh`**: Standalone live demo launcher with terminal REPL.

### Fixed — Engineering & Physics Improvements
- **LiDAR Angle Range Mapping**: Fixed trigonometric angle calculation in exploration scripts (`angle = angle_min + i * angle_increment`) so the robot looks forward ($0^\circ$) instead of backwards ($-180^\circ$).
- **Wheel Motor Torque Limits**: Added explicit `<limit effort="100.0" velocity="20.0" />` to continuous wheel joints in URDF, resolving Gazebo 0-torque physics stalling.
- **Caster Drag & Friction**: Set caster wheel friction to `0.0` with slip parameters to prevent floor dragging.
- **Topic Scoping in Modern Gazebo**: Added leading slashes (`/cmd_vel`, `/odom`, `/scan`, `/camera/image_raw`) to DiffDrive and sensor plugins to match `ros_gz_bridge` global topic namespaces.
- **Gazebo Offline Model URIs**: Replaced legacy remote `model://sun` and `model://ground_plane` URIs with self-contained native SDFormat elements, eliminating network timeout errors.

---

### System Architecture Verification

```text
✓ SDK Config Root: /home/mab/Applications/lpu-project/gracemo-vira
✓ Voice Adapter: Faster-Whisper (CPU INT8) + Silero VAD
✓ Vision Adapter: YOLOv11n + ByteTrack + 3D Spatial
✓ Brain Adapter: NVIDIA NIM (google/diffusiongemma-26b-a4b-it)
✓ Kernel: gracemo-kernel (HTTP 7780 + SQLite Ledger + SSE)
✓ ROS 2 Simulation: Gazebo Sim v6.18 + Nav2 + SLAM Toolbox (4-Room Apartment)
✓ Colcon Build: 4 packages finished (0.97s)
```
