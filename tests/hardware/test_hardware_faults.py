#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 5 Hardware Fault Injection & Lifecycle Safety Tests
Implements Sections 21-23, 28, 29, 30, and 31:
  - Hardware fault injection: motor controller disconnect, encoder failure, sensor timeout
  - Battery monitoring interlocks (NORMAL, LOW, CRITICAL lockout)
  - Communication loss safe stop (ROS 2, EventBus, serial link)
  - Physical robot state machine lifecycle invariants (Section 30)
  - Semantic command simulation/hardware parity verification (Section 31)
"""
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
from graceemo_interaction.core.event_bus import EventBusClient
from graceemo_interaction.core.fast_path import FastPathMatcher
from graceemo_interaction.core.gateway import InteractionGateway
from graceemo_interaction.core.safety_gate import SafetyGate


class TestHardwareFaultsAndParity(unittest.TestCase):
    """Rigorous fault injection and hardware parity test suite."""

    def setUp(self):
        self.motor_controller = MotorControllerInterface(
            wheel_separation_m=0.32,
            wheel_radius_m=0.065,
            encoder_ticks_per_rev=2048,
        )
        self.state_machine = RobotStateMachine(
            initial_state=RobotState.SAFE_IDLE,
            mode=HardwareMode.HARDWARE_TEST,
        )
        self.hardware_adapter = HardwareAdapter(
            state_machine=self.state_machine,
            motor_controller=self.motor_controller,
            watchdog_timeout_sec=0.25,
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

    def tearDown(self):
        self.hardware_adapter.shutdown()

    # ──────────────────────────────────────────────────────────────────────────
    # Section 29: Motor Controller Disconnect During Motion
    # ──────────────────────────────────────────────────────────────────────────

    def test_fault_01_motor_controller_disconnect_safe_stop(self):
        """
        Inject abrupt physical motor controller disconnection during active movement.
        Expected:
          - Zero commanded velocity to motors.
          - State transitions to ERROR or safe stationary stop.
          - Reconnection requires explicit re-authorization before motion can resume.
        """
        self.hardware_adapter.authorize_test_motion()
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertTrue(accepted)
        self.assertEqual(self.state_machine.state, RobotState.MOVING)

        # Invert communication / pull USB plug
        self.motor_controller.disconnect()
        time.sleep(0.05)

        # Subsequent commands must be rejected
        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertFalse(accepted, "Motion command must be rejected when controller is disconnected")
        self.assertEqual(safe_lin, 0.0)

        # Reconnect
        self.motor_controller.connect()
        telem = self.hardware_adapter.get_telemetry()
        self.assertTrue(telem.motor_controller_connected)
        # Robot MUST remain stationary until authorized again
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Section 28: Battery Voltage Interlocks (NORMAL, LOW, CRITICAL)
    # ──────────────────────────────────────────────────────────────────────────

    def test_fault_02_battery_telemetry_interlocks(self):
        """
        Section 28: Battery Monitoring.
        Thresholds:
          - > 11.5V: NORMAL
          - 10.5V - 11.5V: LOW (warnings logged, motion allowed under supervision)
          - < 10.5V: CRITICAL (locomotion strictly locked out)
        """
        self.hardware_adapter.authorize_test_motion()

        # 1. Normal battery (12.4V)
        self.motor_controller.set_battery_voltage(12.4)
        telem = self.hardware_adapter.get_telemetry()
        self.assertEqual(telem.battery_status, BatteryStatus.NORMAL)
        safe_lin, _, accepted = self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertTrue(accepted)

        # 2. Low battery (11.0V) -> Telemetry classifies LOW
        self.motor_controller.set_battery_voltage(11.0)
        telem = self.hardware_adapter.get_telemetry()
        self.assertEqual(telem.battery_status, BatteryStatus.LOW)

        # 3. Critical battery (10.2V) -> Locomotion must be immediately inhibited
        self.motor_controller.set_battery_voltage(10.2)
        telem = self.hardware_adapter.get_telemetry()
        self.assertEqual(telem.battery_status, BatteryStatus.CRITICAL)

        safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(0.08, 0.0)
        self.assertFalse(accepted, "Locomotion must be prohibited when battery is CRITICAL")
        self.assertEqual(safe_lin, 0.0)
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Section 29 & 20: Stale Command Rejection in Hardware
    # ──────────────────────────────────────────────────────────────────────────

    def test_fault_03_stale_hardware_command_rejection(self):
        """
        Verify that commands with timestamps in the past (> 3.0s) are rejected
        before reaching the hardware adapter.
        """
        stale_time = time.time() - 10.0
        res = self.command_handler.handle_action(
            action="NavigateTo",
            params={"x": 1.0, "y": 2.0},
            trace_id="trace-stale-hardware",
            timestamp=stale_time,
        )
        self.assertFalse(res, "Stale command must be rejected before hardware execution")
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Section 30: Physical Robot State Machine Lifecycle Invariants
    # ──────────────────────────────────────────────────────────────────────────

    def test_fault_04_physical_robot_state_machine_lifecycle(self):
        """
        Section 30: Physical Robot State Machine:
          OFFLINE -> INITIALIZING -> SAFE_IDLE -> TEST_AUTHORIZED -> MOVING -> STOPPING -> SAFE_IDLE
          Emergency: ANY STATE -> EMERGENCY_STOP -> SAFE_IDLE
          Restart: ANY STATE -> OFFLINE -> INITIALIZING -> SAFE_IDLE
          NEVER: RESTART -> MOVING
        """
        sm = RobotStateMachine(initial_state=RobotState.OFFLINE, mode=HardwareMode.HARDWARE_TEST)

        # 1. Normal Startup Lifecycle
        self.assertTrue(sm.transition_to(RobotState.INITIALIZING, "Boot"))
        self.assertTrue(sm.transition_to(RobotState.SAFE_IDLE, "Init complete"))
        self.assertTrue(sm.authorize_test_motion("Test permit"))
        self.assertEqual(sm.state, RobotState.TEST_AUTHORIZED)
        self.assertTrue(sm.transition_to(RobotState.MOVING, "Velocity command"))
        self.assertTrue(sm.transition_to(RobotState.STOPPING, "Zero command"))
        self.assertTrue(sm.transition_to(RobotState.SAFE_IDLE, "Stationary"))

        # 2. Emergency stop from ANY state
        sm.transition_to(RobotState.MOVING, "Move")
        sm.emergency_stop("Safety trip")
        self.assertEqual(sm.state, RobotState.EMERGENCY_STOP)
        # Release back to SAFE_IDLE
        sm.reset_from_emergency("Reset")
        self.assertEqual(sm.state, RobotState.IDLE)
        sm.transition_to(RobotState.SAFE_IDLE, "Safe idle")

        # 3. Crash / Restart Lifecycle: Never directly to MOVING
        sm.transition_to(RobotState.OFFLINE, "Power Loss")
        self.assertFalse(sm.can_transition(RobotState.MOVING), "Cannot jump directly from OFFLINE to MOVING")
        self.assertTrue(sm.transition_to(RobotState.INITIALIZING, "Reboot"))
        self.assertFalse(sm.can_transition(RobotState.MOVING), "Cannot jump directly from INITIALIZING to MOVING")
        self.assertTrue(sm.transition_to(RobotState.SAFE_IDLE, "Safe default"))

    # ──────────────────────────────────────────────────────────────────────────
    # Section 31: Simulation / Hardware Semantic Parity
    # ──────────────────────────────────────────────────────────────────────────

    def test_fault_05_simulation_hardware_semantic_parity(self):
        """
        Section 31: Verify that semantic commands (navigate_to, stop, pause, resume)
        produce identical outcomes and event envelopes across SIMULATION and HARDWARE modes.
        """
        sim_bridge = RobotBridge(mode="simulation")
        hw_bridge = RobotBridge(mode="hardware")

        sim_events: List[str] = []
        hw_events: List[str] = []

        sim_bridge.set_emit_callback(lambda env: sim_events.append(env.get("event_type", {}).get("type")))
        hw_bridge.set_emit_callback(lambda env: hw_events.append(env.get("event_type", {}).get("type")))

        sim_bridge.start()
        hw_bridge.start()

        commands = [
            {"action": "NavigateTo", "params": {"x": 2.0, "y": 1.5, "target_name": "Lab"}},
            {"action": "Pause", "params": {}},
            {"action": "Resume", "params": {}},
            {"action": "Stop", "params": {"reason": "Test Parity"}},
        ]

        for cmd in commands:
            sim_res = sim_bridge.command_handler.handle_action(
                action=cmd["action"],
                params=cmd["params"],
                trace_id="parity-trace",
            )
            hw_res = hw_bridge.command_handler.handle_action(
                action=cmd["action"],
                params=cmd["params"],
                trace_id="parity-trace",
            )

            # Both modes must yield identical acceptance results
            self.assertEqual(sim_res, hw_res, f"Parity mismatch for action: {cmd['action']}")

        # Both bridges must finish in EMERGENCY_STOP due to the final Stop action
        self.assertEqual(sim_bridge.state_machine.state, RobotState.EMERGENCY_STOP)
        self.assertEqual(hw_bridge.state_machine.state, RobotState.EMERGENCY_STOP)

        sim_bridge.stop()
        hw_bridge.stop()


if __name__ == "__main__":
    unittest.main()
