#!/usr/bin/env python3
"""
Unit and Integration Tests for GRaCEmo ViRa Command Velocity Multiplexer & Velocity Safety Pipeline.
Validates:
1. Deterministic Command Arbitration (Teleop > Nav2 priority)
2. Teleop timeout and seamless fallback to Nav2
3. Stale message rejection and safe-zero command publication
4. End-to-end velocity topic contract:
   /cmd_vel_nav + /cmd_vel_teleop -> /cmd_vel_mux -> /cmd_vel_smoothed -> /cmd_vel_safe -> /cmd_vel
5. Configuration parameter integrity in nav2_params.yaml
6. Hardware launch coordinator package reference
"""

import os
import sys
import time
import json
import unittest
from pathlib import Path

# Add project roots to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "gracemo_nav2"))
sys.path.insert(0, str(ROOT / "ros2_ws" / "install" / "gracemo_nav2" / "lib" / "gracemo_nav2"))

import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import String as RosString

from cmd_vel_mux_node import CommandVelocityMuxNode


class TestCommandVelocityMux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not rclpy.ok():
            rclpy.init()

    @classmethod
    def tearDownClass(cls):
        if rclpy.ok():
            rclpy.shutdown()

    def setUp(self):
        self.node = CommandVelocityMuxNode(node_name="test_cmd_vel_mux")
        self.node.teleop_timeout_sec = 0.5
        self.node.nav_timeout_sec = 0.5

    def tearDown(self):
        self.node.destroy_node()

    def test_01_no_input_safe_zero(self):
        """When no inputs are received, arbitration evaluates to NONE and latches zero."""
        now = 100.0
        source, cmd, should_publish = self.node.evaluate_arbitration(now)
        self.assertEqual(source, "NONE")
        self.assertEqual(cmd.linear.x, 0.0)
        self.assertEqual(cmd.angular.z, 0.0)

    def test_02_nav_only_arbitration(self):
        """When only autonomous navigation publishes, mux selects NAV."""
        now = 100.0
        nav_twist = Twist()
        nav_twist.linear.x = 0.35
        nav_twist.angular.z = 0.10

        self.node._last_nav_msg = nav_twist
        self.node._last_nav_time = now

        source, cmd, should_publish = self.node.evaluate_arbitration(now)
        self.assertEqual(source, "NAV")
        self.assertAlmostEqual(cmd.linear.x, 0.35)
        self.assertAlmostEqual(cmd.angular.z, 0.10)
        self.assertTrue(should_publish)

    def test_03_teleop_only_arbitration(self):
        """When only teleoperation publishes, mux selects TELEOP."""
        now = 100.0
        teleop_twist = Twist()
        teleop_twist.linear.x = -0.25
        teleop_twist.angular.z = 0.40

        self.node._last_teleop_msg = teleop_twist
        self.node._last_teleop_time = now

        source, cmd, should_publish = self.node.evaluate_arbitration(now)
        self.assertEqual(source, "TELEOP")
        self.assertAlmostEqual(cmd.linear.x, -0.25)
        self.assertAlmostEqual(cmd.angular.z, 0.40)
        self.assertTrue(should_publish)

    def test_04_teleop_preempts_nav_priority(self):
        """When both teleoperation and navigation are active, TELEOP preempts NAV."""
        now = 100.0
        nav_twist = Twist()
        nav_twist.linear.x = 0.30
        self.node._last_nav_msg = nav_twist
        self.node._last_nav_time = now

        teleop_twist = Twist()
        teleop_twist.linear.x = 0.50
        self.node._last_teleop_msg = teleop_twist
        self.node._last_teleop_time = now

        source, cmd, should_publish = self.node.evaluate_arbitration(now)
        self.assertEqual(source, "TELEOP")
        self.assertAlmostEqual(cmd.linear.x, 0.50)
        self.assertTrue(should_publish)

    def test_05_teleop_timeout_fallback_to_nav(self):
        """When teleoperation goes silent past its timeout, arbiter falls back to NAV."""
        start_time = 100.0
        nav_twist = Twist()
        nav_twist.linear.x = 0.30

        teleop_twist = Twist()
        teleop_twist.linear.x = 0.50

        # Nav published recently at t=100.4
        self.node._last_nav_msg = nav_twist
        self.node._last_nav_time = 100.4

        # Teleop published at t=100.0 (aged 0.6s at t=100.6, exceeds 0.5s timeout)
        self.node._last_teleop_msg = teleop_twist
        self.node._last_teleop_time = start_time

        eval_time = 100.6  # 0.6s later: teleop expired, nav still fresh (age 0.2s)
        source, cmd, should_publish = self.node.evaluate_arbitration(eval_time)
        self.assertEqual(source, "NAV")
        self.assertAlmostEqual(cmd.linear.x, 0.30)
        self.assertTrue(should_publish)

    def test_06_both_timeout_safe_stop(self):
        """When both teleop and nav time out, arbiter transitions to NONE with zero velocity."""
        eval_time = 102.0
        self.node._last_nav_msg = Twist()
        self.node._last_nav_time = 100.0  # Expired (2.0s age)

        self.node._last_teleop_msg = Twist()
        self.node._last_teleop_time = 100.0  # Expired (2.0s age)

        self.node._zero_latched = False
        source, cmd, should_publish = self.node.evaluate_arbitration(eval_time)
        self.assertEqual(source, "NONE")
        self.assertEqual(cmd.linear.x, 0.0)
        self.assertEqual(cmd.angular.z, 0.0)
        self.assertTrue(should_publish)  # Must publish at least one zero-halt message


class TestVelocityPipelineConfiguration(unittest.TestCase):
    def test_07_nav2_params_smoother_and_collision_blocks(self):
        """Verify that velocity_smoother, collision_monitor, and cmd_vel_mux exist in nav2_params.yaml."""
        params_path = ROOT / "ros2_ws" / "src" / "gracemo_nav2" / "config" / "nav2_params.yaml"
        self.assertTrue(params_path.exists(), "nav2_params.yaml must exist")

        content = params_path.read_text()
        self.assertIn("velocity_smoother:", content)
        self.assertIn("collision_monitor:", content)
        self.assertIn("cmd_vel_mux:", content)
        self.assertIn('cmd_vel_in_topic: "cmd_vel_smoothed"', content)
        self.assertIn('cmd_vel_out_topic: "cmd_vel_safe"', content)
        self.assertIn('base_frame_id: "base_footprint"', content)
        self.assertIn('topic: "/scan"', content)

    def test_08_hardware_launch_stale_package_remediated(self):
        """Verify that hardware.launch.py references gracemo_nav2 and not the retired package."""
        hw_launch = ROOT / "ros2_ws" / "src" / "gracemo_hardware" / "launch" / "hardware.launch.py"
        content = hw_launch.read_text()
        self.assertNotIn('package="gracemo_command_coordinator"', content, "Stale package reference must not exist")
        self.assertIn('package="gracemo_nav2"', content, "Must reference gracemo_nav2")
        self.assertIn('executable="coordinator_node.py"', content, "Must reference coordinator_node.py executable")

    def test_09_navigation_launch_remappings(self):
        """Verify that gracemo_nav2 navigation_launch.py remaps velocity_smoother to cmd_vel_mux."""
        nav_launch = ROOT / "ros2_ws" / "src" / "gracemo_nav2" / "launch" / "navigation_launch.py"
        self.assertTrue(nav_launch.exists(), "navigation_launch.py must exist in gracemo_nav2")

        content = nav_launch.read_text()
        self.assertIn("('cmd_vel', 'cmd_vel_mux')", content, "velocity_smoother must consume cmd_vel_mux")
        self.assertIn("('cmd_vel', 'cmd_vel_nav')", content, "controller_server must output to cmd_vel_nav")

    def test_10_exploration_scripts_use_teleop(self):
        """Verify that exploration scripts publish to /cmd_vel_teleop."""
        for script_name in ["auto_explore.py", "closed_loop_nav.py", "smart_explore.py"]:
            p = ROOT / "scripts" / script_name
            content = p.read_text()
            self.assertIn("/cmd_vel_teleop", content, f"{script_name} must use /cmd_vel_teleop")


if __name__ == "__main__":
    unittest.main()
