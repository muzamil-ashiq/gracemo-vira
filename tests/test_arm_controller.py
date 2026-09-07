#!/usr/bin/env python3
"""
GRaCEmo ViRa — 5-DOF Arm Controller Unit Verification
Tests:
  1. Initial stance configuration (STANCE_TRAVEL).
  2. Clamping to strict physical limits across 5 joints.
  3. Canonical stance transitions (TRAVEL, CARRY, TABLE_REACH).
  4. End-effector forward pose calculation.
"""

import unittest
import math
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from arm_controller import ArmController


class TestArmController(unittest.TestCase):

    def setUp(self):
        self.arm = ArmController(mock=True)

    def test_01_initial_stance(self):
        """Arm should initialize in STANCE_TRAVEL with 6 joints."""
        q = self.arm.get_joint_positions()
        self.assertEqual(len(q), 7)
        np.testing.assert_allclose(q, self.arm.kinematics.STANCE_TRAVEL, atol=1e-5)

    def test_02_joint_limit_clamping(self):
        """Extreme commands must be clamped to safe joint limits."""
        extreme_q = np.array([5.0, -10.0, 3.0, -2.0, 4.0, 2.0, 6.0])
        self.arm.command_joint_angles(extreme_q)
        q = self.arm.get_joint_positions()
        for i in range(7):
            self.assertGreaterEqual(q[i], self.arm.kinematics.JOINT_LIMITS[i, 0] - 1e-5)
            self.assertLessEqual(q[i], self.arm.kinematics.JOINT_LIMITS[i, 1] + 1e-5)

    def test_03_stance_transitions(self):
        """Test transitioning between TABLE_REACH, CARRY, and TRAVEL."""
        # 1. TABLE_REACH
        ok = self.arm.move_to_stance("TABLE_REACH")
        self.assertTrue(ok)
        np.testing.assert_allclose(self.arm.get_joint_positions(), self.arm.kinematics.STANCE_TABLE_REACH, atol=1e-4)

        # 2. CARRY
        ok = self.arm.move_to_stance("CARRY")
        self.assertTrue(ok)
        np.testing.assert_allclose(self.arm.get_joint_positions(), self.arm.kinematics.STANCE_CARRY, atol=1e-4)

        # 3. TRAVEL
        ok = self.arm.move_to_stance("TRAVEL")
        self.assertTrue(ok)
        np.testing.assert_allclose(self.arm.get_joint_positions(), self.arm.kinematics.STANCE_TRAVEL, atol=1e-4)

    def test_04_ee_pose_tracking(self):
        """Verify get_ee_pose computes palm coordinates in robot frame."""
        self.arm.move_to_stance("TRAVEL")
        p_ee, R_ee = self.arm.get_ee_pose()
        self.assertEqual(len(p_ee), 3)
        self.assertEqual(R_ee.shape, (3, 3))
        # In TRAVEL stance, palm should be tucked close to torso (X < 0.35m, Z > 0.10m)
        self.assertLess(p_ee[0], 0.35)
        self.assertGreater(p_ee[2], 0.10)


if __name__ == "__main__":
    unittest.main()
