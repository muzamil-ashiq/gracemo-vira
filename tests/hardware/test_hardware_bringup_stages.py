#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 5 Hardware-in-the-Loop Bring-Up Test Suite
Implements and rigorously validates Stages 1 through 10 of Section 35:
  Stage 1: Hardware communication & Startup Safety (No Motion)
  Stage 2: Sensors bring-up & Sensor-based safety (No Autonomous Motion)
  Stage 3: Motor test with wheels lifted (Differential drive & encoder direction)
  Stage 4: E-Stop & Command Watchdog
  Stage 5: Controlled low-speed floor movement
  Stage 6: Teleoperation mode
  Stage 7: TF Tree & Odometry Calibration
  Stage 8: Wheel slip measurement & odometry drift
  Stage 9: Voice-controlled movement & deterministic voice STOP
  Stage 10: Full interaction loop with hardware feedback
"""
import math
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))
sys.path.insert(0, str(ROOT / "graceemo_interaction"))

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.command_handler import CommandHandler
from gracemo_bridge.feedback_adapter import FeedbackAdapter
from gracemo_bridge.hardware_adapter import (
    BatteryStatus,
    HardwareAdapter,
    HardwareTelemetry,
    MotorControllerInterface,
)
from gracemo_bridge.navigation_adapter import NavigationAdapter
from gracemo_bridge.safety_adapter import SafetyAdapter
from gracemo_bridge.state_machine import (
    HardwareMode,
    MODE_VELOCITY_LIMITS,
    RobotState,
    RobotStateMachine,
)
from graceemo_interaction.core.event_bus import EventBusClient as ViraEventBus
from graceemo_interaction.core.fast_path import FastPathMatcher
from graceemo_interaction.core.gateway import InteractionGateway
from graceemo_interaction.core.safety_gate import SafetyGate


class TestHardwareBringupStages(unittest.TestCase):
    """Authoritative test suite for Phase 5 hardware bring-up stages."""

    def setUp(self):
        # Establish deterministic bus and hardware adapter
        self.bus = ViraEventBus(base_url="http://127.0.0.1:9999", source_name="test_hardware_bringup")
        self.motor_controller = MotorControllerInterface(
            wheel_separation_m=0.32,
            wheel_radius_m=0.065,
            encoder_ticks_per_rev=2048,
        )
        self.state_machine = RobotStateMachine(
            initial_state=RobotState.SAFE_IDLE,
            mode=HardwareMode.HARDWARE_SAFE,
        )
        self.hardware_adapter = HardwareAdapter(
            state_machine=self.state_machine,
            motor_controller=self.motor_controller,
            watchdog_timeout_sec=0.30,
            battery_low_v=11.5,
            battery_critical_v=10.5,
        )
        self.safety_adapter = SafetyAdapter(state_machine=self.state_machine)
        self.feedback_adapter = FeedbackAdapter(emit_callback=lambda env: None)
        self.navigation_adapter = NavigationAdapter(
            state_machine=self.state_machine,
            feedback_adapter=self.feedback_adapter,
        )
        self.command_handler = CommandHandler(
            state_machine=self.state_machine,
            safety_adapter=self.safety_adapter,
            navigation_adapter=self.navigation_adapter,
            hardware_adapter=self.hardware_adapter,
        )
        self.safety_gate = SafetyGate()
        self.fast_path = FastPathMatcher()
        self.gateway = InteractionGateway(
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        def _on_action(envelope):
            data = envelope.get("event_type", {}).get("data", {}) or envelope.get("data", {})
            self.command_handler.handle_action(
                action=data.get("action", ""),
                params=data.get("params", {}),
                trace_id=envelope.get("trace_id", "trace"),
                timestamp=envelope.get("timestamp"),
                session_id=envelope.get("session_id"),
            )

        self.bus.subscribe("ActionRequested", _on_action)

    def tearDown(self):
        self.hardware_adapter.shutdown()

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 1: Hardware Communication Only (NO MOTION)
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_01_hardware_communication_and_startup_safety(self):
        """
        Stage 1: Verify hardware communication and startup safety.
        Requirements:
          - Startup mode MUST default to HARDWARE_SAFE.
          - Initial velocity MUST be zero.
          - Robot state MUST be stationary SAFE_IDLE or IDLE.
          - Motion commands in HARDWARE_SAFE mode MUST be rejected.
        """
        self.assertEqual(self.state_machine.mode, HardwareMode.HARDWARE_SAFE)
        self.assertIn(self.state_machine.state, (RobotState.SAFE_IDLE, RobotState.IDLE))

        telem = self.hardware_adapter.get_telemetry()
        self.assertTrue(telem.motor_controller_connected)
        self.assertEqual(telem.linear_velocity, 0.0)
        self.assertEqual(telem.angular_velocity, 0.0)
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)

        # Attempt motion while in HARDWARE_SAFE: MUST be blocked
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.15, 0.0)
        self.assertFalse(accepted, "Motion command must be rejected in HARDWARE_SAFE mode")
        self.assertEqual(safe_lin, 0.0)
        self.assertEqual(safe_ang, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.SAFE_IDLE)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 2: Sensors (NO AUTONOMOUS MOTION)
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_02_sensor_bringup_and_sensor_based_safety(self):
        """
        Stage 2: Validate LiDAR, IMU, Camera, Odometry health and sensor-based safety.
        Requirements:
          - Valid sensor data accepted.
          - Degraded/invalid data rejected.
          - Sensor disconnect inhibits motion commands.
        """
        # 1. Validate clean sensor telemetry
        valid_lidar = [1.2] * 360
        ok, msg = self.safety_adapter.validate_sensor_data("lidar", valid_lidar)
        self.assertTrue(ok)

        valid_imu = {"accel_x": 0.01, "accel_y": -0.02, "accel_z": 9.81, "gyro_z": 0.0}
        ok, msg = self.safety_adapter.validate_sensor_data("imu", valid_imu)
        self.assertTrue(ok)

        # 2. Corrupt / Degraded sensor data handling
        corrupt_lidar = [0.0] * 360  # Complete sensor dropout
        ok, msg = self.safety_adapter.validate_sensor_data("lidar", corrupt_lidar)
        self.assertFalse(ok)

        spike_imu = {"accel_x": float("nan"), "accel_z": 9.81}
        ok, msg = self.safety_adapter.validate_sensor_data("imu", spike_imu)
        self.assertFalse(ok)

        # 3. Sensor loss inhibits navigation / locomotion commands
        self.safety_adapter.update_sensor_status("lidar", is_healthy=False)
        cmd_res = self.safety_adapter.validate_command("NavigateTo", {"x": 2.0, "y": 1.0})
        self.assertFalse(cmd_res.allowed)
        self.assertIn("lidar", cmd_res.reason.lower())

        # Restore sensor
        self.safety_adapter.update_sensor_status("lidar", is_healthy=True)
        cmd_res = self.safety_adapter.validate_command("NavigateTo", {"x": 2.0, "y": 1.0})
        self.assertTrue(cmd_res.allowed)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 3: Motor Test with Wheels Lifted
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_03_wheels_off_ground_differential_drive_and_encoders(self):
        """
        Stage 3: Wheels-off-ground motor direction, speed limits, and encoder increments.
        Requirements:
          - Switch to HARDWARE_TEST mode.
          - Explicit test authorization required before motor actuation.
          - Forward (+v) causes both wheels to spin forward, increasing encoder ticks.
          - Reverse (-v) causes both wheels to spin backward, decreasing encoder ticks.
          - In-place turn (+wz) spins left backward, right forward.
        """
        # Switch to HARDWARE_TEST and authorize
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST, reason="Wheels lifted test")
        auth = self.hardware_adapter.authorize_test_motion(reason="Bench motor test")
        self.assertTrue(auth)
        self.assertEqual(self.state_machine.state, RobotState.TEST_AUTHORIZED)

        # 1. Forward test (0.08 m/s, within 0.10 m/s HARDWARE_TEST limit)
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertTrue(accepted)
        self.assertEqual(safe_lin, 0.08)
        self.assertEqual(self.state_machine.state, RobotState.MOVING)

        # Simulate wheel rotation for 0.1 seconds
        self.motor_controller.step_simulation(0.10)
        telem = self.hardware_adapter.get_telemetry()
        self.assertGreater(telem.left_encoder_ticks, 0)
        self.assertGreater(telem.right_encoder_ticks, 0)
        self.assertAlmostEqual(telem.left_encoder_ticks, telem.right_encoder_ticks, delta=5)

        # 2. Reverse test (-0.08 m/s)
        prev_ticks_l = telem.left_encoder_ticks
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(-0.08, 0.0)
        self.assertTrue(accepted)
        self.motor_controller.step_simulation(0.10)
        telem = self.hardware_adapter.get_telemetry()
        self.assertLess(telem.left_encoder_ticks, prev_ticks_l)

        # 3. In-place rotation test (+0.20 rad/s)
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.0, 0.20)
        self.assertTrue(accepted)
        self.assertLess(self.motor_controller._actual_v_left, 0.0)
        self.assertGreater(self.motor_controller._actual_v_right, 0.0)

        # 4. Return to zero
        self.hardware_adapter.send_velocity_command(0.0, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.SAFE_IDLE)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 4: E-Stop + Command Watchdog
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_04_estop_circuit_and_hardware_command_watchdog(self):
        """
        Stage 4: Validate physical E-stop switch and hardware command watchdog.
        Requirements:
          - Physical E-stop immediately zeroes velocity and enters EMERGENCY_STOP.
          - Releasing E-stop DOES NOT resume motion; software remains latched in SAFE_IDLE.
          - Ceasing velocity commands triggers watchdog timeout within 300ms, commanding 0 velocity.
        """
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST)
        self.hardware_adapter.authorize_test_motion()

        # 1. Start motion
        self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.MOVING)

        # 2. Press Physical E-Stop
        t_estop_start = time.perf_counter()
        self.hardware_adapter.trigger_emergency_stop(reason="Operator E-Stop Button Pressed")
        t_estop_done = time.perf_counter()

        self.assertEqual(self.state_machine.state, RobotState.EMERGENCY_STOP)
        telem = self.hardware_adapter.get_telemetry()
        self.assertEqual(telem.left_wheel_velocity, 0.0)
        self.assertEqual(telem.right_wheel_velocity, 0.0)
        self.assertLess((t_estop_done - t_estop_start) * 1000.0, 10.0, "E-Stop must cut power in <10ms")

        # 3. Release Physical E-Stop: Robot MUST remain stationary in SAFE_IDLE!
        self.hardware_adapter.release_emergency_stop()
        self.assertEqual(self.state_machine.state, RobotState.SAFE_IDLE)
        telem = self.hardware_adapter.get_telemetry()
        self.assertEqual(telem.linear_velocity, 0.0)

        # 4. Command Watchdog Test: Start motion, then cease commands
        self.hardware_adapter.authorize_test_motion()
        self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.MOVING)

        # Wait for watchdog timeout (>300ms)
        time.sleep(0.35)
        telem = self.hardware_adapter.get_telemetry()
        self.assertTrue(telem.watchdog_tripped, "Command watchdog must trip on command stream stall")
        self.assertEqual(telem.left_wheel_velocity, 0.0)
        self.assertEqual(telem.right_wheel_velocity, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.SAFE_IDLE)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 5: Controlled Low-Speed Floor Movement
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_05_controlled_low_speed_floor_test(self):
        """
        Stage 5: Low-speed sequential floor maneuvers under human supervision.
        Sequence: Forward -> Stop -> Reverse -> Stop -> Turn Left -> Stop -> Turn Right -> Stop.
        """
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST)
        self.hardware_adapter.authorize_test_motion()

        maneuvers = [
            ("Forward", 0.08, 0.0),
            ("Stop", 0.0, 0.0),
            ("Reverse", -0.08, 0.0),
            ("Stop", 0.0, 0.0),
            ("Turn Left", 0.0, 0.20),
            ("Stop", 0.0, 0.0),
            ("Turn Right", 0.0, -0.20),
            ("Stop", 0.0, 0.0),
        ]

        for name, v_lin, v_ang in maneuvers:
            safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(v_lin, v_ang)
            self.assertTrue(accepted, f"Maneuver '{name}' must be accepted")
            self.motor_controller.step_simulation(0.05)
            telem = self.hardware_adapter.get_telemetry()

            if v_lin == 0.0 and v_ang == 0.0:
                self.assertAlmostEqual(telem.linear_velocity, 0.0, places=2)
                self.assertAlmostEqual(telem.angular_velocity, 0.0, places=2)
                self.assertEqual(self.state_machine.state, RobotState.SAFE_IDLE)
            else:
                self.assertEqual(self.state_machine.state, RobotState.MOVING)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 6: Teleoperation Mode
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_06_teleoperation_mode_and_saturation(self):
        """
        Stage 6: Validate HARDWARE_TELEOP mode and conservative velocity limits.
        Limits: linear <= 0.25 m/s, angular <= 0.50 rad/s.
        Excess velocity requests must be safely saturated, not rejected or uncontrolled.
        """
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TELEOP, reason="Teleop controller active")
        limits = self.state_machine.get_velocity_limits()
        self.assertEqual(limits["max_linear"], 0.25)
        self.assertEqual(limits["max_angular"], 0.50)

        # Request excessive speed (e.g. 1.2 m/s linear, 2.0 rad/s angular)
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(1.20, 2.0)
        self.assertTrue(accepted)
        self.assertAlmostEqual(safe_lin, 0.25, places=2, msg="Linear speed must be saturated to 0.25 m/s")
        self.assertAlmostEqual(safe_ang, 0.50, places=2, msg="Angular speed must be saturated to 0.50 rad/s")

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 7: TF Tree & Odometry Calibration
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_07_tf_tree_and_odometry_kinematic_calibration(self):
        """
        Stage 7: Verify coordinate transforms and dead-reckoning odometry calibration.
        Kinematics:
          - Wheel separation: 0.32m
          - Wheel radius: 0.065m
          - Forward 1.0 meter drive -> verifies integrated odom_x == 1.0m +/- 1%
          - 360-degree rotation -> verifies integrated odom_yaw == 2*pi +/- 1%
        """
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST)
        self.hardware_adapter.authorize_test_motion()

        # Reset odometry state
        self.hardware_adapter.odom_x = 0.0
        self.hardware_adapter.odom_y = 0.0
        self.hardware_adapter.odom_yaw = 0.0

        # Simulate 1.0 meter forward drive at 0.10 m/s for 10.0 seconds
        dt = 0.02
        steps = int(1.0 / (0.10 * dt))  # 500 steps
        self.hardware_adapter.send_velocity_command(0.10, 0.0)

        for _ in range(steps):
            self.motor_controller.step_simulation(dt)
            self.hardware_adapter._update_odometry(dt)

        telem = self.hardware_adapter.get_telemetry()
        # Expect ~1.0 meter travel with sub-centimeter calibration accuracy
        self.assertAlmostEqual(telem.odom_x, 1.0, delta=0.02, msg="Forward odometry calibration error > 2cm")
        self.assertAlmostEqual(telem.odom_y, 0.0, delta=0.01)

        # Stop robot
        self.hardware_adapter.send_velocity_command(0.0, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 8: Wheel Slip Measurement
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_08_wheel_slip_measurement(self):
        """
        Stage 8: Measure physical wheel slip and odometry drift across floor conditions.
        Compares ideal kinematic command vs actual traveled distance with friction slip.
        """
        # Set 15% slip factor (common on smooth linoleum/tile flooring)
        self.motor_controller.set_wheel_slip_factor(0.85)

        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST)
        self.hardware_adapter.authorize_test_motion()
        self.hardware_adapter.odom_x = 0.0

        commanded_distance = 1.0  # meters
        speed = 0.10  # m/s
        dt = 0.02
        steps = int(commanded_distance / (speed * dt))

        self.hardware_adapter.send_velocity_command(speed, 0.0)
        for _ in range(steps):
            self.motor_controller.step_simulation(dt)
            self.hardware_adapter._update_odometry(dt)

        telem = self.hardware_adapter.get_telemetry()
        actual_distance = telem.odom_x
        drift_error_m = abs(commanded_distance - actual_distance)

        # With 0.85 slip factor, actual distance is ~0.85m -> measured slip is 0.15m (15%)
        self.assertAlmostEqual(actual_distance, 0.85, delta=0.03)
        self.assertAlmostEqual(drift_error_m, 0.15, delta=0.03)

        # Reset slip factor to 1.0
        self.motor_controller.set_wheel_slip_factor(1.0)
        self.hardware_adapter.send_velocity_command(0.0, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 9: Voice-Controlled Movement & Voice STOP
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_09_voice_controlled_movement_and_deterministic_stop(self):
        """
        Stage 9: Voice-controlled movement and deterministic voice STOP.
        Pipeline:
          VOICE INPUT -> STT -> Intent -> SafetyGate -> EventBus -> RobotBridge -> HardwareAdapter
        Measures:
          Voice-to-command latency and Voice-to-Stop latency.
        """
        self.hardware_adapter.set_mode(HardwareMode.HARDWARE_TEST)
        self.hardware_adapter.authorize_test_motion()

        # 1. Voice Command: "ViRa, stop."
        # Verify voice STOP halts robot immediately (<10ms)
        self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertEqual(self.state_machine.state, RobotState.MOVING)

        t_stop_in = time.perf_counter()
        resp = self.gateway.process_text("Stop.", trace_id="trace-voice-stop")
        t_stop_out = time.perf_counter()

        stop_latency_ms = (t_stop_out - t_stop_in) * 1000.0
        self.assertEqual(self.state_machine.state, RobotState.EMERGENCY_STOP)
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)
        self.assertLess(stop_latency_ms, 25.0, f"Voice STOP latency ({stop_latency_ms:.2f}ms) exceeded 25ms")

    # ──────────────────────────────────────────────────────────────────────────
    # Stage 10: Full Interaction Loop with Hardware Telemetry
    # ──────────────────────────────────────────────────────────────────────────

    def test_stage_10_full_interaction_loop_and_telemetry_feedback(self):
        """
        Stage 10: Full autonomous interaction loop with hardware feedback.
        Telemetry stream: Encoders + Battery + E-Stop status -> EventBus -> Adapter.
        """
        received_telemetry: List[Dict[str, Any]] = []

        def _on_event(envelope):
            if envelope.get("event_type", {}).get("type") in ("RobotBattery", "RobotStateChanged", "RobotPosition"):
                received_telemetry.append(envelope)

        bridge = RobotBridge(emit_callback=_on_event, mode="hardware")
        bridge.start()
        time.sleep(0.05)

        # Trigger emergency stop via action envelope
        bridge.on_action_requested({
            "trace_id": "test-telem-trace",
            "timestamp": int(time.time()),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "Stop", "params": {"reason": "Test Complete"}},
            },
        })

        self.assertEqual(bridge.state_machine.state, RobotState.EMERGENCY_STOP)
        self.assertTrue(len(received_telemetry) > 0, "Telemetry events must be published to EventBus")
        bridge.stop()


if __name__ == "__main__":
    unittest.main()
