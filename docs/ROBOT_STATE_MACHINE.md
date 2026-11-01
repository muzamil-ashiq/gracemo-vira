# Robot State Machine Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. State Model Overview
The physical robot operates under a strictly validated, thread-safe Finite State Machine implemented in [`adapters/robot-bridge/gracemo_bridge/state_machine.py`](file:///Users/samdavi/projects/VIRA/adapters/robot-bridge/gracemo_bridge/state_machine.py).

The robot state machine is decoupled from the cognitive dialogue FSM ([`InteractionFSM`](file:///Users/samdavi/projects/VIRA/graceemo_interaction/core/state_machine.py#L124)), guaranteeing that communication delays or display rendering glitches do not compromise physical safety.

---

### 2. State Definitions

| State | Description | Allowed Operations |
|---|---|---|
| `OFFLINE` | Low-level hardware drivers / controllers unpowered or uninitialized. | Only `INITIALIZING` transition permitted. All locomotion rejected. |
| `INITIALIZING` | Bootstrapping TF trees, checking LiDAR/IMU streams, and zeroing encoders. | Diagnostics only. |
| `IDLE` | Ready for operation; brakes engaged; awaiting mission goals. | `NavigateTo`, `TurnTo`, `LookAt`, `ScanRoom`, `Stop`. |
| `NAVIGATING` | Active differential-drive locomotion towards target waypoint. | `Stop`, `Pause`, `NavigateTo` (goal pre-emption). |
| `PAUSED` | Temporarily holding stationary pose; current mission state preserved. | `Resume`, `Stop`. |
| `STOPPING` | Controlled deceleration to halt. | `Stop`, `EMERGENCY_STOP`. |
| `ERROR` | Fault condition detected (e.g. planner failure, localized obstruction). | Diagnostic recovery, `INITIALIZING`, `EMERGENCY_STOP`. |
| `EMERGENCY_STOP` | Hardware bumper contact, software voice STOP, or watchdog timeout latched. | All commands rejected until manual `reset_from_emergency()`. |

---

### 3. Transition Matrix

| Current State | Allowed Next States |
|---|---|
| `OFFLINE` | `INITIALIZING`, `ERROR` |
| `INITIALIZING` | `IDLE`, `ERROR`, `OFFLINE` |
| `IDLE` | `NAVIGATING`, `PAUSED`, `STOPPING`, `ERROR`, `EMERGENCY_STOP`, `OFFLINE` |
| `NAVIGATING` | `IDLE` (arrival), `PAUSED`, `STOPPING`, `ERROR`, `EMERGENCY_STOP` |
| `PAUSED` | `NAVIGATING` (resume), `STOPPING`, `IDLE`, `ERROR`, `EMERGENCY_STOP` |
| `STOPPING` | `IDLE`, `ERROR`, `EMERGENCY_STOP` |
| `ERROR` | `INITIALIZING`, `IDLE`, `EMERGENCY_STOP`, `OFFLINE` |
| `EMERGENCY_STOP` | `IDLE`, `INITIALIZING`, `OFFLINE` *(via explicit reset only)* |

---

### 4. Operational Precondition Matrix

Incoming commands are evaluated against current state prior to execution:

| Incoming Command | State: `OFFLINE` | State: `IDLE` | State: `NAVIGATING` | State: `PAUSED` | State: `EMERGENCY_STOP` |
|---|---|---|---|---|---|
| `NavigateTo` | **REJECT** | **ALLOW** | **ALLOW (pre-empts)** | **REJECT** | **REJECT** |
| `Stop` | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| `Pause` | **REJECT** | **REJECT** | **ALLOW** | **REJECT** | **REJECT** |
| `Resume` | **REJECT** | **REJECT** | **REJECT** | **ALLOW** | **REJECT** |
| `LookAt` | **REJECT** | **ALLOW** | **ALLOW** | **ALLOW** | **REJECT** |

---

### 5. Emergency Stop Latching & Recovery
1. When `EMERGENCY_STOP` is triggered (via fast-path voice STOP, bumper switch, or safety gate violation), the state machine latches immediately.
2. All subsequent locomotion commands (`NavigateTo`, `TurnTo`, `Move`) are rejected with error code `ROBOT_ESTOP_ACTIVE`.
3. Recovery requires an explicit invocation of `reset_from_emergency(reason="Operator cleared area")`, transitioning the robot safely back to `IDLE`.
