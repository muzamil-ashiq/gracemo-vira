# Robot Bridge Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. Architectural Mission
The **Robot Bridge** (`adapters/robot-bridge/gracemo_bridge/`) is the authoritative boundary adapter translating high-level semantic commands (`ActionRequested`) from the VIRA EventBus into deterministic physical movements over ROS 2 / Nav2 / Gazebo, and mapping low-level navigation progress back into canonical VIRA event envelopes.

In strict compliance with **Rule 3**, the interaction and LLM tiers never command motors, GPIO, or `/cmd_vel` directly. The Robot Bridge alone owns physical command translation.

---

### 2. Component Architecture

```text
               VIRA EventBus (:7780/emit & SSE /events/live)
                                      │
                         [ActionRequested envelope]
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │        RobotBridge        │
                        └─────────────┬─────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
   ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
   │ CommandHandler  │◄─────►│  SafetyAdapter  │◄─────►│RobotStateMachine│
   └────────┬────────┘       └─────────────────┘       └────────┬────────┘
            │                                                   │
            ▼                                                   ▼
   ┌─────────────────┐                                 ┌─────────────────┐
   │NavigationAdapter│                                 │ StatePublisher  │
   └────────┬────────┘                                 └────────┬────────┘
            │                                                   │
            ▼                                                   │
   ┌─────────────────┐                                          │
   │ FeedbackAdapter ├──────────────────────────────────────────┘
   └────────┬────────┘
            │
            ▼
   [Canonical Feedback Envelopes] ──► VIRA EventBus (trace_id preserved)
```

---

### 3. Module Responsibilities

| Sub-Module | Responsibility |
|---|---|
| [`command_handler.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/command_handler.py) | Ingests `ActionRequested` envelopes, verifies safety authorization with `SafetyAdapter`, and routes actions (`NavigateTo`, `Stop`, `Pause`, `Resume`, `TurnTo`, `LookAt`) to the executor. |
| [`safety_adapter.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/safety_adapter.py) | Enforces operational preconditions: verifies robot is not `OFFLINE` or `EMERGENCY_STOPPED`, checks command timestamp freshness ($< 3.0\text{ s}$), checks battery level ($> 15\%$), and validates coordinate geofence limits ($[-100, 100]$). |
| [`navigation_adapter.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/navigation_adapter.py) | Coordinates trajectory execution against Nav2 `NavigateToPose` or high-fidelity 2D unicycle kinematic simulator, manages goal pre-emption, and supports idempotent cancellation. |
| [`feedback_adapter.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/feedback_adapter.py) | Formats and emits canonical feedback events (`NavigationStarted`, `NavigationProgress`, `NavigationArrived`, `NavigationFailed`, `RobotStopped`) adhering strictly to `contracts/robot-event.schema.json` and preserving `trace_id`. |
| [`state_publisher.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/state_publisher.py) | Broadcasts periodic battery telemetry and event-driven `RobotStateChanged` updates to the EventBus. |
| [`state_machine.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/state_machine.py) | Thread-safe authoritative lifecycle FSM: `OFFLINE`, `INITIALIZING`, `IDLE`, `NAVIGATING`, `PAUSED`, `STOPPING`, `ERROR`, `EMERGENCY_STOP`. |

---

### 4. Semantic Command Mapping

| Semantic Action | Input Parameters | ROS 2 / Hardware Execution | Feedback Event |
|---|---|---|---|
| `NavigateTo` | `x, y, yaw, target_name, tolerance_m` | Nav2 `NavigateToPose.action` or closed-loop waypoint pursuer. | `NavigationStarted` $\to$ `NavigationProgress` $\to$ `NavigationArrived` |
| `Stop` | `reason, emergency` | Instant decelerating brake (`cmd_vel(0, 0)`), latches `EMERGENCY_STOP`. | `RobotStopped(emergency=true)` |
| `Pause` | `reason` | Holds position in place; pauses waypoint streamer. | `RobotStateChanged(PAUSED)` |
| `Resume` | `reason` | Resumes active goal trajectory tracking. | `RobotStateChanged(NAVIGATING)` |
| `TurnTo` | `yaw` | In-place differential spin to target heading. | `TurnCompleted` |
| `LookAt` | `x, y, z` | 2-DOF active neck pan/tilt kinematics (`pan_deg`, `tilt_deg`). Zero base movement. | `LookAtResult` |

---

### 5. Distributed Trace ID Propagation
Every interaction is tagged at user input with a unique `trace_id`. The Robot Bridge preserves this exact identifier across all stages:
1. `ActionRequested` arrives with `trace_id: "golden-e2e-nav-001"`.
2. `FeedbackAdapter` includes `trace_id: "golden-e2e-nav-001"` in `NavigationStarted`.
3. Intermediate 4Hz `NavigationProgress` packets carry `trace_id: "golden-e2e-nav-001"`.
4. Final `NavigationArrived` or `NavigationFailed` envelope contains `trace_id: "golden-e2e-nav-001"`.
5. `InteractionAdapter` and `InteractionGateway` log completion with `trace_id: "golden-e2e-nav-001"`.
