#!/usr/bin/env python3
"""
GRaCEmo ViRa — Milestone 1: Hand Subsystem Verification Suite
Verifies all 7 Acceptance Criteria for the Parallel-Jaw Two-Finger Gripper:
  1. Symmetric finger displacement.
  2. Joint limits respected (0.0m <= disp <= 0.034m).
  3. Non-self-colliding (minimum physical gap >= 0.012m).
  4. Deterministic open / close commands.
  5. Object enclosure width (>= 0.08m).
  6. Anti-False-Positive: Grasping empty air fails (state=EMPTY_CLOSED, returns False).
  7. Contact Confirmation: Grasping with contact succeeds (state=HOLD, returns True).
"""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from hand_controller import HandSubsystem, HandState


class TestHandSubsystem(unittest.TestCase):

    def setUp(self):
        # Use mock mode for deterministic, fast, unit-level validation
        self.hand = HandSubsystem(mock=True)

    def test_01_symmetric_displacement(self):
        """Criterion 1: Finger actuation must be strictly symmetric."""
        for target_w in [0.02, 0.04, 0.06, 0.078]:
            self.hand.open(width_m=target_w)
            l_pos, r_pos = self.hand.get_joint_positions()
            self.assertAlmostEqual(
                l_pos, r_pos, delta=1e-5,
                msg=f"Asymmetric displacement observed at target width {target_w}: L={l_pos}, R={r_pos}"
            )

    def test_02_joint_limits_respected(self):
        """Criterion 2: Prismatic joints must stay within [0.0, 0.034m] even under out-of-bound inputs."""
        # Test negative width request
        self.hand.open(width_m=-0.05)
        l_pos, r_pos = self.hand.get_joint_positions()
        self.assertGreaterEqual(l_pos, 0.0)
        self.assertGreaterEqual(r_pos, 0.0)
        self.assertAlmostEqual(l_pos, self.hand.MAX_STROKE_PER_FINGER_M, delta=1e-4)

        # Test extreme oversized width request (0.25m)
        self.hand.open(width_m=0.25)
        l_pos, r_pos = self.hand.get_joint_positions()
        self.assertLessEqual(l_pos, self.hand.MAX_STROKE_PER_FINGER_M + 1e-5)
        self.assertLessEqual(r_pos, self.hand.MAX_STROKE_PER_FINGER_M + 1e-5)
        self.assertAlmostEqual(l_pos, 0.0, delta=1e-4)  # 0.0 is wide open at 80mm

    def test_03_non_self_colliding_minimum_gap(self):
        """Criterion 3: Fully closed gripper must maintain >= 0.010m gap to prevent self-collision."""
        self.hand.close()
        width = self.hand.get_width()
        self.assertGreaterEqual(
            width, self.hand.MIN_GAP_M - 1e-5,
            msg=f"Gripper self-collision hazard! Width {width*1000:.1f}mm < {self.hand.MIN_GAP_M*1000:.1f}mm"
        )
        self.assertAlmostEqual(width, 0.010, delta=1e-4)

    def test_04_deterministic_open_close(self):
        """Criterion 4: Deterministic open and close operations."""
        # Open to 80mm
        res_open = self.hand.open(width_m=0.080)
        self.assertTrue(res_open)
        self.assertEqual(self.hand.get_state(), HandState.OPEN.value)
        self.assertAlmostEqual(self.hand.get_width(), 0.080, delta=1e-4)

        # Close to minimum (10mm)
        res_close = self.hand.close()
        self.assertTrue(res_close)
        self.assertEqual(self.hand.get_state(), HandState.EMPTY_CLOSED.value)
        self.assertAlmostEqual(self.hand.get_width(), self.hand.MIN_GAP_M, delta=1e-4)

    def test_05_object_enclosure_width(self):
        """Criterion 5: Maximum aperture must enclose standard objects up to 90-100mm."""
        res = self.hand.open(width_m=self.hand.DEFAULT_OPEN_WIDTH_M)
        self.assertTrue(res)
        width = self.hand.get_width()
        self.assertAlmostEqual(width, 0.090, delta=1e-4)
        
        self.hand.open(width_m=self.hand.MAX_GAP_M)
        self.assertAlmostEqual(self.hand.get_width(), 0.100, delta=1e-4)

    def test_06_anti_false_positive_grasp_air(self):
        """Criterion 6: Grasping empty air MUST NEVER report success."""
        self.hand.open(0.078)
        self.hand.set_mock_object(None)
        self.hand.set_mock_contact(False, False)

        success = self.hand.grasp()
        self.assertFalse(
            success,
            msg="CRITICAL VIOLATION: Hand falsely reported successful grasp on empty air!"
        )
        self.assertEqual(
            self.hand.get_state(), HandState.EMPTY_CLOSED.value,
            msg=f"Expected state EMPTY_CLOSED on air grasp, got {self.hand.get_state()}"
        )

    def test_07_contact_confirmed_grasp(self):
        """Criterion 7: Grasping an object with contact confirmed reports success and transitions to HOLD."""
        # Enclose a 40mm book
        book_thickness = 0.040
        self.hand.open(0.078)
        self.hand.set_mock_object(width_m=book_thickness)

        success = self.hand.grasp(target_id="book_math")
        self.assertTrue(
            success,
            msg="Hand failed to grasp object with valid contact!"
        )
        self.assertEqual(self.hand.get_state(), HandState.HOLD.value)
        self.assertAlmostEqual(self.hand.get_width(), book_thickness, delta=1e-4)
        left_c, right_c = self.hand.has_contact()
        self.assertTrue(left_c and right_c, "Dual pad contact not registered")

    def test_08_release_and_hold_semantics(self):
        """Verify release() and hold() operations."""
        # Grasp object first
        self.hand.open(0.078)
        self.hand.set_mock_object(0.040)
        self.hand.grasp()
        self.assertEqual(self.hand.get_state(), HandState.HOLD.value)

        # Release
        rel_ok = self.hand.release(open_width_m=0.078)
        self.assertTrue(rel_ok)
        self.assertEqual(self.hand.get_state(), HandState.OPEN.value)
        self.assertAlmostEqual(self.hand.get_width(), 0.078, delta=1e-4)
        left_c, right_c = self.hand.has_contact()
        self.assertFalse(left_c or right_c)

    def test_09_semantic_dsl_command_dispatcher(self):
        """Verify semantic commands exposed to K DSL / Manipulation Skill."""
        # hand::open
        res = self.hand.execute_command("hand::open[width: 0.070]")
        self.assertEqual(res["status"], "success")
        self.assertAlmostEqual(res["width_m"], 0.070, delta=1e-4)

        # hand::grasp (on air -> fail)
        self.hand.set_mock_object(None)
        res = self.hand.execute_command("hand::grasp")
        self.assertEqual(res["status"], "failed")
        self.assertFalse(res["grasped"])
        self.assertEqual(res["state"], "EMPTY_CLOSED")

        # hand::grasp (with object -> success)
        self.hand.open(0.078)
        self.hand.set_mock_object(0.040)
        res = self.hand.execute_command("hand::grasp[target: 'book_math']")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["grasped"])
        self.assertEqual(res["target"], "book_math")
        self.assertEqual(res["state"], "HOLD")

        # hand::release
        res = self.hand.execute_command("hand::release")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["state"], "OPEN")

    def test_10_far_most_to_inward_invariant(self):
        """Invariant: At open 100mm, displacement is 0.0. During closing, displacement increases symmetrically inward."""
        # 1. Open to max (100mm)
        self.hand.open(0.100)
        l_open, r_open = self.hand.get_joint_positions()
        self.assertAlmostEqual(l_open, 0.0, delta=1e-4)
        self.assertAlmostEqual(r_open, 0.0, delta=1e-4)
        self.assertAlmostEqual(self.hand.get_width(), 0.100, delta=1e-4)

        # 2. Open to default (90mm) -> 5mm inward stroke each: (100 - 90)/2 = 5mm
        self.hand.open(0.090)
        l_90, r_90 = self.hand.get_joint_positions()
        self.assertAlmostEqual(l_90, 0.005, delta=1e-4)
        self.assertAlmostEqual(r_90, 0.005, delta=1e-4)
        self.assertAlmostEqual(self.hand.get_width(), 0.090, delta=1e-4)

        # 3. Close to 40mm -> 30mm inward stroke each: (100 - 40)/2 = 30mm
        self.hand.close(target_width_m=0.040)
        l_close, r_close = self.hand.get_joint_positions()
        self.assertAlmostEqual(l_close, 0.030, delta=1e-4)
        self.assertAlmostEqual(r_close, 0.030, delta=1e-4)
        self.assertAlmostEqual(self.hand.get_width(), 0.040, delta=1e-4)
        self.assertGreater(l_close, l_90, "Left finger did not move inward during closing")
        self.assertGreater(r_close, r_90, "Right finger did not move inward during closing")


if __name__ == "__main__":
    unittest.main()

