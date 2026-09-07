#!/usr/bin/env python3
"""
GRaCEmo ViRa — Manipulation Skill & Grasp Verification Test Suite (5-DOF + In-Hand Carry)
Tests:
  1. Anti-False-Positive: Grasping air fails contact and emits failure.
  2. Slipped Object: Object not lifting with hand triggers GRASP_FAILED.
  3. Verified Grasp: Object tracking hand within tolerance confirms GRASP_CONFIRMED and enters STANCE_CARRY.
  4. In-Hand Carry Verification: Object stability and elevation monitored.
  5. Surface Placement: Controlled release and travel tuck.
  6. Typed K dispatcher command responses.
"""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain" / "skills"))
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from manipulation_skill import ManipulationSkill


class TestManipulationSkill(unittest.TestCase):

    def setUp(self):
        self.skill = ManipulationSkill(mock=True)

    def test_01_air_grasp_rejection(self):
        """Empty air grasp must never confirm grasp."""
        self.skill.hand.set_mock_object(None)
        self.skill.hand.set_mock_contact(False, False)
        res = self.skill.pick_and_verify(target_id="book_math", max_retries=1)
        self.assertFalse(res.verified)
        self.assertEqual(res.status, "CONTACT_FAILED")

    def test_02_slip_detection(self):
        """If contact occurs but object slips (adherence=0.0), verify grasp fails."""
        self.skill.hand.set_mock_object(0.035)
        self.skill.verifier._mock_adherence = 0.0
        res = self.skill.pick_and_verify(target_id="book_math", max_retries=1)
        self.assertFalse(res.verified)
        self.assertEqual(res.status, "GRASP_FAILED")

    def test_03_successful_physical_grasp_verification(self):
        """Valid grasp where object lifts with hand must confirm and enter STANCE_CARRY."""
        self.skill.hand.set_mock_object(0.035)
        self.skill.verifier._mock_adherence = 1.0
        res = self.skill.pick_and_verify(target_id="book_math", max_retries=1)
        self.assertTrue(res.verified)
        self.assertEqual(res.status, "GRASP_CONFIRMED")
        self.assertLessEqual(res.relative_error_m, res.tolerance_m)
        self.assertGreaterEqual(res.measured_object_delta_m, res.commanded_lift_m * 0.65)
        self.assertEqual(self.skill.state, "CARRY_READY")

    def test_04_carry_stability_verification(self):
        """In-hand carry state observation validates object retention."""
        self.skill.held_object = "book_math"
        self.skill.hand.set_mock_object(0.035)
        self.skill.verifier._mock_object_z = 0.45
        res_carry = self.skill.verify_carry("book_math")
        self.assertTrue(res_carry.verified)
        self.assertEqual(res_carry.status, "CARRY_VERIFIED")

    def test_05_surface_placement(self):
        """Surface placement places object, releases gripper, and returns to TRAVEL stance."""
        self.skill.held_object = "book_math"
        self.skill.hand.set_mock_object(0.035)
        self.skill.verifier._mock_object_z = 0.62
        res_place = self.skill.place_on_surface("book_math", surface_height_z=0.62)
        self.assertTrue(res_place.verified)
        self.assertEqual(res_place.status, "PLACEMENT_VERIFIED")
        self.assertEqual(self.skill.state, "IDLE")

    def test_06_typed_k_dispatcher(self):
        """Verify K primitives return typed status objects."""
        # Arm pick with object
        self.skill.hand.set_mock_object(0.035)
        self.skill.verifier._mock_adherence = 1.0
        res_cmd = self.skill.execute_command("arm::pick[target: 'book_math']")
        self.assertEqual(res_cmd["status"], "success")
        self.assertTrue(res_cmd["grasp_result"]["verified"])

        # Carry verify
        res_carry = self.skill.execute_command("arm::carry_verify")
        self.assertEqual(res_carry["status"], "success")
        self.assertEqual(res_carry["carry_result"]["status"], "CARRY_VERIFIED")

        # Place
        res_place = self.skill.execute_command("arm::place[target: 'book_math', surface_z: 0.62]")
        self.assertEqual(res_place["status"], "success")
        self.assertEqual(res_place["placement_result"]["status"], "PLACEMENT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
