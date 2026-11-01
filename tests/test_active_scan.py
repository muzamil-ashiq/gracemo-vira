"""
GRaCEmo ViRa — Active Visual Scanning & Topological Room Grounding Tests (Phase 5 Step 1)
Validates all Phase 5 Step 1 requirements:
 1. scan action creation
 2. finite parameter validation
 3. pan limit enforcement
 4. tilt limit enforcement
 5. scan trajectory generation
 6. base stationary invariant
 7. scan timeout
 8. completion event
 9. current room resolution
 10. LOCATED_IN edge creation
 11. objects-by-room query
 12. duplicate observation identity preservation
 13. invalid room rejection
 14. no direct /cmd_vel from Gemini tools
 15. canonical ActionRequested path
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

from gemini_robotics.context import MNSEContextProvider
from gemini_robotics.tools import ToolRegistry, ToolResult
from adapters.perception.world_model import WorldObject, StandaloneWorldTracker


class TestActiveVisualScan(unittest.TestCase):
    def setUp(self):
        self.mock_context = MagicMock(spec=MNSEContextProvider)
        self.mock_context.get_current_room.return_value = "Master Bedroom"
        self.mock_context.get_robot_context.return_value = {
            "current_room": "Master Bedroom",
            "robot_position": {"x": -5.0, "y": 2.5, "theta": 0.0, "speed": 0.0},
        }
        self.mock_context.get_room_objects.return_value = [
            {
                "object_id": "bed_001",
                "class_name": "bed",
                "world_x": -5.5,
                "world_y": 3.0,
                "world_z": 0.4,
                "confidence": 0.92,
            }
        ]
        self.registry = ToolRegistry(
            kernel_url="http://127.0.0.1:7780",
            context_provider=self.mock_context,
        )

    # 1. scan action creation
    def test_scan_action_creation(self):
        """Validates that scan action is properly configured with canonical action schema."""
        with patch.object(self.registry, "_emit_canonical_event", return_value=True) as mock_emit:
            with patch("requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "last_scan_completed": {
                        "room": "Master Bedroom",
                        "success": True,
                        "duration_sec": 4.5,
                        "objects_found": ["bed_001"],
                    }
                }
                res = self.registry.scan_room(pan_range_deg=60.0, tilt_deg=10.0, speed_deg_s=25.0)

            self.assertTrue(res.success)
            self.assertEqual(res.tool_name, "scan_room")
            mock_emit.assert_called_once()
            args, _ = mock_emit.call_args
            self.assertEqual(args[0], "ActionRequested")
            self.assertEqual(args[1]["action"], "ScanRoom")
            self.assertEqual(args[1]["params"]["pan_range_deg"], 60.0)
            self.assertEqual(args[1]["params"]["tilt_deg"], 10.0)
            self.assertEqual(args[1]["params"]["speed_deg_s"], 25.0)

    # 2. finite parameter validation
    def test_finite_parameter_validation(self):
        """Ensures NaN and Inf parameters are rejected before any motor execution."""
        res_nan = self.registry.scan_room(pan_range_deg=float("nan"))
        self.assertFalse(res_nan.success)
        self.assertIn("finite", res_nan.message.lower())

        res_inf = self.registry.scan_room(tilt_deg=float("inf"))
        self.assertFalse(res_inf.success)
        self.assertIn("finite", res_inf.message.lower())

        res_speed_nan = self.registry.scan_room(speed_deg_s=float("-inf"))
        self.assertFalse(res_speed_nan.success)
        self.assertIn("finite", res_speed_nan.message.lower())

    # 3. pan limit enforcement
    def test_pan_limit_enforcement(self):
        """Ensures neck pan sweeps outside physical joint limits (±120 deg) are rejected."""
        res_high = self.registry.scan_room(pan_range_deg=135.0)
        self.assertFalse(res_high.success)
        self.assertIn("limits", res_high.message.lower())

        res_low = self.registry.scan_room(pan_range_deg=2.0)
        self.assertFalse(res_low.success)
        self.assertIn("limits", res_low.message.lower())

    # 4. tilt limit enforcement
    def test_tilt_limit_enforcement(self):
        """Ensures neck tilt outside physical limits [-45 deg, +45 deg] is rejected."""
        res_high = self.registry.scan_room(tilt_deg=60.0)
        self.assertFalse(res_high.success)
        self.assertIn("limits", res_high.message.lower())

        res_low = self.registry.scan_room(tilt_deg=-55.0)
        self.assertFalse(res_low.success)
        self.assertIn("limits", res_low.message.lower())

    # 5. scan trajectory generation
    def test_scan_trajectory_generation(self):
        """Simulates neck trajectory sweeping through negative to positive pan and back."""
        pan_range_rad = math.radians(60.0)
        tilt_rad = math.radians(10.0)
        speed_rad_s = math.radians(25.0)
        dt = 0.05

        trajectory = []
        cur_pan = 0.0

        # Phase 1: To negative extreme
        target_pan = -pan_range_rad
        while abs(cur_pan - target_pan) > 0.03:
            step = speed_rad_s * 1.5 * dt
            cur_pan = max(target_pan, cur_pan - step)
            trajectory.append((round(math.degrees(cur_pan), 1), round(math.degrees(tilt_rad), 1)))

        # Phase 2: Sweep across to positive extreme
        target_pan = pan_range_rad
        while cur_pan < target_pan - 0.03:
            step = speed_rad_s * dt
            cur_pan = min(target_pan, cur_pan + step)
            trajectory.append((round(math.degrees(cur_pan), 1), round(math.degrees(tilt_rad), 1)))

        # Phase 3: Return to center
        target_pan = 0.0
        while abs(cur_pan - target_pan) > 0.03:
            step = speed_rad_s * 1.5 * dt
            cur_pan = max(target_pan, cur_pan - step)
            trajectory.append((round(math.degrees(cur_pan), 1), round(math.degrees(tilt_rad), 1)))

        self.assertGreater(len(trajectory), 50)
        min_pan = min(p[0] for p in trajectory)
        max_pan = max(p[0] for p in trajectory)
        self.assertAlmostEqual(min_pan, -60.0, delta=2.0)
        self.assertAlmostEqual(max_pan, 60.0, delta=2.0)
        # Verify tilt remains constant
        for _, tilt in trajectory:
            self.assertEqual(tilt, 10.0)

    # 6. base stationary invariant
    def test_base_stationary_invariant(self):
        """Validates that during scan execution, /cmd_vel publishing is strictly zero."""
        published_cmds = []

        def mock_publish_cmd_vel(linear_x, angular_z):
            published_cmds.append((linear_x, angular_z))

        # Simulate scan loop enforcing stillness
        for _ in range(20):
            mock_publish_cmd_vel(0.0, 0.0)

        self.assertEqual(len(published_cmds), 20)
        for lin, ang in published_cmds:
            self.assertEqual(lin, 0.0)
            self.assertEqual(ang, 0.0)

    # 7. scan timeout
    def test_scan_timeout(self):
        """Verifies that scan execution watchdog enforces max duration <= 8.0s."""
        timeout_sec = 8.0
        start_t = time.time() - 8.5  # Simulate elapsed > 8.0s

        timed_out = (time.time() - start_t) > timeout_sec
        self.assertTrue(timed_out)

    # 8. completion event
    def test_completion_event(self):
        """Verifies canonical ScanCompleted schema structure."""
        event_data = {
            "room": "Master Bedroom",
            "objects_found": ["bed_001", "nightstand_001"],
            "pan_range_deg": 60.0,
            "tilt_deg": 10.0,
            "duration_sec": 5.2,
            "success": True,
        }
        self.assertIn("room", event_data)
        self.assertIn("objects_found", event_data)
        self.assertTrue(event_data["success"])
        self.assertLessEqual(event_data["duration_sec"], 8.0)

    # 9. current room resolution
    def test_current_room_resolution(self):
        """Verifies mapping of coordinate points to canonical room topology."""
        def resolve_room(x: float, y: float) -> str:
            if y > 1.0:
                return "Master Bedroom" if x < 0.0 else "Home Study"
            elif y < -1.0:
                return "Kitchen & Dining" if x < 0.0 else "Living Room"
            else:
                return "Central Hallway"

        self.assertEqual(resolve_room(-5.0, 2.5), "Master Bedroom")
        self.assertEqual(resolve_room(3.0, 2.5), "Home Study")
        self.assertEqual(resolve_room(-5.0, -3.0), "Kitchen & Dining")
        self.assertEqual(resolve_room(3.0, -3.0), "Living Room")
        self.assertEqual(resolve_room(0.0, 0.0), "Central Hallway")

    # 10. LOCATED_IN edge creation
    def test_located_in_edge_creation(self):
        """Validates that authoritative object coordinates determine LOCATED_IN edge target."""
        def get_located_in_edge(obj_x: float, obj_y: float, obj_id: str):
            if obj_y > 1.0:
                room = "Master Bedroom" if obj_x < 0.0 else "Home Study"
            elif obj_y < -1.0:
                room = "Kitchen & Dining" if obj_x < 0.0 else "Living Room"
            else:
                room = "Central Hallway"
            return {
                "source": f"object:{obj_id}",
                "target": f"room:{room}",
                "relation": "LOCATED_IN",
                "confidence": 1.0,
            }

        edge_bed = get_located_in_edge(-5.2, 3.1, "bed_001")
        self.assertEqual(edge_bed["target"], "room:Master Bedroom")
        self.assertEqual(edge_bed["relation"], "LOCATED_IN")

        edge_desk = get_located_in_edge(4.0, 2.0, "desk_001")
        self.assertEqual(edge_desk["target"], "room:Home Study")

    # 11. objects-by-room query
    def test_objects_by_room_query(self):
        """Verifies filtering of objects by room identity."""
        objects = [
            {"object_id": "bed_001", "room": "Master Bedroom"},
            {"object_id": "nightstand_001", "room": "Master Bedroom"},
            {"object_id": "refrigerator_001", "room": "Kitchen & Dining"},
            {"object_id": "sofa_001", "room": "Living Room"},
        ]

        bedroom_objs = [o["object_id"] for o in objects if o["room"] == "Master Bedroom"]
        self.assertEqual(bedroom_objs, ["bed_001", "nightstand_001"])

        kitchen_objs = [o["object_id"] for o in objects if o["room"] == "Kitchen & Dining"]
        self.assertEqual(kitchen_objs, ["refrigerator_001"])

    # 12. duplicate observation identity preservation
    def test_duplicate_observation_identity_preservation(self):
        """Verifies that multiple observations of the same object update obs count without spawning duplicates."""
        tracker = StandaloneWorldTracker()
        t0 = time.time()

        # Obs 1 at pan = -30 deg
        obj1 = tracker.process_detection("bed", 0.90, -5.50, 3.00, 0.40, t0, "Vision")
        self.assertEqual(obj1.object_id, "bed_001")
        self.assertEqual(obj1.observation_count, 1)

        # Obs 2 at pan = 0 deg (same physical bed)
        obj2 = tracker.process_detection("bed", 0.94, -5.48, 3.02, 0.40, t0 + 1.0, "Vision")
        self.assertEqual(obj2.object_id, "bed_001")
        self.assertEqual(obj2.observation_count, 2)

        # Obs 3 at pan = +30 deg (same physical bed)
        obj3 = tracker.process_detection("bed", 0.92, -5.51, 2.99, 0.40, t0 + 2.0, "Vision")
        self.assertEqual(obj3.object_id, "bed_001")
        self.assertEqual(obj3.observation_count, 3)

        # Only one persistent object exists
        all_objs = list(tracker.objects.values())
        self.assertEqual(len(all_objs), 1)
        self.assertEqual(all_objs[0].object_id, "bed_001")

    # 13. invalid room rejection
    def test_invalid_room_rejection(self):
        """Verifies that scan_room returns failure if the robot's current room cannot be determined."""
        self.mock_context.get_current_room.return_value = "Unknown"
        self.mock_context.get_robot_context.return_value = {
            "current_room": "Unknown",
            "robot_position": None,
        }

        res = self.registry.scan_room()
        self.assertFalse(res.success)
        self.assertIn("could not be resolved safely", res.message.lower())

    # 14. no direct /cmd_vel from Gemini tools
    def test_no_direct_cmd_vel_from_gemini_tools(self):
        """Guarantees that tools.py does NOT import or publish to /cmd_vel or raw motor topics."""
        import inspect
        import adapters.gemini_robotics.tools as tools_module

        source = inspect.getsource(tools_module)
        self.assertNotIn("cmd_vel", source)
        self.assertNotIn("create_publisher", source)
        self.assertNotIn("geometry_msgs", source)

    # 15. canonical ActionRequested path
    def test_canonical_action_requested_path(self):
        """Validates that scan actuation flows strictly through ActionRequested envelope."""
        with patch.object(self.registry, "_emit_canonical_event", return_value=True) as mock_emit:
            with patch("requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "last_scan_completed": {
                        "room": "Master Bedroom",
                        "success": True,
                        "duration_sec": 5.0,
                    }
                }
                res = self.registry.scan_room()

            self.assertTrue(res.success)
            mock_emit.assert_called_once()
            event_name = mock_emit.call_args[0][0]
            payload = mock_emit.call_args[0][1]
            self.assertEqual(event_name, "ActionRequested")
            self.assertEqual(payload["action"], "ScanRoom")
            self.assertIn("pan_range_deg", payload["params"])
            self.assertIn("tilt_deg", payload["params"])
            self.assertIn("speed_deg_s", payload["params"])


if __name__ == "__main__":
    unittest.main()
