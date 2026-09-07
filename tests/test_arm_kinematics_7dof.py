#!/usr/bin/env python3
"""
Unit tests for Canonical 7-DOF Humanoid Arm Kinematics & 6D Task-Space Solver.
"""

import unittest
import math
import numpy as np
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from arm_kinematics import ArmKinematics


class TestArmKinematics7DOF(unittest.TestCase):

    def setUp(self):
        self.kinematics = ArmKinematics()

    def test_dimensions_and_joint_limits(self):
        self.assertEqual(self.kinematics.JOINT_LIMITS.shape, (7, 2))
        self.assertEqual(self.kinematics.STANCE_TRAVEL.shape, (7,))
        self.assertEqual(self.kinematics.STANCE_CARRY.shape, (7,))
        self.assertEqual(self.kinematics.STANCE_TABLE_REACH.shape, (7,))
        self.assertEqual(self.kinematics.L1, 0.22)
        self.assertEqual(self.kinematics.L2, 0.22)
        self.assertEqual(self.kinematics.L3, 0.075)

    def test_forward_kinematics_travel_stance(self):
        p_ee, R_ee, tfs = self.kinematics.forward_kinematics(self.kinematics.STANCE_TRAVEL)
        self.assertEqual(p_ee.shape, (3,))
        self.assertEqual(R_ee.shape, (3, 3))
        self.assertEqual(len(tfs), 8)
        self.assertGreater(p_ee[2], 0.15)

    def test_jacobian_shape_and_rank(self):
        q = self.kinematics.STANCE_TABLE_REACH
        J = self.kinematics.compute_jacobian_6d(q)
        self.assertEqual(J.shape, (6, 7))
        rank = np.linalg.matrix_rank(J)
        self.assertEqual(rank, 6, f"Expected full rank 6, got {rank}")

    def test_ik_convergence_reach_target(self):
        target_sh = np.array([0.38, 0.04, 0.03])
        ok, q_sol = self.kinematics.inverse_kinematics(
            target_pos=target_sh,
            target_pitch=0.0,
            target_roll=0.0,
            preferred_swivel=math.radians(20.0),
            swivel_range=(math.radians(15.0), math.radians(25.0))
        )
        self.assertTrue(ok, "7-DOF IK failed to converge")
        p_check, R_check, tfs = self.kinematics.forward_kinematics(q_sol)
        pos_err = np.linalg.norm(target_sh - p_check)
        self.assertLess(pos_err, 0.002, f"Position error too large: {pos_err*1000:.2f}mm")

        # Check elbow is DOWN (Z_elbow < Z_ee)
        p_elbow = tfs[3][:3, 3]
        self.assertLess(p_elbow[2], p_check[2], f"Elbow not down: elbow Z={p_elbow[2]} >= EE Z={p_check[2]}")

        # Check elbow swivel angle (shoulder_roll) is within natural range
        sh_roll_deg = math.degrees(q_sol[2])
        self.assertGreaterEqual(sh_roll_deg, 10.0)
        self.assertLessEqual(sh_roll_deg, 30.0)

    def test_sideways_reach_and_wrist_yaw(self):
        target_sh = np.array([0.35, 0.08, 0.04])
        ok, q_sol = self.kinematics.inverse_kinematics(
            target_pos=target_sh,
            target_pitch=0.0,
            target_roll=0.0,
            preferred_swivel=math.radians(20.0)
        )
        self.assertTrue(ok)
        p_check, _, tfs = self.kinematics.forward_kinematics(q_sol)
        self.assertLess(np.linalg.norm(target_sh - p_check), 0.002)
        self.assertGreater(abs(q_sol[0]), 0.05)  # Shoulder yaw
        self.assertGreater(abs(q_sol[2]), 0.10)  # Shoulder roll


if __name__ == "__main__":
    unittest.main()
