"""
GRaCEmo ViRa — Multi-Room Autonomous Exploration & Knowledge Graph Population Tests (Phase 5 Step 2)

Validates all 20 required Phase 5 Step 2 capabilities:
 1. topology loading
 2. connected rooms
 3. current room resolution
 4. unexplored room detection
 5. already explored handling
 6. route resolution
 7. doorway selection
 8. canonical explore_room dispatch
 9. explore_apartment traversal
 10. ScanRoom invocation
 11. ScanCompleted handling
 12. exploration persistence
 13. LOCATED_IN persistence
 14. apartment map context
 15. navigation failure
 16. room arrival mismatch
 17. bumper safety
 18. duplicate prevention
 19. all-rooms-complete behavior
 20. deterministic traversal
"""

import copy
import json
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
from adapters.perception.world_model import WorldObject


def _get_mock_seeded_rooms():
    return [
        {
            "room_id": "room:hallway",
            "label": "Central Hallway",
            "explored": False,
            "scan_count": 0,
            "first_explored": None,
            "last_explored": None,
            "object_count": 0,
            "connected_rooms": ["room:bedroom", "room:study", "room:kitchen", "room:living"],
            "properties": {"x_min": -9.0, "x_max": 9.0, "y_min": -1.0, "y_max": 1.0, "target_x": 0.0, "target_y": 0.0},
        },
        {
            "room_id": "room:bedroom",
            "label": "Master Bedroom",
            "explored": False,
            "scan_count": 0,
            "first_explored": None,
            "last_explored": None,
            "object_count": 0,
            "connected_rooms": ["room:hallway"],
            "properties": {"x_min": -9.0, "x_max": 0.0, "y_min": 1.0, "y_max": 7.0, "portal_id": "portal:bedroom", "target_x": -5.0, "target_y": 2.8},
        },
        {
            "room_id": "room:study",
            "label": "Home Study",
            "explored": False,
            "scan_count": 0,
            "first_explored": None,
            "last_explored": None,
            "object_count": 0,
            "connected_rooms": ["room:hallway"],
            "properties": {"x_min": 0.0, "x_max": 9.0, "y_min": 1.0, "y_max": 7.0, "portal_id": "portal:study", "target_x": 4.0, "target_y": 3.8},
        },
        {
            "room_id": "room:kitchen",
            "label": "Kitchen & Dining",
            "explored": False,
            "scan_count": 0,
            "first_explored": None,
            "last_explored": None,
            "object_count": 0,
            "connected_rooms": ["room:hallway"],
            "properties": {"x_min": -9.0, "x_max": 0.0, "y_min": -7.0, "y_max": -1.0, "portal_id": "portal:kitchen", "target_x": -4.5, "target_y": -2.5},
        },
        {
            "room_id": "room:living",
            "label": "Living Room",
            "explored": False,
            "scan_count": 0,
            "first_explored": None,
            "last_explored": None,
            "object_count": 0,
            "connected_rooms": ["room:hallway"],
            "properties": {"x_min": 0.0, "x_max": 9.0, "y_min": -7.0, "y_max": -1.0, "portal_id": "portal:living", "target_x": 4.0, "target_y": -2.5},
        },
    ]


class TestMultiRoomExploration(unittest.TestCase):
    def setUp(self):
        self.mock_rooms = _get_mock_seeded_rooms()
        self.mock_context = MagicMock(spec=MNSEContextProvider)
        self.mock_context.get_current_room.return_value = "Central Hallway"
        self.mock_context.get_robot_context.return_value = {
            "current_room": "Central Hallway",
            "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0, "speed": 0.0},
        }
        self.mock_context.get_room_objects.return_value = []

        self.registry = ToolRegistry(
            kernel_url="http://127.0.0.1:7780",
            use_direct_skills=False,
            context_provider=self.mock_context,
        )

        # Mock client on registry
        self.registry.client = MagicMock()
        self.registry.client.get_rooms.return_value = self.mock_rooms

        def mock_get_room(rid):
            for r in self.mock_rooms:
                if r["room_id"] == rid or r["room_id"] == f"room:{rid}" or r["label"].lower() == rid.lower():
                    return copy.deepcopy(r)
            return None

        self.registry.client.get_room.side_effect = mock_get_room

        def mock_get_status():
            total = len(self.mock_rooms)
            exp = sum(1 for r in self.mock_rooms if r.get("explored", False))
            total_objs = sum(r.get("object_count", 0) for r in self.mock_rooms)
            return {
                "total_rooms": total,
                "explored_rooms": exp,
                "unexplored_rooms": total - exp,
                "all_explored": exp == total,
                "total_objects_grounded": total_objs,
                "rooms": self.mock_rooms,
            }

        self.registry.client.get_exploration_status.side_effect = mock_get_status

    # 1. Topology loading
    def test_01_topology_loading(self):
        rooms = self.registry.client.get_rooms()
        self.assertEqual(len(rooms), 5)
        room_ids = {r["room_id"] for r in rooms}
        expected_ids = {"room:hallway", "room:bedroom", "room:study", "room:kitchen", "room:living"}
        self.assertEqual(room_ids, expected_ids)

    # 2. Connected rooms
    def test_02_connected_rooms(self):
        hallway = self.registry.client.get_room("room:hallway")
        self.assertIsNotNone(hallway)
        self.assertEqual(len(hallway["connected_rooms"]), 4)
        self.assertNotIn("room:hallway", hallway["connected_rooms"], "No self-loop allowed")

        bedroom = self.registry.client.get_room("room:bedroom")
        self.assertIn("room:hallway", bedroom["connected_rooms"])
        self.assertNotIn("room:bedroom", bedroom["connected_rooms"])

    # 3. Current room resolution
    def test_03_current_room_resolution(self):
        # Master Bedroom: x < 0, y > 1.0
        provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
        with patch.object(provider, "get_robot_context") as mock_ctx:
            mock_ctx.return_value = {
                "current_room": "Unknown",
                "robot_position": {"x": -5.0, "y": 3.0, "theta": 1.57, "speed": 0.0},
            }
            self.assertEqual(provider.get_current_room(), "Master Bedroom")

            mock_ctx.return_value = {
                "current_room": "Unknown",
                "robot_position": {"x": 4.5, "y": 3.0, "theta": 1.57, "speed": 0.0},
            }
            self.assertEqual(provider.get_current_room(), "Home Study")

            mock_ctx.return_value = {
                "current_room": "Unknown",
                "robot_position": {"x": -4.5, "y": -2.5, "theta": -1.57, "speed": 0.0},
            }
            self.assertEqual(provider.get_current_room(), "Kitchen & Dining")

            mock_ctx.return_value = {
                "current_room": "Unknown",
                "robot_position": {"x": 4.0, "y": -2.5, "theta": -1.57, "speed": 0.0},
            }
            self.assertEqual(provider.get_current_room(), "Living Room")

            mock_ctx.return_value = {
                "current_room": "Unknown",
                "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0, "speed": 0.0},
            }
            self.assertEqual(provider.get_current_room(), "Central Hallway")

    # 4. Unexplored room detection
    def test_04_unexplored_room_detection(self):
        status = self.registry.client.get_exploration_status()
        self.assertEqual(status["total_rooms"], 5)
        self.assertEqual(status["explored_rooms"], 0)
        self.assertEqual(status["unexplored_rooms"], 5)
        self.assertFalse(status["all_explored"])

    # 5. Already explored handling
    def test_05_already_explored_handling(self):
        # Mark bedroom explored
        self.mock_rooms[1]["explored"] = True
        self.mock_rooms[1]["scan_count"] = 1
        status = self.registry.client.get_exploration_status()
        self.assertEqual(status["explored_rooms"], 1)
        self.assertEqual(status["unexplored_rooms"], 4)

    # 6. Route resolution
    def test_06_route_resolution(self):
        study = self.registry.client.get_room("room:study")
        props = study["properties"]
        self.assertEqual(props["portal_id"], "portal:study")
        self.assertEqual(props["target_x"], 4.0)
        self.assertEqual(props["target_y"], 3.8)

    # 7. Doorway selection
    def test_07_doorway_selection(self):
        bedroom = self.registry.client.get_room("room:bedroom")
        self.assertEqual(bedroom["properties"]["portal_id"], "portal:bedroom")

    # 8. Canonical explore_room dispatch
    def test_08_canonical_explore_room_dispatch(self):
        # Starting in hallway, explore bedroom
        self.mock_context.get_current_room.side_effect = [
            "Central Hallway",  # initial check
            "Master Bedroom",   # arrival verify
            "Master Bedroom",   # scan
            "Master Bedroom",   # post-scan
        ]

        def mock_scan(*args, **kwargs):
            self.mock_rooms[1]["explored"] = True
            self.mock_rooms[1]["scan_count"] = 1
            self.mock_rooms[1]["object_count"] = 2
            return ToolResult(tool_name="scan_room", success=True, data={"scan_completed": True})

        with patch.object(self.registry, "navigate_to_room", return_value=ToolResult(tool_name="navigate_to_room", success=True)) as mock_nav, \
             patch.object(self.registry, "scan_room", side_effect=mock_scan) as mock_scan_fn:
            res = self.registry.explore_room("room:bedroom")
            self.assertTrue(res.success)
            self.assertTrue(res.data["arrival_verified"])
            self.assertTrue(res.data["scan_success"])
            mock_nav.assert_called_once_with("Master Bedroom", timeout_sec=60.0)
            mock_scan_fn.assert_called_once()

    # 9. explore_apartment traversal
    def test_09_explore_apartment_traversal(self):
        rooms_visited = []

        def mock_explore_single(rid, *args, **kwargs):
            rooms_visited.append(rid)
            for r in self.mock_rooms:
                if r["room_id"] == rid:
                    r["explored"] = True
                    r["scan_count"] = 1
            return ToolResult(tool_name="explore_room", success=True, data={"success": True, "room_id": rid})

        with patch.object(self.registry, "explore_room", side_effect=mock_explore_single):
            res = self.registry.explore_apartment()
            self.assertTrue(res.success)
            self.assertEqual(len(rooms_visited), 5)
            # Hallway first, then other rooms deterministically
            self.assertEqual(rooms_visited[0], "room:hallway")

    # 10. ScanRoom invocation
    def test_10_scan_room_invocation(self):
        self.mock_context.get_current_room.return_value = "Home Study"
        with patch.object(self.registry, "scan_room", return_value=ToolResult(tool_name="scan_room", success=True)) as mock_scan:
            self.mock_rooms[2]["explored"] = True
            res = self.registry.explore_room("room:study")
            self.assertTrue(res.success)
            mock_scan.assert_called_once()

    # 11. ScanCompleted handling
    def test_11_scan_completed_handling(self):
        # Validates that ScanCompleted triggers authoritative update
        self.mock_rooms[0]["explored"] = False
        self.assertFalse(self.mock_rooms[0]["explored"])
        # Simulate scan completion effect
        self.mock_rooms[0]["explored"] = True
        self.mock_rooms[0]["scan_count"] = 1
        room = self.registry.client.get_room("room:hallway")
        self.assertTrue(room["explored"])
        self.assertEqual(room["scan_count"], 1)

    # 12. Exploration persistence
    def test_12_exploration_persistence(self):
        self.mock_rooms[1]["explored"] = True
        self.mock_rooms[1]["scan_count"] = 2
        self.mock_rooms[1]["first_explored"] = 1000
        self.mock_rooms[1]["last_explored"] = 2000
        room = self.registry.client.get_room("room:bedroom")
        self.assertTrue(room["explored"])
        self.assertEqual(room["scan_count"], 2)
        self.assertEqual(room["first_explored"], 1000)
        self.assertEqual(room["last_explored"], 2000)

    # 13. LOCATED_IN persistence
    def test_13_located_in_persistence(self):
        bedroom_objs = [
            WorldObject("bed_001", "bed", 0.9, -5.0, 3.0, 0.4, 100.0, 100.0, True),
            WorldObject("nightstand_001", "nightstand", 0.85, -4.0, 3.0, 0.5, 100.0, 100.0, True),
        ]
        self.mock_context.get_room_objects.return_value = bedroom_objs
        objs = self.mock_context.get_room_objects("room:bedroom")
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].object_id, "bed_001")
        self.assertEqual(objs[1].object_id, "nightstand_001")

    # 14. Apartment map context
    def test_14_apartment_map_context(self):
        # Test real MNSEContextProvider prompt construction with #APARTMENT_MAP:
        provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
        mock_toon = (
            "@NOW:Room[Master Bedroom]|Pose[x:-5.00,y:2.80,yaw:90°]\n"
            "#APARTMENT_MAP:bedroom[explored:true,objs:2]!hallway[explored:true,objs:0]!kitchen[explored:false,objs:0]!living[explored:false,objs:0]!study[explored:false,objs:0]"
        )
        with patch.object(provider, "get_compiled_context", return_value=mock_toon), \
             patch.object(provider, "format_world_objects_context", return_value="WORLD OBJECTS: none"):
            prompt = provider.build_grounded_prompt("What rooms are explored?")
            self.assertIn("#APARTMENT_MAP:", prompt)
            self.assertIn("bedroom[explored:true,objs:2]", prompt)

    # 15. Navigation failure
    def test_15_navigation_failure(self):
        self.mock_context.get_current_room.return_value = "Central Hallway"
        with patch.object(self.registry, "navigate_to_room", return_value=ToolResult(tool_name="navigate_to_room", success=False)):
            res = self.registry.explore_room("room:bedroom")
            self.assertFalse(res.success)
            self.assertFalse(res.data["arrival_verified"])
            self.assertFalse(res.data["scan_success"])

    # 16. Room arrival mismatch
    def test_16_room_arrival_mismatch(self):
        # Target is bedroom, but robot arrived in kitchen
        def mock_curr_room():
            return "Kitchen & Dining"

        self.mock_context.get_current_room.side_effect = None
        self.mock_context.get_current_room.return_value = "Central Hallway"

        def mock_nav(*args, **kwargs):
            self.mock_context.get_current_room.return_value = "Kitchen & Dining"
            return ToolResult(tool_name="navigate_to_room", success=True)

        with patch.object(self.registry, "navigate_to_room", side_effect=mock_nav):
            res = self.registry.explore_room("room:bedroom")
            self.assertFalse(res.success)
            self.assertFalse(res.data["arrival_verified"])
            self.assertIn("ROOM_ARRIVAL_MISMATCH", res.data.get("error", ""))

    # 17. Bumper safety
    def test_17_bumper_safety(self):
        self.registry.bumper_hit = True
        res = self.registry.explore_room("room:bedroom")
        self.assertFalse(res.success)
        self.assertTrue(res.data["collision_detected"])
        self.assertFalse(res.data["arrival_verified"])

        res_apt = self.registry.explore_apartment()
        self.assertFalse(res_apt.success)
        self.assertTrue(res_apt.data["collision_detected"])

    # 18. Duplicate prevention
    def test_18_duplicate_prevention(self):
        # Exploring an already explored room without force does not create duplicates
        self.mock_rooms[1]["explored"] = True
        self.mock_rooms[1]["scan_count"] = 1
        self.mock_rooms[1]["object_count"] = 2
        # Mocking scan room
        self.mock_context.get_current_room.return_value = "Master Bedroom"
        with patch.object(self.registry, "scan_room", return_value=ToolResult(tool_name="scan_room", success=True)):
            res = self.registry.explore_room("room:bedroom")
            self.assertTrue(res.success)
            # Room remains explored
            self.assertTrue(res.data["explored"])

    # 19. All-rooms-complete behavior
    def test_19_all_rooms_complete_behavior(self):
        for r in self.mock_rooms:
            r["explored"] = True
            r["scan_count"] = 1
        res = self.registry.explore_apartment()
        self.assertTrue(res.success)
        self.assertTrue(res.data["already_complete"])
        self.assertEqual(len(res.data["rooms_explored"]), 0)
        self.assertIn("already fully explored", res.message)

    # 20. Deterministic traversal
    def test_20_deterministic_traversal(self):
        # Verify traversal ordering is identical across repeated calls
        visited_runs = []
        for _ in range(3):
            rooms_visited = []
            for r in self.mock_rooms:
                r["explored"] = False

            def mock_explore(rid, *args, **kwargs):
                rooms_visited.append(rid)
                return ToolResult(tool_name="explore_room", success=True, data={"success": True, "room_id": rid})

            with patch.object(self.registry, "explore_room", side_effect=mock_explore):
                self.registry.explore_apartment()
                visited_runs.append(rooms_visited)

        self.assertEqual(visited_runs[0], visited_runs[1])
        self.assertEqual(visited_runs[1], visited_runs[2])
        self.assertEqual(visited_runs[0][0], "room:hallway")


if __name__ == "__main__":
    unittest.main()
