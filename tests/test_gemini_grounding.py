"""
GRaCEmo ViRa — Phase 4 Step 3: Gemini Robotics ER 2 Object-Grounded Closed Loop Tests
Validates all Phase 4 Step 3 requirements:
1. Single chair resolution (class query -> chair_001).
2. Exact chair_001 resolution (ID query -> chair_001).
3. Multiple-chair ambiguity (chair_001, chair_002 -> AMBIGUOUS, no arbitrary selection).
4. Missing object (table -> NOT_FOUND, no fabricated coordinates).
5. Stale object rejection (currently_visible=False -> STALE).
6. NaN coordinate rejection.
7. Inf coordinate rejection.
8. Finite coordinate validation.
9. Authoritative coordinate usage (Gemini cannot override MNSE coordinates).
10. look_at_object action generation.
11. Canonical ActionRequested event emission.
12. No direct motor/cmd_vel publishing from Gemini adapters.
13. Closed-loop orchestrator verification (Observe -> Reason -> Act -> Re-Observe -> Complete).
14. Object identity preservation across re-observation.
15. Client mock reasoning cases A through F.
"""

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
adapters_path = ROOT_DIR / "adapters"
sdk_path = ROOT_DIR / "adapters" / "sdk"
for p in [adapters_path, sdk_path, ROOT_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gemini_robotics.context import MNSEContextProvider, ObjectResolutionResult
from gemini_robotics.tools import ToolRegistry, ToolResult
from gemini_robotics.client import GeminiRoboticsClient, GeminiResponse, ToolCall
from gemini_robotics.orchestrator import GeminiRoboticsOrchestrator, OrchestratorResult
from adapters.perception.world_model import WorldObject, StandaloneWorldTracker


class TestGeminiGrounding(unittest.TestCase):
    def setUp(self):
        self.provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
        self.tracker = StandaloneWorldTracker(visibility_timeout=10.0)
        self.provider._standalone_tracker = self.tracker

        # Standard test chair: chair_001 at (2.240, -0.160, 0.450)
        self.chair_001 = self.tracker.process_detection(
            class_name="chair",
            confidence=0.69,
            x=2.240,
            y=-0.160,
            z=0.450,
            timestamp=100.0,
        )

        self.registry = ToolRegistry(
            kernel_url="http://127.0.0.1:7780",
            use_direct_skills=False,
            context_provider=self.provider,
        )

    # -------------------------------------------------------------------------
    # 1. Single Chair Resolution
    # -------------------------------------------------------------------------
    def test_01_single_chair_resolution(self):
        """'Look at the chair' resolves to chair_001 with exact MNSE coordinates."""
        res = self.provider.resolve_object("chair", reference_time=102.0)
        self.assertEqual(res.status, "RESOLVED")
        self.assertTrue(res.is_resolved)
        self.assertIsNotNone(res.object)
        self.assertEqual(res.object.object_id, "chair_001")
        self.assertEqual(res.object.class_name, "chair")
        self.assertAlmostEqual(res.object.world_x, 2.240, places=3)
        self.assertAlmostEqual(res.object.world_y, -0.160, places=3)
        self.assertAlmostEqual(res.object.world_z, 0.450, places=3)

    # -------------------------------------------------------------------------
    # 2. Exact chair_001 Resolution
    # -------------------------------------------------------------------------
    def test_02_exact_chair_001_resolution(self):
        """'chair_001' directly resolves the exact object ID even if others exist."""
        # Add a second chair
        self.tracker.process_detection("chair", 0.75, 4.0, 1.0, 0.45, timestamp=100.0)
        self.assertEqual(len(self.tracker.objects), 2)

        res = self.provider.resolve_object("chair_001", reference_time=102.0)
        self.assertEqual(res.status, "RESOLVED")
        self.assertEqual(res.object.object_id, "chair_001")
        self.assertAlmostEqual(res.object.world_x, 2.240, places=3)

    # -------------------------------------------------------------------------
    # 3. Multiple-Chair Ambiguity
    # -------------------------------------------------------------------------
    def test_03_multiple_chair_ambiguity(self):
        """When 2 visible chairs exist, 'chair' query returns AMBIGUOUS (no arbitrary guess)."""
        # Add chair_002 (>0.5m away to create a separate object)
        self.tracker.process_detection("chair", 0.80, 5.0, 2.0, 0.45, timestamp=100.0)
        self.assertEqual(len(self.tracker.objects), 2)

        res = self.provider.resolve_object("chair", reference_time=102.0)
        self.assertEqual(res.status, "AMBIGUOUS")
        self.assertFalse(res.is_resolved)
        self.assertEqual(len(res.candidates), 2)
        cand_ids = [o.object_id for o in res.candidates]
        self.assertIn("chair_001", cand_ids)
        self.assertIn("chair_002", cand_ids)

        # ToolRegistry must fail safely
        tool_res = self.registry.look_at_object("chair")
        self.assertFalse(tool_res.success)
        self.assertIn("Multiple objects matching 'chair' found", tool_res.message)
        self.assertEqual(tool_res.data.get("status"), "AMBIGUOUS")

    # -------------------------------------------------------------------------
    # 4. Missing Object
    # -------------------------------------------------------------------------
    def test_04_missing_object(self):
        """Missing object (e.g. 'table') returns NOT_FOUND; no fabricated coordinates."""
        res = self.provider.resolve_object("table", reference_time=102.0)
        self.assertEqual(res.status, "NOT_FOUND")
        self.assertFalse(res.is_resolved)
        self.assertIsNone(res.object)

        tool_res = self.registry.look_at_object("table")
        self.assertFalse(tool_res.success)
        self.assertEqual(tool_res.data.get("status"), "NOT_FOUND")
        self.assertIn("not been sighted", tool_res.message)

    # -------------------------------------------------------------------------
    # 5. Stale Object Rejection
    # -------------------------------------------------------------------------
    def test_05_stale_object_rejection(self):
        """Objects older than visibility timeout (10.0s) return STALE for current action."""
        # Query at t=120.0 (20 seconds after t=100.0 observation)
        res = self.provider.resolve_object("chair", visible_only=True, reference_time=120.0)
        self.assertEqual(res.status, "STALE")
        self.assertFalse(res.is_resolved)

        tool_res = self.registry.look_at_object("chair")
        # In tool registry without reference_time, check against currently_visible
        self.chair_001.currently_visible = False
        tool_res_stale = self.registry.look_at_object("chair")
        self.assertFalse(tool_res_stale.success)
        self.assertEqual(tool_res_stale.data.get("status"), "STALE")

    # -------------------------------------------------------------------------
    # 6. NaN Coordinate Rejection
    # -------------------------------------------------------------------------
    def test_06_nan_coordinate_rejection(self):
        """Coordinates containing NaN must be rejected immediately without event emission."""
        res = self.registry.look_at(float("nan"), 0.0, 0.5)
        self.assertFalse(res.success)
        self.assertIn("finite numbers", res.message)

        res2 = self.registry.look_at(1.0, float("nan"), 0.5)
        self.assertFalse(res2.success)

        res3 = self.registry.look_at(1.0, 0.0, float("nan"))
        self.assertFalse(res3.success)

        # Object in MNSE with NaN coordinates
        self.chair_001.world_x = float("nan")
        resolve_res = self.provider.resolve_object("chair")
        self.assertEqual(resolve_res.status, "INVALID_COORDINATES")

        tool_res = self.registry.look_at_object("chair")
        self.assertFalse(tool_res.success)
        self.assertEqual(tool_res.data.get("status"), "INVALID_COORDINATES")

    # -------------------------------------------------------------------------
    # 7. Inf Coordinate Rejection
    # -------------------------------------------------------------------------
    def test_07_inf_coordinate_rejection(self):
        """Coordinates containing +Inf or -Inf must be rejected immediately."""
        res_pos = self.registry.look_at(float("inf"), 1.0, 0.5)
        self.assertFalse(res_pos.success)
        self.assertIn("finite numbers", res_pos.message)

        res_neg = self.registry.look_at(1.0, float("-inf"), 0.5)
        self.assertFalse(res_neg.success)

        self.chair_001.world_y = float("inf")
        resolve_res = self.provider.resolve_object("chair")
        self.assertEqual(resolve_res.status, "INVALID_COORDINATES")

        tool_res = self.registry.look_at_object("chair")
        self.assertFalse(tool_res.success)

    # -------------------------------------------------------------------------
    # 8. Finite Coordinate Validation
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_08_finite_coordinate_validation(self, mock_post):
        """Valid finite coordinates pass safety validation and emit ActionRequested."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = self.registry.look_at(2.240, -0.160, 0.450)
        self.assertTrue(res.success)
        self.assertEqual(res.data["target"]["x"], 2.240)
        self.assertEqual(res.data["target"]["y"], -0.160)
        self.assertEqual(res.data["target"]["z"], 0.450)
        self.assertTrue(mock_post.called)

    # -------------------------------------------------------------------------
    # 9. Authoritative Coordinate Usage (Zero Invention)
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_09_authoritative_coordinate_usage(self, mock_post):
        """Proves look_at_object uses MNSE coordinates strictly; cannot be overridden."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # Call look_at_object with semantic name 'chair'
        res = self.registry.look_at_object("chair")
        self.assertTrue(res.success)
        self.assertEqual(res.data["object_id"], "chair_001")

        # The emitted coordinates must match MNSE exactly: (2.240, -0.160, 0.450)
        envelope = mock_post.call_args.kwargs["json"]
        params = envelope["event_type"]["data"]["params"]
        self.assertAlmostEqual(params["x"], 2.240, places=3)
        self.assertAlmostEqual(params["y"], -0.160, places=3)
        self.assertAlmostEqual(params["z"], 0.450, places=3)

    # -------------------------------------------------------------------------
    # 10. look_at_object Action Generation
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_10_look_at_object_action_generation(self, mock_post):
        """look_at_object resolves object, formats message, and populates ToolResult."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = self.registry.look_at_object("chair")
        self.assertEqual(res.tool_name, "look_at_object")
        self.assertTrue(res.success)
        self.assertIn("Gazing at chair_001 (chair)", res.message)
        self.assertEqual(res.data["class_name"], "chair")
        self.assertEqual(res.data["confidence"], 0.69)
        self.assertEqual(res.data["observation_count"], 1)

    # -------------------------------------------------------------------------
    # 11. Canonical ActionRequested Event Envelope
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_11_canonical_action_requested_envelope(self, mock_post):
        """Validates exact canonical envelope schema of emitted ActionRequested."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        self.registry.look_at_object("chair")
        self.assertTrue(mock_post.called)
        envelope = mock_post.call_args.kwargs["json"]

        self.assertIn("id", envelope)
        self.assertIn("timestamp", envelope)
        self.assertEqual(envelope["source"], "Brain")
        self.assertEqual(envelope["observed_by"], "gemini_robotics_er")
        self.assertIsNone(envelope["parent_event_id"])
        self.assertEqual(envelope["event_type"]["type"], "ActionRequested")
        self.assertEqual(envelope["event_type"]["data"]["action"], "LookAt")
        self.assertEqual(envelope["event_type"]["data"]["params"], {
            "x": 2.240,
            "y": -0.160,
            "z": 0.450,
        })

    # -------------------------------------------------------------------------
    # 12. No Direct /cmd_vel Publishing from Gemini Adapter
    # -------------------------------------------------------------------------
    def test_12_no_direct_cmd_vel_publishing(self):
        """Verifies no Gemini adapter file publishes directly to /cmd_vel or ROS topics."""
        import gemini_robotics.tools as tools_mod
        import gemini_robotics.context as ctx_mod
        import gemini_robotics.client as client_mod
        import gemini_robotics.orchestrator as orch_mod

        forbidden_tokens = [
            "/cmd_vel",
            "cmd_vel",
            "create_publisher",
            "/head/pan/cmd_pos",
            "/head/tilt/cmd_pos",
            "gz.transport",
        ]

        for mod in [tools_mod, ctx_mod, client_mod, orch_mod]:
            src = Path(mod.__file__).read_text()
            for token in forbidden_tokens:
                self.assertNotIn(
                    token,
                    src,
                    f"Module '{mod.__name__}' must not contain direct motor topic reference '{token}'",
                )

    # -------------------------------------------------------------------------
    # 13. Closed-Loop Orchestrator Verification
    # -------------------------------------------------------------------------
    def test_13_closed_loop_verification(self):
        """Observe -> Reason -> Act -> Re-Observe -> Complete verified end-to-end."""
        # 1. Setup mock client for 2 turns:
        # Turn 1: Gemini decides to look_at_object("chair")
        # Turn 2: Gemini completes verbally
        client = GeminiRoboticsClient(mock_mode=True)
        client.set_mock_responses([
            GeminiResponse(
                text="I will look at the chair.",
                function_calls=[ToolCall("look_at_object", {"object_name": "chair"})],
            ),
            GeminiResponse(
                text="I am now looking directly at chair_001. Base remained stationary."
            ),
        ])

        # Mock robot context: base stays at (0.0, 0.0)
        self.provider.get_robot_context = MagicMock(return_value={
            "status": "online",
            "current_room": "Kitchen & Dining",
            "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0, "speed": 0.0},
        })

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            orchestrator = GeminiRoboticsOrchestrator(
                client=client,
                context_provider=self.provider,
                registry=self.registry,
            )

            result = orchestrator.run_task("Look at the chair.")

            self.assertTrue(result.success)
            self.assertTrue(result.verified)
            self.assertEqual(result.turns_count, 2)
            self.assertEqual(result.actions_dispatched, ["look_at_object"])
            self.assertLess(result.base_displacement_m, 0.01)
            self.assertIn("looking directly at chair_001", result.final_response)

    # -------------------------------------------------------------------------
    # 14. Object Identity Preservation Across Re-Observation
    # -------------------------------------------------------------------------
    def test_14_object_identity_preservation(self):
        """New observation within 0.5m updates chair_001 without changing object ID."""
        initial_id = self.chair_001.object_id
        initial_obs = self.chair_001.observation_count
        self.assertEqual(initial_id, "chair_001")
        self.assertEqual(initial_obs, 1)

        # Re-observation of chair at (2.250, -0.150, 0.450) -> delta = 0.014m (<0.5m)
        updated_obj = self.tracker.process_detection(
            class_name="chair",
            confidence=0.85,
            x=2.250,
            y=-0.150,
            z=0.450,
            timestamp=105.0,
        )

        self.assertEqual(updated_obj.object_id, initial_id, "Object ID must be strictly preserved!")
        self.assertEqual(updated_obj.observation_count, 2)
        self.assertEqual(updated_obj.last_seen, 105.0)
        self.assertEqual(updated_obj.first_seen, 100.0)

        # Position smoothed: 0.7 * 2.250 + 0.3 * 2.240 = 2.247
        self.assertAlmostEqual(updated_obj.world_x, 2.247, places=3)

    # -------------------------------------------------------------------------
    # 15. Client Mock Reasoning Cases (A through F)
    # -------------------------------------------------------------------------
    def test_15_mock_reasoning_cases_a_through_f(self):
        """Validates offline mock reasoning for all required specification cases."""
        client = GeminiRoboticsClient(mock_mode=True)
        tools = self.registry.get_tool_callables()

        # CASE A — Single visible chair
        prompt_a = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "- chair_001\n"
            "  class: chair\n"
            "  position: (2.240, -0.160, 0.450)\n"
            "  visible: true\n"
            "===========================================\n\n"
            'User Command: "Look at the chair."'
        )
        resp_a = client.reason(prompt_a, tools=tools)
        self.assertTrue(resp_a.has_function_calls)
        self.assertEqual(resp_a.primary_tool_call.name, "look_at_object")
        self.assertEqual(resp_a.primary_tool_call.args["object_name"], "chair")

        # CASE B — Multiple chairs (Ambiguity)
        prompt_b = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "- chair_001\n"
            "  class: chair\n"
            "  position: (2.240, -0.160, 0.450)\n"
            "  visible: true\n"
            "- chair_002\n"
            "  class: chair\n"
            "  position: (1.500, 0.800, 0.450)\n"
            "  visible: true\n"
            "===========================================\n\n"
            'User Command: "Look at the chair."'
        )
        resp_b = client.reason(prompt_b, tools=tools)
        self.assertFalse(resp_b.has_function_calls, "Ambiguity must NOT dispatch an arbitrary tool call")
        self.assertIn("Clarification required", resp_b.text)
        self.assertIn("chair_001", resp_b.text)
        self.assertIn("chair_002", resp_b.text)

        # CASE C — No chair (Missing)
        prompt_c = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "(None currently recorded in persistent world model)\n"
            "===========================================\n\n"
            'User Command: "Look at the chair."'
        )
        resp_c = client.reason(prompt_c, tools=tools)
        self.assertFalse(resp_c.has_function_calls)
        self.assertIn("Unresolved object", resp_c.text)

        # CASE D — Stale chair
        prompt_d = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "- chair_001\n"
            "  class: chair\n"
            "  position: (2.240, -0.160, 0.450)\n"
            "  visible: false\n"
            "===========================================\n\n"
            'User Command: "Look at the chair."'
        )
        resp_d = client.reason(prompt_d, tools=tools)
        self.assertFalse(resp_d.has_function_calls)
        self.assertIn("no longer currently visible", resp_d.text)

        # CASE E — Invalid coordinates (NaN)
        prompt_e = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "- chair_001\n"
            "  class: chair\n"
            "  position: (nan, -0.160, 0.450)\n"
            "  visible: true\n"
            "===========================================\n\n"
            'User Command: "Look at the chair."'
        )
        resp_e = client.reason(prompt_e, tools=tools)
        self.assertFalse(resp_e.has_function_calls)
        self.assertIn("invalid", resp_e.text.lower())

        # CASE F — Exact ID query
        prompt_f = (
            "=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            "WORLD OBJECTS:\n"
            "- chair_001\n"
            "  class: chair\n"
            "  position: (2.240, -0.160, 0.450)\n"
            "  visible: true\n"
            "- chair_002\n"
            "  class: chair\n"
            "  position: (1.500, 0.800, 0.450)\n"
            "  visible: true\n"
            "===========================================\n\n"
            'User Command: "Look at chair_001."'
        )
        resp_f = client.reason(prompt_f, tools=tools)
        self.assertTrue(resp_f.has_function_calls)
        self.assertEqual(resp_f.primary_tool_call.name, "look_at_object")
        self.assertEqual(resp_f.primary_tool_call.args["object_name"], "chair_001")


if __name__ == "__main__":
    unittest.main()
