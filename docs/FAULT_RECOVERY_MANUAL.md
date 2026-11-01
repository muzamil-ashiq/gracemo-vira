# GRaCEmo ViRa — Fault Recovery Manual & Diagnostics Matrix
**Classification:** SUPERVISED AUTONOMOUS NAVIGATION  
**Applicability:** Production Operations, Field Diagnostics, and Service Qualification  

---

## 1. Subsystem Fault Matrix & Deterministic Actions

Every failure scenario in ViRa has a deterministic, mathematically defined safety and recovery state:

| Subsystem / Fault Condition | Immediate Safe Physical Behavior | Software State | Automatic Recovery Path | Manual Intervention Required |
|:---|:---|:---|:---|:---|
| **LiDAR Disconnect / Timeout** | Immediate deceleration to $0.0\text{ m/s}$ within 200 ms | `NAVIGATION_FAILED` $\to$ `SAFE_IDLE` | Re-poll USB-serial device `/dev/rplidar` up to 3 times | If unrecovered, service sensor cable & restart bridge |
| **IMU Signal Drop / Covariance Spike** | Safe stop, freeze orientation estimate | `NAVIGATION_FAILED` $\to$ `SAFE_IDLE` | Reset I2C/SPI bus transceiver | Re-level robot and re-run preflight check |
| **Encoder Signal Loss / Disparity** | Abort differential drive; halt motors | `ERROR` $\to$ `SAFE_IDLE` | Check quadrature signal counter continuity | Inspect optical/magnetic wheel encoder wiring |
| **RGB-D Camera Disconnect** | Nav2 local costmap drops 3D obstacle layer; limits speed to $0.15\text{ m/s}$ | `DEGRADED_NAVIGATION` or `SAFE_IDLE` | Re-enumerate RealSense USB3 endpoint | Reconnect USB-C cable if device dropped to USB2 |
| **Motor Controller Disconnect** | Motors depowered by hardware pull-down; MCU watchdog halts | `EMERGENCY_STOP` | Auto-reconnect serial handshake (`/dev/ttyACM0`) | Verify battery bus power switch & USB link |
| **ROS 2 Daemon / Node Crash** | Bridge detects dead DDS participant; sends emergency stop | `ERROR` $\to$ `SAFE_IDLE` | Systemd restarts `ros2-core` service container | Re-launch lifecycle manager if not converged |
| **EventBus Failure / Lockup** | Fallback queues bypass EventBus; priority STOP routes directly | `SAFE_IDLE` | Worker thread pool recycled | None; logged in trace telemetry |
| **Nav2 Action Failure / Obstruction** | Decelerate, execute 3 recovery spins (if clear) or stop | `NAVIGATION_FAILED` $\to$ `SAFE_IDLE` | 3 costmap clearing & backward recovery attempts | Clear physical blockage from corridor |
| **Localization Loss ($> 0.5\text{m}$ cov)** | Stop motion immediately; do not wander blindly | `NAVIGATION_FAILED` $\to$ `SAFE_IDLE` | Global AMCL particle expansion / spin scan | Manually reposition robot or re-localize via UI |
| **Battery Critical ($< 10.5\text{V}$)** | Immediate controlled halt; all actuators unpowered | `SAFE_IDLE` (Locked) | None (Locked out against brownout damage) | Plug in balance charger; charge to $\ge 11.5\text{V}$ |
| **Network / Wi-Fi Drop** | Continue local navigation; FastPath voice & physical STOP active | `OPERATIONAL_OFFLINE` | Auto-reconnect to campus WPA2 enterprise | None for physical safety; cloud sync resumes when online |
| **Microphone / Audio Capture Failure** | Voice input muted; touch / web console remains active | `DEGRADED_INTERACTION` | Re-open ALSA / PulseAudio recording stream | Inspect USB microphone array connection |
| **STT Engine Failure** | Voice recognition unavailable; GUI / CLI commands active | `DEGRADED_INTERACTION` | Reload Vosk model in background thread | Fall back to manual operator console |
| **Cloud LLM Latency / Timeout** | Instant fallback to local deterministic FastPath & offline brain | `NORMAL_NAVIGATION` | Exponential backoff retry (1s, 2s, 4s) | None; safety is completely independent of cloud |
| **TTS / Audio Playback Crash** | Voice muted; visual responses shown on web/avatar console | `DEGRADED_INTERACTION` | Fallback to `espeak-ng` system voice | None; navigation unaffected |
| **Avatar Web View Crash** | Face display goes blank; interaction core unaffected | `OPERATIONAL` | Chromium kiosk re-renders page | None; pure display process |
| **Main Process Crash** | Hardware watchdog trips within 300 ms, shutting down motors | `HARDWARE_HALT` | Systemd restarts `vira-bridge.service` | Operator must re-authorize motion before moving |

---

## 2. Zero Auto-Resume Enforcement

> [!CAUTION]
> Under no circumstances will ViRa resume motion following an unlatched fault without an affirmative operator authorization command (`MOTION_AUTHORIZED`). All mission objectives active prior to the fault are marked `FAILED` or `CANCELLED`.
