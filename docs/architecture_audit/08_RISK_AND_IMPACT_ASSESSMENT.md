# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 08: Risk and Impact Assessment

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Objective:** Comprehensive qualitative and quantitative risk analysis of identified duplications, conflicts, and architectural overlaps.

---

## 1. Risk Matrix Overview

```
Impact / Severity
  ▲
  │ [CRITICAL]               RSK-01 (Safety Gate Bypass)
  │                          RSK-02 (Wheelbase Odometry Drift)
  │
  │ [HIGH]                   RSK-03 (Dual Launch Transform Conflict)
  │                          RSK-04 (Dual Audio Device Lockup)
  │                          RSK-05 (Destination Schema Incompatibility)
  │
  │ [MEDIUM]                 RSK-06 (Package Duality Divergence)
  │                          RSK-07 (REST Port Discrepancy)
  │
  │ [LOW]                    RSK-08 (124 MB Disk Space Bloat)
  │
  └────────────────────────────────────────────────────────► Probability
              Low                    Medium               High
```

---

## 2. Detailed Risk Assessment Profiles

### RSK-01: Bypass of Authoritative `/cmd_vel` Safety Gate
- **Severity:** **CRITICAL** | **Probability:** **MEDIUM**
- **Affected Subsystem:** Motion Control, Autonomous Navigation, Collision Avoidance.
- **Root Cause:** Six standalone exploration and test scripts (`auto_explore.py`, `closed_loop_nav.py`, `smart_explore.py`, `mission_control.py`, `test_drive_diagnostics.py`, `test_navigation_grounding_live.py`) create publishers directly on `/cmd_vel`.
- **Failure Mode:**
  1. Bypasses `collision_monitor`: Robot ignores 2D LiDAR polygon safety bubbles (Warning $\rightarrow$ Slowdown $\rightarrow$ Stop).
  2. Bypasses `gracemo_terrain_monitor`: Robot ignores pitch/roll tilt warnings and `/terrain/emergency_stop` assertions.
  3. If run concurrently with Nav2, two nodes publish conflicting velocities simultaneously, causing violent motor torque oscillations.
- **Mitigation (Recommended):**
  - Re-route all non-Nav2 manual or scripted drive commands to `/cmd_vel_teleop` or through a unified multiplexer (`twist_mux`).
  - Deprecate ad-hoc scripts in favor of Nav2 action goals.

---

### RSK-02: 20 mm Discrepancy in Wheel Separation (Wheelbase)
- **Severity:** **HIGH** | **Probability:** **HIGH**
- **Affected Subsystem:** Wheel Odometry, AMCL Localization, Trajectory Execution.
- **Root Cause:**
  - `config/robot.yaml` declares: `wheel_separation_m: 0.32`
  - `hardware_params.yaml` declares: `wheel_separation_m: 0.34`
  - `gracemo_vira.urdf.xacro` declares: `wheel_separation = 0.34`
- **Failure Mode:**
  - Differential drive forward kinematics calculates angular velocity as $\omega = \frac{v_R - v_L}{L}$.
  - Using $L = 0.32\text{ m}$ instead of $0.34\text{ m}$ produces a **6.25% systematic heading over-estimation error** on every turn.
  - Over a $360^\circ$ in-place rotation, the robot's calculated odometric yaw diverges by $\approx 22.5^\circ$, causing AMCL particle distribution dispersion and localization failure.
- **Mitigation (Recommended):**
  - Perform physical caliper measurement of wheel centers on the physical chassis.
  - Enforce a single canonical parameter definition in `hardware_params.yaml`.

---

### RSK-03: Dual Launch File Invocations & Transform Frame Collisions
- **Severity:** **HIGH** | **Probability:** **MEDIUM**
- **Affected Subsystem:** ROS 2 Middleware, TF2 Transform Tree, Simulation Physics.
- **Root Cause:** Co-existence of `vira_complete.launch.py` (workspace) and `prototype.launch.py` (prototype).
- **Failure Mode:**
  - If both launch files are executed, two instances of `robot_state_publisher` and `amcl` publish transforms for `odom -> base_footprint` and `map -> odom`.
  - In RViz2 and UARCC, the robot model jumps erratically between two conflicting coordinate frames, triggering emergency safety stops.
- **Mitigation (Recommended):**
  - Establish `vira_complete.launch.py` as the sole canonical top-level launch file.
  - Deprecate `prototype.launch.py`.

---

### RSK-04: Multiple Voice Engine Audio Device Contention
- **Severity:** **MEDIUM** | **Probability:** **HIGH**
- **Affected Subsystem:** Voice Interaction, Pygame Avatar, Microphone Input.
- **Root Cause:** Two independent speech recognition implementations (`vira_interaction/core/stt_adapter.py` and `adapters/voice/gracemo_voice/stt.py`).
- **Failure Mode:**
  - Under Linux ALSA/PulseAudio, opening multiple hardware audio capture streams on `/dev/snd/pcmC*` causes device locking.
  - The second process crashes with `PyAudio / sounddevice Device Unavailable` error, disabling speech recognition.
- **Mitigation (Recommended):**
  - Preserve `vira_interaction` as the sole active speech capture engine.
  - Retire `adapters/voice/gracemo_voice/`.

---

### RSK-05: Incompatible Room Destination Schema Formats
- **Severity:** **MEDIUM** | **Probability:** **HIGH**
- **Affected Subsystem:** Voice Command Grounding, Coordinator Action Dispatch, UARCC Destination Picker.
- **Root Cause:**
  - `config/places.json` uses a 4-element list format: `[-5.0, -2.5, "Kitchen & Dining", -1.57]`
  - `config/destinations.json` uses an associative dictionary format: `{"x": -5.0, "y": -2.5, "yaw": -1.57, "aliases": [...]}`
- **Failure Mode:**
  - Code expecting a dictionary (e.g. UARCC navigation selector) crashes with `TypeError: list indices must be integers or slices, not str` if directed to `places.json`.
  - Code expecting a list crashes with `KeyError: 0` if directed to `destinations.json`.
- **Mitigation (Recommended):**
  - Standardize on `destinations.json` schema across all modules.
  - Provide a backward-compatible adapter function for legacy list indexing.

---

### RSK-06: Cognitive Daemon REST Port Divergence
- **Severity:** **MEDIUM** | **Probability:** **MEDIUM**
- **Affected Subsystem:** MNSE Cognitive Kernel, UARCC Cognitive View, Agent SDK.
- **Root Cause:**
  - `kernel/gracemo-kernel` listens on port **7780**.
  - `gracemo_control_center/modules/cognitive/` probes port **7780**.
  - `adapters/sdk/gracemo_sdk/config.py` defaults to port **7777**.
- **Failure Mode:**
  - Python SDK clients fail to communicate with the Rust cognitive kernel, timing out after 5.0 seconds.
- **Mitigation (Recommended):**
  - Align SDK default port in `adapters/sdk/` to 7780.
