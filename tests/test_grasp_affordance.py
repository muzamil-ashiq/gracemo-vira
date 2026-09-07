#!/usr/bin/env python3
"""
Unit tests for GraspAffordanceSynthesizer.
Verifies:
  - Bounding box dimension analysis.
  - Standoff depth and guaranteed palm clearance.
  - Zero palm collision guarantee.
  - Candidate 6D grasp generation.
"""

import unittest
import numpy as np
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain" / "skills"))
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from grasp_affordance import GraspAffordanceSynthesizer, GraspCandidate
from arm_kinematics import ArmKinematics


class TestGraspAffordance(unittest.TestCase):

    def setUp(self):
        self.kinematics = ArmKinematics()
        self.affordance = GraspAffordanceSynthesizer(kinematics=self.kinematics)

    def test_book_math_affordance(self):
        """Verify standoff and palm clearance for book_math."""
        obj_center = np.array([0.380, 0.0, 0.030])
        cand = self.affordance.synthesize_grasp("book_math", obj_center)

        self.assertIsNotNone(cand)
        self.assertEqual(cand.object_id, "book_math")
        self.assertAlmostEqual(cand.expected_aperture_m, 0.060, delta=1e-3)
        self.assertGreater(cand.standoff_clearance_m, 0.010, "Palm clearance must be > 10mm to avoid collision")
        self.assertAlmostEqual(cand.target_roll, 0.0, delta=1e-3)
        self.assertAlmostEqual(cand.target_pitch, 0.0, delta=1e-3)

        # Grasp position must be reachable by 6-DOF IK
        ok, q = self.kinematics.solve_human_elbow_down(
            cand.grasp_pos_sh,
            target_pitch=cand.target_pitch,
            target_roll=cand.target_roll,
            shoulder_roll=cand.shoulder_roll
        )
        self.assertTrue(ok, f"Grasp pose {cand.grasp_pos_sh} must be reachable with human elbow-down IK")

    def test_pre_grasp_hover_offset(self):
        """Pre-grasp hover must be backed away and elevated."""
        obj_center = np.array([0.400, 0.0, 0.035])
        cand = self.affordance.synthesize_grasp("book_math", obj_center)
        self.assertLess(cand.pre_grasp_hover_sh[0], cand.grasp_pos_sh[0])
        self.assertGreater(cand.pre_grasp_hover_sh[2], cand.grasp_pos_sh[2])


if __name__ == "__main__":
    unittest.main()
