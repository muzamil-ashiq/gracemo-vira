#!/usr/bin/env python3
"""
Unit and Contract tests for Authoritative Place Resolution (PlaceResolver).
Verifies:
  - Exact and phrase matching for campus landmarks (Robotics Lab, Library, Gate)
  - Apartment simulation topology (Kitchen, Bedroom, Study, Living Room)
  - Rejection of non-existent destinations (e.g. Moon Lab) with zero commands issued.
"""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "graceemo_interaction"))

from core.place_resolver import PlaceResolver, PlaceInfo
from core.fast_path import FastPathMatcher
from core.state_machine import Expression


class TestPlaceResolution(unittest.TestCase):
    def setUp(self):
        self.resolver = PlaceResolver()
        self.fast_path = FastPathMatcher()

    def test_campus_landmarks_resolution(self):
        # 1. Robotics Lab
        p = self.resolver.resolve_place("Take me to the Robotics Lab")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Robotics Research Lab")
        self.assertEqual(p.x, 2.5)
        self.assertEqual(p.y, 2.0)

        # 2. Central Library
        p = self.resolver.resolve_place("go to central library")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Central Library (B37)")
        self.assertEqual(p.x, 45.0)
        self.assertEqual(p.y, 20.0)

        # 3. Uni-Mall
        p = self.resolver.resolve_place("drive to Uni-Mall")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Uni-Mall Shopping Center")

    def test_simulation_apartment_topology(self):
        # Kitchen
        p = self.resolver.resolve_place("head to the kitchen")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Kitchen & Dining")
        self.assertEqual(p.x, -5.0)
        self.assertEqual(p.y, -2.5)

        # Bedroom
        p = self.resolver.resolve_place("walk to the master bedroom")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Master Bedroom")
        self.assertEqual(p.x, -5.0)
        self.assertEqual(p.y, 2.2)

        # Study
        p = self.resolver.resolve_place("navigate to the home study")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "Home Study")
        self.assertEqual(p.x, 4.5)
        self.assertEqual(p.y, 3.0)

    def test_unknown_location_rejection(self):
        """Golden Test #4 precondition: 'Moon Lab' is not known."""
        p, unknown_phrase = self.resolver.resolve_navigation_request("Take me to the Moon Lab.")
        self.assertIsNone(p)
        self.assertIsNotNone(unknown_phrase)
        self.assertIn("moon lab", unknown_phrase.lower())

        # Test through FastPathMatcher
        res = self.fast_path.match("Take me to the Moon Lab.")
        self.assertTrue(res.matched)
        self.assertEqual(res.intent, "UNKNOWN_DESTINATION")
        self.assertEqual(res.expression, Expression.SAD)
        self.assertEqual(len(res.semantic_actions), 0, "Unknown location MUST emit ZERO semantic actions")
        self.assertIn("do not have", res.response_text)
        self.assertIn("moon lab", res.response_text.lower())

    def test_list_known_places(self):
        known = self.resolver.list_known_places()
        self.assertTrue(len(known) >= 8)
        self.assertIn("Robotics Research Lab", known)
        self.assertIn("Central Library (B37)", known)
        self.assertIn("Kitchen & Dining", known)


if __name__ == "__main__":
    unittest.main()
