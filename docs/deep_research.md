# GRACEemo ViRa — Deep Research Report

> This document compiles all research findings so you can make informed decisions before writing a single line of code.

---

## 1. ROS2 Distribution

| Distro | Release | EOL | Python | Gazebo | Verdict |
|--------|---------|-----|--------|--------|---------|
| **Humble** | May 2022 | May 2027 | 3.10 | Classic (gazebo11) | ⚠️ Aging, Gazebo Classic is EOL since Jan 2025 |
| **Jazzy** ⭐ | May 2024 | May 2029 | 3.12 | Harmonic (gz-sim) | ✅ Current LTS, modern Gazebo, 3 years of support |
| **Rolling** | Continuous | N/A | Latest | Latest | ❌ Unstable, breaks often, not for production |

> [!TIP]
> **Pick Jazzy.** It's the current LTS, has native Gazebo Harmonic support, and will be supported through your entire project and beyond. Humble is aging out and its Gazebo Classic is already EOL.

**Gotcha:** Jazzy targets Ubuntu 24.04 + Python 3.12. Your Arch host has Python 3.14. **Docker is mandatory** — no bare-metal ROS2 on Arch.

---

## 2. Simulation Engine

| Engine | GPU Requirement | Docker? | ROS2 Integration | Verdict |
|--------|----------------|---------|-----------------|---------|
| **Gazebo Classic (gazebo11)** | Minimal | Easy | Native (Humble) | ❌ EOL since Jan 2025, deprecated |
| **Gazebo Harmonic (gz-sim)** ⭐ | Minimal-moderate | Easy | Native (Jazzy) via `ros_gz` | ✅ Modern, lightweight, standard |
| **NVIDIA Isaac Sim** | RTX GPU, 8GB+ VRAM | NVIDIA NGC | Excellent | ❌ **Won't run on GTX 1650** (needs RTX + 8GB VRAM) |

> [!IMPORTANT]
> **Isaac Sim is out** — your GTX 1650 with 4GB VRAM cannot run it. Gazebo Harmonic is the right choice. It's lightweight, well-documented, and the Docker image `osrf/ros:jazzy-desktop` includes everything.

**Gotcha:** Gazebo Harmonic uses SDF natively, but your URDF works fine via the `ros_gz` bridge + `robot_state_publisher`.

---

## 3. SLAM Algorithm

| Algorithm | Type | Maintenance | Nav2 Integration | Best For | Verdict |
|-----------|------|-------------|-----------------|----------|---------|
| **slam_toolbox** ⭐ | 2D | Active, standard | Native | Indoor 2D mapping | ✅ **The standard** — use this |
| **cartographer_ros** | 2D/3D | Inactive maintenance | Works | Large-scale mapping | ⚠️ Not recommended for new projects |
| **rtabmap_ros** | 3D Visual | Active | Works | RGB-D / Visual SLAM | 🟡 Great but overkill for v1 2D prototype |

> [!TIP]
> **Start with `slam_toolbox`** for 2D LiDAR mapping. It's what Nav2 expects, it's the most documented, and it just works. Add `rtabmap_ros` later when you have RGB-D cameras for 3D SLAM experiments.

---

## 4. Navigation

**Nav2 is the undisputed standard.** No real alternatives in the ROS2 ecosystem. Its plug-and-play architecture is one of the best things about it:

```yaml
# nav2_params.yaml — swap algorithms by changing ONE line
controller_server:
  plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
  # Swap to: "dwb_core::DWBLocalPlanner" — just change this line

planner_server:
  plugin: "nav2_navfn_planner::NavfnPlanner"
  # Swap to: "nav2_smac_planner::SmacPlannerHybrid" — just change this line
```

This is the **plug-and-play pattern** you want to replicate in your own modules.

---

## 5. Object Detection — YOLO Version

| Model | Params | Speed (GTX 1650) | mAP | VRAM | Verdict |
|-------|--------|-------------------|-----|------|---------|
| **YOLOv8n** | 3.2M | ~45 FPS | 37.3 | ~1 GB | ✅ Battle-tested, huge community |
| **YOLOv10n** | 2.3M | ~50 FPS | 38.5 | ~0.8 GB | ✅ NMS-free, slightly faster |
| **YOLOv11n** ⭐ | 2.6M | ~48 FPS | 39.5 | ~1 GB | ✅ Best accuracy/speed balance |
| **YOLOv11s** | 9.4M | ~30 FPS | 46.5 | ~1.5 GB | 🟡 Better accuracy, still fits |
| **YOLO-World** | Various | ~15 FPS | Open-vocab | ~2 GB | 🟡 Cool but slower, open-vocabulary |

> [!TIP]
> **YOLOv11n (Nano)** for real-time detection. Export to **TensorRT** (`yolo export format=engine half=True`) for maximum performance on your GPU. The nano model leaves plenty of VRAM for other models.

**Gotcha:** To get real-time performance on GTX 1650, you **must** export to TensorRT with FP16. Running the raw PyTorch model is 2-3x slower.

---

## 6. Speech-to-Text (STT)

| Engine | Runs On | Speed | Quality | Offline | VRAM Usage | Verdict |
|--------|---------|-------|---------|---------|------------|---------|
| **Vosk** | CPU | Instant | Medium | ✅ | 0 MB | 🟡 Good for wake-word only |
| **Faster-Whisper (small)** ⭐ | GPU (CTranslate2) | ~0.3s | High | ✅ | ~1 GB | ✅ **Best balance** |
| **Faster-Whisper (medium)** | GPU | ~0.5s | Very High | ✅ | ~2 GB | 🟡 Fits but tight with other models |
| **Faster-Whisper (large-v3)** | GPU | ~1s+ | Best | ✅ | ~3.5 GB | ❌ No room for YOLO |
| **Whisper.cpp** | CPU/GPU | ~0.5-1s | High | ✅ | Flexible | 🟡 Good C++ alternative |

> [!TIP]
> **Two-stage approach:**
> 1. **Vosk** for always-on wake-word detection (zero GPU cost, instant)
> 2. **Faster-Whisper small** for actual transcription after wake-word triggers (GPU, high quality)
> 
> This is exactly what MNSE does and it works brilliantly.

---

## 7. Text-to-Speech (TTS)

| Engine | Runs On | Latency | Quality | Offline | Verdict |
|--------|---------|---------|---------|---------|---------|
| **edge-tts** | Cloud (Microsoft) | ~200ms | Very Natural | ❌ | 🟡 Free, great quality, needs internet |
| **piper-tts** | CPU | ~50ms | Good | ✅ | 🟡 Fast but less natural |
| **Kokoro TTS** ⭐ | GPU/CPU | ~80ms | Studio Quality | ✅ | ✅ **Best quality, works offline** |
| **Coqui TTS** | GPU | ~150ms | Good | ✅ | ⚠️ Project discontinued |
| **Bark** | GPU | ~2s | Very Natural | ✅ | ❌ Too slow, too much VRAM |

> [!TIP]
> **Kokoro TTS** (82M params) is the clear winner — studio-quality voice, runs locally, minimal VRAM. Use **edge-tts as a fallback** when internet is available and you want zero GPU cost.
>
> Make this **configurable**: a YAML config lets you switch between `kokoro`, `edge-tts`, and `piper` without code changes.

---

## 8. LLM Backend for Robot Brain

### Cloud APIs (Internet Required)

| API | Structured Output | Latency | Cost | Verdict |
|-----|-------------------|---------|------|---------|
| **Gemini API** | JSON mode ✅ | ~500ms | Free tier available | ✅ Best free option |
| **GPT-4o-mini** | JSON mode ✅ | ~400ms | Cheap | ✅ Good alternative |
| **Claude Haiku** | Tool use ✅ | ~300ms | Cheap | ✅ Good for reasoning |

### Local Models (Offline, 4GB VRAM)

| Model | Size (Q4) | VRAM | Quality | Verdict |
|-------|-----------|------|---------|---------|
| **Phi-3 Mini (3.8B)** | ~2 GB | ~2.5 GB | Good | ✅ Fits with YOLO |
| **Qwen 2.5 (4B)** | ~2.5 GB | ~3 GB | Good | ✅ Good at structured output |
| **Llama 3 (8B)** | ~4.5 GB | ~5 GB | Very Good | ❌ **Won't fit** with other models |
| **Gemma 2 (2B)** | ~1.5 GB | ~2 GB | Decent | 🟡 Fits easily but less capable |

> [!IMPORTANT]
> **Make it configurable** — your project proposal already says "Configurable API/local backend." Build a simple abstraction:
> ```python
> # config.yaml
> llm:
>   backend: "gemini"  # Options: gemini, openai, local
>   local_model: "phi-3-mini"
>   api_key_env: "GEMINI_API_KEY"
> ```
> 
> For the **prototype demo**, use **Gemini API** (free, fast, best quality). For offline/Jetson deployment later, swap to Phi-3.

**Critical gotcha for local models:** Use **grammar-constrained decoding** (llama.cpp GBNF or Outlines) to force valid JSON output. Prompt engineering alone is unreliable.

---

## 9. Language Decisions

### The 2026 Consensus

| Module Type | Recommended Language | Why |
|------------|---------------------|-----|
| **AI/ML nodes** (YOLO, Whisper, TTS, LLM) | **Python** | PyTorch, Ultralytics, Hugging Face — all Python-first |
| **Navigation (Nav2)** | **C++ (pre-built)** | You don't write Nav2 — you configure it via YAML |
| **SLAM** | **C++ (pre-built)** | Same — slam_toolbox is a binary you configure |
| **Behavior Trees** | **C++ (BT.CPP)** | Nav2's native BT framework, best tooling |
| **Robot description** | **Xacro/URDF** (XML) | Standard, required by RViz + robot_state_publisher |
| **Launch files** | **Python** | ROS2 launch system uses Python |
| **Bridge/orchestration** | **Python** | Easy to iterate, glue code |
| **ESP32 firmware** (future) | **C/C++** (Arduino/PlatformIO) | Embedded standard |
| **Memory/knowledge node** | **Python** | SQLite + vector search libs are Python |
| **Configuration** | **YAML** | ROS2 standard for parameters |

> [!TIP]
> **For v1 prototype: Python-dominant** with C++ only from pre-built packages (Nav2, slam_toolbox, BT.CPP). You don't need to write C++ for the prototype — the heavy lifting is done by existing ROS2 packages.

### What About Rust?
- `ros2_rust` / `rclrs` exists but lacks feature parity with `rclcpp`
- Not enough community packages, documentation, or tutorials
- **Verdict**: Skip for this project. Great for future personal interest but not practical for a team academic project.

---

## 10. Plug-and-Play Architecture Patterns

### The Nav2 Model (Gold Standard)
Nav2 achieves plug-and-play through:
1. **`pluginlib`** — C++ plugin loading at runtime
2. **YAML configuration** — swap algorithms by changing config, not code
3. **Behavior Trees** — compose behaviors from modular nodes via XML
4. **Lifecycle nodes** — deterministic startup/shutdown sequencing

### Applying This to GRACEemo

```
gracemo_ws/src/
├── gracemo_description/        # URDF/Xacro + meshes
│   ├── urdf/
│   ├── meshes/
│   └── launch/display.launch.py
│
├── gracemo_gazebo/             # Simulation worlds + spawn
│   ├── worlds/
│   ├── models/
│   └── launch/sim.launch.py
│
├── gracemo_navigation/         # Nav2 + SLAM configs
│   ├── config/
│   │   ├── nav2_params.yaml        # ← Swap planners here
│   │   ├── slam_params.yaml        # ← Swap SLAM here
│   │   └── costmap_params.yaml
│   └── launch/nav.launch.py
│
├── gracemo_perception/         # Vision (YOLO, face detection)
│   ├── config/
│   │   └── perception.yaml         # ← model_type: yolo11n | yolo11s | ssd
│   ├── gracemo_perception/
│   │   ├── detector_node.py
│   │   └── face_node.py
│   └── launch/perception.launch.py
│
├── gracemo_voice/              # STT + TTS + dialogue
│   ├── config/
│   │   └── voice.yaml              # ← stt: whisper | vosk, tts: kokoro | edge | piper
│   ├── gracemo_voice/
│   │   ├── stt_node.py
│   │   ├── tts_node.py
│   │   └── dialogue_node.py
│   └── launch/voice.launch.py
│
├── gracemo_memory/             # Knowledge + memory
│   ├── config/
│   │   └── memory.yaml             # ← db_path, vector_dim, retention
│   ├── gracemo_memory/
│   │   ├── memory_node.py
│   │   └── knowledge_graph.py
│   └── launch/memory.launch.py
│
├── gracemo_brain/              # LLM + behavior trees + planning
│   ├── config/
│   │   ├── brain.yaml              # ← llm_backend: gemini | openai | local
│   │   └── behavior_trees/         # ← XML BT definitions
│   ├── gracemo_brain/
│   │   ├── llm_node.py
│   │   └── planner_node.py
│   └── launch/brain.launch.py
│
├── gracemo_interfaces/         # Custom messages, services, actions
│   ├── msg/
│   │   ├── Detection.msg
│   │   ├── VoiceCommand.msg
│   │   └── RobotState.msg
│   ├── srv/
│   │   ├── Remember.srv
│   │   └── Navigate.srv
│   └── action/
│       ├── DetectObjects.action
│       └── SpeakText.action
│
└── gracemo_bringup/            # Top-level launch + config
    ├── config/
    │   └── robot.yaml              # ← Master config
    └── launch/
        ├── simulation.launch.py    # Everything for sim
        ├── real_robot.launch.py    # Everything for hardware (future)
        └── demo.launch.py          # Curated demo launch
```

### Key Configurable Points
Every module reads from YAML — **no hardcoded values**:

```yaml
# gracemo_bringup/config/robot.yaml — MASTER CONFIG
robot:
  name: "gracemo"
  wheel_radius: 0.05
  wheel_separation: 0.3
  max_speed: 0.5

perception:
  detector: "yolo11n"           # yolo11n | yolo11s | yolo8n | ssd
  confidence_threshold: 0.5
  device: "cuda:0"              # cuda:0 | cpu
  face_detection: true
  face_model: "yunet"           # yunet | mediapipe

voice:
  stt_engine: "faster-whisper"  # faster-whisper | vosk | whisper-cpp
  stt_model: "small"            # tiny | base | small | medium
  tts_engine: "kokoro"          # kokoro | edge-tts | piper
  wake_word: "hey gracemo"
  language: "en"

brain:
  llm_backend: "gemini"         # gemini | openai | local
  llm_model: "gemini-2.0-flash"
  local_model_path: ""
  enable_behavior_trees: true

memory:
  database: "sqlite"
  db_path: "~/.gracemo/memory.db"
  vector_search: true
  vector_dimensions: 384
  retention_days: 30

navigation:
  slam_algorithm: "slam_toolbox"  # slam_toolbox | rtabmap
  planner: "NavfnPlanner"        # NavfnPlanner | SmacPlannerHybrid
  controller: "RegulatedPurePursuit"  # RegulatedPurePursuit | DWB
```

---

## 11. Memory & Knowledge System

| Approach | Best For | Complexity | Verdict |
|----------|---------|------------|---------|
| **SQLite** ⭐ | Persistent structured data | Low | ✅ Right choice for embedded robot |
| **SQLite + sqlite-vec** | Semantic vector search | Low-Medium | ✅ Adds semantic recall, single file |
| **Redis** | High-speed volatile shared state | Medium | 🟡 Useful if distributed, overkill for v1 |
| **Neo4j** | Full knowledge graph | High | ❌ Too heavy for embedded |
| **ROS2 Parameter Server** | Config state only | Low | 🟡 Not designed for persistent memory |

> [!TIP]
> **SQLite + sqlite-vec** (same as MNSE uses) is the right approach. Single file, no server, works offline, supports both relational queries and vector similarity search. Build it as a ROS2 service node.

---

## 12. Behavior Trees

| Framework | Language | Nav2 Compatible | Visualization | Verdict |
|-----------|---------|----------------|---------------|---------|
| **BehaviorTree.CPP** ⭐ | C++ | Native | Groot2 (GUI) | ✅ **The standard** — Nav2 uses this |
| **py_trees** | Python | Needs bridge | py_trees_ros_viewer | 🟡 Good for Python-only teams |
| **SMACH** | Python | Needs bridge | smach_viewer | ❌ Outdated |
| **FlexBE** | Python | Needs bridge | FlexBE UI | 🟡 Good for HRI, less scalable |

> [!TIP]
> **BehaviorTree.CPP** is the answer. Nav2 already uses it, Groot2 gives you a visual editor, and you define trees in XML — making them configurable and swappable without recompiling.

---

## 13. Docker Setup (Arch + Wayland + GPU)

```dockerfile
# docker/Dockerfile.ros2
FROM osrf/ros:jazzy-desktop

# GPU support
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all

# Display (XWayland)
ENV DISPLAY=${DISPLAY}
ENV QT_QPA_PLATFORM=xcb

# Install Nav2 + SLAM + Gazebo extras
RUN apt-get update && apt-get install -y \
    ros-jazzy-navigation2 \
    ros-jazzy-nav2-bringup \
    ros-jazzy-slam-toolbox \
    ros-jazzy-ros-gz \
    ros-jazzy-teleop-twist-keyboard \
    ros-jazzy-xacro \
    && rm -rf /var/lib/apt/lists/*
```

```yaml
# docker/docker-compose.yml
services:
  ros2:
    build: .
    runtime: nvidia
    environment:
      - DISPLAY=${DISPLAY}
      - QT_QPA_PLATFORM=xcb
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix
      - ../gracemo_ws:/workspace/gracemo_ws
    devices:
      - /dev/dri:/dev/dri
    network_mode: host
```

**Host setup:**
```bash
xhost +si:localuser:root  # Allow Docker to use X11
```

---

## 14. Reference Projects to Study

| Project | Why Study It | Key Takeaway |
|---------|-------------|-------------|
| **[TurtleBot4](https://turtlebot.github.io/turtlebot4-user-manual/)** | Industry standard educational robot | Clean package structure, Nav2 integration patterns |
| **[Andino](https://github.com/Ekumen-OS/andino)** | Sub-$300 DIY ROS2 robot | Microcontroller integration, affordable BOM |
| **[ROSbot (Husarion)](https://husarion.com/tutorials/ros2/)** | Docker-first robot architecture | Containerized deployment patterns |
| **[mini_pupper_ros](https://github.com/mangdangroboticsclub/mini_pupper_ros)** | Quadruped with ROS2 | Gazebo sim + real hardware workflow |

---

## 15. Python 3.14 Compatibility

> [!WARNING]
> **This is a real issue.** ROS2 Jazzy ships with Python 3.12. Your Arch host has Python 3.14.

| Component | Python 3.14 Support | Solution |
|-----------|-------------------|----------|
| ROS2 Jazzy | ❌ Requires 3.12 | **Run in Docker** (Ubuntu 24.04 + Python 3.12) |
| PyTorch | ✅ Works | Run in Docker |
| Ultralytics (YOLO) | ✅ Works | Run in Docker |
| Faster-Whisper | ✅ Works | Run in Docker |
| Kokoro TTS | ✅ Works | Run in Docker |

**Solution:** Everything runs inside the Docker container with Python 3.12. Your host Python version doesn't matter.

---

## Summary Decision Matrix

| Decision | Recommended Choice | Alternatives |
|----------|-------------------|-------------|
| **ROS2 Distro** | Jazzy (LTS) | — |
| **Simulation** | Gazebo Harmonic | — |
| **SLAM** | slam_toolbox (2D) | rtabmap for 3D later |
| **Navigation** | Nav2 | — |
| **Object Detection** | YOLOv11n + TensorRT | YOLOv8n, YOLOv10n |
| **STT** | Vosk (wake) + Faster-Whisper small (transcribe) | whisper.cpp |
| **TTS** | Kokoro (offline) + edge-tts (fallback) | piper |
| **LLM (demo)** | Gemini API (free) | GPT-4o-mini |
| **LLM (offline)** | Phi-3 Mini Q4 | Qwen 2.5 4B |
| **Language** | Python-dominant, C++ from pre-built packages | — |
| **Behavior Trees** | BehaviorTree.CPP | py_trees |
| **Memory** | SQLite + sqlite-vec | — |
| **Robot Model** | URDF via Xacro | — |
| **Config Format** | YAML (ROS2 standard) | — |
| **Docker Base** | `osrf/ros:jazzy-desktop` | — |

---

## ❓ What Do You Want to Decide Next?

Now that you have the full research, we can:
1. **Lock these decisions** and finalize the teamwork prompt
2. **Dig deeper** into any specific area
3. **Adjust** any recommendations based on your preferences
