# GRaCEmo ViRa — Real-World Operational Test Plan

**Document ID:** PLAN-P8-DEPLOY-001  
**Target Release:** `1.0.0-rc1` (Frozen Production Release)  
**Operating Classification:** CONTROLLED REAL-WORLD DEPLOYMENT  
**Author:** GRaCEmo Safety & Qualification Engineering  

---

## 1. Scope & Objective

This test plan defines the exact verification protocols for qualifying the frozen GRaCEmo ViRa production candidate under controlled real-world operating conditions.

Testing is designed to validate:
- Physical safety invariants and hard stopping latencies.
- Autonomous navigation stability in dynamic indoor campus environments.
- Voice-based human-robot interaction without safety gate bypass.
- Resilience during degraded sensing, communication loss, and cloud outages.
- Standard operating procedures using the frozen operator manual.

---

## 2. Test Environment Specification

The qualification environment encompasses diverse physical topologies, surfaces, and acoustic/optical conditions:

### A. Spatial Topologies
1. **Long Corridors:** $35\,\text{m} \times 2.4\,\text{m}$ clear sightline with high-traffic pedestrian zones.
2. **Standard Research Rooms:** Furniture clusters, rolling office chairs, desks, whiteboard stands.
3. **90-Degree Blind Intersections:** Cross-junctions requiring sensor field-of-view clearing before turn execution.
4. **Constrained Doorways & Passages:** Apertures from $0.82\,\text{m}$ to $0.90\,\text{m}$ (robot chassis width: $0.54\,\text{m}$).

### B. Material & Surface Variations
1. **Low-Pile Carpet:** Friction coefficient $\mu \approx 0.65$; moderate rolling resistance.
2. **Polished Concrete / Vinyl:** Friction coefficient $\mu \approx 0.42$; higher susceptibility to wheel slip under abrupt deceleration.
3. **Threshold Transitions:** Metal/rubber floor joins with up to $8\,\text{mm}$ step height.
4. **Reflective Surfaces:** Glass interior partition walls and polished stainless-steel kickplates affecting LiDAR and depth camera returns.

### C. Environmental Lighting & Acoustics
1. **Illumination:** Variable between $180\,\text{lux}$ (dim side-corridors) and $850\,\text{lux}$ (perimeter offices with natural sunlight).
2. **Acoustic Noise Floor:** Ambient $48\text{–}62\,\text{dBA}$ SPL, with intermittent background speech and HVAC air currents.

---

## 3. Mandatory Pre-Flight Protocol

No robot motion may occur without satisfying the strict pre-flight gating sequence:

```text
 ┌────────────────┐
 │ 1. SYSTEM BOOT │
 └───────┬────────┘
         ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. AUTOMATED PRE-FLIGHT DIAGNOSTICS (PreflightValidator)│
 │    ✓ Battery voltage > 10.8V                           │
 │    ✓ Physical E-stop circuit closed                    │
 │    ✓ Motor controller communication active             │
 │    ✓ LiDAR data streaming at >= 8 Hz                   │
 │    ✓ IMU gyro/accel biases within calibration envelope │
 │    ✓ Odometry drift within nominal limits              │
 │    ✓ EventBus internal queue operational               │
 │    ✓ ROS 2 Bridge lifecycle in ACTIVE state            │
 └───────────────────────┬────────────────────────────────┘
                         ▼
             [Are all 8 checks passed?]
                   │           │
                 YES           NO
                   │           └──► [TRANSITION TO SAFE_IDLE / NO MOTION]
                   ▼
       ┌────────────────────────┐
       │ 3. ASSERT SYSTEM_READY │
       └───────────┬────────────┘
                   ▼
 ┌──────────────────────────────────────┐
 │ 4. OPERATOR MOTION AUTHORIZATION     │
 │    (Requires explicit operator token)│
 └─────────────────┬────────────────────┘
                   ▼
       ┌────────────────────────┐
       │ 5. MOTION_AUTHORIZED   │
       └───────────┬────────────┘
                   ▼
       ┌────────────────────────┐
       │ 6. DISPATCH MISSION    │
       └────────────────────────┘
```

**Rule:** Any critical pre-flight failure aborts the boot pipeline and latches the state machine in `SAFE_IDLE`.

---

## 4. Operational Campaign Groups (A–K)

Qualification executes across 11 structured campaign groups (5 missions per group, 55 total missions):

| Group | Identifier | Environmental & Operational Conditions | Pass Criteria |
|:---:|:---|:---|:---|
| **A** | `KNOWN_DESTINATION` | Direct nominal runs to mapped goals (`lab`, `workshop`, `dock`). | Arrival within $0.30\,\text{m}$ tolerance, 0 safety faults. |
| **B** | `START_VARIATION` | Missions initiated from 5 dispersed starting locations. | Successful global relocalization within 3 seconds. |
| **C** | `STATIC_OBSTACLE` | Stationary boxes, waste bins, and chairs obstructing nominal path. | Real-time local replan with $\ge 0.25\,\text{m}$ clearance; no contact. |
| **D** | `DYNAMIC_PEDESTRIAN` | Pedestrians crossing corridor $1.5\text{–}2.5\,\text{m}$ ahead at $1.0\,\text{m/s}$. | Deceleration to zero, distance maintained $\ge 0.80\,\text{m}$, safe clearance resume. |
| **E** | `TEMP_OBSTACLE_RECOVERY` | Path fully blocked for $10\,\text{s}$, then obstacle removed. | Standstill hold, obstacle clearance detection, nominal mission resume. |
| **F** | `NARROW_PASSAGE` | Transit through $0.82\,\text{m}$ constriction (doorway B). | Transit speed $\le 0.20\,\text{m/s}$, zero bumper strikes, safe passage. |
| **G** | `LOCALIZATION_DEGRADE` | Simulated feature deprivation (symmetric corridor / sensor occlusions). | Uncertainty covariance monitoring; safe stop if covariance exceeds threshold. |
| **H** | `COMMUNICATION_DEGRADE` | Intermittent packet drops on internal motor/sensor links. | Safe stop within $300\,\text{ms}$ watchdog limit; zero runaway motion. |
| **I** | `CLOUD_OUTAGE` | WAN disconnect, no internet, cloud LLM completely unreachable. | Local speech fallback operational; zero impact on physical navigation and STOP. |
| **J** | `VOICE_UNDER_TRANSIT` | Voice status and distance queries issued while robot is moving at $0.35\,\text{m/s}$. | TTS responds accurately without causing trajectory jitter or velocity drops. |
| **K** | `EMERGENCY_STOP` | Unannounced verbal "STOP" and physical E-stop button presses under transit. | Deceleration to absolute standstill within $< 100\,\text{ms}$; zero auto-resume. |

---

## 5. Intervention Classification Taxonomy

Every human operator intervention must be classified according to the 9 standard operational categories:

1. `INTENTIONAL_TEST_STOP`: Planned test stop mandated by qualification protocol (e.g. testing stop accuracy).
2. `SAFETY_PRECAUTION`: Operator intervenes due to unexpected environment hazard (e.g. unmonitored child entering zone).
3. `NAVIGATION_RECOVERY`: Robot trapped in local minimum or path planning failure; operator nudges or clears path.
4. `LOCALIZATION_RECOVERY`: Robot lost global pose; operator triggers manual re-localization.
5. `OBSTACLE_INTERVENTION`: Physical removal of an unyielding obstacle blocking robot route.
6. `VOICE_ERROR`: Acoustic misrecognition or STT failure requiring command repetition.
7. `SYSTEM_FAULT`: Hardware or software fault trip (e.g. sensor disconnect, watchdog timeout).
8. `OPERATOR_ERROR`: Incorrect command or procedure executed by the test operator.
9. `UNEXPECTED_FAILURE`: Unhandled exception or state collapse (requires immediate release freeze restart).

---

## 6. Physical Latency Instrumentation Methodology

Timestamps must be captured using monotonic microsecond clocks (`time.perf_counter()`):

### Voice Navigation Latency Breakdown
- $T_0$: User finishes speaking (end of audio buffer).
- $T_1$: Local STT pipeline completes text transcription.
- $T_2$: Intent classifier determines semantic command.
- $T_3$: `SafetyGate` verifies authorization and constraints.
- $T_4$: `EventBus` publishes `ActionRequested` envelope.
- $T_5$: `RobotBridge` receives event.
- $T_6$: ROS 2 Nav2 goal handle created.
- $T_7$: Motor controller registers first velocity command.
- $T_8$: Optical encoders detect first wheel displacement ($\Delta \theta > 0$).
- **True Voice-to-First-Motion:** $T_8 - T_0$.

### Stopping Latency Breakdown
- $S_0$: Verbal "STOP" or E-stop button contact detected.
- $S_1$: STOP intent classified.
- $S_2$: `SafetyGate` asserts hardware emergency hold.
- $S_3$: `RobotBridge` cancels Nav2 goal.
- $S_4$: Zero-velocity twist frame dispatched to MCU.
- $S_5$: Motor controller applies dynamic electrical braking.
- $S_6$: Wheel velocity $v = 0.000\,\text{m/s}$ verified by encoders.
- **Command Stop Latency:** $S_4 - S_0$.
- **True Physical Stopping Latency:** $S_6 - S_0$.

---

## 7. Cloud Independence & Air-Gap Verification

The robot must be validated under three strict operational profiles:
- **Profile A (Full Connectivity):** Local stack + Cloud LLM Brain enabled.
- **Profile B (WAN Disconnected):** Ethernet/WiFi WAN routed to `127.0.0.1`; local network preserved.
- **Profile C (Complete Air-Gap):** Zero external connectivity; Cloud Brain adapter set to `None`.

**Acceptance Criteria:**
1. Voice commands `STOP`, `STATUS`, `WHERE_ARE_YOU`, `NAVIGATE_TO` execute deterministically via local fast path.
2. Under no circumstance may cloud outage delay emergency stopping or motor control.
3. LLM cannot issue raw coordinates or kinematic motor commands.

---

## 8. Continuous Soak Test Protocol

Run the integrated system continuously for 20 soak test cycles:
- Log CPU, RSS memory, thread counts, and process states every $500\,\text{ms}$.
- Verify that RSS memory remains stable (zero unbounded memory growth).
- Verify zero thread leaks, zombie processes, or stale goal handles.
- Confirm zero duplicate TTS utterances and zero state-machine deadlocks.
