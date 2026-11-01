#!/usr/bin/env python3
"""
Contract tests for GRaCEmo ViRa.
Validates all emitted event envelopes and semantic robot commands against
the canonical JSON schemas in contracts/*.schema.json.
"""
import unittest
import sys
import json
from pathlib import Path

# Add workspace root and graceemo_interaction
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "graceemo_interaction"))

from core.event_bus import EventBusClient
from core.safety_gate import CommandValidator

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class TestContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.envelope_schema_path = ROOT / "contracts" / "event-envelope.schema.json"
        cls.command_schema_path = ROOT / "contracts" / "robot-command.schema.json"

        with open(cls.envelope_schema_path, "r", encoding="utf-8") as f:
            cls.envelope_schema = json.load(f)

        with open(cls.command_schema_path, "r", encoding="utf-8") as f:
            cls.command_schema = json.load(f)

    def test_canonical_envelope_compliance(self):
        bus = EventBusClient()
        envelope = bus.create_envelope(
            event_type="VoiceDetected",
            data={"transcription": "Take me to the Robotics Lab", "confidence": 0.95},
            trace_id="test-trace-12345",
        )

        # Standard field assertions
        self.assertIn("id", envelope)
        self.assertIn("trace_id", envelope)
        self.assertEqual(envelope["trace_id"], "test-trace-12345")
        self.assertIn("timestamp", envelope)
        self.assertIn("timestamp_iso", envelope)
        self.assertIn("source", envelope)
        self.assertIn("event_type", envelope)
        self.assertEqual(envelope["event_type"]["type"], "VoiceDetected")

        if HAS_JSONSCHEMA:
            jsonschema.validate(instance=envelope, schema=self.envelope_schema)

    def test_robot_command_schema_compliance(self):
        valid_commands = [
            {"action": "NavigateTo", "params": {"x": 2.5, "y": 2.0, "yaw": 1.57}},
            {"action": "NavigateToRoom", "params": {"room": "Robotics Research Lab"}},
            {"action": "Stop", "params": {"reason": "User stop command"}},
            {"action": "Express", "params": {"emotion": "happy"}},
            {"action": "Speak", "params": {"text": "Hello, welcome to LPU."}},
            {"action": "LookAt", "params": {"x": 1.5, "y": 0.5, "z": 0.75}},
        ]

        validator = CommandValidator()
        for cmd in valid_commands:
            v_res = validator.validate(cmd)
            self.assertTrue(v_res.valid, f"Validation failed for valid command: {cmd}")
            if HAS_JSONSCHEMA:
                jsonschema.validate(instance=cmd, schema=self.command_schema)

    def test_invalid_robot_command_rejection(self):
        invalid_commands = [
            {"action": "NavigateTo", "params": {}},  # Missing x, y
            {"action": "UnknownAction", "params": {}},
            {"action": "motor_forward", "params": {"speed": 1.0}},  # Rule 3 violation
        ]

        validator = CommandValidator()
        for cmd in invalid_commands:
            v_res = validator.validate(cmd)
            self.assertFalse(v_res.valid, f"Invalid command was incorrectly accepted: {cmd}")


if __name__ == "__main__":
    unittest.main()
