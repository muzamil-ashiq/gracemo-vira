#!/usr/bin/env python3
"""
GRaCEmo ViRa — Physical Embodiment Phase 1 Regression Tests:
  1. Generated SDF contains valid bumper collision target matching lumped link collision.
  2. Base collision envelope reasonably matches the cylindrical chassis geometry.
  3. Upper-body collision geometry exists on all required upper-body links.
  4. Bumper contact sensor message handling in BaseController.
"""

import os
import sys
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORLD_FILE = ROOT / "ros2_ws" / "src" / "gracemo_gazebo" / "worlds" / "apartment_floor.world"
URDF_XACRO = ROOT / "ros2_ws" / "src" / "gracemo_description" / "urdf" / "gracemo_vira.urdf.xacro"


class TestCollisionAndBumper(unittest.TestCase):

    def setUp(self):
        self.assertTrue(WORLD_FILE.exists(), f"World file not found: {WORLD_FILE}")
        self.assertTrue(URDF_XACRO.exists(), f"URDF Xacro not found: {URDF_XACRO}")
        with open(WORLD_FILE, "r") as f:
            self.world_content = f.read()
        with open(URDF_XACRO, "r") as f:
            self.urdf_content = f.read()

    def test_01_sdf_bumper_collision_target_validity(self):
        """Regression Test 1: Sensor collision target matches an existing collision in the SDF."""
        # Find sensor bumper_contact
        sensor_match = re.search(
            r"<sensor name=['\"]bumper_contact['\"][^>]*>(.*?)</sensor>",
            self.world_content,
            re.DOTALL
        )
        self.assertIsNotNone(sensor_match, "Sensor 'bumper_contact' must exist in apartment_floor.world")
        sensor_block = sensor_match.group(1)

        # Extract target collision name
        col_target_match = re.search(r"<collision>(.*?)</collision>", sensor_block)
        self.assertIsNotNone(col_target_match, "Sensor 'bumper_contact' must specify a <collision> target")
        target_name = col_target_match.group(1).strip()
        self.assertNotEqual(
            target_name, "bumper_collision",
            "CRITICAL BUG: Bumper sensor target must NOT be un-lumped 'bumper_collision'"
        )

        # Verify target_name exists as an actual <collision name='...'> in the robot model
        col_decl = re.search(rf"<collision name=['\"]{re.escape(target_name)}['\"]>", self.world_content)
        self.assertIsNotNone(
            col_decl,
            f"Sensor collision target '{target_name}' must exist as a <collision name='...'> in the world model!"
        )

        # Verify topic
        topic_match = re.search(r"<topic>(.*?)</topic>", sensor_block)
        self.assertIsNotNone(topic_match)
        self.assertIn("bumper/contacts", topic_match.group(1))

    def test_02_base_collision_envelope(self):
        """Regression Test 2: Base collision matches the cylindrical chassis envelope."""
        # Check URDF base_link collision
        base_link_match = re.search(r"<link name=\"base_link\">(.*?)</link>", self.urdf_content, re.DOTALL)
        self.assertIsNotNone(base_link_match, "base_link must exist in URDF")
        base_link_xml = base_link_match.group(1)

        self.assertIn("<cylinder", base_link_xml, "base_link collision should be a cylinder matching chassis envelope")
        self.assertNotIn('<box size="0.24 0.20', base_link_xml, "Old undersized box collision must be replaced")

        # Verify radius is 0.19m (chassis_radius property)
        self.assertIn('radius="${chassis_radius}"', base_link_xml)

        # Verify ground clearance in SDF
        col_match = re.search(
            r"<collision name=['\"]base_footprint_fixed_joint_lump__base_link_collision_collision['\"]>.*?<pose>(.*?)</pose>.*?<cylinder>.*?<length>(.*?)</length>.*?<radius>(.*?)</radius>",
            self.world_content,
            re.DOTALL
        )
        self.assertIsNotNone(col_match, "Lumped base_link collision must exist in SDF")
        pose_str = col_match.group(1).split()
        z_center = float(pose_str[2])
        length = float(col_match.group(2))
        radius = float(col_match.group(3))

        self.assertAlmostEqual(radius, 0.19, places=2)
        bottom_z = z_center - length / 2.0
        # base_footprint is at ground (z=0), wheel radius = 0.065m, base origin z = 0.065
        # z_center relative to base_footprint should be >= 0.10m, so bottom_z >= 0.05m above ground
        self.assertGreaterEqual(bottom_z, 0.05, f"Chassis collision bottom Z={bottom_z}m must not drag on ground")

    def test_03_upper_body_collisions_exist(self):
        """Regression Test 3: Upper-body collision geometry exists on all required links."""
        required_links = [
            "torso_link",
            "head_link",
            "camera_link",
            "lidar_link",
            "left_arm_link",
            "right_shoulder_yaw_link",
            "right_shoulder_pitch_link",
            "right_wrist_pitch_link",
            "right_wrist_yaw_link",
        ]

        for link in required_links:
            link_match = re.search(rf"<link name=\"{link}\">(.*?)</link>", self.urdf_content, re.DOTALL)
            self.assertIsNotNone(link_match, f"Link '{link}' must exist in URDF")
            link_xml = link_match.group(1)
            self.assertIn(
                "<collision",
                link_xml,
                f"Link '{link}' must have a <collision> element defining physical boundary"
            )

    def test_04_base_controller_bumper_subscription(self):
        """Regression Test 4: BaseController subscribes to both /bumper/contacts and canonical topic."""
        ctrl_path = ROOT / "adapters" / "motion" / "gracemo_base_controller.py"
        with open(ctrl_path, "r") as f:
            code = f.read()

        self.assertIn("/bumper/contacts", code)
        self.assertIn("bumper_contact/contact", code, "BaseController must subscribe to canonical gazebo topic as well")

    def test_05_bumper_contact_event_behavior(self):
        """Regression Test 5: Validate behavioral processing of real Gazebo contact messages."""
        sys.path.insert(0, str(ROOT / "adapters" / "motion"))
        from gracemo_base_controller import BaseController

        # Mock a BaseController without starting network threads
        controller = object.__new__(BaseController)
        controller.bumper_hit = False
        controller.last_bumper_hit_time = 0.0

        # Create a mock contact message simulating Gazebo Contacts message
        class MockEntity:
            def __init__(self, name):
                self.name = name

        class MockContact:
            def __init__(self, c1, c2):
                self.collision1 = MockEntity(c1)
                self.collision2 = MockEntity(c2)

        class MockContactsMsg:
            def __init__(self, contacts):
                self.contact = contacts

        lumped_collision = "gracemo_vira::base_footprint::base_footprint_fixed_joint_lump__bumper_collision_collision_1"
        wall_collision = "hall_north_middle::l::c"
        msg = MockContactsMsg([MockContact(lumped_collision, wall_collision)])

        # Trigger event handler
        controller._on_contacts(msg)
        self.assertTrue(controller.bumper_hit, "BaseController must set bumper_hit=True on contact")
        self.assertGreater(controller.last_bumper_hit_time, 0.0)


if __name__ == "__main__":
    unittest.main()

