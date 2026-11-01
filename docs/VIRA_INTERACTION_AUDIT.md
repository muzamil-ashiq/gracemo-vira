# GRaCEmo ViRa — Repository & Interaction Subsystem Audit
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-AUDIT-P1-001`  
**System Version:** v0.0.3  

---

## 1. Executive Summary

This audit assesses the state of the **GRaCEmo ViRa (VIRA)** repository, with specific emphasis on the interaction subsystem ([`graceemo_interaction/`](file:///Users/samdavi/projects/VIRA/graceemo_interaction)), the nervous system kernel ([`kernel/`](file:///Users/samdavi/projects/VIRA/kernel)), adapters ([`adapters/`](file:///Users/samdavi/projects/VIRA/adapters)), the ROS 2 / Gazebo workspace ([`ros2_ws/`](file:///Users/samdavi/projects/VIRA/ros2_ws)), simulation assets, and automated tests ([`tests/`](file:///Users/samdavi/projects/VIRA/tests)).

The repository features high-value existing capabilities:
1. **Interactive Facial Expression Avatar & Engine** ([`graceemo_interaction/model.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/model.py)): 38 video transition clips across 6 facial expressions, Apple Silicon MLX GPU local offline LLM (`Qwen2.5-3B-Instruct-4bit`), Groq Whisper STT with domain grounding, and Edge-TTS Indian English neural synthesis (`en-IN-NeerjaNeural`).
2. **Deterministic Fast-Path Intent & Campus Navigation** ([`graceemo_interaction/core/dialogue_engine.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/core/dialogue_engine.py), [`places.json`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/config/places.json)): Direct regex and keyword parsing for emergency stops, greetings, and waypoint targets.
3. **Rust Multi-Memory Substrate Kernel** ([`kernel/gracemo-kernel`](file:///Users/samdavi/projects/VIRA/kernel/gracemo-kernel)): Axum HTTP REST server (port 7780), Server-Sent Events (SSE) stream (`/events/live`), Tokio broadcast EventBus, SQLite causal ledger (`Ledger`), and relational knowledge graph (`GraphDb`).
4. **Embodied Robot Bridge & 2-DOF Active Neck Kinematics** ([`ros2_ws/src/gracemo_bridge/gracemo_bridge/kernel_bridge.py`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_bridge/gracemo_bridge/kernel_bridge.py)): Direct bridge between Gazebo Harmonic (`gz-transport13`), ROS 2 (`rclpy`), and the Kernel EventBus.
5. **URDF / Gazebo Simulation Workspace** ([`ros2_ws/src/gracemo_description`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_description), [`ros2_ws/src/gracemo_gazebo`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_gazebo)): Fully specified TurtleBot3 Waffle physical base with pan/tilt head, LiDAR, RGB camera, balanced inertia tensor, and a 16m × 12m furnished 4-room apartment world (`apartment_floor.world`).

### Critical Architectural Deficit Identified
The `graceemo_interaction/` subsystem currently operates as an **island**. It possesses its own isolated STT/TTS and dialogue logic, but **does not communicate with the Rust EventBus (`http://127.0.0.1:7780`) or ROS 2 (`kernel_bridge.py`)**. Furthermore, [`graceemo_interaction/functions.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/functions.py) directly drives motors and servos using `gpiozero.Robot`, violating **Rule 3 (No direct LLM motor control)**.

---

## 2. Component Audit Table

| Component | Existing Implementation | Status | Reuse | Refactor | Replace | Missing |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **STT** | Groq Whisper (`model.py`), Faster-Whisper (`adapters/voice`), SpeechRecognition (`core/stt_engine.py`) | WORKING / DUPLICATED | Yes | Yes | — | Unified fallback pipeline (Whisper local $\to$ Groq $\to$ Web) |
| **VAD** | RMS energy gate (`model.py`), Silero VAD (`adapters/voice`) | WORKING | Yes | Yes | — | Consistent VAD across CLI, avatar, and background daemon |
| **Brain / LLM** | MLX Qwen 2.5 3B local (`model.py`), Groq cloud (`model.py`), Gemini 2.0 / Groq / Ollama (`core/llm_engine.py`, `adapters/brain`) | WORKING | Yes | Yes | — | Standardized priority provider chain emitting typed `RobotAction` |
| **Memory** | `human_memory.json` (`data/`), SQLite Ledger & GraphDb (`kernel/`) | WORKING / PARTIAL | Yes | Yes | — | Sync between interaction memory and Kernel GraphDb |
| **TTS** | Edge-TTS `en-IN-NeerjaNeural` (`model.py`), `pyttsx3`/`gTTS` (`core/tts_engine.py`), Kokoro (`adapters/voice`) | WORKING / DUPLICATED | Yes | Yes | — | Unified non-blocking player with cancel/barge-in |
| **Avatar / Face** | Pygame + `pyvidplayer2` 38 video transitions (`model.py`, `vid/`) | WORKING | Yes | Yes | — | EventBus listener for `RobotAction::Express` |
| **EventBus** | Tokio broadcast + Axum SSE + Unix socket (`kernel/`) | WORKING | Yes | — | — | Standard event validation middleware |
| **ROS 2 Interface** | `kernel_bridge.py` (`ros2_ws/src/gracemo_bridge`) | WORKING | Yes | Yes | — | Lifecycle management and dynamic re-registration |
| **Nav2** | DWB planner, costmaps, dynamic frontier explorer (`gracemo_nav2`) | WORKING | Yes | — | — | Action-based status feedback hook |
| **Gazebo Sim** | Gazebo Harmonic 8, `apartment_floor.world`, gz-transport13 | WORKING | Yes | — | — | Headless CI execution profile |
| **Robot Bridge** | `kernel_bridge.py` handling `NavigateTo`, `LookAt`, `ScanRoom`, `Stop` | WORKING | Yes | Yes | — | Bidirectional telemetry stream for physical base |
| **Safety Gateway** | Ad-hoc clamp checks in `kernel_bridge.py` and `model.py` | PARTIAL | Partial | Yes | — | Formal Command Validator & Hardware Safety Gate |
| **Physical Hardware** | `functions.py` (`gpiozero.Robot`, `AngularServo`) | BROKEN / VIOLATION | No | No | Yes | Disconnect LLM from GPIO; route via ROS 2 ESP32 bridge |
| **Telemetry** | `InspectorState` in `kernel` and `core/models.py` | PARTIAL | Yes | Yes | — | Unified distributed `trace_id` and latency metrics |
| **Testing** | 32 test scripts in `tests/` covering kinematics, scan, navigation | WORKING | Yes | Yes | — | Automated contract validation against schemas |

---

## 3. Deep Dive: `graceemo_interaction`

### 3.1 Input Channels
- **Microphone**: PyAudio 16 kHz mono stream via `record_audio()` in [`model.py:L278-L378`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/model.py#L278-L378).
- **Keyboard Overrides**: `s` (start listening), `e` (stop listening), `f` (toggle fullscreen), `q`/`Esc` (quit) via `pynput.keyboard` and Pygame `KEYDOWN`.
- **Terminal Stdin**: Background thread `terminal_input_listener()` accepts typed input at any time.
- **REST API**: FastAPI server in [`main.py:L209-L293`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/main.py#L209-L293) exposing `POST /interact` and `GET /state` on port 8420.
- **Wake Word**: Porcupine models (`mint.ppn`, `pi.ppn`) in [`wake-word/`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/wake-word) and regex `"hey gracemo"` in [`core/stt_engine.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/core/stt_engine.py).

### 3.2 Speech-to-Text (STT)
- **Engine**: Groq Whisper `whisper-large-v3-turbo` in [`model.py:L422-L464`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/model.py#L422-L464).
- **Prompt Grounding**: Injects `WHISPER_PROMPT` containing key entities (*"Lovely Professional University, Vice Chancellor, Dr. Ashok Kumar Mittal, Dr. Mohit Arora, Sam Davi, Robotics Research Lab, Uni-Mall, Central Library"*).
- **Endpointing**: Dynamic energy gate computes background noise floor on 5-frame calibration; switches to speech when RMS exceeds ambient by 25%; terminates after 11 silence frames (~1.4s).
- **Ghost Filter**: Rejects Whisper hallucinations (*"thanks for watching"*, *"subtitles by"*, single characters).
- **Limitation**: Hard dependency on internet access when using Groq Whisper. If network drops, transcription fails. Must integrate offline Faster-Whisper / Silero fallback.

### 3.3 Brain & Cognition
- **Tier 1 (Native Local Offline)**: Local Qwen 2.5 3B Instruct 4-bit (`models/Qwen2.5-3B-Instruct-4bit`) executed via Apple Silicon MLX GPU (`mlx_lm`). Sub-second response time with zero network requirement.
- **Tier 2 (Cloud Fallback)**: Groq Cloud API with `qwen/qwen3.8-27b` and `groq/compound-mini`. In [`core/llm_engine.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/core/llm_engine.py), supports Google Gemini 2.0 Flash (`google-genai`) and local Ollama (`llama3`).
- **Deterministic Fast Path**: Fast intent matching for STOP, GREET, NAVIGATE, HAND_UP, HAND_DOWN, bypassing LLM latency.
- **Live Search**: Intercepts `{search}` tags to execute live internet lookups via `fetch_live_data()`.

### 3.4 Text-to-Speech (TTS)
- **Primary**: `edge-tts` with voice `en-IN-NeerjaNeural`. High naturalness and correct pronunciation of Indian campus terminology.
- **Audio Output Pipeline**: Converts MP3 to 24 kHz mono WAV via `ffmpeg`; dispatches playback via `afplay` (macOS), `pw-play` (PipeWire), `aplay` (ALSA), or `pygame.mixer`.
- **Limitation**: Lacks clean runtime audio interruption (barge-in) when the user speaks while the robot is speaking.

### 3.5 Facial Expression Renderer (Avatar)
- Pygame display rendering 38 video animation clips in [`vid/`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/vid).
- 6 canonical expressions: `idle`, `happy`, `focus`, `sad`, `angry`, `intent`.
- Smooth state transition machine (`PREVIOUS_EXP` $\to$ `CURRENT_EXP` $\to$ `NEXT_EXP`) avoids visual freezing or blank frame stuttering.
- Live caption overlay rendered at the bottom of the screen.

### 3.6 Physical Action Hooks & Rule 3 Violation
- In [`graceemo_interaction/functions.py`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/functions.py):
  ```python
  robot = Robot(left=(4, 23), right=(17, 18), pin_factory=factory)
  servo = AngularServo(12, min_angle=0, max_angle=180, pin_factory=factory)
  ```
- Functions `motor_forward()`, `motor_backward()`, and `rotate_servo_to_180()` directly drive hardware without obstacle checks, kinematics, velocity ramps, or safety limits.
- **Action Required**: Deprecate direct hardware calls in `functions.py`. Reroute all physical action requests as typed events (`ActionRequested(RobotAction)`) to the Kernel EventBus and ROS 2 Robot Bridge.

---

## 4. Deep Dive: VIRA Architecture & Kernel

### 4.1 Communication Substrate
- **EventBus**: Tokio broadcast channel (capacity 2048) in [`kernel/gracemo-kernel/src/main.rs:L36`](file:///Users/samdavi/projects/VIRA/kernel/gracemo-kernel/src/main.rs#L36).
- **Ingestion Interfaces**:
  1. `POST http://127.0.0.1:7780/emit` (accepts canonical JSON `Event`)
  2. Unix Domain Socket `/tmp/gracemo.sock` (accepts newline-delimited JSON `Event`)
- **Egress / Distribution Interfaces**:
  1. `GET http://127.0.0.1:7780/events/live` (SSE stream for live events)
  2. `GET http://127.0.0.1:7780/snapshot` (in-memory `InspectorState` JSON)
  3. `GET http://127.0.0.1:7780/context` (compiled truth: NOW + PAST + RELATIONS)
  4. `GET http://127.0.0.1:7780/graph` (relational knowledge graph)

### 4.2 Canonical Rust Data Model
Defined in [`kernel/gracemo-types/src/lib.rs`](file:///Users/samdavi/projects/VIRA/kernel/gracemo-types/src/lib.rs):
- `Event`: `{ id, timestamp, source, observed_by, event_type, parent_event_id }`
- `RobotAction`:
  - `Speak { text }`
  - `NavigateTo { x, y, yaw }`
  - `TurnTo { yaw }`
  - `NavigateToRoom { room }`
  - `LookAt { x, y, z }`
  - `ScanRoom { pan_range_deg, tilt_deg, speed_deg_s }`
  - `Express { emotion }`
  - `Stop`

---

## 5. Deep Dive: Simulation & Robot Bridge

### 5.1 Robot Bridge (`kernel_bridge.py`)
- Located at [`ros2_ws/src/gracemo_bridge/gracemo_bridge/kernel_bridge.py`](file:///Users/samdavi/projects/VIRA/ros2_ws/src/gracemo_bridge/gracemo_bridge/kernel_bridge.py).
- Listens to Kernel SSE `/events/live` for `ActionRequested` payloads.
- Drives mobile base via ROS 2 `/cmd_vel` (`geometry_msgs/msg/Twist`) and Gazebo Harmonic `gz-transport13`.
- Solves 2-DOF active neck inverse kinematics for `LookAt(x, y, z)` within mechanical limits (Pan: $\pm 120^\circ$, Tilt: $\pm 45^\circ$) without rotating the base.
- Performs autonomous topological waypoint navigation to designated rooms (`Kitchen & Dining`, `Master Bedroom`, `Home Study`, `Living Room`, `Central Hallway`).
- Emits feedback events (`NavigationArrived`, `TurnCompleted`, `ScanCompleted`, `LookAtResult`, `RobotPosition`).

### 5.2 Simulation Pipeline
- **Physics Engine**: Gazebo Sim Harmonic 8 with ODE solver and contact slip tuning.
- **Chassis**: Standardized TurtleBot3 Waffle URDF/Xacro ($1.372\text{ kg}$, $0.288\text{ m}$ wheelbase, $0.033\text{ m}$ wheel radius).
- **Environment**: `apartment_floor.world` with 1.4m wide doorways, grounded furniture models, and self-contained SDFormat lighting.

---

## 6. Audit Conclusions & Critical Deficiencies

```text
[WORKING]     Pygame 38-video transition avatar engine
[WORKING]     Local Apple Silicon MLX Qwen 2.5 3B inference
[WORKING]     Groq Whisper STT with LPU prompt context
[WORKING]     Edge-TTS en-IN-NeerjaNeural speech synthesis
[WORKING]     Rust Kernel EventBus, SQLite Ledger, GraphDb, and SSE
[WORKING]     ROS 2 + Gazebo Harmonic bridge with LookAt kinematics
[WORKING]     URDF and Gazebo 4-room apartment simulation

[PARTIAL]     Interaction memory stored in human_memory.json instead of Kernel GraphDb
[PARTIAL]     FastAPI interaction endpoints isolated from Kernel HTTP endpoints

[DUPLICATED]  Two STT engines (Faster-Whisper in adapters/voice vs Groq Whisper in model.py)
[DUPLICATED]  Two TTS engines (Kokoro/Edge in adapters/voice vs Edge/pyttsx3 in interaction)

[VIOLATION]   functions.py directly drives GPIO motors and servos from interaction code
[MISSING]     Interaction layer has no connection to Kernel EventBus (http://127.0.0.1:7780)
[MISSING]     No Command Validator / Hardware Safety Gate between brain and robot bridge
[MISSING]     Avatar does not listen for RobotAction::Express emitted by robot/vision
```
