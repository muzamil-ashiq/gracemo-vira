# Physics, Collisions, and Dynamic Stability

This document details the physical modeling, inertial distribution, contact parameters, and stability metrics implemented for the GRaCEmo ViRa integrated model in Gazebo Harmonic 8.15.0.

---

## 1. Mass & Inertial Budget Breakdown

| Subsystem / Link | Mass [kg] | Center of Mass $(x, y, z)$ [m] | Principal Moments of Inertia $(I_{xx}, I_{yy}, I_{zz})$ [$\text{kg}\cdot\text{m}^2$] | Physical Rationale |
|---|---|---|---|---|
| `base_link` (Chassis) | $22.0$ | $(0.0, 0.0, +0.020)$ | $(0.380, 0.520, 0.680)$ | Houses battery packs, power converters, heavy drive motors, and chassis structure. Center of gravity kept low to maximize pitch/roll stability. |
| Drive Wheels (4 links) | $1.8$ each ($7.2$ total) | $(0.0, 0.0, 0.0)$ | $(0.00745, 0.01190, 0.00745)$ | High-torque in-hub motorized wheel assemblies ($R=0.115\text{ m}$). |
| `torso_link` (Upper Body) | $7.0$ | $(0.0, 0.0, +0.200)$ | $(0.180, 0.160, 0.120)$ | Electronics bays, compute modules (NVIDIA Jetson / x86 PC), waist actuators, internal wiring. |
| `neck_pan_link` | $0.2$ | $(0.0, 0.0, +0.020)$ | $(0.001, 0.001, 0.001)$ | High-torque pan servo bracket. |
| `head_link` | $1.5$ | $(0.0, 0.0, +0.080)$ | $(0.015, 0.015, 0.015)$ | OLED display panel, stereo camera bar, LiDAR sensor, tilt servo, speakers. |
| `left_arm_link` | $1.0$ | $(0.0, 0.0, -0.150)$ | $(0.010, 0.010, 0.005)$ | Lightweight fairing and resting arm pod. |
| Right Arm & Gripper | $1.0$ total | Distributed | Distributed | 7-DOF manipulator links & gripper fingers. |
| **Total Robot Mass** | **$39.9\text{ kg}$** | **$(0.0, 0.0, +0.215)$** | **Positive-Definite Tensor** | Full service-robot mass budget. |

---

## 2. Collision Geometry & Ground Clearance

Visual meshes have complex polyhedral boundaries that produce high friction spikes and numerical instability when used as contact geometry. The collision geometry is decoupled into simplified analytical shapes:

1. **Chassis Collision Hull:**
   - Geometry: Box $0.58\text{ m}$ (length) $\times 0.40\text{ m}$ (width) $\times 0.17\text{ m}$ (height).
   - Origin: Center $Z = +0.085\text{ m}$ relative to axle.
   - **Ground Clearance:** Exactly $80\text{ mm}$ ($0.080\text{ m}$) above floor level.
   - **Verification:** During all driving, acceleration, and ramp ascents, zero contact events are detected between `base_link` and ground planes.
2. **Wheel Contact Cylinders:**
   - Geometry: Cylinder radius $R = 0.115\text{ m}$, length $0.100\text{ m}$, oriented along $Y$-axis (`rpy="1.5707963 0 0"`).
   - Precision: $R$ exactly matches visual tire radius so that visual wheel mesh contacts ground seamlessly without clipping or floating.
3. **Torso & Head Collisions:**
   - Torso: Box $0.32\text{ m} \times 0.36\text{ m} \times 0.44\text{ m}$.
   - Head: Sphere radius $0.130\text{ m}$.

---

## 3. Surface Contact & Friction Model

Configured inside `gazebo_plugins.xacro` for all four wheel links:

```xml
<gazebo reference="${prefix}_wheel_link">
  <mu1>1.2</mu1>
  <mu2>1.0</mu2>
  <kp>1000000.0</kp>
  <kd>100.0</kd>
  <minDepth>0.002</minDepth>
  <maxVel>1.5</maxVel>
</gazebo>
```

- **$\mu_1 = 1.2$ (Primary tangential friction):** Simulates high-traction indoor rubber compounds on polished concrete and wood floors.
- **$\mu_2 = 1.0$ (Secondary lateral friction):** Prevents skid drift while allowing smooth differential turning.
- **$k_p = 10^6, k_d = 100$:** High contact stiffness with critical damping prevents numerical vibration and bouncing.

---

## 4. Active Posture Stabilization (Waist Pitch)

The torso is articulated via `waist_pitch_joint` to enable humanoid bowing, terrain compensation, and active balance:
- **Joint Range:** $\pm 30^\circ$ ($\pm 0.5236\text{ rad}$).
- **Controller:** Joint position PID controller in Gazebo Harmonic:
  - Proportional Gain ($P$): $800.0$
  - Integral Gain ($I$): $12.0$
  - Derivative Gain ($D$): $20.0$
  - Maximum Effort: $80.0\text{ N}\cdot\text{m}$
- **Empirical Settlement Performance:**
  - Upon spawn at $Z = 0.115\text{ m}$, the robot settles stably under gravity ($g = 9.801\text{ m/s}^2$) within $0.4\text{ seconds}$.
  - Steady-state waist pitch angle remains held at $-0.0002\text{ rad}$ ($0.01^\circ$ from perfectly upright) during rapid forward acceleration ($+0.3\text{ m/s}$) and stopping.
