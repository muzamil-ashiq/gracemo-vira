"""
GRaCEmo ViRa — Gemini Robotics ER 2 Adapter Unit Tests
Validates configuration, context integration, client, tools, canonical event schemas,
and closed-loop reasoning without requiring live network or Gazebo simulation.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure paths
ROOT_DIR = Path(__file__).resolve().parent.parent
adapters_path = ROOT_DIR / "adapters"
if str(adapters_path) not in sys.path:
    sys.path.insert(0, str(adapters_path))
if str(ROOT_DIR / "adapters" / "sdk") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "adapters" / "sdk"))

from gemini_robotics.config import GeminiRoboticsConfig
from gemini_robotics.context import MNSEContextProvider
from gemini_robotics.client import GeminiRoboticsClient, GeminiResponse, ToolCall
from gemini_robotics.tools import ToolRegistry, ToolResult
from gemini_robotics.orchestrator import GeminiRoboticsOrchestrator


class TestGeminiRoboticsConfig(unittest.TestCase):
    def test_config_defaults(self):
        config = GeminiRoboticsConfig()
        self.assertEqual(config.model_name, "gemini-robotics-er-2-preview")
        self.assertEqual(config.temperature, 0.2)
        self.assertEqual(config.max_turns, 5)
        self.assertEqual(config.kernel_url, "http://127.0.0.1:7780")

    def test_secret_masking(self):
        config = GeminiRoboticsConfig(api_key="AIzaSyTestSecretKey123456")
        d = config.to_dict()
        self.assertNotIn("AIzaSyTestSecretKey123456", repr(config))
        self.assertTrue(d["api_key"].startswith("AIza..."))
        self.assertTrue(config.is_configured())


class TestMNSEContextProvider(unittest.TestCase):
    def setUp(self):
        self.provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")

    @patch("requests.get")
    def test_get_robot_context(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "online",
            "current_room": "Home Study",
            "robot_position": {"x": 4.0, "y": 3.5, "theta": 1.57, "speed": 0.0},
            "battery": {"level": 90, "charging": False},
        }
        mock_get.return_value = mock_resp

        ctx = self.provider.get_robot_context()
        self.assertEqual(ctx["current_room"], "Home Study")
        self.assertEqual(ctx["robot_position"]["x"], 4.0)

    @patch("requests.get")
    def test_get_compiled_context_toon(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "@NOW:Room[Master Bedroom]|Pose[x:-4.50,y:3.80]\n#GRAPH:desk[in:Master Bedroom,conf:0.95]"
        mock_get.return_value = mock_resp

        toon = self.provider.get_compiled_context(fmt="toon")
        self.assertIn("@NOW:Room[Master Bedroom]", toon)
        self.assertIn("#GRAPH:desk", toon)

    @patch("requests.get")
    def test_toon_reflects_updated_robot_state_consistency(self, mock_get):
        """Regression test: Proves that after robot position/room changes, compiled TOON reflects the new state."""
        # 1. State in Central Hallway
        def mock_dispatch(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            params = kwargs.get("params", {})
            if "snapshot" in url:
                resp.json.return_value = {
                    "status": "online",
                    "current_room": "Central Hallway",
                    "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0, "speed": 0.0},
                }
            elif "context" in url and params.get("format") == "toon":
                resp.text = "@NOW:Room[Central Hallway]|Pose[x:0.00,y:0.00,yaw:0°]"
            return resp

        mock_get.side_effect = mock_dispatch
        snap_initial = self.provider.get_robot_context()
        toon_initial = self.provider.get_compiled_context(fmt="toon")
        self.assertEqual(snap_initial["current_room"], "Central Hallway")
        self.assertIn("@NOW:Room[Central Hallway]", toon_initial)
        self.assertIn("Pose[x:0.00,y:0.00", toon_initial)

        # 2. Robot physically navigates to Kitchen & Dining
        def mock_dispatch_navigated(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            params = kwargs.get("params", {})
            if "snapshot" in url:
                resp.json.return_value = {
                    "status": "online",
                    "current_room": "Kitchen & Dining",
                    "robot_position": {"x": -4.66, "y": -2.20, "theta": -1.12, "speed": 0.0},
                }
            elif "context" in url and params.get("format") == "toon":
                resp.text = "@NOW:Room[Kitchen & Dining]|Pose[x:-4.66,y:-2.20,yaw:-64°]"
            return resp

        mock_get.side_effect = mock_dispatch_navigated
        snap_updated = self.provider.get_robot_context()
        toon_updated = self.provider.get_compiled_context(fmt="toon")

        # Both /snapshot and /context?format=toon must represent the same current robot state
        self.assertEqual(snap_updated["current_room"], "Kitchen & Dining")
        self.assertIn("@NOW:Room[Kitchen & Dining]", toon_updated)
        self.assertIn("Pose[x:-4.66,y:-2.20", toon_updated)
        self.assertNotIn("Room[Central Hallway]", toon_updated)

    @patch("requests.get")
    def test_query_object_location(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "found": True,
            "result": {"object": "coke", "location": "Kitchen & Dining", "confidence": 0.98}
        }
        mock_get.return_value = mock_resp

        res = self.provider.query_object_location("coke")
        self.assertIsNotNone(res)
        self.assertEqual(res["location"], "Kitchen & Dining")


class TestGeminiRoboticsClient(unittest.TestCase):
    def test_mock_mode_reasoning(self):
        client = GeminiRoboticsClient(mock_mode=True)
        resp = client.reason(
            prompt="Go to the kitchen",
            tools=[lambda: None]
        )
        # Mock mode detects 'kitchen' and synthesizes navigate_to_room tool call
        self.assertTrue(resp.has_function_calls or resp.text is not None)

    def test_injected_mock_responses(self):
        client = GeminiRoboticsClient(mock_mode=True)
        client.set_mock_responses([
            GeminiResponse(
                text="Planning to reach kitchen",
                function_calls=[ToolCall("navigate_to_room", {"room": "Kitchen & Dining"})]
            ),
            GeminiResponse(text="I have arrived in the kitchen.")
        ])

        r1 = client.reason("user command 1")
        self.assertEqual(r1.primary_tool_call.name, "navigate_to_room")
        self.assertEqual(r1.primary_tool_call.args["room"], "Kitchen & Dining")

        r2 = client.reason("user command 2")
        self.assertFalse(r2.has_function_calls)
        self.assertEqual(r2.text, "I have arrived in the kitchen.")


class TestToolRegistryAndCanonicalEvents(unittest.TestCase):
    def setUp(self):
        # Disable direct physical skills in unit test to avoid needing Gazebo
        self.registry = ToolRegistry(use_direct_skills=False)
        self.registry.context_provider.get_robot_context = MagicMock(return_value={
            "status": "online",
            "current_room": "Kitchen & Dining",
            "robot_position": {"x": -4.66, "y": -2.20, "theta": -1.12, "speed": 0.0},
        })

    def test_tool_registration(self):
        callables = self.registry.get_tool_callables()
        tool_names = [fn.__name__ for fn in callables]

        expected_tools = [
            "navigate_to_room",
            "navigate_to",
            "find_object",
            "pick_object",
            "verify_grasp",
            "place_object",
            "speak",
            "show_emotion",
            "stop",
            "get_robot_state",
            "get_world_state",
        ]
        for t in expected_tools:
            self.assertIn(t, tool_names, f"Tool '{t}' must be registered.")

    @patch("requests.post")
    def test_navigate_to_room_canonical_event(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.navigate_to_room("kitchen")
        self.assertTrue(result.success)
        self.assertEqual(result.data["room"], "Kitchen & Dining")

        # Verify emitted canonical event structure
        calls = mock_post.call_args_list
        action_call = None
        for c in calls:
            body = c.kwargs.get("json", {})
            if body.get("event_type", {}).get("type") == "ActionRequested":
                action_call = body
                break

        self.assertIsNotNone(action_call, "ActionRequested event must be emitted")
        self.assertIn("id", action_call)
        self.assertIn("timestamp", action_call)
        self.assertEqual(action_call["source"], "Brain")
        self.assertEqual(action_call["observed_by"], "gemini_robotics_er")
        self.assertIsNone(action_call["parent_event_id"])
        self.assertEqual(action_call["event_type"]["data"]["action"], "NavigateToRoom")
        self.assertEqual(action_call["event_type"]["data"]["params"]["room"], "Kitchen & Dining")

    @patch("requests.post")
    def test_stop_canonical_event(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.stop()
        self.assertTrue(result.success)

        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["event_type"]["type"], "ActionRequested")
        self.assertEqual(body["event_type"]["data"]["action"], "Stop")
        self.assertEqual(body["source"], "Brain")

    @patch("requests.post")
    def test_speak_canonical_event(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.registry.speak("Hello, welcome to LPU!")
        self.assertTrue(result.success)

        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["event_type"]["data"]["action"], "Speak")
        self.assertEqual(body["event_type"]["data"]["params"]["text"], "Hello, welcome to LPU!")


class TestGeminiRoboticsOrchestrator(unittest.TestCase):
    def test_closed_loop_kitchen_demo(self):
        # 1. Setup mock client with multi-turn sequence
        client = GeminiRoboticsClient(mock_mode=True)
        client.set_mock_responses([
            # Turn 1: Gemini decides to navigate to the Kitchen & Dining area
            GeminiResponse(
                text="I will guide you to the Kitchen & Dining area.",
                function_calls=[ToolCall("navigate_to_room", {"room": "Kitchen & Dining"})]
            ),
            # Turn 2: Gemini confirms arrival and finishes
            GeminiResponse(
                text="We have safely arrived at the Kitchen & Dining room. What would you like next?"
            )
        ])

        # 2. Setup mock context provider
        mock_context = MagicMock(spec=MNSEContextProvider)
        mock_context.build_grounded_prompt.return_value = "Prompt with grounded context"
        mock_context.get_compiled_context.return_value = "@NOW:Room[Kitchen & Dining]|Pose[x:3.80,y:3.60]"
        mock_context.get_robot_context.return_value = {
            "current_room": "Kitchen & Dining",
            "robot_position": {"x": -4.0, "y": -2.5, "theta": 0.0, "speed": 0.0},
        }

        # 3. Setup registry
        registry = ToolRegistry(use_direct_skills=False, context_provider=mock_context)

        orchestrator = GeminiRoboticsOrchestrator(
            client=client,
            context_provider=mock_context,
            registry=registry,
        )

        # 4. Run closed-loop mission
        result = orchestrator.run_task("Go to the kitchen.")

        self.assertTrue(result.success)
        self.assertEqual(result.turns_count, 2)
        self.assertEqual(result.actions_dispatched, ["navigate_to_room"])
        self.assertIn("arrived at the Kitchen", result.final_response)
        self.assertEqual(len(result.turns), 2)
        self.assertEqual(result.turns[0].tool_call.name, "navigate_to_room")

    def test_max_turns_safety_guardrail(self):
        # Setup client that constantly calls a tool
        config = GeminiRoboticsConfig(max_turns=3)
        client = GeminiRoboticsClient(mock_mode=True)
        client.set_mock_responses([
            GeminiResponse(function_calls=[ToolCall("get_robot_state", {})]),
            GeminiResponse(function_calls=[ToolCall("get_robot_state", {})]),
            GeminiResponse(function_calls=[ToolCall("get_robot_state", {})]),
            GeminiResponse(function_calls=[ToolCall("get_robot_state", {})]),
        ])

        mock_context = MagicMock(spec=MNSEContextProvider)
        mock_context.build_grounded_prompt.return_value = "prompt"
        mock_context.get_compiled_context.return_value = "@NOW:Room[Hallway]"

        registry = ToolRegistry(use_direct_skills=False)
        orchestrator = GeminiRoboticsOrchestrator(
            config=config,
            client=client,
            context_provider=mock_context,
            registry=registry,
        )

        result = orchestrator.run_task("Keep checking")
        self.assertEqual(result.turns_count, 3)
        self.assertIn("reached maximum reasoning limit of 3 turns", result.final_response)


class TestVisualPerceptionIntegration(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(kernel_url="http://127.0.0.1:7780", use_direct_skills=False)
        self.client = GeminiRoboticsClient(mock_mode=True)

    def test_inspect_visual_scene_tool(self):
        self.registry.context_provider.get_robot_context = MagicMock(return_value={"current_room": "Kitchen & Dining"})
        self.registry.context_provider.get_latest_camera_frame = MagicMock(return_value=b"\xff\xd8\xff\xe0")

        result = self.registry.inspect_visual_scene(focus="dining table")
        self.assertTrue(result.success)
        self.assertEqual(result.data["room"], "Kitchen & Dining")
        self.assertTrue(result.data["frame_available"])
        self.assertEqual(result.data["frame_size_bytes"], 4)
        self.assertEqual(result.data["focus"], "dining table")
        self.assertIn("Captured live visual camera frame", result.message)

    @patch("requests.post")
    def test_emit_object_detected_canonical_event(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok = self.registry.emit_object_detected(
            class_name="refrigerator",
            confidence=0.94,
            x=-1.5,
            y=-6.2,
            source="Vision",
        )
        self.assertTrue(ok)
        self.assertTrue(mock_post.called)
        envelope = mock_post.call_args.kwargs["json"]
        self.assertEqual(envelope["source"], "Vision")
        self.assertEqual(envelope["event_type"]["type"], "ObjectDetected")
        self.assertEqual(envelope["event_type"]["data"]["class_name"], "refrigerator")
        self.assertEqual(envelope["event_type"]["data"]["confidence"], 0.94)
        self.assertEqual(envelope["event_type"]["data"]["x"], -1.5)
        self.assertEqual(envelope["event_type"]["data"]["y"], -6.2)

    def test_multimodal_image_mock_reasoning(self):
        mock_image = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        resp = self.client.reason(
            prompt="What objects can you see in the kitchen?",
            image_bytes=mock_image,
        )
        self.assertIsNotNone(resp.text)
        self.assertTrue(resp.is_mock)
        self.assertIn("dining table", resp.text.lower())

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_bytes")
    def test_get_latest_camera_frame_provider(self, mock_read, mock_exists):
        mock_exists.return_value = True
        mock_read.return_value = b"test_frame_data"
        provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
        frame = provider.get_latest_camera_frame("/tmp/test.jpg")
        self.assertEqual(frame, b"test_frame_data")


if __name__ == "__main__":
    unittest.main()

