# GRaCEmo ViRa — Safety Architecture & Command Validation
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-SAFETY-P1-006`  
**System Version:** v0.0.3  

---

## 1. Safety Principles & Non-Negotiable Boundaries

Autonomous robots operating in proximity to humans must guarantee deterministic physical safety. Under no circumstances may an unvalidated or hallucinated AI model output reach robot motor controllers.

```text
                        COGNITIVE BRAIN / LLM
                                  │
                                  ▼
                       Untrusted Semantic Request
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │   COMMAND VALIDATOR   │
                      │  • Schema Compliance  │
                      │  • Workspace Bounds   │
                      │  • Kinematic Limits   │
                      └───────────┬───────────┘
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │     SAFETY GATE       │
                      │  • Battery Threshold  │
                      │  • Rate Limiting      │
                      │  • Obstacle Proximity │
                      └───────────┬───────────┘
                                  │
                        Validated RobotAction
                                  │
                                  ▼
                         ROBOT BRIDGE (ROS 2)
                                  │
                                  ▼
                     Low-Level Hardware Drivers
```

---

## 2. Command Validator Specification

Every action request emitted by the Brain or DialogueEngine must pass the Command Validator before entering the EventBus:

### 2.1 Coordinate Boundary Checks
- Target coordinates $(X, Y)$ must fall strictly within the active environment bounding box:
  $$\text{Apartment Floor: } -8.5\text{ m} \le X \le +8.5\text{ m}, \quad -6.5\text{ m} \le Y \le +6.5\text{ m}$$
  $$\text{Campus Quad: } -100.0\text{ m} \le X \le +100.0\text{ m}, \quad -100.0\text{ m} \le Y \le +100.0\text{ m}$$
- Any command containing `NaN`, `Infinity`, or non-finite numbers is rejected immediately with an `ErrorDetected` event.

### 2.2 Kinematic Limits Verification
- Head Pan $\alpha$ must satisfy $|\alpha| \le 2.0944\text{ rad}$ ($120.0^\circ$).
- Head Tilt $\beta$ must satisfy $|\beta| \le 0.7854\text{ rad}$ ($45.0^\circ$).
- Neck rotation speed must not exceed $90.0^\circ/\text{s}$.
- Mobile base translation velocity is clamped to maximum $0.45\text{ m/s}$ in corridors and $0.25\text{ m/s}$ in doorways.

### 2.3 Stale Command Protection
- Every action payload includes an epoch millisecond timestamp. If an action arrives at the Robot Bridge with age $>1000\text{ ms}$, it is dropped as **stale**.

---

## 3. Emergency Stop (E-STOP) Architecture

The Emergency Stop path is entirely independent of cloud LLMs, local LLMs, and network connectivity:

```text
Human Speech: "STOP!" / Hardware Bumper / Red Button
                     │
                     ▼
          Acoustic Regex Detector
                     │ (< 20 ms)
                     ▼
             HARDWARE BRAKE
   • Publishes Twist { linear: 0, angular: 0 } to /cmd_vel
   • Cancels Nav2 Action Client
   • Transitions Cognitive FSM to EMERGENCY_STOP
   • Latches state until explicit resume command
```

### Invariant
The stop sequence requires zero dynamic memory allocation and executes directly in the acoustic/reflex thread.

---

## 4. Hardware Interlocks & Fault Recovery

| Trigger Event | Threshold | System Action | Recovery Procedure |
| :--- | :--- | :--- | :--- |
| **Proximity Obstacle** | LiDAR range $<0.30\text{ m}$ | Halts translation; allows rotation only | In-place rotation toward clear opening |
| **Bumper Collision** | Contact switch true | Immediate motor shutdown; reverse $0.15\text{ m}$ | Re-evaluate local costmap; request clearance |
| **Low Battery** | Level $<15\%$ | Inhibit navigation; announce low battery | Direct to charging station waypoint |
| **Lost Odometry** | No `/odom` for $0.5\text{ s}$ | Hard stop; emit `RobotFault` | Wait for odometry recovery; reset filter |
| **Bridge Disconnect** | SSE heartbeat missed | Graceful deceleration to zero | Attempt reconnect every $1.0\text{ s}$ |
