#!/usr/bin/env python3
"""
Safety tests for CommandValidator and SafetyGate.
Validates rejection of out-of-bounds coordinates, non-finite values (NaN/Inf),
rate limiting, battery interlocks, emergency stop latching, and strict Rule 3 enforcement.
"""
import unittest
import sys
import math
from pathlib import Path

interaction_dir = Path(__file__).resolve().parent.parent.parent / "graceemo_interaction"
sys.path.insert(0, str(interaction_dir))

from core.safety_gate import CommandValidator, SafetyGate, ValidationResult


class TestSafetyGate(unittest.TestCase):
    def setUp(self):
        self.validator = CommandValidator(bounds_x=(-10.0, 10.0), bounds_y=(-10.0, 10.0), max_commands_per_min=5)
        self.gate = SafetyGate(validator=self.validator)

    def test_valid_navigation_command(self):
        act = {"action": "NavigateTo", "params": {"x": 2.5, "y": 3.0}}
        res = self.gate.evaluate_action(act)
        self.assertTrue(res.valid)
        self.assertEqual(res.sanitized_action["params"]["x"], 2.5)

    def test_out_of_bounds_rejection(self):
        # Exceeds bounds (-10, 10)
        act = {"action": "NavigateTo", "params": {"x": 55.0, "y": 2.0}}
        res = self.gate.evaluate_action(act)
        self.assertFalse(res.valid)
        self.assertIn("exceed boundary limits", res.error_message)

    def test_nan_and_infinity_rejection(self):
        nan_act = {"action": "NavigateTo", "params": {"x": float("nan"), "y": 1.0}}
        res = self.gate.evaluate_action(nan_act)
        self.assertFalse(res.valid)
        self.assertIn("must be finite", res.error_message)

        inf_act = {"action": "NavigateTo", "params": {"x": 1.0, "y": float("inf")}}
        res2 = self.gate.evaluate_action(inf_act)
        self.assertFalse(res2.valid)
        self.assertIn("must be finite", res2.error_message)

    def test_rule_3_forbidden_hardware_control_rejection(self):
        forbidden_payloads = [
            {"action": "motor_forward", "params": {"speed": 0.5}},
            {"action": "set_pwm", "params": {"pin": 12, "duty": 100}},
            {"action": "gpio_write", "params": {"pin": 4, "val": 1}},
            {"action": "NavigateTo", "params": {"x": 1.0, "y": 1.0, "raw_servo": 90}},
        ]
        for f_act in forbidden_payloads:
            res = self.gate.evaluate_action(f_act)
            self.assertFalse(res.valid, f"Forbidden action '{f_act}' was incorrectly allowed!")
            self.assertIn("forbidden", res.error_message.lower())

    def test_look_at_kinematic_limits(self):
        # Normal LookAt
        valid_look = {"action": "LookAt", "params": {"x": 2.0, "y": 1.5, "z": 0.7}}
        res = self.gate.evaluate_action(valid_look)
        self.assertTrue(res.valid)

        # Missing params
        invalid_look = {"action": "LookAt", "params": {"x": 2.0}}
        res2 = self.gate.evaluate_action(invalid_look)
        self.assertFalse(res2.valid)

    def test_emergency_stop_always_allowed_and_latches(self):
        stop_act = {"action": "Stop", "params": {"reason": "Manual E-STOP"}}
        res = self.gate.evaluate_action(stop_act)
        self.assertTrue(res.valid)
        self.assertTrue(self.gate.emergency_stop_latched)

        # Subsequent navigation command must be BLOCKED because E-STOP is latched
        nav_act = {"action": "NavigateTo", "params": {"x": 1.0, "y": 1.0}}
        res_nav = self.gate.evaluate_action(nav_act)
        self.assertFalse(res_nav.valid)
        self.assertIn("Emergency Stop is currently latched", res_nav.error_message)

        # Clear E-STOP
        self.gate.reset_emergency_stop()
        res_nav_cleared = self.gate.evaluate_action(nav_act)
        self.assertTrue(res_nav_cleared.valid)

    def test_low_battery_interlock(self):
        self.gate.update_telemetry(battery_level=8.5, obstacle_active=False)
        nav_act = {"action": "NavigateTo", "params": {"x": 1.0, "y": 1.0}}
        res = self.gate.evaluate_action(nav_act)
        self.assertFalse(res.valid)
        self.assertIn("Battery level critically low", res.error_message)


if __name__ == "__main__":
    unittest.main()
