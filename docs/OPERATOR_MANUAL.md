# GRaCEmo ViRa — Operator Manual & Standard Operating Procedures
**Classification:** SUPERVISED AUTONOMOUS NAVIGATION  
**Applicability:** Production Candidates running Firmware v2.4.1+ and Software v1.0.0-rc1+  

---

## 1. Safety Principles & Operator Responsibilities

> [!IMPORTANT]
> GRaCEmo ViRa is qualified exclusively for **Supervised Autonomous Navigation**. The assigned human operator must maintain continuous visual line-of-sight (VLOS), remain within immediate reach of physical E-stop switches, and supervise all autonomous maneuvers. No unrestricted autonomy is permitted.

---

## 2. Standard Operating Procedure (SOP)

### Step 1: Boot ViRa (Cold Start)
1. Ensure the robot is parked on a level surface away from stairs or ledges.
2. Verify that the physical red Mushroom E-Stop button is **released** (twist clockwise to release).
3. Connect the 3S LiPo/LiFePO4 battery pack and observe the main power LED.
4. Toggle the main power switch to `ON`.
5. Observe status illumination:
   - Green strobe on MCU indicates motor controller initialized.
   - Solid blue LED on sensor hub indicates LiDAR, IMU, and RealSense cameras powered.
   - Host computer completes boot cycle (~30 seconds).

### Step 2: Perform Pre-Flight Diagnostics
Run the automated preflight verification command from the operator terminal or onboard console:
```bash
./scripts/run_preflight.py --json
```
Verify that all 15 operational subsystems return `"PASS"`:
1. Battery Voltage ($\ge 11.5\text{V}$)
2. Physical E-stop Switch (Unlatched)
3. Motor Controller MCU (Heartbeat active)
4. Encoders (Left/Right counters responding)
5. LiDAR (2D planar scan streaming at $\ge 10\text{Hz}$)
6. IMU (6-DOF orientation and acceleration streaming)
7. RGB-D Camera (Depth stream healthy)
8. Coordinate Frames / TF Tree (Base-to-map transforms valid)
9. Odometry Filter (Covariance within acceptable envelope)
10. ROS 2 Middleware (Core nodes active)
11. VIRA EventBus (Priority dispatch verified)
12. RobotBridge (State: `IDLE`)
13. Nav2 Navigation Stack (`lifecycle_manager` active)
14. Localization / AMCL (Particle cloud converged)
15. InteractionGateway (FastPath active, fallback operational)

*If any check reports `FAIL`, the robot automatically enforces `SAFE_IDLE`. Do not attempt motion until resolved.*

### Step 3: Authorize Motion
Software boot alone does **not** grant motion permission. The operator must explicitly authorize locomotion:
```bash
# Via CLI command:
vira-cli authorize-motion --operator "operator_name" --timeout 3600

# Or via interaction voice interface:
"ViRa, authorize motion for operator John"
```
The state machine will transition from `IDLE` / `SYSTEM_READY` to `MOTION_AUTHORIZED`.

### Step 4: Start Supervised Navigation
Command a navigation mission using either voice or semantic dispatch:
- **Voice Command:** `"ViRa, take me to the robotics research lab."`
- **CLI Dispatch:**
  ```bash
  vira-cli dispatch-mission --destination "Robotics Research Lab"
  ```
ViRa will announce intent via TTS (`"Navigating to Robotics Research Lab"`), generate path plan, and transition to `NAVIGATING`.

### Step 5: Monitor Telemetry
Operators must keep the telemetry surface active during transit:
```bash
vira-cli monitor-telemetry --stream
```
Monitor the 15 subsystem health bars, current velocity, battery level, and obstacle proximity.

### Step 6: Execute Controlled STOP
To halt the robot smoothly without triggering a hard safety trip:
- **Voice:** Say `"ViRa, stop"` or `"Stop right now"`. FastPath executes within `< 10ms`.
- **CLI:** Press `Spacebar` in the monitor console or run `vira-cli stop`.
- Robot brings velocity to `0.0 m/s` and transitions to `STOPPING` $\to$ `IDLE`.

### Step 7: Perform Physical Emergency Stop (E-Stop)
In any critical hazard scenario:
- **Depress the red mushroom E-Stop button** on the robot top deck.
- Motor power is mechanically/electrically cut in hardware; software enters `EMERGENCY_STOP`.
- Velocity commands are unconditionally locked out at `0.0 m/s`.

### Step 8: Recover from a Fault / Emergency Stop
ViRa strictly enforces **Zero Auto-Resume**:
1. Remove all physical obstacles or resolve hardware issues.
2. Twist the red E-Stop button to mechanically reset it.
3. Explicitly reset the safety gate:
   ```bash
   vira-cli reset-safety --operator "operator_name"
   ```
4. Verify pre-flight status is clean before creating a new mission.

### Step 9: Controlled Shutdown
1. Ensure the robot is stopped in `IDLE`.
2. Execute graceful shutdown:
   ```bash
   sudo systemctl stop vira-stack
   sudo shutdown -h now
   ```
3. Toggle main power switch to `OFF`.
4. Disconnect battery charging leads if storing.
