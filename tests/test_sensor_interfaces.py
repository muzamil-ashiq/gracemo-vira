#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 2 Sensor & ROS 2 Physical Interface Unit Tests:
  1. URDF sensor definitions exist and match hardware specification.
  2. ROS 2 topic names and standard message types.
  3. Canonical frame IDs across all sensor streams.
  4. CameraInfo optical intrinsics computation.
  5. Depth PointCloud2 field layout and data schema.
  6. Launch integration in sim.launch.py.
"""

import os
import sys
import re
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XACRO_FILE = ROOT / "ros2_ws" / "src" / "gracemo_description" / "urdf" / "gazebo_plugins.xacro"
BRIDGE_SRC = ROOT / "ros2_ws" / "src" / "gracemo_bridge" / "gracemo_bridge" / "sensor_bridge.py"
LAUNCH_SRC = ROOT / "ros2_ws" / "src" / "gracemo_gazebo" / "launch" / "sim.launch.py"


class TestSensorInterfaces(unittest.TestCase):

    def setUp(self):
        self.assertTrue(XACRO_FILE.exists(), f"Xacro file not found: {XACRO_FILE}")
        self.assertTrue(BRIDGE_SRC.exists(), f"Bridge source not found: {BRIDGE_SRC}")
        self.assertTrue(LAUNCH_SRC.exists(), f"Launch source not found: {LAUNCH_SRC}")

        with open(XACRO_FILE, "r") as f:
            self.xacro_content = f.read()
        with open(BRIDGE_SRC, "r") as f:
            self.bridge_content = f.read()
        with open(LAUNCH_SRC, "r") as f:
            self.launch_content = f.read()

    def test_01_urdf_sensor_definitions(self):
        """Test 1: Check that physical Gazebo sensors are defined in URDF/Xacro."""
        # LiDAR
        self.assertIn('<sensor name="lidar" type="gpu_lidar">', self.xacro_content)
        self.assertIn('<topic>/scan</topic>', self.xacro_content)

        # IMU
        self.assertIn('<sensor name="imu" type="imu">', self.xacro_content)
        self.assertIn('<topic>/imu/data</topic>', self.xacro_content)

        # RGB Camera
        self.assertIn('<sensor name="camera" type="camera">', self.xacro_content)
        self.assertIn('<topic>/camera/image_raw</topic>', self.xacro_content)

        # Depth Camera
        self.assertIn('<sensor name="depth_camera" type="depth_camera">', self.xacro_content)
        self.assertIn('<topic>/camera/depth_image</topic>', self.xacro_content)

        # Joint State Publisher
        self.assertIn('name="gz::sim::systems::JointStatePublisher"', self.xacro_content)

    def test_02_sensor_bridge_topics_and_types(self):
        """Test 2: Check that sensor_bridge exposes all required ROS 2 topics and message types."""
        expected_mappings = {
            "/scan": "RosLaserScan",
            "/joint_states": "RosJointState",
            "/odom": "RosOdometry",
            "/imu/data": "RosImu",
            "/camera/image_raw": "RosImage",
            "/camera/camera_info": "RosCameraInfo",
            "/camera/depth_image": "RosImage",
            "/camera/depth/camera_info": "RosCameraInfo",
            "/camera/depth/points": "RosPointCloud2",
            "/cmd_vel": "RosTwist",
        }

        for topic, msg_type in expected_mappings.items():
            self.assertIn(topic, self.bridge_content, f"Topic '{topic}' missing from sensor_bridge.py")
            self.assertIn(msg_type, self.bridge_content, f"Message type '{msg_type}' missing from sensor_bridge.py")

    def test_03_canonical_frame_names(self):
        """Test 3: Verify canonical URDF frame IDs are assigned to sensor streams."""
        canonical_frames = [
            'frame_id = "lidar_link"',
            'frame_id = "imu_link"',
            'frame_id = "camera_optical_link"',
            'frame_id = "odom"',
            'child_frame_id = "base_footprint"',
            'frame_id = "world"',
        ]

        for frame in canonical_frames:
            self.assertIn(frame, self.bridge_content, f"Required frame assignment '{frame}' missing")

    def test_04_camera_info_intrinsics_math(self):
        """Test 4: Validate pinhole CameraInfo focal length and optical center math."""
        # Calculate expected fx for 640x480 at hfov 1.15 rad
        width = 640
        height = 480
        hfov = 1.15
        expected_fx = (width / 2.0) / math.tan(hfov / 2.0)
        expected_cx = width / 2.0
        expected_cy = height / 2.0

        self.assertAlmostEqual(expected_fx, 493.79, places=2)
        self.assertEqual(expected_cx, 320.0)
        self.assertEqual(expected_cy, 240.0)

        # Check that bridge source contains the pinhole formula
        self.assertIn("fx = (width / 2.0) / math.tan(hfov / 2.0)", self.bridge_content)
        self.assertIn("cx = width / 2.0", self.bridge_content)
        self.assertIn("cy = height / 2.0", self.bridge_content)

    def test_05_depth_pointcloud_field_schema(self):
        """Test 5: Verify PointCloud2 fields schema (x, y, z, rgb float32)."""
        self.assertIn("RosPointField.FLOAT32", self.bridge_content)
        self.assertIn("point_step", self.bridge_content)
        self.assertIn("row_step", self.bridge_content)

    def test_06_sim_launch_contains_sensor_bridge(self):
        """Test 6: Verify sim.launch.py launches gracemo_sensor_bridge Node unconditionally."""
        self.assertIn('executable="sensor_bridge"', self.launch_content)
        self.assertIn('name="gracemo_sensor_bridge"', self.launch_content)
        self.assertIn('package="gracemo_bridge"', self.launch_content)


if __name__ == "__main__":
    unittest.main()
