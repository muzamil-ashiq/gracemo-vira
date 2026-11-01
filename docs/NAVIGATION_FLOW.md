# Navigation Flow Specification
## GRaCEmo ViRa Autonomous Robot System — Phase 3

### 1. End-to-End Autonomous Transit Sequence

```text
USER SPEECH: "Take me to the Robotics Lab."
   │
   ▼
[STTAdapter] ────────────────► Transcript: "Take me to the Robotics Lab."
   │
   ▼
[InteractionGateway] ────────► Generates trace_id: "nav-trace-9821"
   │                           Transitions InteractionFSM: IDLE ──► THINKING
   │
   ▼
[PlaceResolver] ─────────────► Matches "Robotics Research Lab"
   │                           x = 2.50, y = 2.00, yaw = 0.00
   │
   ▼
[FastPathMatcher] ───────────► Produces semantic action:
                               NavigateTo(x=2.50, y=2.00, target_name="Robotics Research Lab")
   │
   ▼
[SafetyGate] ────────────────► Evaluates geofence [-100, 100], non-NaN/Inf,
                               checks battery (> 15%) and e-stop state.
   │
   ▼
[EventBusClient] ────────────► Emits canonical ActionRequested envelope:
                               {
                                 "trace_id": "nav-trace-9821",
                                 "event_type": {
                                   "type": "ActionRequested",
                                   "data": {
                                     "action": "NavigateTo",
                                     "params": {"x": 2.5, "y": 2.0, "target_name": "Robotics Research Lab"}
                                   }
                                 }
                               }
   │
   ▼
[RobotBridge] ───────────────► SafetyAdapter verifies RobotState == IDLE.
                               Transitions RobotState: IDLE ──► NAVIGATING.
   │
   ├──► [FeedbackAdapter] ───► Emits NavigationStarted (trace_id preserved)
   │
   ▼
[NavigationAdapter / Nav2] ──► Dispatches goal to Nav2 NavigateToPose action.
                               Differential drive tracks path via /cmd_vel.
                               Streams NavigationProgress (4Hz).
   │
   ▼
[Destination Reached] ───────► Robot coordinates within tolerance (0.30m).
                               Transitions RobotState: NAVIGATING ──► IDLE.
   │
   ▼
[FeedbackAdapter] ───────────► Emits NavigationArrived(success=true, trace_id="nav-trace-9821").
   │
   ▼
[InteractionAdapter] ────────► Receives NavigationArrived on EventBus.
                               Transitions InteractionFSM: EXECUTING ──► IDLE.
                               Sets Avatar Expression: HAPPY.
                               Invokes TTSAdapter: "We've arrived at Robotics Research Lab."
```

---

### 2. Fast-Path Emergency STOP Flow

```text
USER SPEECH: "Stop." (while robot is in transit)
   │
   ▼
[FastPathMatcher] ───────────► Deterministic word-boundary match on "stop" (< 2ms)
                               ZERO LLM reasoning invoked.
   │
   ▼
[SafetyGate] ────────────────► Latches EMERGENCY_STOP state immediately.
   │
   ▼
[EventBusClient] ────────────► Dispatches ActionRequested(Stop).
   │
   ▼
[RobotBridge] ───────────────► Cancels Nav2 action / stops trajectory tracking.
                               Sets cmd_vel(0.0, 0.0) decelerating brake.
                               Transitions RobotState: NAVIGATING ──► EMERGENCY_STOP.
   │
   ▼
[FeedbackAdapter] ───────────► Emits RobotStopped(emergency=true, trace_id preserved).
   │
   ▼
[InteractionAdapter] ────────► Cancels active TTS audio synthesis.
                               Sets Avatar Expression: IDLE.
```

---

### 3. Invalid Destination Rejection Flow (Golden Test #4)

```text
USER SPEECH: "Take me to the Moon Lab."
   │
   ▼
[PlaceResolver] ─────────────► Checks candidate destination "Moon Lab".
                               Modifier "Moon" does not match canonical database.
                               Returns (None, "Moon Lab") -> NOT FOUND.
   │
   ▼
[FastPathMatcher] ───────────► Detects unknown location.
                               Produces FastPathResult:
                               - intent: UNKNOWN_DESTINATION
                               - semantic_actions: []  (CRITICAL: ZERO ROBOT COMMANDS)
                               - response_text: "I do not have 'Moon Lab' in my campus map..."
                               - expression: SAD
   │
   ▼
[InteractionGateway] ────────► Returns controlled conversational response.
                               No event published to Robot Bridge.
                               Robot remains stationary in IDLE state.
```
