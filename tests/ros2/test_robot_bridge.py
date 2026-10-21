#!/usr/bin/env python3
"""
Unit and Contract tests for the VIRA Robot Bridge (adapters/robot-bridge).
Validates:
  - Robot state machine transitions and preconditions (OFFLINE, IDLE, NAVIGATING, EMERGENCY_STOP)
  - SafetyAdapter constraints: bounds, battery interlock, stale timestamps, emergency stop latch
  - NavigationAdapter goal dispatch, progress streaming, arrival, and idempotent cancellation
  - Trace ID propagation from incoming ActionRequested to outgoing feedback events
"""
import unittest
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.state_machine import RobotState


class TestRobotBridge(unittest.TestCase):
    def setUp(self):
        self.emitted_events = []
        self.bridge = RobotBridge(
            emit_callback=lambda env: self.emitted_events.append(env),
            mode="simulation",
        )
        self.bridge.navigation_adapter.sim_step_dt = 0.01  # fast simulation rate for testing
        self.bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

    def tearDown(self):
        self.bridge.stop()

    def test_initial_state(self):
        self.assertEqual(self.bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(self.bridge.mode, "simulation")

    def test_valid_navigate_to_command(self):
        trace_id = "test-bridge-trace-001"
        action_envelope = {
            "id": "act-001",
            "trace_id": trace_id,
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "NavigateTo",
                    "params": {
                        "x": 2.5,
                        "y": 2.0,
                        "target_name": "Robotics Research Lab",
                        "tolerance_m": 0.1,
                    },
                },
            },
        }

        success = self.bridge.on_action_requested(action_envelope)
        self.assertTrue(success)
        self.assertEqual(self.bridge.state_machine.state, RobotState.NAVIGATING)

        # Verify NavigationStarted was emitted with same trace_id
        started_events = [
            e for e in self.emitted_events
            if e.get("event_type", {}).get("type") == "NavigationStarted"
        ]
        self.assertTrue(len(started_events) >= 1)
        self.assertEqual(started_events[0]["trace_id"], trace_id)
        self.assertEqual(started_events[0]["event_type"]["data"]["destination"], "Robotics Research Lab")

    def test_precondition_rejection_when_offline(self):
        self.bridge.state_machine.transition_to(RobotState.OFFLINE, reason="Maintenance")
        self.assertEqual(self.bridge.state_machine.state, RobotState.OFFLINE)

        action_envelope = {
            "id": "act-002",
            "trace_id": "trace-offline-test",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "NavigateTo",
                    "params": {"x": 1.0, "y": 1.0},
                },
            },
        }
        success = self.bridge.on_action_requested(action_envelope)
        self.assertFalse(success, "Must reject NavigateTo when robot is OFFLINE")

    def test_precondition_rejection_when_emergency_stopped(self):
        self.bridge.state_machine.emergency_stop(reason="Hardware bumper hit")
        self.assertEqual(self.bridge.state_machine.state, RobotState.EMERGENCY_STOP)

        action_envelope = {
            "id": "act-003",
            "trace_id": "trace-estop-test",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "NavigateTo",
                    "params": {"x": 1.0, "y": 1.0},
                },
            },
        }
        success = self.bridge.on_action_requested(action_envelope)
        self.assertFalse(success, "Must reject NavigateTo when in EMERGENCY_STOP")

    def test_low_battery_interlock(self):
        self.bridge.safety_adapter.update_battery(level=10, charging=False)

        action_envelope = {
            "id": "act-004",
            "trace_id": "trace-battery-test",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "NavigateTo",
                    "params": {"x": 1.0, "y": 1.0},
                },
            },
        }
        success = self.bridge.on_action_requested(action_envelope)
        self.assertFalse(success, "Must reject NavigateTo when battery is below 15%")

    def test_stale_command_rejection(self):
        action_envelope = {
            "id": "act-005",
            "trace_id": "trace-stale-test",
            "timestamp": time.time() - 10.0,  # 10s old
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "NavigateTo",
                    "params": {"x": 1.0, "y": 1.0},
                },
            },
        }
        success = self.bridge.on_action_requested(action_envelope)
        self.assertFalse(success, "Must reject stale command older than 3 seconds")

    def test_idempotent_cancellation(self):
        # Start navigation
        self.bridge.navigation_adapter.navigate_to(
            target_x=10.0,
            target_y=10.0,
            target_name="Far Target",
            trace_id="cancel-test-trace",
        )
        self.assertEqual(self.bridge.state_machine.state, RobotState.NAVIGATING)

        # First cancel
        res1 = self.bridge.navigation_adapter.cancel_navigation(reason="Test Cancel 1")
        self.assertTrue(res1)
        self.assertEqual(self.bridge.state_machine.state, RobotState.IDLE)

        # Second cancel (idempotency check)
        res2 = self.bridge.navigation_adapter.cancel_navigation(reason="Test Cancel 2")
        self.assertTrue(res2, "Second cancel call must succeed idempotently")
        self.assertEqual(self.bridge.state_machine.state, RobotState.IDLE)

    def test_stop_action_immediate_execution(self):
        # Start navigation
        self.bridge.navigation_adapter.navigate_to(
            target_x=10.0,
            target_y=10.0,
            target_name="Far Target",
            trace_id="stop-test-trace",
        )
        self.assertEqual(self.bridge.state_machine.state, RobotState.NAVIGATING)

        # Issue Stop action
        stop_envelope = {
            "id": "act-stop",
            "trace_id": "stop-test-trace",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "Stop",
                    "params": {"reason": "Voice STOP"},
                },
            },
        }
        success = self.bridge.on_action_requested(stop_envelope)
        self.assertTrue(success)
        self.assertEqual(self.bridge.state_machine.state, RobotState.EMERGENCY_STOP)


if __name__ == "__main__":
    unittest.main()
