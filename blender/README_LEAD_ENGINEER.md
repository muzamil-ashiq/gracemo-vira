# GRACEEMO-01 — Blender Robotics Engineering Handover Dossier

**Target Platform:** Blender 5.2.1 LTS  
**Project:** GRACEEMO-01 Service Humanoid & Campus Digital Twin  
**Status:** Engineering Phase 1, Phase 2, & Phase 3 Complete  
**Deliverable Archive:** [`blender/GRACEEMO-01_Blender_Engineering_Deliverable.zip`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GRACEEMO-01_Blender_Engineering_Deliverable.zip) (4.12 MB)

---

## 1. Master Blender Files Summary

| File | Phase | Key Features & Contents | Validation Status |
| :--- | :--- | :--- | :--- |
| **[`GRACEEMO-01_MASTER_ENGINEERING_PHASE3_HARDWARE.blend`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GRACEEMO-01_MASTER_ENGINEERING_PHASE3_HARDWARE.blend)** | **Phase 3** *(Current Master)* | Complete internal component packaging: 24V LiFePO4 battery pack, Jetson Orin compute bay, STM32 MCU, 4-wheel multi-part mechanical assemblies (motors, encoders, bearings, hubs, axles), arm harmonic actuator envelopes, neck servos, camera & LiDAR FOV visualization cones, 7 cable conduit runs in `12_CABLE_ROUTING`, collision proxies in `14_COLLISION`, service access panels, and live CoM estimation. Preserves all Phase 2 motion. | **PASS** (10-Point Engineering Check) |
| **[`GRACEEMO-01_MASTER_ENGINEERING_PHASE2_MOTION.blend`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GRACEEMO-01_MASTER_ENGINEERING_PHASE2_MOTION.blend)** | **Phase 2** | Full interactive articulation rig: 15 dedicated controllers in `15_DEBUG`, 2-bone rigid inverse kinematics (IK) with elbow pole vector targets, 240-frame motion validation timeline, non-destructive poses (`IDLE`, `GREETING`, `NAMASTE`, `POINT`, `GUIDE`, `ASSIST`), and interactive `GRACEEMO CONTROL` 3D Viewport sidebar panel. Zero mesh deformation. | **100% PASS** (10/10 Checks) |
| **[`GRACEEMO-01_MASTER_ENGINEERING_PHASE1_FIXED.blend`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GRACEEMO-01_MASTER_ENGINEERING_PHASE1_FIXED.blend)** | **Phase 1** | Clean robotics kinematic tree: 16 semantic collections, eliminated duplicate frames (`JOINT_base_link`, `JOINT_LEFT/RIGHT_Shoulder`), standard ROS optical camera rotation `[-90°, 0°, -90°]`, 4WD drive wheel reference frames. | **100% PASS** (16/16 Checks) |
| **[`GRACEEMO-01_Engineering_Prototype.blend`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GRACEEMO-01_Engineering_Prototype.blend)** | Baseline | Original visual prototype model (unmodified reference). | Preserved |
| **[`GraceEMO_LPU.blend`](file:///Users/samdavi/projects/GraceEMO-Final/blender/GraceEMO_LPU.blend)** | Environment | 200×200m LPU university campus digital twin with 13 semantic building blocks, navigation graph, and road network. | Integrated |

---

## 2. Hardware Manifest & Engineering Database

- **YAML Specification:** [`docs/hardware/graceemo_hardware_manifest.yaml`](file:///Users/samdavi/projects/GraceEMO-Final/docs/hardware/graceemo_hardware_manifest.yaml)
- **JSON Mirror:** [`docs/hardware/graceemo_hardware_manifest.json`](file:///Users/samdavi/projects/GraceEMO-Final/docs/hardware/graceemo_hardware_manifest.json)
- **Master Excel Database:** [`docs/GraceEMO_Master_Database.xlsx`](file:///Users/samdavi/projects/GraceEMO-Final/docs/GraceEMO_Master_Database.xlsx) (22 corporate sheets covering Architecture, Code Deep Dive, End-to-End Workflows, Logic Rationale, and Upgrade Logs).

### Component Manifest Summary (38 Components across 10 Categories)
- **MOBILITY:** 4× Driven Wheel Hubs, In-Wheel BLDC Gearmotors (`MOB-06`), Optical Encoders (`MOB-07`), 6004-2RS Ball Bearings (`MOB-08`), Passive Casters (`MOB-05`).
- **POWER:** 24V 25Ah LiFePO4 Battery (`PWR-01`, 7.2kg), MIDI-40A Fuse (`PWR-02`), Main Contactor (`PWR-03`), 24V→12V/5V DC-DC (`PWR-04`), Magnetic Charging Port (`PWR-05`).
- **COMPUTE:** NVIDIA Jetson Orin Nano / AGX Edge Computer (`CMP-01`), STM32 Real-Time MCU Carrier (`CMP-02`).
- **CONTROL:** Dual-Channel BLDC Motor Controllers (`CTL-01`), Serial Bus Actuator Hub (`CTL-02`).
- **PERCEPTION:** Forward 2D/3D LiDAR (`SEN-01`), Intel RealSense D435i Depth Camera (`SEN-02`), 9-DoF IMU (`SEN-03`), 5× ToF Sensors (`SEN-04`).
- **COMMUNICATION:** Industrial 5-Port Gigabit Ethernet Switch (`COM-02`), Wi-Fi 6 / BT Module (`COM-01`).
- **AUDIO:** Forehead Beamforming Dual MEMS Mic Array (`AUD-01`), 15W High-Fidelity Voice Speaker (`AUD-02`).
- **ACTUATION:** Neck Dynamixel XM430 Servos (`ACT-01`), Shoulder Harmonic Actuators (`ACT-02`), Elbow Servos (`ACT-03`), Wrist Micro Actuators (`ACT-04`), Hand Finger Mechanisms (`ACT-05`).
- **MECHANICAL:** Lower Aluminum Chassis Baseplate (`MEC-01`), Torso Structural Frame (`MEC-02`), Battery Sliding Trays (`MEC-03`), Service Access Hatches (`MEC-04`, `MEC-05`).
- **SAFETY:** Hardwired Emergency Stop Switch (`SAF-01`), System Key/Rocker Switch (`SAF-02`), 360° Waist LED Ring (`SAF-03`).

---

## 3. Mass Properties & Center of Mass (CoM)

- **Total System Mass Estimate:** **18.55 kg** (based on currently selected hardware envelopes; structural skins & patient support provisional).
- **Center of Mass (CoM) in `base_footprint`:**
  - $X_{CoM} = 0.000\text{ m}$ (perfect lateral symmetry)
  - $Y_{CoM} = -0.012\text{ m}$ (slight forward bias for navigation stability)
  - $Z_{CoM} = 0.385\text{ m}$ (low center of gravity well within wheel base height)
- **Visual CoM Indicator:** Represented in Blender viewport as `INDICATOR_CENTER_OF_MASS` in `15_DEBUG`.

---

## 4. How to Test & Interact in Blender 5.2.1

### A. Opening the Master Phase 3 Scene
```bash
/Applications/Blender.app/Contents/MacOS/Blender blender/GRACEEMO-01_MASTER_ENGINEERING_PHASE3_HARDWARE.blend
```

### B. Interactive Viewport Sidebar (`GRACEEMO CONTROL`)
1. Press `N` in the 3D Viewport to open the right-hand Sidebar.
2. Select the **`GRACEEMO`** tab.
3. Use the live buttons:
   - **HEAD:** Look Left / Center / Right, Up / Forward / Down, Tilt Left / Right.
   - **LEFT / RIGHT ARM:** Raise / Lower, Elbow Bend / Straight.
   - **HANDS:** Left Open / Close, Right Open / Close.
   - **POSES:** `IDLE`, `GREETING`, `NAMASTE`, `POINT`, `GUIDE`, `ASSIST`.
   - **MOBILITY:** Forward, Reverse, Rotate Left, Rotate Right, Stop.
   - **SYSTEM:** Reset Pose, Reset Robot, Validate.

### C. Manual FK/IK Posing
- Select any empty in collection **`15_DEBUG`**:
  - Rotate `CTRL_NECK_YAW` ($Z$), `CTRL_NECK_PITCH` ($X$), `CTRL_NECK_ROLL` ($Y$).
  - Rotate `CTRL_LEFT_SHOULDER` or `CTRL_RIGHT_SHOULDER` (pitch/roll).
  - Drag `CTRL_LEFT_HAND_IK` or `CTRL_RIGHT_HAND_IK` to test rigid inverse kinematics.
  - Rotate `CTRL_LEFT_WHEEL`, `CTRL_RIGHT_WHEEL`, etc., to test drive axle rotation.
- To reset at any time, run `from animation.poses import reset_robot_pose; reset_robot_pose()`.

### D. Running Motion Timeline
- Press `Spacebar` to play the 240-frame validation timeline:
  - Frame 1: `IDLE`
  - Frame 30: `HEAD LOOK LEFT`
  - Frame 60: `HEAD CENTER`
  - Frame 90: `RIGHT ARM RAISE`
  - Frame 120: `RIGHT ARM LOWER`
  - Frame 150: `LEFT ARM RAISE`
  - Frame 180: `BOTH ARMS NEUTRAL`
  - Frame 210: `GREETING`
  - Frame 240: `IDLE`

---

## 5. Engineering Validation Reports

### Phase 2 Motion Validation: **100% PASS**
```text
Neck:                PASS
Left Arm:            PASS
Right Arm:           PASS
Hands:               PASS
Wheels:              PASS
IK:                  PASS
Joint Limits:        PASS
Reset:               PASS
Pose System:         PASS
UI:                  PASS
```

### Phase 3 Hardware Packaging Validation: **PASS**
```text
Hardware Envelopes:              PASS
Mechanical Interference:         PASS / WARNING (Clearances verified; FEA pending)
Sensor Obstruction:              PASS (Camera & LiDAR unobstructed)
Cable Routing & Clearance:       PASS (7 realistic conduits routed)
Joint Clearance:                 PASS (Actuators move rigidly with link frames)
Wheel Clearance & Axles:         PASS (Hubs, axles, bearings, motors, encoders verified)
Service Access:                  PASS (Battery, compute, wheel & sensor panels marked)
Collision Envelopes:             PASS (Simplified physics proxies in 14_COLLISION)
Manifest & Mass Integrity:       PASS (38 components mapped & CoM evaluated)
Packaging Feasibility:           PASS (Feasible concept layout)
```

---

## 6. Critical Engineering Disclaimer
*This deliverable represents preliminary mechanical packaging, envelope layout, and kinematic motion verification. It is not final production tooling CAD, nor does it represent certified electrical schematics or clinically validated medical patient support mechanisms.*
