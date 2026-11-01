# GRaCEmo ViRa — Safety Operations Manual & Invariants
**Classification:** SUPERVISED AUTONOMOUS NAVIGATION  
**Reference Standard:** ISO 13849 / ISO 3691-4 Fail-Safe Architectural Guidance  

---

## 1. Safety Core Invariants

The VIRA software and hardware integration adheres strictly to seven immutable safety invariants:

| ID | Safety Invariant | Architectural Enforcement Mechanism |
|:---|:---|:---|
| **INV-01** | **No Unsupervised Locomotion** | System readiness (`SYSTEM_READY`) is isolated from motion authorization (`MOTION_AUTHORIZED`). Human operator must affirmatively issue motion token. |
| **INV-02** | **Zero Auto-Resume** | Following an E-stop latch, sensor drop, or safety violation, the robot transitions to `SAFE_IDLE` or `EMERGENCY_STOP`. Automatic resumption is prohibited. |
| **INV-03** | **Hardware Watchdog Protection** | Motor MCU enforces a 300 ms tick watchdog. If software commands lapse $> 300\text{ms}$, motors drop to zero power passively. |
| **INV-04** | **Velocity Envelopes** | Hard limits are capped at $0.35\text{ m/s}$ linear and $0.60\text{ rad/s}$ angular. Commands exceeding limits are clamped or rejected. |
| **INV-05** | **Offline FastPath STOP** | Emergency voice and button STOP operate locally without network, ROS 2 action latency, or cloud LLM involvement ($< 10\text{ms}$). |
| **INV-06** | **LLM Separation** | Cloud LLM inference produces strictly advisory semantic representations. Direct output of motor velocities or hardware pins is architecturally impossible. |
| **INV-07** | **Fail-Safe Sensor Interlocking** | Loss or corruption of LiDAR, IMU, odometry, or camera streams initiates immediate controlled deceleration to `SAFE_IDLE`. |

---

## 2. Emergency Stop (E-Stop) Hierarchy

ViRa incorporates defense-in-depth across multiple emergency stop mechanisms:

```
[Level 0] Mechanical Red Mushroom Switch (Physical Deck)
   └── Directly interrupts motor gate drivers; reports active low to MCU.
[Level 1] MCU Hardware Watchdog (Microcontroller)
   └── Cuts PWM signals if valid heartbeat command is absent for 300 ms.
[Level 2] RobotBridge SafetyAdapter / SafetyGate (Low-level Software)
   └── Enforces latched EMERGENCY_STOP state, drops velocity commands to 0.0 m/s.
[Level 3] FastPath Speech / Operator Terminal STOP (Interaction Layer)
   └── Sub-10ms priority event bypasses LLM and halts active Nav2 trajectory.
```

---

## 3. Battery Safety & Voltage Envelopes

ViRa operates on a 3S nominal battery configuration (12.6V fully charged):

- **$> 11.5\text{ V}$ (Nominal):** Normal navigation permitted.
- **$11.1\text{ V} - 11.5\text{ V}$ (Warning):** Operator warning emitted; ongoing mission allowed to complete.
- **$10.8\text{ V} - 11.1\text{ V}$ (Safe Hold):** New missions blocked. Robot parks in place and requests charging.
- **$< 10.5\text{ V}$ (Critical Stop):** Immediate safe deceleration. Active mission aborted to prevent cell damage.

---

## 4. Reset & Clear Procedures

Following any safety event:
1. Verify the surrounding environment is clear of human personnel and physical obstructions.
2. If physical E-Stop was engaged: Twist mushroom cap clockwise to mechanically unlatch.
3. Execute software safety unlatch:
   ```bash
   vira-cli reset-safety --operator <id>
   ```
4. Verify `SafetyGate.is_emergency_stop_latched() == False` and state is `IDLE`.
5. Re-run pre-flight check before issuing a new motion authorization.
