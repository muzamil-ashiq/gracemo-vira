# Test Execution and Verification Results

This document consolidates all empirical test executions, automated test suites, kinematics diagnostics, and runtime verification results across the integration phases.

---

## 1. Automated Test Suites Summary

### Suite A: Primary Migration Workspace (`VIRA-agent-bridge-migration`)
Command:
```bash
PYTHONPATH="adapters/robot-bridge:vira_interaction:.:$PYTHONPATH" pytest tests/unit \
  tests/test_active_neck_urdf.py tests/test_base_controller.py tests/test_arm_controller.py \
  tests/test_arm_kinematics_7dof.py
```
**Results:** **75 PASSED, 0 FAILED** in 0.37 seconds.

| Test Module | Tests | Status | Scope |
|---|---|---|---|
| `tests/unit/test_drive_layout_urdf.py` | 2 | **PASS** | 4-Wheel skid-steer & differential layout generation |
| `tests/unit/test_fast_path.py` | 5 | **PASS** | Fast-path latency & command caching |
| `tests/unit/test_human_interaction_behavior.py` | 9 | **PASS** | Proximity detection & greeting states |
| `tests/unit/test_interaction_fsm.py` | 6 | **PASS** | Interaction finite state machine |
| `tests/unit/test_live_sensor_pipeline.py` | 6 | **PASS** | Synthetic vs live camera/LiDAR/IMU streams |
| `tests/unit/test_mcu_protocol_engine.py` | 10 | **PASS** | STM32 packet framing & checksums |
| `tests/unit/test_serial_mcu_transport.py` | 7 | **PASS** | Safety transport locks (`PROTOCOL_CONFIRMED = False`) |
| `tests/unit/test_stm32_protocol_parser.py` | 8 | **PASS** | Protocol parsing & telemetry unpack |
| `tests/test_active_neck_urdf.py` | 8 | **PASS** | Release-frozen neck pan/tilt limits and dynamics |
| `tests/test_base_controller.py` | 5 | **PASS** | Base controller velocity commands |
| `tests/test_arm_controller.py` | 4 | **PASS** | Manipulator trajectory execution |
| `tests/test_arm_kinematics_7dof.py` | 5 | **PASS** | 7-DOF forward and inverse kinematics |

---

### Suite B: Integrated Prototype Workspace (`gracemo_integrated_v1`)
Command:
```bash
python3 -m pytest prototypes/gracemo_integrated_v1/tests/test_command_validator.py \
  prototypes/gracemo_integrated_v1/tests/test_destination_registry.py \
  prototypes/gracemo_integrated_v1/tests/test_intent_parser.py \
  prototypes/gracemo_integrated_v1/tests/test_navigation_simulation.py
```
**Results:** **17 PASSED, 0 FAILED** in 0.32 seconds.

| Test Module | Tests | Status | Scope |
|---|---|---|---|
| `test_command_validator.py` | 2 | **PASS** | Safe velocity limits & command bounds |
| `test_destination_registry.py` | 3 | **PASS** | Apartment room coordinates & aliases |
| `test_intent_parser.py` | 5 | **PASS** | NLP intent parsing (navigate, stop, status) |
| `test_navigation_simulation.py` | 7 | **PASS** | 4WD URDF, differential URDF, terrain monitor, frontier exploration, attitude diagnostics |

---

## 2. Quantitative Drive Kinematics Test (`test_drive_diagnostics.py`)

Executed live inside Gazebo Harmonic with the integrated robot in `gracemo_apartment.world`:

| Maneuver | Commanded Input | Theoretical Wheel Speed | Observed Left Wheels | Observed Right Wheels | Net Displacement | Status |
|---|---|---|---|---|---|---|
| **Forward** | $v_x = +0.3\text{ m/s}, \omega_z = 0.0$ | $+2.6087\text{ rad/s}$ | $+2.6087\text{ rad/s}$ | $+2.6087\text{ rad/s}$ | $+0.75\text{ m}$ forward | **PASS** |
| **Reverse** | $v_x = -0.3\text{ m/s}, \omega_z = 0.0$ | $-2.6087\text{ rad/s}$ | $-2.6087\text{ rad/s}$ | $-2.6087\text{ rad/s}$ | $-0.75\text{ m}$ reverse | **PASS** |
| **CCW Spin** | $v_x = 0.0, \omega_z = +0.8\text{ rad/s}$ | $L: -1.9826, R: +1.9826$ | $-1.9826\text{ rad/s}$ | $+1.9826\text{ rad/s}$ | $+114.6^\circ$ yaw | **PASS** |
| **CW Spin** | $v_x = 0.0, \omega_z = -0.8\text{ rad/s}$ | $L: +1.9826, R: -1.9826$ | $+1.9826\text{ rad/s}$ | $-1.9826\text{ rad/s}$ | $-114.6^\circ$ yaw | **PASS** |
| **Stopping** | $v_x = 0.0, \omega_z = 0.0$ | $0.0000\text{ rad/s}$ | $0.0000\text{ rad/s}$ | $0.0000\text{ rad/s}$ | Velocity drops to $0$ | **PASS** |
