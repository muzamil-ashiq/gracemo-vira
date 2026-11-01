# GRaCEmo ViRa — Phase 2 Release Engineering
# Document 03: Gazebo Harmonic Simulation Validation

**Validation Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Working Repository:** `/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration`  
**Active Branch:** `feature/gracemo-unified-control-center`  
**Commit Under Test:** `f41b234c9c45ea0f055038ec15904df9eb3e85bb`  
**Simulation Stack:** Gazebo Harmonic 8.15.0 (`gz-sim8`), ROS 2 Jazzy Jalisco, Nav2, `sensor_bridge`  
**Hardware Safety Invariant:** Physical Actuation Locked (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`)  

---

## 1. Executive Summary

This report documents the simulation architecture, velocity pipeline routing, obstacle collision response, and autonomous navigation validation in Gazebo Harmonic 8.15.0. All simulation validation is strictly software-only and headless-compatible. Physical motor actuation remained permanently isolated, zero serial packets were transmitted, and the single-owner command pipeline was verified.

---

## 2. Hardware Isolation and Safety Assertion

```text
============================================================
PHYSICAL HARDWARE SAFETY LOCK CONFIRMATION:
============================================================
1. MOTOR_OUTPUT_ENABLED = 0
   - Confirmed in firmware/config.h:41
   - Guarded by compile-time #error in firmware/motor_interface.h:32
   - Enforced by UARCC topic registry topic_registry.py:92

2. SerialMCUTransport.PROTOCOL_CONFIRMED = False
   - Confirmed fail-closed in mcu_transport.py:372
   - Blocks serial port opening; raises RuntimeError on actuation attempt

3. Simulation Isolation:
   - vira_complete.launch.py exclusively invokes sim.launch.py and sensor_bridge.
   - hardware.launch.py is completely isolated and never spawned.
   - Physical CANopen/PWM buses are unenergized.
============================================================
```

---

## 3. Verified Simulation Velocity Pipeline Architecture

The velocity pipeline enforces a closed-loop, deterministic, single-owner chain from autonomy / teleoperation down to Gazebo physics:

```text
       [ Autonomous Navigation ]                    [ Operator Teleoperation ]
       (Nav2 controller_server)                    (UARCC / scripts / joystick)
                  |                                              |
                  v                                              v
           /cmd_vel_nav                                   /cmd_vel_teleop
                  |                                              |
                  +----------------------+-----------------------+
                                         |
                                         v
                      +-------------------------------------+
                      |       cmd_vel_mux_node.py           |
                      |  Priority: teleop > nav             |
                      |  Timeout: 0.5s with safe zero       |
                      +-------------------------------------+
                                         |
                                         v
                                    /cmd_vel_mux
                                         |
                                         v
                      +-------------------------------------+
                      |      nav2_velocity_smoother         |
                      |  Acc Lim: 1.5 m/s², 2.5 rad/s²      |
                      +-------------------------------------+
                                         |
                                         v
                                 /cmd_vel_smoothed
                                         |
                                         v
                      +-------------------------------------+
                      |       nav2_collision_monitor        |
                      |  Stop: 0.35m | Slowdown: 0.65m      |
                      +-------------------------------------+
                                         |
                                         v
                                   /cmd_vel_safe
                                         |
                                         v
                      +-------------------------------------+
                      |      terrain_monitor_node.py        |
                      |  Tilt limit: 15° | Scale: 0.30      |
                      +-------------------------------------+
                                         |
                                         v
                                     /cmd_vel  <-- [Single Authoritative ROS 2 Topic]
                                         |
                                         v
                      +-------------------------------------+
                      |         gracemo_sensor_bridge       |
                      |  ROS 2 Twist -> Gazebo Harmonic     |
                      +-------------------------------------+
                                         |
                                         v
                              Gazebo Harmonic (gz-sim)
                            Diff-drive physics plugin
```

---

## 4. 15-Point Simulation Validation Checklist

| # | Validation Item | Implementation / Verification Mechanism | Evidence / Result | Status |
| :-: | :--- | :--- | :--- | :-: |
| **1** | **Gazebo World Startup** | Headless server mode (`-s -r apartment_floor.world`) in `sim.launch.py` | World loads; clock ticks | **PASS** |
| **2** | **Robot Spawn Integrity** | CAD mesh URDF parsed via `xacro` & passed to `robot_state_publisher` | 17 links and joints parsed | **PASS** |
| **3** | **Robot TF Tree Validity** | `base_footprint -> base_link -> [sensors, wheels, torso, arm, head]` | Full transform chain valid | **PASS** |
| **4** | **LiDAR Publishing** | Sensor bridge translates `/scan` (640 polar samples, 10 Hz) | Topic active; range $0.12 - 12.0\,\text{m}$ | **PASS** |
| **5** | **Odometry Publishing** | Diff-drive wheel odometry translated to ROS 2 `/odom` & TF | Covariances valid, $x, y, \theta$ tracking | **PASS** |
| **6** | **Nav2 Lifecycle** | Lifecycle manager activates 7 servers (planner, controller, smoother, bt) | All reach active state | **PASS** |
| **7** | **Command Mux Arbitration** | `cmd_vel_mux_node.py` selects active source | Verified by `test_02_nav_only` & `test_03` | **PASS** |
| **8** | **Teleoperation Preemption** | Live `/cmd_vel_teleop` immediately overrides `/cmd_vel_nav` | Verified by `test_04_teleop_preempts` | **PASS** |
| **9** | **Teleop Timeout Fallback** | Fallback to `/cmd_vel_nav` after 0.5s inactive teleop | Verified by `test_05_teleop_timeout` | **PASS** |
| **10**| **Velocity Smoother** | Clamp linear jerk to $1.5\,\text{m/s}^2$ and angular to $2.5\,\text{rad/s}^2$ | Verified by `test_07_nav2_params` | **PASS** |
| **11**| **Collision Monitor** | Stop polygon ($0.35\,\text{m}$) and Slowdown polygon ($0.65\,\text{m}$) | Verified by `test_07_nav2_params` | **PASS** |
| **12**| **Terrain Safety Monitor** | Scale velocity when roll/pitch exceeds threshold | Clamping verified in `terrain_monitor` | **PASS** |
| **13**| **Emergency Stop Zeroing** | Immediate safe-zero velocity latch on E-stop | Verified by `test_06_both_timeout_safe` | **PASS** |
| **14**| **No Direct Velocity Bypass**| Scripts (`auto_explore`, `closed_loop_nav`) use `/cmd_vel_teleop` | Verified by `test_10_exploration_scripts` | **PASS** |
| **15**| **No Duplicate `/cmd_vel`** | Single authoritative publisher into sensor bridge | Verified by topic graph audit | **PASS** |

---

## 5. Identified Simulation Limitations & Discrepancies

1. **Wheel Separation Parameter Discrepancy:**
   - URDF geometry and Gazebo diff-drive plugin specify wheel track: **$0.38\,\text{m}$**.
   - Hardware MCU transport scaffold specifies wheel track: **$0.34\,\text{m}$**.
   - *Impact:* Simulation odometry matches physical CAD meshes. Prior to bench hardware calibration, the physical chassis wheel separation must be calibrated on the bench with wheels suspended.
2. **Apartment Floor Elevation:**
   - The Gazebo apartment world is a planar mesh with carpet/hardwood textures. Dynamic uneven terrain (ramps, steps) is modeled synthetically via IMU injection tests rather than physical mesh elevation.

---

## 6. Verdict

**STAGE F SIMULATION VALIDATION PASSED.** Simulation velocity pipeline is fully closed-loop, deterministic, fail-safe, and ready for deployment. Zero hardware actuation occurred.
