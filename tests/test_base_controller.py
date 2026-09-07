#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase B Automated Verification Suite
Tests Level 1 Base Controller APF Safety Filter:
  1. Full emergency braking when obstacle <= stop_threshold (0.22m).
  2. Proportional deceleration in cushion zone (0.22m to 0.40m).
  3. Lateral repulsive steering deflection away from obstacles.
  4. Unobstructed velocity pass-through when clear.
"""

import unittest
import math
import numpy as np
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from gracemo_base_controller import BaseController

class MockLaserScan:
    def __init__(self, ranges, angle_min=-math.pi, angle_step=(2*math.pi)/360):
        self.ranges = ranges
        self.angle_min = angle_min
        self.angle_step = angle_step

class TestBaseControllerReflex(unittest.TestCase):
    def setUp(self):
        # Instantiate controller without connecting network signals for unit test
        self.controller = BaseController()
        # Ensure sensors wait is bypassed for unit testing
        self.controller.safety_cushion_dist = 0.40
        self.controller.stop_threshold_dist = 0.22
        self.controller.repulsion_influence_dist = 0.55

    def test_clear_corridor_pass_through(self):
        """When all ranges > 2.0m, commands must pass through without modification."""
        ranges = [3.0] * 360
        self.controller.latest_scan = MockLaserScan(ranges)

        safe_vx, safe_wz, active = self.controller.filter_velocity(0.40, 0.10)
        self.assertAlmostEqual(safe_vx, 0.40, places=2)
        self.assertAlmostEqual(safe_wz, 0.10, places=2)
        self.assertFalse(active, "Reflex shield should NOT be active in clear space")

    def test_emergency_stop_within_threshold(self):
        """When an obstacle is at 0.20m directly in front, forward velocity must clamp to 0."""
        # Laser index 180 is angle 0.0 (directly forward in [-pi, pi])
        ranges = [3.0] * 360
        ranges[180] = 0.20  # Dangerously close obstacle
        self.controller.latest_scan = MockLaserScan(ranges)

        safe_vx, safe_wz, active = self.controller.filter_velocity(0.40, 0.0)
        self.assertEqual(safe_vx, 0.0, "Forward velocity must be clamped to 0.0m/s")
        self.assertTrue(active, "Reflex shield must be active")

    def test_proportional_deceleration_cushion(self):
        """When an obstacle is at 0.31m (midway in cushion), velocity must proportionally brake."""
        ranges = [3.0] * 360
        ranges[180] = 0.31  # Midway between 0.22 and 0.40
        self.controller.latest_scan = MockLaserScan(ranges)

        safe_vx, safe_wz, active = self.controller.filter_velocity(0.40, 0.0)
        self.assertGreater(safe_vx, 0.0, "Velocity should not be completely zeroed")
        self.assertLess(safe_vx, 0.40, "Velocity must be decelerated from 0.40m/s")
        self.assertTrue(active)

    def test_lateral_obstacle_repulsion(self):
        """When an obstacle is on the front-left (+30 deg), APF must produce negative (rightward) yaw."""
        # Index corresponding to +30 degrees = +pi/6 rad
        idx_30deg = int(180 + (math.radians(30) / ((2 * math.pi) / 360)))
        ranges = [3.0] * 360
        ranges[idx_30deg] = 0.35  # Obstacle on front-left
        self.controller.latest_scan = MockLaserScan(ranges)

        safe_vx, safe_wz, active = self.controller.filter_velocity(0.30, 0.0)
        self.assertLess(safe_wz, 0.0, "Safety filter must repel rightward (negative wz) from left obstacle")
        self.assertTrue(active)

    def test_zero_semantic_knowledge(self):
        """Verify that BaseController does not contain any room names or static apartment coordinates."""
        self.assertFalse(hasattr(self.controller, "DEFAULT_ROOM_GEOMETRY"), "BaseController must not contain room geometry")
        self.assertFalse(hasattr(self.controller, "ROOM_ALIASES"), "BaseController must not contain room aliases")
        self.assertFalse(hasattr(self.controller, "goto_room"), "BaseController must not contain goto_room")

if __name__ == "__main__":
    unittest.main()
