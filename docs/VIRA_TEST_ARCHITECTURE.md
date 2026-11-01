# GRaCEmo ViRa — Test Architecture & Golden Scenarios
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-TEST-P1-009`  
**System Version:** v0.0.3  

---

## 1. Test Layering Architecture

The testing framework enforces behavioral verification at every layer. Mocking imports merely to achieve test coverage is strictly prohibited. Tests must assert actual system behavior, network contracts, kinematic limits, and physical convergence.

```
tests/
├── unit/           # Pure function tests (intent regex, noise math, kinematic solver)
├── contract/       # JSON schema validation against contracts/*.json
├── integration/    # Subsystem wiring (Interaction Gateway <-> Kernel <-> Bridge)
├── simulation/     # Headless Gazebo Harmonic simulation tests in apartment_floor.world
├── safety/         # Out-of-bounds rejection, E-STOP timing, NaN injection
├── performance/    # Latency histograms, EventBus throughput, token rates
├── fault/          # Network disconnect, audio drop, missing sensor injection
├── regression/     # Past bug verification (doorway transit chattering, drift)
└── hil/            # Hardware-in-the-loop physical bench verification
```

---

## 2. Test Layer Responsibilities

| Test Layer | Target Under Test | Success Criteria | Execution Frequency |
| :--- | :--- | :--- | :--- |
| **`unit/`** | `DialogueEngine`, `compute_look_at`, `NoiseGate` | $100\%$ deterministic assertions pass in $<2\text{ s}$ | Every git commit / pre-push |
| **`contract/`** | Events emitted by Python SDK & Rust Kernel | Every event validates against `contracts/*.schema.json` | Every PR / CI run |
| **`integration/`** | EventBus $\to$ SSE $\to$ `kernel_bridge` | Dispatched `ActionRequested` arrives at Bridge $<10\text{ ms}$ | Nightly / CI |
| **`simulation/`** | Gazebo Harmonic 4-room navigation | Multi-room grand tour completes with $0\text{ cm}$ wall collision | PR / Release |
| **`safety/`** | Command Validator & Safety Gate | Rejects coordinates outside apartment; E-STOP halts $\le 30\text{ ms}$| Daily / CI |
| **`performance/`** | End-to-end latency benchmarks | P95 dialogue latency $\le 2100\text{ ms}$; EventBus $\ge 10\text{k eps}$ | Weekly benchmark |
| **`fault/`** | Network cutoff, microphone unplug | Fallback to offline Qwen / local heuristics; safe stop | Pre-release |
| **`hil/`** | Physical micro-ROS ESP32 & sensors | Actuator response and physical odometry match model | Hardware bench |

---

## 3. Golden Acceptance Scenarios

### 3.1 Golden Scenario 1 — Autonomous Campus Navigation
**User Intent:** *"Take me to the Robotics Lab."*

```
1. Human speaks utterance into Microphone.
2. VAD detects speech initiation (>25% over noise floor); cuts off after 1.2s silence.
3. Groq Whisper / Faster-Whisper transcribes: "Take me to the Robotics Lab" (confidence: 0.96).
4. DialogueEngine matches intent: NAVIGATE; resolves destination: "Robotics Research Lab".
5. Interaction Gateway emits VoiceDetected and VoiceIntent events to Kernel (/emit).
6. Cognitive Brain / Fast Path emits ActionRequested(RobotAction::NavigateTo { x: 2.5, y: 2.0, yaw: 1.57 }).
7. Safety Gateway verifies coordinates (2.5, 2.0) are inside perimeter; approves action.
8. Avatar transitions expression: idle -> focus.
9. TTS synthesizes: "Navigating to the Robotics Research Lab. Please follow me."
10. Robot Bridge (kernel_bridge.py) consumes action from SSE stream (/events/live).
11. Robot Bridge dispatches waypoints through doorway slow zone (0.25 m/s) to ROS 2 /cmd_vel.
12. Gazebo simulation / Physical robot traverses path avoiding furniture obstacles.
13. Odometry confirms robot arrival within 0.30m of target coordinates.
14. Robot Bridge publishes Twist { 0, 0 } and emits NavigationArrived { destination: "Robotics Research Lab", success: true }.
15. Avatar transitions expression: focus -> happy.
16. TTS announces: "We have arrived at the Robotics Research Lab."
```
**Pass Criteria:** Robot arrives at destination without collision; total elapsed navigation time within budget; all events recorded in Kernel SQLite ledger.

---

### 3.2 Golden Scenario 2 — Emergency Stop During Transit
**User Intent:** *"Stop!"* (spoken while robot is in motion at $0.35\text{ m/s}$).

```
1. Robot is actively executing navigation waypoints in corridor.
2. Human shouts: "Stop!"
3. Acoustic energy trigger trips VAD immediately.
4. Fast-path acoustic regex catches STOP in <15 ms without waiting for cloud LLM.
5. Safety Gateway directly bypasses queuing and posts high-priority E-STOP event.
6. Robot Bridge receives E-STOP; immediately commands Twist { linear: 0.0, angular: 0.0 }.
7. Active Nav2 action client goal is cancelled.
8. Deceleration completes within < 0.12m stopping distance.
9. Avatar updates expression: focus -> intent.
10. TTS acknowledges: "Stopping immediately. Standing by for instructions."
11. System latches state in EMERGENCY_STOP until explicit resume command.
```
**Pass Criteria:** Complete motion arrest in $<65\text{ ms}$; zero dependencies on internet or cloud APIs; robot remains braked.

---

### 3.3 Golden Scenario 3 — Autonomous Interactive Greeting
**User Intent:** *"Hello ViRa."*

```
1. Vision adapter detects face via YuNet CNN (identity: "Sam Davi", distance: 1.2m).
2. Vision emits PersonVisible { identity: "Sam Davi", distance: 1.2, confidence: 0.98 }.
3. User says: "Hello ViRa."
4. STT transcribes utterance; DialogueEngine classifies intent: GREET.
5. Brain inspects human_memory.json / GraphDb; identifies Sam Davi as Lead Robotics Engineer.
6. Avatar transitions expression: idle -> happy.
7. Brain dispatches ActionRequested(RobotAction::Express { emotion: "happy" }).
8. Brain dispatches ActionRequested(RobotAction::LookAt { x: 1.2, y: 0.0, z: 1.65 }) to gaze at human face.
9. Robot Bridge moves active neck without moving base.
10. TTS speaks: "Hello Sam Davi! Welcome back to the Robotics Lab. How may I assist you today?"
```
**Pass Criteria:** Neck camera centers on face; greeting acknowledges identity; no wheel movement occurs.
