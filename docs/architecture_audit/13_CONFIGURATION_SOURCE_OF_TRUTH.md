# GRaCEmo ViRa — Configuration Source of Truth
# Document 13: Authoritative Configuration & Parameter Standards

**Consolidation Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Status:** Canonical Configuration Reference  
**Scope:** Kinematics, Network Endpoints, Schemas, and Safety Limits.

---

## 1. Single Source of Truth Parameter Table

| Parameter | Authoritative Value | Authoritative Source File | Consumers & Adapters | Conflict / Ambiguity Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **Wheel Separation (Track)** | `0.34 m` *(Nominal URDF)* | `ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro` & `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml` | Differential drive controller, Gazebo physics, UARCC display | Annotated as `[UNVERIFIED CONFLICT]` in `config/robot.yaml` (`0.32m`). Requires physical caliper measurement before hardware motor activation. |
| **Wheel Radius** | `0.065 m` | `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml` & `config/robot.yaml` | MCU odometry, differential drive kinematics | Standardized on `0.065 m`. |
| **Robot Collision Radius** | `0.23 m` | `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` | Nav2 local/global costmaps, collision monitor | Standardized on `0.23 m` footprint radius for Nav2 obstacle inflation. |
| **Max Linear Velocity (HW)** | `0.35 m/s` | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py` | Physical MCU serial transport clamp | Hardware fail-safe clamp strictly enforced at $\le 0.35\text{ m/s}$. |
| **Max Linear Velocity (Sim)** | `0.80 m/s` | `config/robot.yaml` & `gracemo_nav2/config/nav2_params.yaml` | Gazebo Harmonic simulation | Permitted in simulation only; never sent to physical motors. |
| **Max Angular Velocity (HW)** | `0.75 rad/s` | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py` | Physical MCU serial transport clamp | Hardware fail-safe clamp strictly enforced at $\le 0.75\text{ rad/s}$. |
| **Max Angular Velocity (Sim)** | `1.50 rad/s` | `config/robot.yaml` & `gracemo_nav2/config/nav2_params.yaml` | Gazebo Harmonic simulation | Permitted in simulation only; never sent to physical motors. |
| **Cognitive Kernel HTTP Port** | `7780` | `kernel/gracemo-kernel/src/api.rs` & `config/system.yaml` | UARCC, Python reasoner, perception bridge | Unified across all adapters and UARCC modules. |
| **Cognitive Kernel Socket** | `/tmp/kernel.sock` | `kernel/gracemo-kernel/src/main.rs` | Local IPC transport | Unified; `/tmp/gracemo.sock` retained as backward-compatible symlink. |

---

## 2. Destination Schemas & Functional Demarcation

The repository maintains two intentional, complementary destination files with distinct functional responsibilities:

### A. Coordinate Navigation Targets: `config/destinations.json`
- **Owner:** Autonomous Coordinator (`gracemo_nav2/coordinator_node.py`) and UARCC Mission Control.
- **Purpose:** Strict $(X, Y, Z, Q_x, Q_y, Q_z, Q_w)$ metric coordinates and orientation for 6 simulation rooms:
  - `kitchen` $(x=3.5, y=-2.0)$
  - `living_room` $(x=1.2, y=0.5)$
  - `bedroom` $(x=-2.5, y=3.0)$
  - `office` $(x=-1.0, y=-2.5)$
  - `hallway` $(x=0.0, y=0.0)$
  - `charging_station` $(x=0.0, y=-0.5)$
- **Schema:**
```json
{
  "destinations": [
    {
      "id": "kitchen",
      "name": "Kitchen",
      "pose": {
        "position": {"x": 3.5, "y": -2.0, "z": 0.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
      }
    }
  ]
}
```

### B. Natural Language Alias Grounding: `config/places.json`
- **Owner:** Pygame Speech & Dialogue Engine (`vira_interaction/core/destination_grounding.py`) and Hardware Qualification Tests.
- **Purpose:** Maps 26 informal spoken aliases (e.g., `"pantry"`, `"cooking area"`, `"fridge"`) to spatial boundaries and target destinations.
- **Preservation Notice:** Required by `tests/hardware/test_phase7_production_acceptance.py` and `test_phase8_operational_qualification.py`. Both `config/places.json` and `vira_interaction/config/places.json` are maintained.

---

## 3. Physical Hardware Sign-Off Requirements

Prior to modifying `MOTOR_OUTPUT_ENABLED = 1` or `SerialMCUTransport.PROTOCOL_CONFIRMED = True`:
1. **Track Measurement:** Measure distance between centerlines of left and right drive wheels with Vernier calipers. Update `config/robot.yaml` and `hardware_params.yaml`.
2. **Wheel Diameter:** Measure left and right drive wheel outer rubber diameter under full robot payload weight.
3. **Emergency Stop Verification:** Confirm physical E-stop latch breaks motor driver enable signal mechanically.
