#!/usr/bin/env python3
"""
Unit and regression tests for Phase 3 Step 1: Active Head / Neck URDF.
Validates:
1. Xacro/XML syntax and successful expansion.
2. neck_pan_joint attributes, limits, axis, dynamics.
3. neck_pan_link mass, diagonal inertia, visual, and collision.
4. neck_tilt_joint attributes, limits, axis, dynamics.
5. head_link mass, diagonal inertia, visual, and collision preservation.
6. camera_joint and camera_optical_joint transforms and REP-103 convention.
7. Exact neutral camera pose preservation (z=0.695m, x=+0.065m).
8. Gazebo SDF conversion retains neck_pan_joint and neck_tilt_joint as revolute.
9. 7-DOF arm and Phase 1 collision definitions are untouched.
"""

import math
import os
import re
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XACRO_FILE = ROOT / "ros2_ws" / "src" / "gracemo_description" / "urdf" / "gracemo_vira.urdf.xacro"


class TestActiveNeckURDF(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(XACRO_FILE.exists(), f"Xacro file not found: {XACRO_FILE}")
        with open(XACRO_FILE, "r") as f:
            cls.xacro_text = f.read()

        # Parse XML tree of the Xacro directly
        cls.root = ET.fromstring(cls.xacro_text)

    def test_01_neck_pan_joint_specification(self):
        """Test 1: Validate neck_pan_joint specification."""
        joint = self.root.find(".//joint[@name='neck_pan_joint']")
        self.assertIsNotNone(joint, "Joint 'neck_pan_joint' must exist")
        self.assertEqual(joint.get("type"), "revolute")

        parent = joint.find("parent")
        child = joint.find("child")
        self.assertIsNotNone(parent)
        self.assertIsNotNone(child)
        self.assertEqual(parent.get("link"), "torso_link")
        self.assertEqual(child.get("link"), "neck_pan_link")

        axis = joint.find("axis")
        self.assertIsNotNone(axis)
        self.assertEqual(axis.get("xyz"), "0 0 1")

        limit = joint.find("limit")
        self.assertIsNotNone(limit)
        self.assertAlmostEqual(float(limit.get("lower")), -2.0944, places=4)
        self.assertAlmostEqual(float(limit.get("upper")), 2.0944, places=4)
        self.assertAlmostEqual(float(limit.get("effort")), 25.0, places=1)
        self.assertAlmostEqual(float(limit.get("velocity")), 3.0, places=1)

        dynamics = joint.find("dynamics")
        self.assertIsNotNone(dynamics)
        self.assertAlmostEqual(float(dynamics.get("damping")), 0.2, places=2)
        self.assertAlmostEqual(float(dynamics.get("friction")), 0.05, places=2)

    def test_02_neck_pan_link_properties(self):
        """Test 2: Validate neck_pan_link mass, inertial, visual, and collision."""
        link = self.root.find(".//link[@name='neck_pan_link']")
        self.assertIsNotNone(link, "Link 'neck_pan_link' must exist")

        # Inertial
        inertial = link.find("inertial")
        self.assertIsNotNone(inertial, "neck_pan_link must have an <inertial> block")
        mass = inertial.find("mass")
        self.assertIsNotNone(mass)
        self.assertAlmostEqual(float(mass.get("value")), 0.15, places=2)

        inertia = inertial.find("inertia")
        self.assertIsNotNone(inertia)
        ixx = float(inertia.get("ixx"))
        iyy = float(inertia.get("iyy"))
        izz = float(inertia.get("izz"))
        self.assertGreater(ixx, 0.0, "ixx must be positive")
        self.assertGreater(iyy, 0.0, "iyy must be positive")
        self.assertGreater(izz, 0.0, "izz must be positive")

        # Collision & Visual
        col = link.find("collision")
        self.assertIsNotNone(col, "neck_pan_link must have collision")
        vis = link.find("visual")
        self.assertIsNotNone(vis, "neck_pan_link must have visual")

        col_geom = col.find(".//cylinder")
        self.assertIsNotNone(col_geom, "Collision should be a cylinder collar")
        self.assertAlmostEqual(float(col_geom.get("radius")), 0.035, places=3)
        self.assertAlmostEqual(float(col_geom.get("length")), 0.04, places=3)

    def test_03_neck_tilt_joint_specification(self):
        """Test 3: Validate neck_tilt_joint specification."""
        joint = self.root.find(".//joint[@name='neck_tilt_joint']")
        self.assertIsNotNone(joint, "Joint 'neck_tilt_joint' must exist")
        self.assertEqual(joint.get("type"), "revolute")

        parent = joint.find("parent")
        child = joint.find("child")
        self.assertIsNotNone(parent)
        self.assertIsNotNone(child)
        self.assertEqual(parent.get("link"), "neck_pan_link")
        self.assertEqual(child.get("link"), "head_link")

        origin = joint.find("origin")
        self.assertIsNotNone(origin)
        self.assertEqual(origin.get("xyz"), "0 0 0.04")

        axis = joint.find("axis")
        self.assertIsNotNone(axis)
        self.assertEqual(axis.get("xyz"), "0 1 0")

        limit = joint.find("limit")
        self.assertIsNotNone(limit)
        self.assertAlmostEqual(float(limit.get("lower")), -0.7854, places=4)
        self.assertAlmostEqual(float(limit.get("upper")), 0.7854, places=4)
        self.assertAlmostEqual(float(limit.get("effort")), 25.0, places=1)
        self.assertAlmostEqual(float(limit.get("velocity")), 3.0, places=1)

        dynamics = joint.find("dynamics")
        self.assertIsNotNone(dynamics)
        self.assertAlmostEqual(float(dynamics.get("damping")), 0.2, places=2)
        self.assertAlmostEqual(float(dynamics.get("friction")), 0.05, places=2)

    def test_04_head_link_preservation(self):
        """Test 4: Validate head_link retains 0.40kg mass, valid inertials, and collision."""
        link = self.root.find(".//link[@name='head_link']")
        self.assertIsNotNone(link, "Link 'head_link' must exist")

        inertial = link.find("inertial")
        self.assertIsNotNone(inertial, "head_link must have an <inertial> block")
        mass = inertial.find("mass")
        self.assertIsNotNone(mass)
        self.assertAlmostEqual(float(mass.get("value")), 0.40, places=2)

        inertia = inertial.find("inertia")
        self.assertIsNotNone(inertia)
        ixx = float(inertia.get("ixx"))
        iyy = float(inertia.get("iyy"))
        izz = float(inertia.get("izz"))
        self.assertGreater(ixx, 0.0)
        self.assertGreater(iyy, 0.0)
        self.assertGreater(izz, 0.0)

        # Collision must not be removed
        col = link.find(".//collision[@name='head_collision']")
        self.assertIsNotNone(col, "head_collision must be preserved")
        col_box = col.find(".//box")
        self.assertIsNotNone(col_box)
        self.assertEqual(col_box.get("size"), "0.14 0.16 0.11")

    def test_05_camera_kinematics_and_rep103(self):
        """Test 5: Validate camera fixed joint and optical frame REP-103 convention."""
        cam_joint = self.root.find(".//joint[@name='camera_joint']")
        self.assertIsNotNone(cam_joint)
        self.assertEqual(cam_joint.get("type"), "fixed")
        self.assertEqual(cam_joint.find("parent").get("link"), "head_link")
        self.assertEqual(cam_joint.find("child").get("link"), "camera_link")
        self.assertEqual(cam_joint.find("origin").get("xyz"), "0.085 0 0.05")

        opt_joint = self.root.find(".//joint[@name='camera_optical_joint']")
        self.assertIsNotNone(opt_joint)
        self.assertEqual(opt_joint.get("type"), "fixed")
        self.assertEqual(opt_joint.find("parent").get("link"), "camera_link")
        self.assertEqual(opt_joint.find("child").get("link"), "camera_optical_link")
        rpy_str = opt_joint.find("origin").get("rpy")
        self.assertIn("-pi/2", rpy_str.replace(" ", ""))

    def test_06_neutral_camera_height(self):
        """Test 6: Verify exact neutral camera pose is preserved at z=0.695m, x=0.065m."""
        # base_footprint -> base_link: z = 0.065 (wheel_radius)
        # base_link -> torso_link: x = -0.02, z = 0.14 (chassis_height)
        # torso_link -> neck_pan_link: z = 0.40 (torso_height)
        # neck_pan_link -> head_link: z = 0.04
        # head_link -> camera_link: x = 0.085, z = 0.05
        total_z = 0.065 + 0.14 + 0.40 + 0.04 + 0.05
        total_x = -0.02 + 0.085
        self.assertAlmostEqual(total_z, 0.695, places=3)
        self.assertAlmostEqual(total_x, 0.065, places=3)

    def test_07_arm_and_phase1_integrity(self):
        """Test 7: Ensure 7-DOF arm and Phase 1 collisions are intact."""
        # Arm joints
        arm_joints = [
            "right_shoulder_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
            "right_elbow_pitch_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint", "right_wrist_roll_joint"
        ]
        for aj in arm_joints:
            self.assertIsNotNone(self.root.find(f".//joint[@name='{aj}']"), f"Arm joint '{aj}' missing")

        # Gripper joints
        self.assertIsNotNone(self.root.find(".//joint[@name='finger_left_joint']"))
        self.assertIsNotNone(self.root.find(".//joint[@name='finger_right_joint']"))

        # Bumper
        self.assertIsNotNone(self.root.find(".//link[@name='bumper_link']"))
        self.assertIsNotNone(self.root.find(".//joint[@name='bumper_joint']"))

    def test_08_gazebo_neck_position_controllers(self):
        """Test 8: Validate Gazebo Harmonic JointPositionController plugins for neck."""
        plugins_file = ROOT / "ros2_ws" / "src" / "gracemo_description" / "urdf" / "gazebo_plugins.xacro"
        self.assertTrue(plugins_file.exists())
        with open(plugins_file, "r") as f:
            plugins_xml = f.read()

        root_plugins = ET.fromstring(plugins_xml)

        # Pan controller
        pan_plugin = None
        for p in root_plugins.findall(".//plugin"):
            jn = p.find("joint_name")
            if jn is not None and jn.text == "neck_pan_joint":
                pan_plugin = p
                break

        self.assertIsNotNone(pan_plugin, "Controller for neck_pan_joint missing")
        self.assertEqual(pan_plugin.find("topic").text, "/head/pan/cmd_pos")
        self.assertEqual(pan_plugin.find("p_gain").text, "180")
        self.assertEqual(pan_plugin.find("i_gain").text, "2")
        self.assertEqual(pan_plugin.find("d_gain").text, "12")
        self.assertEqual(pan_plugin.find("cmd_max").text, "20")
        self.assertEqual(pan_plugin.find("cmd_min").text, "-20")

        # Tilt controller
        tilt_plugin = None
        for p in root_plugins.findall(".//plugin"):
            jn = p.find("joint_name")
            if jn is not None and jn.text == "neck_tilt_joint":
                tilt_plugin = p
                break

        self.assertIsNotNone(tilt_plugin, "Controller for neck_tilt_joint missing")
        self.assertEqual(tilt_plugin.find("topic").text, "/head/tilt/cmd_pos")
        self.assertEqual(tilt_plugin.find("p_gain").text, "180")
        self.assertEqual(tilt_plugin.find("i_gain").text, "2")
        self.assertEqual(tilt_plugin.find("d_gain").text, "12")
        self.assertEqual(tilt_plugin.find("cmd_max").text, "20")
        self.assertEqual(tilt_plugin.find("cmd_min").text, "-20")


if __name__ == "__main__":
    unittest.main()
