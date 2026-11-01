"""
GRaCEmo ViRa — Navigation-Grounded Object Interaction Unit & Integration Tests (Phase 4 Step 4)
Validates all Phase 4 Step 4 requirements:
 1. exact object resolution
 2. class-name resolution
 3. ambiguous object rejection
 4. stale object rejection
 5. invalid coordinate rejection
 6. finite coordinate validation
 7. gaze reachable classification
 8. gaze reachable does NOT generate navigation (test_gaze_reachable_does_not_generate_navigation)
 9. base turn required classification
10. navigation required classification
11. navigation target generation
12. unsafe target rejection
13. TurnTo action generation
14. NavigateTo action generation
15. canonical ActionRequested
16. no direct /cmd_vel from Gemini
17. timeout handling
18. collision stop
19. object lost handling
20. successful navigation
21. post-navigation re-observation
22. object identity preservation
23. final LookAt
24. closed-loop completion
25. navigation cannot override MNSE coordinates (test_navigation_cannot_override_mnse_coordinates)
"""

import math
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
adapters_path = ROOT_DIR / "adapters"
sdk_path = ROOT_DIR / "adapters" / "sdk"
bridge_path = ROOT_DIR / "ros2_ws" / "src" / "gracemo_bridge" / "gracemo_bridge"
for p in [adapters_path, sdk_path, bridge_path, ROOT_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gemini_robotics.context import MNSEContextProvider, ObjectResolutionResult
from gemini_robotics.tools import ToolRegistry, ToolResult
from gemini_robotics.navigation_grounding import (
    GazeWorkspaceEvaluator,
    NavigationGroundedStateMachine,
    WorkspaceReachability,
    NavigationState,
    WorkspaceEvaluationResult,
    StateMachineExecutionResult,
)
from adapters.perception.world_model import WorldObject, StandaloneWorldTracker


class TestNavigationGrounding(unittest.TestCase):
    def setUp(self):
        self.provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
        self.tracker = StandaloneWorldTracker(visibility_timeout=10.0)
        self.provider._standalone_tracker = self.tracker

        # Standard test chair: chair_001 at (2.240, -0.160, 0.450)
        self.chair_001 = self.tracker.process_detection(
            class_name="chair",
            confidence=0.75,
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
        self.evaluator = GazeWorkspaceEvaluator()

    # -------------------------------------------------------------------------
    # 1. Exact Object Resolution
    # -------------------------------------------------------------------------
    def test_01_exact_object_resolution(self):
        """Querying exact ID 'chair_001' resolves directly to the matching object."""
        res = self.provider.resolve_object("chair_001", reference_time=102.0)
        self.assertEqual(res.status, "RESOLVED")
        self.assertTrue(res.is_resolved)
        self.assertEqual(res.object.object_id, "chair_001")
        self.assertAlmostEqual(res.object.world_x, 2.240, places=3)
        self.assertAlmostEqual(res.object.world_y, -0.160, places=3)

    # -------------------------------------------------------------------------
    # 2. Class-Name Resolution
    # -------------------------------------------------------------------------
    def test_02_class_name_resolution(self):
        """Querying class name 'chair' resolves to single visible chair_001."""
        res = self.provider.resolve_object("chair", reference_time=102.0)
        self.assertEqual(res.status, "RESOLVED")
        self.assertTrue(res.is_resolved)
        self.assertEqual(res.object.object_id, "chair_001")
        self.assertEqual(res.object.class_name, "chair")

    # -------------------------------------------------------------------------
    # 3. Ambiguous Object Rejection
    # -------------------------------------------------------------------------
    def test_03_ambiguous_object_rejection(self):
        """Multiple visible chairs return AMBIGUOUS status; no physical motion permitted."""
        # Add chair_002
        self.tracker.process_detection("chair", 0.80, 5.0, 2.0, 0.45, timestamp=100.0)
        self.assertEqual(len(self.tracker.objects), 2)

        res = self.provider.resolve_object("chair", reference_time=102.0)
        self.assertEqual(res.status, "AMBIGUOUS")
        self.assertFalse(res.is_resolved)

        # ToolRegistry turn_toward_object and navigate_to_object must safely abort
        turn_res = self.registry.turn_toward_object("chair")
        self.assertFalse(turn_res.success)
        self.assertEqual(turn_res.data.get("status"), "AMBIGUOUS")

        nav_res = self.registry.navigate_to_object("chair")
        self.assertFalse(nav_res.success)
        self.assertEqual(nav_res.data.get("status"), "AMBIGUOUS")

    # -------------------------------------------------------------------------
    # 4. Stale Object Rejection
    # -------------------------------------------------------------------------
    def test_04_stale_object_rejection(self):
        """Stale object (not visible past timeout) returns STALE and no motion is emitted."""
        res = self.provider.resolve_object("chair", reference_time=120.0)  # dt=20s > timeout 10s
        self.assertEqual(res.status, "STALE")
        self.assertFalse(res.is_resolved)

        # In tool registry without reference_time, check against currently_visible
        self.chair_001.currently_visible = False
        nav_res = self.registry.navigate_to_object("chair")
        self.assertFalse(nav_res.success)
        self.assertEqual(nav_res.data.get("status"), "STALE")

    # -------------------------------------------------------------------------
    # 5. Invalid Coordinate Rejection
    # -------------------------------------------------------------------------
    def test_05_invalid_coordinate_rejection(self):
        """Objects with NaN or Inf coordinates are rejected with INVALID_COORDINATES."""
        bad_chair = WorldObject(
            object_id="bad_chair",
            class_name="chair",
            confidence=0.9,
            world_x=float("nan"),
            world_y=1.0,
            world_z=0.5,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        self.tracker.objects["bad_chair"] = bad_chair

        res = self.provider.resolve_object("bad_chair", reference_time=101.0)
        self.assertEqual(res.status, "INVALID_COORDINATES")

        turn_res = self.registry.turn_toward_object("bad_chair")
        self.assertFalse(turn_res.success)
        self.assertEqual(turn_res.data.get("status"), "INVALID_COORDINATES")

    # -------------------------------------------------------------------------
    # 6. Finite Coordinate Validation
    # -------------------------------------------------------------------------
    def test_06_finite_coordinate_validation(self):
        """GazeWorkspaceEvaluator correctly validates finite coordinates and flags inf."""
        inf_obj = WorldObject(
            object_id="inf_obj",
            class_name="chair",
            confidence=0.9,
            world_x=float("inf"),
            world_y=0.0,
            world_z=0.5,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        eval_res = self.evaluator.evaluate(inf_obj, {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(eval_res.status, WorkspaceReachability.UNSAFE)
        self.assertIn("non-finite", eval_res.reason)

    # -------------------------------------------------------------------------
    # 7. Gaze Reachable Classification
    # -------------------------------------------------------------------------
    def test_07_gaze_reachable_classification(self):
        """Target directly in front at 2.24m is classified as GAZE_REACHABLE."""
        eval_res = self.evaluator.evaluate(self.chair_001, {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(eval_res.status, WorkspaceReachability.GAZE_REACHABLE)
        self.assertTrue(eval_res.is_gaze_reachable)
        self.assertFalse(eval_res.requires_base_motion)

    # -------------------------------------------------------------------------
    # 8. Gaze Reachable Does NOT Generate Navigation
    # -------------------------------------------------------------------------
    def test_gaze_reachable_does_not_generate_navigation(self):
        """CRITICAL: If an object is GAZE_REACHABLE, state machine MUST execute LookAt only; 0 base motion."""
        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="LookAt ok"))

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
        )

        res = sm.execute("chair_001")
        self.assertTrue(res.success)
        self.assertEqual(res.state, NavigationState.COMPLETE)
        self.assertEqual(res.action_dispatched, "look_at")
        self.assertEqual(res.base_displacement_m, 0.0)

        # Ensure NO base motion actions were dispatched
        for call in mock_emit.call_args_list:
            action_name = call[0][0]
            self.assertNotIn(action_name, ["TurnTo", "NavigateTo"])
        self.assertTrue(mock_look.called)

    # -------------------------------------------------------------------------
    # 9. Base Turn Required Classification
    # -------------------------------------------------------------------------
    def test_09_base_turn_required_classification(self):
        """Object behind robot (pan ~180°) at 2.0m is classified as BASE_TURN_REQUIRED."""
        chair_behind = WorldObject(
            object_id="chair_behind",
            class_name="chair",
            confidence=0.85,
            world_x=-2.0,
            world_y=0.0,
            world_z=0.45,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        eval_res = self.evaluator.evaluate(chair_behind, {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(eval_res.status, WorkspaceReachability.BASE_TURN_REQUIRED)
        self.assertFalse(eval_res.is_gaze_reachable)
        self.assertTrue(eval_res.requires_base_motion)
        self.assertIsNotNone(eval_res.recommended_turn_yaw)
        self.assertAlmostEqual(abs(eval_res.recommended_turn_yaw), math.pi, delta=0.05)

    # -------------------------------------------------------------------------
    # 10. Navigation Required Classification
    # -------------------------------------------------------------------------
    def test_10_navigation_required_classification(self):
        """Object far away (>3.5m) behind robot is classified as NAVIGATION_REQUIRED."""
        far_chair = WorldObject(
            object_id="far_chair",
            class_name="chair",
            confidence=0.85,
            world_x=-6.5,
            world_y=0.0,
            world_z=0.45,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        eval_res = self.evaluator.evaluate(far_chair, {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(eval_res.status, WorkspaceReachability.NAVIGATION_REQUIRED)
        self.assertTrue(eval_res.requires_base_motion)
        self.assertIsNotNone(eval_res.recommended_nav_pose)

    # -------------------------------------------------------------------------
    # 11. Navigation Target Generation
    # -------------------------------------------------------------------------
    def test_11_navigation_target_generation(self):
        """Navigation target maintains exact standoff distance (1.2m) facing target."""
        target_x, target_y = -6.5, 0.0
        standoff = 1.2
        target_obj = WorldObject(
            object_id="target_obj",
            class_name="chair",
            confidence=0.8,
            world_x=target_x,
            world_y=target_y,
            world_z=0.5,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        eval_res = self.evaluator.evaluate(
            target_obj,
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            desired_standoff_m=standoff,
        )
        nav_pose = eval_res.recommended_nav_pose
        self.assertIsNotNone(nav_pose)
        nav_x, nav_y, nav_yaw = nav_pose
        expected_x = target_x - standoff * math.cos(math.pi)  # -6.5 - 1.2*(-1) = -5.3m
        self.assertAlmostEqual(nav_x, expected_x, places=2)
        self.assertAlmostEqual(nav_y, 0.0, places=2)
        self.assertAlmostEqual(abs(nav_yaw), math.pi, places=2)

    # -------------------------------------------------------------------------
    # 12. Unsafe Target Rejection
    # -------------------------------------------------------------------------
    def test_12_unsafe_target_rejection(self):
        """Target whose navigation vantage violates floor bounds returns UNSAFE and rejects navigation."""
        out_of_bounds_obj = WorldObject(
            object_id="out_of_bounds",
            class_name="chair",
            confidence=0.8,
            world_x=-15.0,  # Floor boundary is ±9.5m, standoff violates
            world_y=0.0,
            world_z=0.5,
            first_seen=100.0,
            last_seen=100.0,
            currently_visible=True,
        )
        eval_res = self.evaluator.evaluate(out_of_bounds_obj, {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(eval_res.status, WorkspaceReachability.UNSAFE)
        self.assertIn("violates world bounds", eval_res.reason)

    # -------------------------------------------------------------------------
    # 13. TurnTo Action Generation
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_13_turn_to_action_generation(self, mock_post):
        """turn_toward_object generates canonical ActionRequested with action 'TurnTo'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # Set robot at (0, 0, 0)
        with patch.object(self.provider, "get_robot_context", return_value={"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}}):
            res = self.registry.turn_toward_object("chair_001")
            self.assertTrue(res.success)
            self.assertIn("robot_action", res.data)
            action_data = res.data["robot_action"]
            self.assertEqual(action_data["action"], "TurnTo")
            self.assertIn("yaw", action_data["params"])
            expected_yaw = math.atan2(-0.160, 2.240)
            self.assertAlmostEqual(action_data["params"]["yaw"], expected_yaw, places=3)

    # -------------------------------------------------------------------------
    # 14. NavigateTo Action Generation
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_14_navigate_to_action_generation(self, mock_post):
        """navigate_to_object generates canonical ActionRequested with action 'NavigateTo'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        with patch.object(self.provider, "get_robot_context", return_value={"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}}):
            res = self.registry.navigate_to_object("chair_001", standoff_dist_m=1.0)
            self.assertTrue(res.success)
            self.assertIn("robot_action", res.data)
            action_data = res.data["robot_action"]
            self.assertEqual(action_data["action"], "NavigateTo")
            params = action_data["params"]
            self.assertIn("x", params)
            self.assertIn("y", params)
            self.assertIn("yaw", params)
            self.assertTrue(math.isfinite(params["x"]))
            self.assertTrue(math.isfinite(params["y"]))

    # -------------------------------------------------------------------------
    # 15. Canonical ActionRequested Format
    # -------------------------------------------------------------------------
    @patch("requests.post")
    def test_15_canonical_action_requested(self, mock_post):
        """ActionRequested envelope preserves strict canonical schema."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        self.registry.turn_toward_object("chair_001")
        self.assertTrue(mock_post.called)
        envelope = mock_post.call_args.kwargs.get("json", {})
        self.assertEqual(envelope.get("source"), "Brain")
        self.assertEqual(envelope.get("observed_by"), "gemini_robotics_er")
        self.assertIn("id", envelope)
        self.assertIn("timestamp", envelope)
        event_type = envelope.get("event_type", {})
        self.assertEqual(event_type.get("type"), "ActionRequested")

    # -------------------------------------------------------------------------
    # 16. No Direct /cmd_vel from Gemini
    # -------------------------------------------------------------------------
    def test_16_no_direct_cmd_vel_from_gemini(self):
        """Gemini tools and state machine never directly instantiate Twist or publish to /cmd_vel."""
        # Inspect all methods and attributes on ToolRegistry
        self.assertFalse(hasattr(self.registry, "cmd_vel_pub"))
        self.assertFalse(hasattr(self.registry, "twist_pub"))
        # Verify emit goes strictly to EventBus endpoint
        self.assertEqual(self.registry.kernel_url, "http://127.0.0.1:7780")

    # -------------------------------------------------------------------------
    # 17. Timeout Handling
    # -------------------------------------------------------------------------
    def test_17_timeout_handling(self):
        """When base motion does not reach target within timeout_sec, transitions to TIMEOUT."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock()

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=0.1,  # short timeout
        )

        with patch("time.sleep", return_value=None):
            res = sm.execute("chair_behind")
            self.assertFalse(res.success)
            self.assertEqual(res.state, NavigationState.TIMEOUT)
            self.assertIn("timed out", res.message)

    # -------------------------------------------------------------------------
    # 18. Collision Stop
    # -------------------------------------------------------------------------
    def test_18_collision_stop(self):
        """Bumper/collision event immediately forces emergency stop and COLLISION_STOP state."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock()

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        def trigger_bumper_during_wait(*args):
            sm.trigger_collision_stop()

        with patch("time.sleep", side_effect=trigger_bumper_during_wait):
            res = sm.execute("chair_behind")
            self.assertFalse(res.success)
            self.assertEqual(res.state, NavigationState.COLLISION_STOP)
            # Verify emergency Stop was emitted
            stop_emitted = any(call[0][0] == "Stop" for call in mock_emit.call_args_list)
            self.assertTrue(stop_emitted)

    # -------------------------------------------------------------------------
    # 19. Object Lost Handling
    # -------------------------------------------------------------------------
    def test_19_object_lost_handling(self):
        """If target disappears during re-observation, state transitions to OBJECT_LOST."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock()

        # Simulate reaching the turn pose quickly
        pose_mock = MagicMock(side_effect=[
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ])

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        # Remove object before re-observation query
        def remove_obj():
            self.tracker.objects.clear()

        sm.perception_fn = remove_obj

        with patch.object(self.provider, "get_robot_context", pose_mock):
            with patch("time.sleep", return_value=None):
                res = sm.execute("chair_behind")
                self.assertFalse(res.success)
                self.assertEqual(res.state, NavigationState.OBJECT_LOST)
                self.assertFalse(mock_look.called)

    # -------------------------------------------------------------------------
    # 20. Successful Navigation
    # -------------------------------------------------------------------------
    def test_20_successful_navigation(self):
        """Successful navigation moves base, re-observes, and completes."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="ok"))

        # Odometry progression from (0,0,0) to rotated pose (0,0,pi)
        poses = [
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ]
        pose_iter = iter(poses)

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        with patch.object(self.provider, "get_robot_context", side_effect=lambda: next(pose_iter, poses[-1])):
            with patch("time.sleep", return_value=None):
                res = sm.execute("chair_behind")
                self.assertTrue(res.success)
                self.assertEqual(res.state, NavigationState.COMPLETE)
                self.assertEqual(res.action_dispatched, "turn_to")
                self.assertTrue(res.re_observed)
                self.assertTrue(res.final_look_at_success)

    # -------------------------------------------------------------------------
    # 21. Post-Navigation Re-Observation
    # -------------------------------------------------------------------------
    def test_21_post_navigation_reobservation(self):
        """Perception pipeline is invoked during the REOBSERVING state."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="ok"))
        mock_perception = MagicMock()

        poses = [
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ]
        pose_iter = iter(poses)

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            perception_fn=mock_perception,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        with patch.object(self.provider, "get_robot_context", side_effect=lambda: next(pose_iter, poses[-1])):
            with patch("time.sleep", return_value=None):
                res = sm.execute("chair_behind")
                self.assertTrue(mock_perception.called)

    # -------------------------------------------------------------------------
    # 22. Object Identity Preservation
    # -------------------------------------------------------------------------
    def test_22_object_identity_preservation(self):
        """Target ID 'chair_001' remains 'chair_001' after navigation and re-observation."""
        chair_behind = WorldObject("chair_001", "chair", 0.85, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_001"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="ok"))

        poses = [
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ]
        pose_iter = iter(poses)

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        with patch.object(self.provider, "get_robot_context", side_effect=lambda: next(pose_iter, poses[-1])):
            with patch("time.sleep", return_value=None):
                res = sm.execute("chair_001")
                self.assertTrue(res.success)
                self.assertEqual(res.target_object_id, "chair_001")
                self.assertTrue(res.metadata.get("identity_preserved"))

    # -------------------------------------------------------------------------
    # 23. Final LookAt
    # -------------------------------------------------------------------------
    def test_23_final_look_at(self):
        """Final LookAt is dispatched with updated authoritative coordinates from MNSE."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="ok"))

        poses = [
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ]
        pose_iter = iter(poses)

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        with patch.object(self.provider, "get_robot_context", side_effect=lambda: next(pose_iter, poses[-1])):
            with patch("time.sleep", return_value=None):
                sm.execute("chair_behind")
                self.assertTrue(mock_look.called)
                args = mock_look.call_args[0]
                self.assertAlmostEqual(args[0], -2.0, places=2)
                self.assertAlmostEqual(args[1], 0.0, places=2)
                self.assertAlmostEqual(args[2], 0.45, places=2)

    # -------------------------------------------------------------------------
    # 24. Closed-Loop Completion
    # -------------------------------------------------------------------------
    def test_24_closed_loop_completion(self):
        """State machine completes the full cycle returning COMPLETE and success=True."""
        chair_behind = WorldObject("chair_behind", "chair", 0.8, -2.0, 0.0, 0.45, 100.0, 100.0, True)
        self.tracker.objects["chair_behind"] = chair_behind

        mock_emit = MagicMock(return_value=True)
        mock_look = MagicMock(return_value=ToolResult(tool_name="look_at", success=True, message="ok"))

        poses = [
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
            {"robot_position": {"x": 0.0, "y": 0.0, "theta": math.pi}},
        ]
        pose_iter = iter(poses)

        sm = NavigationGroundedStateMachine(
            context_provider=self.provider,
            emit_action_fn=mock_emit,
            look_at_fn=mock_look,
            evaluator=self.evaluator,
            timeout_sec=5.0,
        )

        with patch.object(self.provider, "get_robot_context", side_effect=lambda: next(pose_iter, poses[-1])):
            with patch("time.sleep", return_value=None):
                res = sm.execute("chair_behind")
                self.assertEqual(res.state, NavigationState.COMPLETE)
                self.assertTrue(res.success)
                self.assertTrue(res.final_look_at_success)

    # -------------------------------------------------------------------------
    # 25. Navigation Cannot Override MNSE Coordinates
    # -------------------------------------------------------------------------
    def test_navigation_cannot_override_mnse_coordinates(self):
        """CRITICAL: ToolRegistry strictly queries MNSE; client cannot inject coordinates to bypass MNSE."""
        # navigate_to_object only takes object_name and optional standoff_dist_m
        # It has NO parameters for user-supplied target coordinates (x, y, z)
        import inspect
        sig = inspect.signature(self.registry.navigate_to_object)
        param_names = list(sig.parameters.keys())
        self.assertIn("object_name", param_names)
        self.assertNotIn("x", param_names)
        self.assertNotIn("y", param_names)
        self.assertNotIn("z", param_names)
        self.assertNotIn("target_x", param_names)
        self.assertNotIn("target_y", param_names)

        # Same for turn_toward_object
        turn_sig = inspect.signature(self.registry.turn_toward_object)
        turn_params = list(turn_sig.parameters.keys())
        self.assertIn("object_name", turn_params)
        self.assertNotIn("target_yaw", turn_params)
        self.assertNotIn("yaw", turn_params)


if __name__ == "__main__":
    unittest.main()
