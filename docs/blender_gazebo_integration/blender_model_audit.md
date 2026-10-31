# Blender Master Model Audit: `robot.blend`

**Source File:** `~/gracemo_gazebo/gracemo_blender_to_gazebo/robot.blend`  
**Blender Engine:** Blender 5.2.2 LTS Python Environment (`bpy`)  
**SHA-256 Checksum:** `8bece57adfed0a40560d19c2d8f4da380b5c5718ee903237ba2d01e54e57b12a`  
**Deep Inventory JSON:** [blender_deep_inventory.json](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/staging_blender_integration/reports/blender_deep_inventory.json)  

---

## 1. Scene Structure Overview

Inspection via the embedded Blender Python API revealed:
- **Total Objects:** 96
  - **MESH Objects:** 71
  - **EMPTY Objects (Rig & Animation Controls):** 24
  - **FONT Objects:** 1
- **Overall Bounding Dimensions:**
  - Width ($X$ in Blender / lateral): $0.700\text{ m}$
  - Depth ($Y$ in Blender / longitudinal): $0.580\text{ m}$
  - Height ($Z$ in Blender / vertical): $1.240\text{ m}$ (Human-scale domestic service robot)

---

## 2. Coordinate Conventions & Transform Alignment

| Axis | Blender Master Convention | Standard ROS 2 / REP-103 Convention | Integration Transform |
|---|---|---|---|
| **Forward** | $-Y$ | $+X$ | Rotated $+90^\circ$ about $Z$ |
| **Left** | $+X$ | $+Y$ | Rotated $+90^\circ$ about $Z$ |
| **Up** | $+Z$ | $+Z$ | Preserved invariant |

All visual sub-assemblies were exported with a fixed basis transformation matrix applying $+90^\circ$ rotation about $Z$, mapping Blender's $-Y$ forward vector directly onto ROS 2 $+X$ forward vector.

---

## 3. Wheel Assembly Analysis & Kinematics

In Blender, the drive base consists of four distinct wheel locations. Crucially, each location does not consist of a single mesh, but **three co-axial visual subcomponents**:

```
Front Left Wheel Assembly:
├── WHEEL_FRONT_LEFT       (Rubber tire tread, material GRACE_TIRE)
├── WHEEL_RING_FRONT_LEFT  (Decorative outer ring, material GRACE_ACCENT)
└── WHEEL_HUB_FRONT_LEFT   (Illuminated hubcap, material GRACE_BLUE_GLOW)
```

### Physical Dimensions Derived from Geometry:
- **Wheel Outer Radius ($R$):** $0.115\text{ m}$ ($115\text{ mm}$ radius, $230\text{ mm}$ diameter).
- **Wheel Tread Width:** $0.100\text{ m}$ ($100\text{ mm}$).
- **Axle Centers:**
  - Front Axle: $X = +0.220\text{ m}$ (in ROS frame)
  - Rear Axle: $X = -0.220\text{ m}$ (in ROS frame)
  - **Wheelbase ($L$):** $0.440\text{ m}$
  - Left Wheel Centers: $Y = +0.285\text{ m}$
  - Right Wheel Centers: $Y = -0.285\text{ m}$
  - **Track Width ($W$):** $0.570\text{ m}$

### Kinematic Unification:
The temporary conversion pipeline had mistakenly attached rings and hubs to `base_link`, causing tires to spin in place while rings and hubs remained stationary. Our production exporter unifies `WHEEL_*`, `WHEEL_RING_*`, and `WHEEL_HUB_*` into a single continuous joint link per wheel (`wheel_*_visual.obj`), ensuring synchronous physical rotation.

---

## 4. Articulation vs. Visual Empties

The Blender file contains 24 EMPTY objects representing animation pivot targets (e.g. `ANIM_TORSO`, `ANIM_HEAD`, `ANIM_SHOULDER_LEFT`, `ANIM_ELBOW_LEFT`).
- **Kinematic Rule:** Blender empties do not automatically represent physical actuators or bearings.
- **Physical Integration:**
  1. `ANIM_TORSO` ($Z=0.320\text{ m}$) aligns with the physical deck plate and active waist pitch joint ($\pm 30^\circ$).
  2. `ANIM_HEAD` ($Z=0.905\text{ m}$) aligns with the pan-tilt neck bracket ($Z$-pan $\pm 90^\circ$, $Y$-tilt $-30^\circ$ to $+45^\circ$).
  3. Left arm components (`UPPER_ARM_LEFT`, `ELBOW_LEFT`, `FOREARM_LEFT`, `PALM_LEFT`, `FINGER_LEFT_1..4`) are unified into a static resting pod (`left_arm_visual.obj`), matching the physical prototype design.
  4. Right arm components (`UPPER_ARM_RIGHT`, `ELBOW_RIGHT`, `FOREARM_RIGHT`, etc.) map onto the 7-DOF serial manipulator and parallel gripper.

---

## 5. Material & Texture Assignments

Blender materials assigned in the source scene:
1. `GRACE_WHITE`: Body shell, head casing, arm fairings.
2. `GRACE_BLACK`: Chassis internal chassis, sensor housings, bezels.
3. `GRACE_ACCENT`: Safety orange highlight rings, button trim, base stripe (`#FF7900`).
4. `GRACE_TIRE`: High-friction dark rubber compound (`#222222`).
5. `GRACE_SCREEN`: Ultra-gloss OLED face display panel (`#111111`).
6. `GRACE_BLUE_GLOW`: Cyan emissive OLED eyes, mouth, and hub rings (`#00D9FF`).
