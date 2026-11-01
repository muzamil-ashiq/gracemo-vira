"""
GRaCEmo ViRa — Phase 4 Step 2: Persistent World / Object Context in MNSE
Focused Unit & Integration Tests covering all 14 mandatory behavioral requirements:
1. ObjectDetected creates state
2. Nearby same-class detection associates
3. Distant same-class detection creates separate object
4. Observation count increments
5. last_seen updates
6. first_seen remains stable
7. stale object becomes invisible after >10s
8. stale object remains queryable
9. context JSON exposes objects
10. TOON exposes objects
11. nearest-object query works
12. multiple classes coexist
13. ambiguous association does not silently merge
14. backward-compatible ObjectDetected deserialization works
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))

from adapters.perception.world_model import (
    WorldObject,
    StandaloneWorldTracker,
    WorldModelClient,
    VISIBILITY_TIMEOUT_SEC,
    ASSOCIATION_DISTANCE_THRESHOLD,
    AMBIGUITY_THRESHOLD,
)
from adapters.perception.models import BoundingBox, Point3D, Detection
from gracemo_sdk import AdapterClient


class TestWorldModel(unittest.TestCase):
    """Test suite validating persistent 3D world/object context in MNSE."""

    def setUp(self):
        self.tracker = StandaloneWorldTracker(visibility_timeout=10.0)
        self.t0 = 1000.0  # Deterministic reference timestamp (no sleep)

    # -------------------------------------------------------------------------
    # TEST 1: ObjectDetected creates state
    # -------------------------------------------------------------------------
    def test_01_object_detected_creates_state(self):
        """Verify an initial ObjectDetected event creates a persistent world object record."""
        obj = self.tracker.process_detection(
            class_name="chair",
            confidence=0.67,
            x=2.18,
            y=0.19,
            z=0.52,
            timestamp=self.t0,
            source="Vision",
            frame_id="world",
            bbox=[100.0, 150.0, 200.0, 300.0],
            depth_m=2.18,
        )

        self.assertIsNotNone(obj)
        self.assertEqual(obj.object_id, "chair_001")
        self.assertEqual(obj.class_name, "chair")
        self.assertAlmostEqual(obj.confidence, 0.67, places=2)
        self.assertAlmostEqual(obj.world_x, 2.18, places=2)
        self.assertAlmostEqual(obj.world_y, 0.19, places=2)
        self.assertAlmostEqual(obj.world_z, 0.52, places=2)
        self.assertEqual(obj.position, (2.18, 0.19, 0.52))
        self.assertEqual(obj.first_seen, self.t0)
        self.assertEqual(obj.last_seen, self.t0)
        self.assertEqual(obj.observation_count, 1)
        self.assertTrue(obj.currently_visible)
        self.assertEqual(obj.source, "Vision")
        self.assertEqual(obj.frame_id, "world")
        self.assertEqual(obj.bbox, [100.0, 150.0, 200.0, 300.0])
        self.assertAlmostEqual(obj.depth_m, 2.18, places=2)

    # -------------------------------------------------------------------------
    # TEST 2: Nearby same-class detection associates
    # -------------------------------------------------------------------------
    def test_02_nearby_same_class_detection_associates(self):
        """Verify a repeated nearby detection of the same class (<= 0.5m) updates the same object."""
        # Initial observation
        self.tracker.process_detection(
            class_name="chair",
            confidence=0.67,
            x=2.18,
            y=0.19,
            z=0.52,
            timestamp=self.t0,
        )

        # Repeated nearby observation: distance = sqrt((2.20-2.18)^2 + (0.21-0.19)^2 + (0.51-0.52)^2) = 0.03m <= 0.5m
        updated_obj = self.tracker.process_detection(
            class_name="chair",
            confidence=0.85,
            x=2.20,
            y=0.21,
            z=0.51,
            timestamp=self.t0 + 1.0,
        )

        # Still exactly one chair in tracker
        all_chairs = self.tracker.get_objects_by_class("chair")
        self.assertEqual(len(all_chairs), 1, "Nearby detection must associate, not duplicate")
        self.assertEqual(updated_obj.object_id, "chair_001")

        # Position smoothed: 0.7 * 2.20 + 0.3 * 2.18 = 1.54 + 0.654 = 2.194
        expected_x = 0.7 * 2.20 + 0.3 * 2.18
        self.assertAlmostEqual(updated_obj.world_x, expected_x, places=3)
        self.assertAlmostEqual(updated_obj.confidence, 0.85, places=2)
        self.assertAlmostEqual(updated_obj.max_confidence, 0.85, places=2)

    # -------------------------------------------------------------------------
    # TEST 3: Distant same-class detection creates separate object
    # -------------------------------------------------------------------------
    def test_03_distant_same_class_detection_creates_separate_object(self):
        """Verify a detection of the same class > 0.5m away creates a separate object (chair_002)."""
        self.tracker.process_detection(
            class_name="chair",
            confidence=0.67,
            x=2.18,
            y=0.19,
            z=0.52,
            timestamp=self.t0,
        )

        # Distant chair: distance ~ 2.47m > 0.5m
        obj2 = self.tracker.process_detection(
            class_name="chair",
            confidence=0.72,
            x=4.50,
            y=1.00,
            z=0.50,
            timestamp=self.t0 + 2.0,
        )

        all_chairs = self.tracker.get_objects_by_class("chair")
        self.assertEqual(len(all_chairs), 2, "Distant detection must create separate object")
        self.assertEqual(obj2.object_id, "chair_002")
        self.assertEqual(all_chairs[0].object_id, "chair_001")
        self.assertEqual(all_chairs[1].object_id, "chair_002")

    # -------------------------------------------------------------------------
    # TEST 4: Observation count increments
    # -------------------------------------------------------------------------
    def test_04_observation_count_increments(self):
        """Verify observation_count increments with each matched detection."""
        obj = self.tracker.process_detection(
            class_name="table", confidence=0.80, x=0.0, y=1.0, z=0.0, timestamp=self.t0
        )
        self.assertEqual(obj.observation_count, 1)

        obj = self.tracker.process_detection(
            class_name="table", confidence=0.82, x=0.05, y=1.02, z=0.0, timestamp=self.t0 + 0.5
        )
        self.assertEqual(obj.observation_count, 2)

        obj = self.tracker.process_detection(
            class_name="table", confidence=0.84, x=0.02, y=0.98, z=0.0, timestamp=self.t0 + 1.0
        )
        self.assertEqual(obj.observation_count, 3)

    # -------------------------------------------------------------------------
    # TEST 5: last_seen updates
    # -------------------------------------------------------------------------
    def test_05_last_seen_updates(self):
        """Verify last_seen updates to the timestamp of the latest observation."""
        self.tracker.process_detection(
            class_name="bottle", confidence=0.90, x=1.0, y=1.0, z=0.8, timestamp=1000.0
        )
        obj = self.tracker.process_detection(
            class_name="bottle", confidence=0.91, x=1.02, y=1.01, z=0.8, timestamp=1005.5
        )
        self.assertEqual(obj.last_seen, 1005.5)

    # -------------------------------------------------------------------------
    # TEST 6: first_seen remains stable
    # -------------------------------------------------------------------------
    def test_06_first_seen_remains_stable(self):
        """Verify first_seen is preserved and does not change across repeated observations."""
        first_t = 1000.0
        self.tracker.process_detection(
            class_name="cup", confidence=0.70, x=1.5, y=-0.5, z=0.9, timestamp=first_t
        )
        obj = self.tracker.process_detection(
            class_name="cup", confidence=0.75, x=1.52, y=-0.48, z=0.9, timestamp=1010.0
        )
        self.assertEqual(obj.first_seen, first_t)
        self.assertEqual(obj.last_seen, 1010.0)

    # -------------------------------------------------------------------------
    # TEST 7: Stale object becomes invisible after >10s
    # -------------------------------------------------------------------------
    def test_07_stale_object_becomes_invisible_after_timeout(self):
        """Verify object transitions currently_visible from True to False when time > 10.0s."""
        obj = self.tracker.process_detection(
            class_name="laptop", confidence=0.88, x=-2.0, y=1.5, z=0.75, timestamp=1000.0
        )
        self.assertTrue(obj.is_visible_at(current_time=1005.0, timeout_sec=10.0))
        self.assertTrue(obj.is_visible_at(current_time=1010.0, timeout_sec=10.0))  # At boundary: still visible
        self.assertFalse(obj.is_visible_at(current_time=1010.1, timeout_sec=10.0))  # After 10s: invisible

        # Query visible objects at t=1015.0
        visible_objs = self.tracker.get_visible_objects(reference_time=1015.0)
        self.assertEqual(len(visible_objs), 0, "Stale object must not be marked currently_visible")

    # -------------------------------------------------------------------------
    # TEST 8: Stale object remains queryable
    # -------------------------------------------------------------------------
    def test_08_stale_object_remains_queryable(self):
        """Verify historical objects are NOT deleted when visibility expires; remain fully queryable."""
        self.tracker.process_detection(
            class_name="laptop", confidence=0.88, x=-2.0, y=1.5, z=0.75, timestamp=1000.0
        )
        # Evaluate 50 seconds later
        all_objs = self.tracker.get_objects(visible_only=False, reference_time=1050.0)
        self.assertEqual(len(all_objs), 1, "Historical object must never be deleted")
        self.assertEqual(all_objs[0].object_id, "laptop_001")
        self.assertFalse(all_objs[0].currently_visible)

        # Specific lookup by ID succeeds
        historical = self.tracker.get_object_by_id("laptop_001")
        self.assertIsNotNone(historical)
        self.assertEqual(historical.class_name, "laptop")

    # -------------------------------------------------------------------------
    # TEST 9: Context JSON exposes objects
    # -------------------------------------------------------------------------
    def test_09_context_json_exposes_objects(self):
        """Verify serialized world object dictionaries match the required context JSON schema."""
        obj = self.tracker.process_detection(
            class_name="chair",
            confidence=0.67,
            x=2.18,
            y=0.19,
            z=0.52,
            timestamp=1000.0,
            source="Vision",
            frame_id="world",
            bbox=[10.0, 20.0, 30.0, 40.0],
            depth_m=2.18,
        )
        d = obj.to_dict()
        self.assertEqual(d["object_id"], "chair_001")
        self.assertEqual(d["class_name"], "chair")
        self.assertEqual(d["position"], [2.18, 0.19, 0.52])
        self.assertEqual(d["confidence"], 0.67)
        self.assertEqual(d["first_seen"], 1000.0)
        self.assertEqual(d["last_seen"], 1000.0)
        self.assertEqual(d["observation_count"], 1)
        self.assertTrue(d["currently_visible"])
        self.assertEqual(d["source"], "Vision")
        self.assertEqual(d["frame_id"], "world")
        self.assertEqual(d["bbox"], [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(d["depth_m"], 2.18)

    # -------------------------------------------------------------------------
    # TEST 10: TOON exposes objects
    # -------------------------------------------------------------------------
    def test_10_toon_exposes_objects(self):
        """Verify TOON output formats #OBJECTS section with proper delimiters."""
        self.tracker.process_detection(
            class_name="chair", confidence=0.67, x=2.18, y=0.19, z=0.52, timestamp=1000.0
        )
        self.tracker.process_detection(
            class_name="table", confidence=0.88, x=4.00, y=-2.50, z=0.75, timestamp=1000.0
        )

        toon = self.tracker.to_toon(reference_time=1000.0)
        self.assertTrue(toon.startswith("#OBJECTS:"), f"Actual: {toon}")
        self.assertIn("chair_001[class:chair,pos:(2.18,0.19,0.52),conf:0.67,vis:1,obs:1]", toon)
        self.assertIn("table_001[class:table,pos:(4.00,-2.50,0.75),conf:0.88,vis:1,obs:1]", toon)

    # -------------------------------------------------------------------------
    # TEST 11: Nearest-object query works
    # -------------------------------------------------------------------------
    def test_11_nearest_object_query(self):
        """Verify get_nearest_object selects the spatially closest object by 3D Euclidean distance."""
        # Chair 1 at (2.0, 0.0, 0.5)
        self.tracker.process_detection(
            class_name="chair", confidence=0.7, x=2.0, y=0.0, z=0.5, timestamp=1000.0
        )
        # Chair 2 at (5.0, 0.0, 0.5)
        self.tracker.process_detection(
            class_name="chair", confidence=0.7, x=5.0, y=0.0, z=0.5, timestamp=1000.0
        )
        # Chair 3 at (-2.0, 0.0, 0.5)
        self.tracker.process_detection(
            class_name="chair", confidence=0.7, x=-2.0, y=0.0, z=0.5, timestamp=1000.0
        )

        # Query from (1.8, 0.1, 0.5) -> nearest should be chair_001
        nearest = self.tracker.get_nearest_object("chair", from_pos=(1.8, 0.1, 0.5))
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest.object_id, "chair_001")

        # Query from (4.8, 0.0, 0.5) -> nearest should be chair_002
        nearest2 = self.tracker.get_nearest_object("chair", from_pos=(4.8, 0.0, 0.5))
        self.assertIsNotNone(nearest2)
        self.assertEqual(nearest2.object_id, "chair_002")

        # Query from (-3.0, 0.0, 0.5) -> nearest should be chair_003
        nearest3 = self.tracker.get_nearest_object("chair", from_pos=(-3.0, 0.0, 0.5))
        self.assertIsNotNone(nearest3)
        self.assertEqual(nearest3.object_id, "chair_003")

        # Query nonexistent class returns None
        self.assertIsNone(self.tracker.get_nearest_object("motorcycle"))

    # -------------------------------------------------------------------------
    # TEST 12: Multiple classes coexist
    # -------------------------------------------------------------------------
    def test_12_multiple_classes_coexist(self):
        """Verify multiple distinct object classes track and index independently."""
        self.tracker.process_detection("chair", 0.7, 1.0, 1.0, 0.5, timestamp=1000.0)
        self.tracker.process_detection("person", 0.9, 1.05, 1.02, 1.6, timestamp=1000.0)
        self.tracker.process_detection("table", 0.8, 1.1, 0.9, 0.7, timestamp=1000.0)

        all_objs = self.tracker.get_objects()
        self.assertEqual(len(all_objs), 3, "All distinct classes must coexist")
        ids = {o.object_id for o in all_objs}
        self.assertEqual(ids, {"chair_001", "person_001", "table_001"})

        # Subsequent chairs and persons increment their own indices
        chair2 = self.tracker.process_detection("chair", 0.7, 4.0, 1.0, 0.5, timestamp=1000.0)
        person2 = self.tracker.process_detection("person", 0.9, -3.0, 0.0, 1.6, timestamp=1000.0)
        self.assertEqual(chair2.object_id, "chair_002")
        self.assertEqual(person2.object_id, "person_002")

    # -------------------------------------------------------------------------
    # TEST 13: Ambiguous association does not silently merge
    # -------------------------------------------------------------------------
    def test_13_ambiguous_association_does_not_silently_merge(self):
        """
        Verify that if two existing objects are tied within 0.5m (|d1 - d2| <= 0.01m),
        the system does NOT make an arbitrary choice; it creates a new object.
        """
        # Create chair_001 at (0.0, 0.35, 0.0)
        self.tracker.process_detection("chair", 0.8, 0.0, 0.35, 0.0, timestamp=1000.0)
        # Create chair_002 at (0.0, -0.35, 0.0) (distance between chair 1 and 2 is 0.70m > 0.5m)
        self.tracker.process_detection("chair", 0.8, 0.0, -0.35, 0.0, timestamp=1000.0)

        all_chairs = self.tracker.get_objects_by_class("chair")
        self.assertEqual(len(all_chairs), 2)

        # Detection at (0.0, 0.0, 0.0):
        # Distance to chair_001: 0.35m (<= 0.5m)
        # Distance to chair_002: 0.35m (<= 0.5m)
        # |d1 - d2| = 0.00 <= 0.01m (Ambiguous tie between two candidates!)
        new_obj = self.tracker.process_detection("chair", 0.85, 0.0, 0.0, 0.0, timestamp=1001.0)
        self.assertEqual(new_obj.object_id, "chair_003", "Ambiguous detection must create a new object rather than arbitrarily merging")
        self.assertEqual(len(self.tracker.get_objects_by_class("chair")), 3)

    # -------------------------------------------------------------------------
    # TEST 14: Backward-compatible ObjectDetected deserialization works
    # -------------------------------------------------------------------------
    def test_14_backward_compatible_object_detected(self):
        """Verify events without optional z, bbox, depth_m deserialize and process cleanly."""
        legacy_data = {
            "object_id": "legacy_chair_001",
            "class_name": "chair",
            "confidence": 0.65,
            "world_x": 1.0,
            "world_y": 2.0,
            # No world_z, bbox, depth_m
            "first_seen": 1000.0,
            "last_seen": 1000.0,
            "observation_count": 1,
            "currently_visible": True,
        }
        obj = WorldObject.from_dict(legacy_data)
        self.assertEqual(obj.object_id, "legacy_chair_001")
        self.assertEqual(obj.world_z, 0.0)
        self.assertIsNone(obj.bbox)
        self.assertIsNone(obj.depth_m)
        self.assertEqual(obj.frame_id, "world")

        # Canonical event from Phase 4 Step 1 Detection
        bbox = BoundingBox(x1=50.0, y1=60.0, x2=150.0, y2=160.0)
        pc = Point3D(x=0.0, y=0.0, z=2.0)
        pw = Point3D(x=2.18, y=0.19, z=0.52)
        det = Detection(
            class_name="chair",
            confidence=0.77,
            bbox=bbox,
            depth_m=2.18,
            position_camera=pc,
            position_world=pw,
        )
        envelope = det.to_canonical_event()
        data = envelope["event_type"]["data"]
        self.assertEqual(data["class_name"], "chair")
        self.assertEqual(data["x"], 2.18)
        self.assertEqual(data["y"], 0.19)
        self.assertEqual(data["z"], 0.52)
        self.assertIn("bbox", data)
        self.assertIn("depth_m", data)


class TestWorldModelClient(unittest.TestCase):
    """Test suite validating typed client interactions with Kernel /world/objects and /context."""

    def setUp(self):
        from unittest.mock import patch, MagicMock
        self.patcher = patch("requests.get")
        self.mock_get = self.patcher.start()
        self.client = WorldModelClient(kernel_url="http://127.0.0.1:7780")
        self.adapter_client = AdapterClient(adapter_name="test_adapter", base_url="http://127.0.0.1:7780")

    def tearDown(self):
        self.patcher.stop()

    def test_get_objects_from_kernel(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "objects": [
                {
                    "object_id": "chair_001",
                    "class_name": "chair",
                    "confidence": 0.85,
                    "position": [2.18, 0.19, 0.52],
                    "first_seen": 1000.0,
                    "last_seen": 1005.0,
                    "observation_count": 5,
                    "currently_visible": True,
                    "source": "Vision",
                    "frame_id": "world",
                }
            ],
            "count": 1,
        }
        self.mock_get.return_value = mock_resp

        objs = self.client.get_objects(visible_only=True, class_name="chair")
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].object_id, "chair_001")
        self.assertEqual(objs[0].class_name, "chair")
        self.assertEqual(objs[0].position, (2.18, 0.19, 0.52))

        # Check request query parameters
        self.mock_get.assert_called_with(
            "http://127.0.0.1:7780/world/objects",
            params={"visible_only": "true", "class": "chair"},
            timeout=2.0,
        )

    def test_get_nearest_object_from_kernel(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "found": True,
            "object": {
                "object_id": "table_001",
                "class_name": "table",
                "confidence": 0.90,
                "position": [4.0, -2.5, 0.75],
                "first_seen": 1000.0,
                "last_seen": 1002.0,
                "observation_count": 3,
                "currently_visible": True,
                "source": "Vision",
                "frame_id": "world",
            },
        }
        self.mock_get.return_value = mock_resp

        obj = self.client.get_nearest_object("table", from_pos=(3.8, -2.4, 0.75))
        self.assertIsNotNone(obj)
        self.assertEqual(obj.object_id, "table_001")
        self.mock_get.assert_called_with(
            "http://127.0.0.1:7780/world/objects",
            params={
                "class": "table",
                "nearest_x": 3.8,
                "nearest_y": -2.4,
                "nearest_z": 0.75,
                "visible_only": "false",
            },
            timeout=2.0,
        )

    def test_adapter_client_query_helpers(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "objects": [{"object_id": "cup_001", "class_name": "cup"}],
            "count": 1,
        }
        self.mock_get.return_value = mock_resp

        objs = self.adapter_client.get_objects_by_class("cup")
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0]["object_id"], "cup_001")


if __name__ == "__main__":
    unittest.main()
