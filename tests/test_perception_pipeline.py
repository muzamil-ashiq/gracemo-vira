"""
GRaCEmo ViRa — Phase 4 Step 1 Perception Pipeline Unit Tests
Validates:
1. Pinhole back-projection math from CameraInfo to camera-frame coordinates.
2. Robust median depth sampling with NaN/Inf/out-of-range rejection.
3. Rigid 3D spatial transformation from camera_optical_link to world frame.
4. Structured Detection schema and canonical ObjectDetected event generation.
5. RGB (640x480) to Depth (320x240) coordinate scaling.
6. GazeBridge LookAt consumption without neck computation.
"""

import math
import sys
import unittest
from pathlib import Path
import numpy as np
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.perception.models import BoundingBox, Point3D, Detection, PerceptionResult
from adapters.perception.depth_estimator import DepthEstimator
from adapters.perception.coordinate_transformer import CoordinateTransformer, quaternion_rotate_vector
from adapters.perception.visualizer import PerceptionVisualizer
from adapters.perception.gaze_bridge import GazeBridge


class FakeCameraInfo:
    """Mock CameraInfo matching sensor_msgs/CameraInfo."""
    def __init__(self, width=640, height=480, fx=550.0, fy=550.0, cx=320.0, cy=240.0, frame_id="camera_optical_link"):
        self.width = width
        self.height = height
        self.header = MagicMock()
        self.header.frame_id = frame_id
        self.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
        self.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]


class TestPerceptionPipeline(unittest.TestCase):
    def setUp(self):
        self.estimator = DepthEstimator(neighborhood_size=5)
        self.cam_info = FakeCameraInfo(width=640, height=480, fx=500.0, fy=500.0, cx=320.0, cy=240.0)
        self.estimator.update_camera_info(self.cam_info)

    # -------------------------------------------------------------------------
    # TEST 1: BoundingBox calculation
    # -------------------------------------------------------------------------
    def test_bounding_box_geometry(self):
        bbox = BoundingBox(x1=100.0, y1=150.0, x2=200.0, y2=250.0)
        self.assertEqual(bbox.width, 100.0)
        self.assertEqual(bbox.height, 100.0)
        self.assertEqual(bbox.cx, 150.0)
        self.assertEqual(bbox.cy, 200.0)

    # -------------------------------------------------------------------------
    # TEST 2: Robust Median Depth Sampling
    # -------------------------------------------------------------------------
    def test_median_depth_sampling_with_noise_and_nans(self):
        depth_img = np.ones((240, 320), dtype=np.float32) * 2.5
        # Inject NaNs, zeros, and out-of-range values around center (160, 120)
        depth_img[119, 159] = np.nan
        depth_img[120, 160] = 0.0  # Invalid <= 0.05m
        depth_img[121, 161] = 99.0 # Out of range > 15m
        depth_img[119, 161] = 2.4
        depth_img[121, 159] = 2.6

        # Median of valid values [2.4, 2.5, ..., 2.6]
        val = self.estimator.sample_median_depth(depth_img, u_depth=160, v_depth=120)
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 2.5, places=1)

    # -------------------------------------------------------------------------
    # TEST 3: Reject completely invalid depth patches
    # -------------------------------------------------------------------------
    def test_reject_invalid_depth_patch(self):
        depth_img = np.full((240, 320), np.nan, dtype=np.float32)
        val = self.estimator.sample_median_depth(depth_img, u_depth=160, v_depth=120)
        self.assertIsNone(val)

    # -------------------------------------------------------------------------
    # TEST 4: Pinhole 3D Projection at Optical Center
    # -------------------------------------------------------------------------
    def test_3d_projection_center(self):
        # Target directly at optical center (320, 240) in RGB
        bbox = BoundingBox(x1=300.0, y1=220.0, x2=340.0, y2=260.0)
        self.assertEqual(bbox.cx, 320.0)
        self.assertEqual(bbox.cy, 240.0)

        # Depth image 320x240 filled with 2.0 meters
        depth_img = np.full((240, 320), 2.0, dtype=np.float32)

        depth_m, point_cam = self.estimator.estimate_3d_position(bbox, depth_img, rgb_width=640, rgb_height=480)
        self.assertIsNotNone(depth_m)
        self.assertIsNotNone(point_cam)
        self.assertAlmostEqual(depth_m, 2.0, places=2)
        self.assertAlmostEqual(point_cam.x, 0.0, places=2)
        self.assertAlmostEqual(point_cam.y, 0.0, places=2)
        self.assertAlmostEqual(point_cam.z, 2.0, places=2)
        self.assertEqual(point_cam.frame_id, "camera_optical_link")

    # -------------------------------------------------------------------------
    # TEST 5: Pinhole 3D Projection with Lateral & Vertical Offsets
    # -------------------------------------------------------------------------
    def test_3d_projection_off_center(self):
        # Center shifted: u = 420 (offset = +100px), v = 140 (offset = -100px)
        # With fx=500, fy=500, Z=2.5m:
        # X = 100 * 2.5 / 500 = +0.50m
        # Y = -100 * 2.5 / 500 = -0.50m
        bbox = BoundingBox(x1=400.0, y1=120.0, x2=440.0, y2=160.0)
        depth_img = np.full((240, 320), 2.5, dtype=np.float32)

        depth_m, point_cam = self.estimator.estimate_3d_position(bbox, depth_img, rgb_width=640, rgb_height=480)
        self.assertIsNotNone(point_cam)
        self.assertAlmostEqual(point_cam.x, 0.50, places=2)
        self.assertAlmostEqual(point_cam.y, -0.50, places=2)
        self.assertAlmostEqual(point_cam.z, 2.50, places=2)

    # -------------------------------------------------------------------------
    # TEST 6: RGB to Depth Resolution Scaling
    # -------------------------------------------------------------------------
    def test_rgb_to_depth_scaling(self):
        # RGB point at (640, 480) -> Depth point at (320, 240)
        depth_img = np.zeros((240, 320), dtype=np.float32)
        # Put 3.0m only at the bottom-right corner (319, 239)
        depth_img[238:240, 318:320] = 3.0

        bbox = BoundingBox(x1=630.0, y1=470.0, x2=640.0, y2=480.0)
        depth_m, _ = self.estimator.estimate_3d_position(bbox, depth_img, rgb_width=640, rgb_height=480)
        self.assertIsNotNone(depth_m)
        self.assertAlmostEqual(depth_m, 3.0, places=2)

    # -------------------------------------------------------------------------
    # TEST 7: Rigid Spatial Transformation to World Frame
    # -------------------------------------------------------------------------
    def test_rigid_transform_to_world(self):
        point_cam = Point3D(x=0.0, y=0.0, z=2.0, frame_id="camera_optical_link")

        # Identity rotation (0, 0, 0, 1), translation (1.0, 2.0, 0.5)
        pw = CoordinateTransformer.apply_transform(
            point_cam,
            translation=(1.0, 2.0, 0.5),
            rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
            target_frame="world",
        )
        self.assertAlmostEqual(pw.x, 1.0, places=2)
        self.assertAlmostEqual(pw.y, 2.0, places=2)
        self.assertAlmostEqual(pw.z, 2.5, places=2)
        self.assertEqual(pw.frame_id, "world")

    # -------------------------------------------------------------------------
    # TEST 8: Optical Frame to ROS World Frame Rotation
    # -------------------------------------------------------------------------
    def test_optical_to_world_orientation(self):
        # In optical frame: +Z is forward, +X is right, +Y is down.
        # Robot at origin facing +X (East).
        # Camera optical frame relative to base:
        # Optical Z (forward) -> World X (forward)
        # Optical X (right)   -> World -Y (right in base frame)
        # Optical Y (down)    -> World -Z (down in base frame)
        # Standard camera_optical_link to base_link quaternion:
        # q = [-0.5, 0.5, -0.5, 0.5]
        q = (-0.5, 0.5, -0.5, 0.5)
        # Vector forward in optical frame: (0, 0, 2)
        rot_v = quaternion_rotate_vector(q, (0.0, 0.0, 2.0))
        self.assertAlmostEqual(rot_v[0], 2.0, places=2) # World X
        self.assertAlmostEqual(rot_v[1], 0.0, places=2) # World Y
        self.assertAlmostEqual(rot_v[2], 0.0, places=2) # World Z

    # -------------------------------------------------------------------------
    # TEST 9: Structured Detection Dataclass & Canonical Event Schema
    # -------------------------------------------------------------------------
    def test_detection_canonical_event_schema(self):
        bbox = BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0)
        pc = Point3D(x=0.1, y=-0.2, z=1.8, frame_id="camera_optical_link")
        pw = Point3D(x=-4.5, y=-4.0, z=0.75, frame_id="world")

        det = Detection(
            class_name="dining table",
            confidence=0.92,
            bbox=bbox,
            depth_m=1.8,
            position_camera=pc,
            position_world=pw,
        )

        d_dict = det.to_dict()
        self.assertEqual(d_dict["class_name"], "dining table")
        self.assertEqual(d_dict["confidence"], 0.92)
        self.assertEqual(d_dict["depth_m"], 1.8)
        self.assertEqual(d_dict["position_world"]["x"], -4.5)
        self.assertEqual(d_dict["position_world"]["y"], -4.0)

        envelope = det.to_canonical_event(source="Vision", observed_by="perception_service")
        self.assertEqual(envelope["source"], "Vision")
        self.assertEqual(envelope["observed_by"], "perception_service")
        self.assertEqual(envelope["event_type"]["type"], "ObjectDetected")
        self.assertEqual(envelope["event_type"]["data"]["class_name"], "dining table")
        self.assertEqual(envelope["event_type"]["data"]["x"], -4.5)
        self.assertEqual(envelope["event_type"]["data"]["y"], -4.0)

    # -------------------------------------------------------------------------
    # TEST 10: GazeBridge Interface
    # -------------------------------------------------------------------------
    def test_gaze_bridge_routing(self):
        bridge = GazeBridge()
        # Mock registry
        mock_registry = MagicMock()
        mock_tool_res = MagicMock()
        mock_tool_res.success = True
        mock_tool_res.message = "Dispatched LookAt"
        mock_tool_res.data = {}
        mock_registry.execute.return_value = mock_tool_res
        bridge.registry = mock_registry

        res = bridge.look_at_world_point(-4.5, -4.0, 0.75, target_name="dining table")
        self.assertTrue(res["success"])
        mock_registry.execute.assert_called_once_with(
            "look_at",
            {"x": -4.5, "y": -4.0, "z": 0.75},
        )


if __name__ == "__main__":
    unittest.main()
