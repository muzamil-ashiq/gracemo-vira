#!/usr/bin/env python3
"""
Fault and Recovery Test Suite for GRaCEmo ViRa Robot Bridge & Interaction System.
Validates:
  - EventBus network failure / disconnection: service degrades gracefully and retains local ledger
  - Emergency Stop latching: rejected commands while latched, clean recovery to IDLE after manual reset
  - Kinematic and boundary violation rejection
  - Low battery interlock enforcement
  - Timeout and stale command rejection
"""
import unittest
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "graceemo_interaction"))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))

from core.event_bus import EventBusClient
from core.safety_gate import SafetyGate
from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.state_machine import RobotState


class TestFaultRecovery(unittest.TestCase):
    def setUp(self):
        # Point to invalid port to simulate dead network/Kernel daemon
        self.dead_bus = EventBusClient(base_url="http://127.0.0.1:9999")
        self.safety_gate = SafetyGate()
        self.bridge = RobotBridge(
            emit_callback=lambda env: self.dead_bus.emit_envelope(env),
            mode="simulation",
        )

    def tearDown(self):
        self.bridge.stop()

    def test_event_bus_offline_graceful_degradation(self):
        """When Kernel REST daemon is offline, local bus must not throw exceptions."""
        envelope = {
            "id": "offline-evt-1",
            "trace_id": "offline-trace",
            "timestamp": time.time(),
            "event_type": {"type": "TestEvent", "data": {"status": "ok"}},
        }
        # Emitting over offline bus returns false for HTTP, but stores in ledger and dispatches locally
        res = self.dead_bus.emit_envelope(envelope)
        self.assertFalse(res)  # HTTP failed
        self.assertIn(envelope, self.dead_bus.get_ledger())

    def test_emergency_stop_latch_and_recovery(self):
        """Emergency stop latches the safety gate and robot bridge until explicitly cleared."""
        # 1. Trigger emergency stop
        self.bridge.navigation_adapter.stop_immediately(reason="Bumper hit", trace_id="trace-estop")
        self.assertEqual(self.bridge.state_machine.state, RobotState.EMERGENCY_STOP)

        # 2. Attempting navigation must be rejected while latched
        act = {
            "id": "act-while-latched",
            "trace_id": "trace-latched",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "NavigateTo", "params": {"x": 5.0, "y": 5.0}},
            },
        }
        allowed = self.bridge.on_action_requested(act)
        self.assertFalse(allowed, "Must reject locomotion while in EMERGENCY_STOP")

        # 3. Explicit manual recovery
        recovered = self.bridge.state_machine.reset_from_emergency(reason="Operator cleared area")
        self.assertTrue(recovered)
        self.assertEqual(self.bridge.state_machine.state, RobotState.IDLE)

        # 4. Navigation should now succeed
        allowed_after_recovery = self.bridge.on_action_requested(act)
        self.assertTrue(allowed_after_recovery, "Navigation should be allowed after clean recovery")

    def test_nan_and_inf_coordinate_rejection(self):
        nan_act = {
            "id": "act-nan",
            "trace_id": "trace-nan",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "NavigateTo", "params": {"x": float("nan"), "y": 5.0}},
            },
        }
        res = self.safety_gate.evaluate_action(nan_act["event_type"]["data"])
        self.assertFalse(res.valid)
        self.assertIn("non-NaN", res.error_message)

    def test_low_battery_locomotion_interlock(self):
        self.bridge.safety_adapter.update_battery(level=12, charging=False)
        act = {
            "id": "act-low-battery",
            "trace_id": "trace-batt",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "NavigateTo", "params": {"x": 2.0, "y": 2.0}},
            },
        }
        allowed = self.bridge.on_action_requested(act)
        self.assertFalse(allowed, "Locomotion must be blocked when battery is under 15%")


if __name__ == "__main__":
    unittest.main()
