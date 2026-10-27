#!/usr/bin/env python3
"""
Unit tests for Fast-Path Intent & Place Dispatcher (FastPathMatcher).
Validates sub-millisecond deterministic matching for STOP, GREET, IDENTITY,
and campus/apartment place extraction.
"""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
interaction_dir = ROOT / "vira_interaction" if (ROOT / "vira_interaction").exists() else ROOT / "graceemo_interaction"
sys.path.insert(0, str(interaction_dir))

from core.fast_path import FastPathMatcher
from core.state_machine import Expression


class TestFastPathMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = FastPathMatcher()

    def test_emergency_stop_intents(self):
        stop_phrases = ["Stop", "stop now", "please halt", "emergency freeze", "Cancel task", "WAIT"]
        for phrase in stop_phrases:
            res = self.matcher.match(phrase)
            self.assertTrue(res.matched, f"Failed for phrase: '{phrase}'")
            self.assertEqual(res.intent, "STOP")
            self.assertTrue(res.is_emergency)
            self.assertEqual(len(res.semantic_actions), 1)
            self.assertEqual(res.semantic_actions[0]["action"], "Stop")

    def test_greeting_intents(self):
        greetings = ["Hello GraceEMO", "Hi", "Hey there", "good morning", "Wave"]
        for phrase in greetings:
            res = self.matcher.match(phrase)
            self.assertTrue(res.matched, f"Failed for greeting: '{phrase}'")
            self.assertEqual(res.intent, "GREET")
            self.assertEqual(res.expression, Expression.HAPPY)

    def test_identity_intents(self):
        queries = ["who are you", "what is your name", "what's your name"]
        for phrase in queries:
            res = self.matcher.match(phrase)
            self.assertTrue(res.matched, f"Failed for identity: '{phrase}'")
            self.assertEqual(res.intent, "IDENTITY")
            self.assertIn("GraceEMO", res.response_text)
            self.assertTrue(
                "Vice Chancellor" in res.response_text
                or "academic leader" in res.response_text
            )

    def test_campus_navigation_places(self):
        test_cases = [
            ("Take me to the Robotics Lab", 2.5, 2.0, "Robotics Research Lab"),
            ("Go to central library", 45.0, 20.0, "Central Library (B37)"),
            ("Drive to Uni-Mall", 30.0, -40.0, "Uni-Mall Shopping Center"),
            ("Head to the kitchen", -5.0, -2.5, "Kitchen & Dining"),
            ("Navigate to master bedroom", -5.0, 2.2, "Master Bedroom"),
            ("Walk to home study", 4.5, 3.0, "Home Study"),
        ]

        for utterance, exp_x, exp_y, exp_name in test_cases:
            res = self.matcher.match(utterance)
            self.assertTrue(res.matched, f"Failed to match navigation for '{utterance}'")
            self.assertEqual(res.intent, "NAVIGATE")
            self.assertEqual(res.expression, Expression.FOCUS)

            nav_action = [a for a in res.semantic_actions if a["action"] == "NavigateTo"]
            self.assertEqual(len(nav_action), 1)
            params = nav_action[0]["params"]
            self.assertEqual(params["x"], exp_x)
            self.assertEqual(params["y"], exp_y)
            self.assertEqual(params["target_name"], exp_name)

    def test_unmatched_falls_through(self):
        unmatched = [
            "What is quantum computing?",
            "Can you explain the admissions criteria for B.Tech in CSE?",
            "Tell me about Dr. Mohit Arora's latest research publication.",
        ]
        for phrase in unmatched:
            res = self.matcher.match(phrase)
            self.assertFalse(res.matched, f"Phrase '{phrase}' should not have matched fast-path")


if __name__ == "__main__":
    unittest.main()
