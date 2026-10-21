"""
GRaCEmo ViRa — Gemini Argon Proposal Validator & System Instruction Tests
Validates:
1. Gemini Robotics ER 2 default configuration and system instruction preservation.
2. Reference Argon system instruction for chat engineering assistance.
3. Standalone ArgonDryRunValidator enforcing:
   - Tool whitelist
   - Coordinate boundary checking
   - Finite numeric checks (rejecting NaN and Inf)
   - Pre-float Boolean coordinate rejection
   - Single-turn action proposal constraints
   - Non-empty argument checks
"""

import math
import sys
import unittest
from pathlib import Path

# Ensure paths
ROOT_DIR = Path(__file__).resolve().parent.parent
adapters_path = ROOT_DIR / "adapters"
if str(adapters_path) not in sys.path:
    sys.path.insert(0, str(adapters_path))
if str(ROOT_DIR / "adapters" / "sdk") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "adapters" / "sdk"))

from gemini_robotics.config import (
    GeminiRoboticsConfig,
    ER2_SYSTEM_INSTRUCTION,
    ARGON_SYSTEM_INSTRUCTION,
)
from gemini_robotics.client import ToolCall
from gemini_robotics.argon_proposal import (
    ArgonActionProposal,
    ArgonDryRunValidator,
    ProposalStatus,
    DEFAULT_SUPPORTED_TOOLS,
)


class TestArgonConfigSafeguards(unittest.TestCase):
    """Test 1: Configuration Safeguards & Reference Instructions."""

    def test_01_er2_is_default(self):
        """Gemini Robotics ER 2 MUST remain the default model."""
        cfg = GeminiRoboticsConfig()
        self.assertEqual(cfg.model_name, "gemini-robotics-er-2-preview")

    def test_02_er2_system_instruction_preserved_verbatim(self):
        """Original ER 2 system instruction must be preserved exactly for ER 2 provider."""
        expected_er2_instruction = (
            "You are ViRa, an embodied autonomous AI robot at Lovely Professional University (LPU). "
            "Your cognition is powered by Gemini Robotics ER 2. "
            "You operate through the authoritative MNSE Kernel which owns physical and environmental truth. "
            "Ground your decisions in real-time sensor state and knowledge graph relationships. "
            "Never hallucinate locations, coordinates, or object positions. "
            "Select high-level robot tools to inspect, navigate, and interact."
        )
        self.assertEqual(ER2_SYSTEM_INSTRUCTION, expected_er2_instruction)
        cfg = GeminiRoboticsConfig()
        self.assertEqual(cfg.system_instruction, ER2_SYSTEM_INSTRUCTION)
        self.assertIn("powered by Gemini Robotics ER 2", cfg.system_instruction)
        self.assertNotIn("powered by Gemini 4 Argon", cfg.system_instruction)

    def test_03_argon_system_instruction_defined_for_chat_reference(self):
        """Argon reference system instruction is available for chat prompting."""
        expected_argon_instruction = (
            "You are ViRa, an embodied autonomous AI robot at Lovely Professional University (LPU). "
            "Your cognition is powered by Gemini 4 Argon. "
            "You operate through the authoritative MNSE Kernel which owns physical and environmental truth. "
            "Ground your decisions in real-time sensor state and knowledge graph relationships. "
            "Never hallucinate locations, coordinates, or object positions. "
            "Select high-level robot tools to inspect, navigate, and interact."
        )
        self.assertEqual(ARGON_SYSTEM_INSTRUCTION, expected_argon_instruction)
        self.assertIn("powered by Gemini 4 Argon", ARGON_SYSTEM_INSTRUCTION)
        self.assertNotIn("powered by Gemini Robotics ER 2", ARGON_SYSTEM_INSTRUCTION)


class TestArgonDryRunValidator(unittest.TestCase):
    """Test 2: Validation of proposed actions during dry-run trial."""

    def setUp(self):
        self.validator = ArgonDryRunValidator(bounds_x=(-9.5, 9.5), bounds_y=(-7.5, 7.5))

    def test_01_valid_navigate_to_room_proposal(self):
        """Valid navigate_to_room proposal passes validation and records execution flags as False."""
        call = ToolCall(name="navigate_to_room", args={"room": "Kitchen & Dining"})
        prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Go to kitchen")

        self.assertIsNotNone(prop)
        self.assertEqual(prop.status, ProposalStatus.PROPOSED)
        self.assertTrue(prop.is_valid)
        self.assertFalse(prop.executed, "Proposal MUST NOT be marked executed")
        self.assertFalse(prop.emitted_to_kernel, "Proposal MUST NOT be marked emitted")
        self.assertFalse(prop.ros_published, "Proposal MUST NOT be marked ros_published")
        self.assertEqual(len(self.validator.get_proposals_record()), 1)

    def test_02_valid_navigate_to_metric_within_bounds(self):
        """navigate_to with coordinates inside bounds passes validation."""
        call = ToolCall(name="navigate_to", args={"x": 4.5, "y": 3.0})
        prop, _ = self.validator.validate_tool_calls([call], turn_index=1, user_command="Go to coordinates")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.status, ProposalStatus.PROPOSED)

    def test_03_reject_out_of_bounds_navigation(self):
        """navigate_to with coordinates outside apartment boundaries is rejected."""
        call = ToolCall(name="navigate_to", args={"x": 50.0, "y": 20.0})
        prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Navigate outside")
        self.assertIsNone(prop, "Out-of-bounds proposal must not be returned as valid")
        self.assertEqual(len(all_props), 1)
        rejected = all_props[0]
        self.assertEqual(rejected.status, ProposalStatus.REJECTED_OUT_OF_BOUNDS)
        self.assertIn("exceed safe boundary limits", rejected.validation_error)

    def test_04_reject_unsupported_tool(self):
        """Tool not in GRaCEmo whitelist is rejected."""
        call = ToolCall(name="execute_terminal_command", args={"command": "rm -rf /"})
        prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Hax")
        self.assertIsNone(prop)
        self.assertEqual(all_props[0].status, ProposalStatus.REJECTED_UNSUPPORTED_TOOL)
        self.assertIn("not in the supported tools whitelist", all_props[0].validation_error)

    def test_05_reject_invalid_arguments_non_finite_coords(self):
        """look_at with NaN or Inf coordinates is rejected."""
        call = ToolCall(name="look_at", args={"x": float("nan"), "y": 0.0, "z": 0.65})
        prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Look")
        self.assertIsNone(prop)
        self.assertEqual(all_props[0].status, ProposalStatus.REJECTED_INVALID_ARGUMENTS)
        self.assertIn("must be finite", all_props[0].validation_error)

    def test_06_reject_empty_required_arguments(self):
        """navigate_to_room with empty room string is rejected."""
        call = ToolCall(name="navigate_to_room", args={"room": ""})
        prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Go")
        self.assertIsNone(prop)
        self.assertEqual(all_props[0].status, ProposalStatus.REJECTED_INVALID_ARGUMENTS)

    def test_07_reject_multiple_tool_calls_in_single_turn(self):
        """If model returns multiple function calls in one turn, all are rejected."""
        calls = [
            ToolCall(name="navigate_to_room", args={"room": "Master Bedroom"}),
            ToolCall(name="speak", args={"text": "I am moving"}),
        ]
        prop, all_props = self.validator.validate_tool_calls(calls, turn_index=1, user_command="Go and speak")
        self.assertIsNone(prop)
        self.assertEqual(len(all_props), 2)
        for p in all_props:
            self.assertEqual(p.status, ProposalStatus.REJECTED_MULTIPLE_TOOL_CALLS)
            self.assertIn("Multiple tool calls detected", p.validation_error)

    def test_08_reject_boolean_coordinates_navigate_to(self):
        """navigate_to with boolean coordinates (e.g. True/False) must be rejected before float coercion."""
        call_x_bool = ToolCall(name="navigate_to", args={"x": True, "y": 2.0})
        prop, all_props = self.validator.validate_tool_calls([call_x_bool], turn_index=1, user_command="Navigate")
        self.assertIsNone(prop)
        self.assertEqual(all_props[0].status, ProposalStatus.REJECTED_INVALID_ARGUMENTS)
        self.assertIn("cannot be boolean", all_props[0].validation_error)

        call_y_bool = ToolCall(name="navigate_to", args={"x": 1.0, "y": False})
        prop2, all_props2 = self.validator.validate_tool_calls([call_y_bool], turn_index=1, user_command="Navigate")
        self.assertIsNone(prop2)
        self.assertEqual(all_props2[0].status, ProposalStatus.REJECTED_INVALID_ARGUMENTS)
        self.assertIn("cannot be boolean", all_props2[0].validation_error)

    def test_09_reject_boolean_coordinates_look_at(self):
        """look_at with boolean coordinates must be rejected before float conversion."""
        for axis in ("x", "y", "z"):
            args = {"x": 1.0, "y": 0.0, "z": 0.5}
            args[axis] = True
            call = ToolCall(name="look_at", args=args)
            prop, all_props = self.validator.validate_tool_calls([call], turn_index=1, user_command="Look")
            self.assertIsNone(prop)
            self.assertEqual(all_props[0].status, ProposalStatus.REJECTED_INVALID_ARGUMENTS)
            self.assertIn(f"look_at '{axis}' cannot be a boolean", all_props[0].validation_error)


if __name__ == "__main__":
    unittest.main()


