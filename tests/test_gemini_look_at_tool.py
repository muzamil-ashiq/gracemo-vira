"""
GRaCEmo ViRa — Gemini Robotics ER 2 LookAt Tool Focused Tests
Validates Phase 3 Step 5:
1. look_at(2.0, 0.0, 0.65) generates canonical ActionRequested event.
2. look_at(1.4, 1.4, 0.65) contains exact coordinates x=1.4, y=1.4, z=0.65.
3. look_at(1.2, 0.0, 0.10) contains exact coordinates x=1.2, y=0.0, z=0.10.
4. Tool does NOT publish to /cmd_vel, /head/pan/cmd_pos, or /head/tilt/cmd_pos.
5. FunctionDeclaration exposes exactly x, y, z as required NUMBER parameters.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
adapters_path = ROOT_DIR / "adapters"
if str(adapters_path) not in sys.path:
    sys.path.insert(0, str(adapters_path))
if str(ROOT_DIR / "adapters" / "sdk") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "adapters" / "sdk"))

from gemini_robotics.tools import ToolRegistry, ToolResult


class TestGeminiLookAtTool(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(use_direct_skills=False)

    @patch("requests.post")
    def test_01_look_at_action_requested_generated(self, mock_post):
        """TEST 1: look_at(2.0, 0.0, 0.65) generates canonical ActionRequested event."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.look_at(2.0, 0.0, 0.65)

        # Structured ToolResult
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.tool_name, "look_at")
        self.assertTrue(result.success)
        self.assertIn("2.00, 0.00, 0.65", result.message)

        # Canonical envelope verification
        self.assertTrue(mock_post.called, "requests.post must be called to emit canonical event")
        envelope = mock_post.call_args.kwargs.get("json", {})
        self.assertEqual(envelope.get("source"), "Brain")
        self.assertEqual(envelope.get("observed_by"), "gemini_robotics_er")
        self.assertIn("id", envelope)
        self.assertIn("timestamp", envelope)

        event_type = envelope.get("event_type", {})
        self.assertEqual(event_type.get("type"), "ActionRequested")

        action_data = event_type.get("data", {})
        self.assertEqual(action_data.get("action"), "LookAt")
        self.assertEqual(action_data.get("params"), {"x": 2.0, "y": 0.0, "z": 0.65})

    @patch("requests.post")
    def test_02_look_at_coordinates_quadrant_1(self, mock_post):
        """TEST 2: look_at(1.4, 1.4, 0.65) canonical action contains x=1.4, y=1.4, z=0.65."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.look_at(1.4, 1.4, 0.65)
        self.assertTrue(result.success)

        envelope = mock_post.call_args.kwargs.get("json", {})
        action_data = envelope.get("event_type", {}).get("data", {})
        self.assertEqual(action_data.get("action"), "LookAt")

        params = action_data.get("params", {})
        self.assertEqual(params.get("x"), 1.4)
        self.assertEqual(params.get("y"), 1.4)
        self.assertEqual(params.get("z"), 0.65)

    @patch("requests.post")
    def test_03_look_at_coordinates_low_floor_target(self, mock_post):
        """TEST 3: look_at(1.2, 0.0, 0.10) canonical action contains correct coordinates."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.look_at(1.2, 0.0, 0.10)
        self.assertTrue(result.success)

        envelope = mock_post.call_args.kwargs.get("json", {})
        action_data = envelope.get("event_type", {}).get("data", {})
        self.assertEqual(action_data.get("action"), "LookAt")

        params = action_data.get("params", {})
        self.assertEqual(params.get("x"), 1.2)
        self.assertEqual(params.get("y"), 0.0)
        self.assertEqual(params.get("z"), 0.10)

    @patch("requests.post")
    def test_04_no_ros_or_gazebo_publishing_from_tool(self, mock_post):
        """
        TEST 4: Verify the tool itself does NOT publish /cmd_vel, /head/pan/cmd_pos,
        or /head/tilt/cmd_pos. The tool should only emit the canonical action.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        import gemini_robotics.tools as tools_module

        # Verify module imports do NOT contain ROS or Gazebo publishers
        module_source = Path(tools_module.__file__).read_text()
        forbidden_strings = [
            "/cmd_vel",
            "/head/pan/cmd_pos",
            "/head/tilt/cmd_pos",
            "cmd_vel",
            "create_publisher",
            "gz.transport",
            "gz_cmd_pub",
            "gz_pan_pub",
            "gz_tilt_pub",
        ]
        for forbidden in forbidden_strings:
            self.assertNotIn(
                forbidden,
                module_source,
                f"Tool layer must NOT contain reference to ROS/Gazebo control topic: '{forbidden}'"
            )

        # Verify executing tool only calls requests.post for /emit and nothing else
        result = self.registry.look_at(2.0, 0.0, 0.65)
        self.assertTrue(result.success)
        self.assertEqual(mock_post.call_count, 1)
        url_called = mock_post.call_args[0][0]
        self.assertTrue(url_called.endswith("/emit"))

    def test_05_function_declaration_schema(self):
        """
        TEST 5: Verify FunctionDeclaration exposes exactly: x, y, z and all three are required.
        """
        try:
            from google.genai import types
        except ImportError:
            self.skipTest("google.genai not installed in current environment")

        decls = self.registry.get_function_declarations()
        look_at_decls = [d for d in decls if getattr(d, "name", None) == "look_at"]
        self.assertEqual(len(look_at_decls), 1, "Exactly one 'look_at' FunctionDeclaration must exist")

        decl = look_at_decls[0]
        self.assertEqual(decl.name, "look_at")
        self.assertIn("Directs the robot's active head/camera gaze", decl.description)
        self.assertIn("without rotating the mobile base", decl.description)
        self.assertIn("±120 degrees", decl.description)
        self.assertIn("±45 degrees", decl.description)

        # Check properties
        params = decl.parameters
        self.assertIsNotNone(params)
        self.assertEqual(params.type, types.Type.OBJECT)

        properties = params.properties
        self.assertEqual(set(properties.keys()), {"x", "y", "z"}, "Properties must be exactly {x, y, z}")

        for param_name in ["x", "y", "z"]:
            prop = properties[param_name]
            self.assertEqual(prop.type, types.Type.NUMBER, f"Parameter '{param_name}' must be NUMBER")
            self.assertTrue(len(prop.description) > 0, f"Parameter '{param_name}' must have a description")

        # Check required fields
        self.assertEqual(set(params.required), {"x", "y", "z"}, "All three parameters x, y, z must be REQUIRED")


if __name__ == "__main__":
    unittest.main()
