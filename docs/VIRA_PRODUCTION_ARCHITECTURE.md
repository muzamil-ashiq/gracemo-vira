# GRaCEmo ViRa — Production Architecture Specification
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-ARCH-P1-002`  
**System Version:** v0.0.3  

---

## 1. Architectural Vision & Core Principles

GRaCEmo ViRa is an embodied artificial intelligence platform operating under a **hierarchical event-driven nervous system** pattern. The architecture decouples high-level human multimodal interaction and cognitive reasoning from low-level physical dynamics and motor control.

```
                         HUMAN INTERACTION
                                 │
                   Microphone / Keyboard / REST
                                 ▼
                         VAD / WAKE WORD
                                 │
                                 ▼
                                STT
                                 │
                     ┌───────────────────────┐
                     │  INTERACTION GATEWAY  │
                     └───────────┬───────────┘
                                 │
                      ┌──────────┴──────────┐
                      ▼                     ▼
                 FAST PATH                BRAIN
              (Regex / Heuristic)     (Local Qwen / Gemini)
                      │                     │
                      └──────────┬──────────┘
                                 │ Semantic Command
                                 ▼
                         SAFETY GATEWAY
                    (Boundary / Rate / State)
                                 │
                                 ▼
                        KERNEL EVENTBUS
                      (Tokio / SSE / Ledger)
                      /                    \
                     /                      \
                    ▼                        ▼
           INTERACTION ADAPTER          ROBOT BRIDGE
             (Avatar / TTS)            (ROS 2 / rclpy)
              ┌────┼────┐                    │
              ▼    ▼    ▼                    ▼
            FACE  TTS  CAPTION              NAV2
                                             │
                                      ┌──────┴──────┐
                                      ▼             ▼
                                   GAZEBO       PHYSICAL
                                 SIMULATION      ROBOT
```

### Invariant Rules
1. **Rule of Separation**: The Cognitive Brain / LLM **never** commands raw motor voltages, PWM, joint torques, or `/cmd_vel` directly. It produces semantic commands (`NavigateTo`, `LookAt`, `Speak`, `Stop`).
2. **Deterministic Parity**: The command and event contracts between the Interaction Gateway and the Robot Bridge are identical whether executing in Gazebo Simulation or on the Physical Robot.
3. **Fail-Safe Fast Path**: Emergency commands (`STOP`, `HALT`, `FREEZE`) execute over a deterministic, zero-allocation local path with latency $<50\text{ ms}$, entirely independent of LLM or network availability.
4. **Authoritative State Substrate**: The Rust Kernel owns authoritative physical awareness via `InspectorState`, chronological history via the append-only SQLite `Ledger`, and spatial relations via `GraphDb`.

---

## 2. Production Component Specifications

### 2.1 Interaction Gateway
- **Responsibility**: Ingests acoustic audio frames or text queries, controls session lifecycle, coordinates VAD, STT, and intent routing.
- **Inputs**: PyAudio 16 kHz stream, CLI stdin, REST API `POST /interact`.
- **Outputs**: `VoiceDetected` event, `VoiceIntent` event, dispatches to Fast Path or Brain.
- **Dependencies**: Audio I/O hardware, VAD engine.
- **Timeouts**: Audio capture cutoff: 6.0s max duration; silence cutoff: 1.4s.
- **Failure Modes**: Microphone hardware disconnect $\to$ fall back to Stdin / REST API mode.

### 2.2 Voice & STT Engine
- **Responsibility**: Transcribes speech into text with domain grounding.
- **Inputs**: 16 kHz 16-bit mono PCM audio buffer.
- **Outputs**: Transcribed text string and confidence score.
- **Fallback Chain**:
  1. Groq Whisper `whisper-large-v3-turbo` (sub-second cloud transcription with LPU prompt grounding)
  2. Local Faster-Whisper `base.en` (CPU/GPU offline fallback)
  3. Google Web Speech API fallback
- **Failure Handling**: If transcription returns empty or ghost hallucination, auto-resume listening.

### 2.3 Cognitive Brain Adapter
- **Responsibility**: Multi-turn dialogue reasoning, campus knowledge grounding, and task decomposition.
- **Inputs**: User utterance, live world snapshot from Kernel `GET /context`.
- **Outputs**: Synthesized spoken text response and semantic `RobotAction`.
- **Provider Chain**:
  1. Apple Silicon Native Qwen 2.5 3B Instruct 4-bit (100% offline, MLX GPU)
  2. Groq Cloud LPU (`qwen/qwen3.8-27b` / `compound-mini`)
  3. Google Gemini 2.0 Flash (`google-genai`)
  4. Campus Heuristics Engine (offline deterministic fallback)
- **Timeout**: Cloud LLM call timeout: 3.5s. If exceeded, immediately fall back to local model or heuristics.

### 2.4 Safety Gateway
- **Responsibility**: Intercepts all semantic action requests before dispatching to the EventBus or physical actuators.
- **Validation Rules**:
  - `NavigateTo`: Verifies coordinates fall within configured topological bounds; rejects NaN/Infinity; verifies distance $>0.1\text{m}$.
  - `LookAt`: Computes neck inverse kinematics; rejects targets exceeding mechanical limits (Pan: $[-120^\circ, +120^\circ]$, Tilt: $[-45^\circ, +45^\circ]$).
  - Rate Limiting: Max 5 navigation commands per minute; max 10 head movements per minute.
  - State Check: Rejects navigation requests if `RobotBattery` $<10\%$ or obstacle is currently latched.

### 2.5 Kernel EventBus Substrate
- **Responsibility**: Pub/Sub routing, SQLite event persistence, relational knowledge graph maintenance, and distributed SSE streaming.
- **Inputs**: `POST /emit` and Unix Domain Socket `/tmp/gracemo.sock`.
- **Outputs**: SSE broadcast at `GET /events/live`, snapshot at `GET /snapshot`.
- **Performance**: In-memory broadcast throughput $>50,000\text{ events/sec}$; SQLite persistence latency $<1.5\text{ ms}$.

### 2.6 Avatar & Emotive Expression Renderer
- **Responsibility**: High-framerate visual rendering of the robot's emotional face and text captions on the physical screen or simulation monitor.
- **Inputs**: Subscribes to `RobotAction::Express` and `interaction.state` via EventBus SSE.
- **Outputs**: Pygame video window rendering 38 transition clips across 6 states (`idle`, `happy`, `focus`, `sad`, `angry`, `intent`).
- **Performance**: 60 FPS rendering loop with zero frame stuttering.

### 2.7 Text-to-Speech (TTS) Engine
- **Responsibility**: Synthesizes natural spoken voice output.
- **Inputs**: Spoken text string, emotion tag.
- **Outputs**: Audio PCM playback via `afplay`, `pw-play`, or ALSA.
- **Fallback Chain**:
  1. Edge-TTS `en-IN-NeerjaNeural` (high-fidelity neural cloud)
  2. Offline `pyttsx3` (local OS voice synthesizer)
  3. Pygame mixer fallback / console text log
- **Interruption Capability**: Supports immediate audio cancellation on STOP command.

### 2.8 Robot Bridge (`gracemo_bridge`)
- **Responsibility**: Translates semantic `RobotAction` payloads into ROS 2 topics/actions and Gazebo transport.
- **Inputs**: SSE stream from Kernel `/events/live`.
- **Outputs**:
  - `/cmd_vel` (`geometry_msgs/msg/Twist`)
  - `/head/pan/cmd_pos` (`std_msgs/msg/Float64`)
  - `/head/tilt/cmd_pos` (`std_msgs/msg/Float64`)
  - Nav2 action goals
- **Feedback**: Publishes `RobotPosition`, `NavigationArrived`, `ScanCompleted`, `LookAtResult` back to Kernel `/emit`.

---

## 3. Dual-Target Parity: Simulation vs Physical Hardware

The interface contract exposed by the Interaction Subsystem is strictly identical whether connected to Gazebo Harmonic or the Physical Robot:

```
┌────────────────────────────────────────────────────────┐
│                   VIRA SEMANTIC ACTION                 │
│         RobotAction::NavigateTo { x, y, yaw }          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                      ROBOT BRIDGE                      │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
     [SIMULATION TARGET]           [PHYSICAL TARGET]
              │                            │
              ▼                            ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│ Gazebo Harmonic Sim       │ │ Physical Robot Base      │
│ • gz-transport13 / cmd_vel│ │ • ROS 2 Nav2 Controller  │
│ • apartment_floor.world   │ │ • TurtleBot3 Waffle Base │
│ • Simulated LiDAR & IMU   │ │ • Micro-ROS ESP32 Driver │
└───────────────────────────┘ └──────────────────────────┘
```
