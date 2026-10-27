#!/usr/bin/env python3
"""
Unit tests for GRaCEmo ViRa Cognitive Interaction State Machine (InteractionFSM).
Validates allowed transitions, illegal transition rejection, emergency stop overrides,
and the strict decoupling between Cognitive State and Emotional Expression.
"""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
interaction_dir = ROOT / "vira_interaction" if (ROOT / "vira_interaction").exists() else ROOT / "graceemo_interaction"
sys.path.insert(0, str(interaction_dir))

from core.state_machine import CognitiveState, Expression, InteractionFSM


class TestInteractionFSM(unittest.TestCase):
    def setUp(self):
        self.fsm = InteractionFSM(initial_state=CognitiveState.BOOT)

    def test_initial_state(self):
        self.assertEqual(self.fsm.state, CognitiveState.BOOT)
        self.assertEqual(self.fsm.expression, Expression.IDLE)

    def test_valid_conversational_cycle(self):
        # BOOT -> IDLE
        self.assertTrue(self.fsm.transition_to(CognitiveState.IDLE, reason="Boot complete"))
        self.assertEqual(self.fsm.state, CognitiveState.IDLE)
        self.assertEqual(self.fsm.expression, Expression.IDLE)

        # IDLE -> LISTENING
        self.assertTrue(self.fsm.transition_to(CognitiveState.LISTENING, reason="User began speaking"))
        self.assertEqual(self.fsm.state, CognitiveState.LISTENING)
        self.assertEqual(self.fsm.expression, Expression.FOCUS)

        # LISTENING -> THINKING
        self.assertTrue(self.fsm.transition_to(CognitiveState.THINKING, reason="VAD speech endpoint reached"))
        self.assertEqual(self.fsm.state, CognitiveState.THINKING)
        self.assertEqual(self.fsm.expression, Expression.INTENT)

        # THINKING -> EXECUTING
        self.assertTrue(self.fsm.transition_to(CognitiveState.EXECUTING, reason="Action dispatched to robot"))
        self.assertEqual(self.fsm.state, CognitiveState.EXECUTING)
        self.assertEqual(self.fsm.expression, Expression.FOCUS)

        # EXECUTING -> WAITING
        self.assertTrue(self.fsm.transition_to(CognitiveState.WAITING, reason="Robot traversing to waypoint"))
        self.assertEqual(self.fsm.state, CognitiveState.WAITING)

        # WAITING -> IDLE
        self.assertTrue(self.fsm.transition_to(CognitiveState.IDLE, reason="Task complete"))
        self.assertEqual(self.fsm.state, CognitiveState.IDLE)
        self.assertEqual(self.fsm.expression, Expression.IDLE)

    def test_illegal_transitions_rejected(self):
        # BOOT cannot jump directly to SPEAKING or EXECUTING
        self.assertFalse(self.fsm.transition_to(CognitiveState.SPEAKING))
        self.assertEqual(self.fsm.state, CognitiveState.BOOT)

        self.assertFalse(self.fsm.transition_to(CognitiveState.EXECUTING))
        self.assertEqual(self.fsm.state, CognitiveState.BOOT)

        # Move to IDLE
        self.fsm.transition_to(CognitiveState.IDLE)

        # IDLE cannot jump directly to WAITING
        self.assertFalse(self.fsm.transition_to(CognitiveState.WAITING))
        self.assertEqual(self.fsm.state, CognitiveState.IDLE)

    def test_emergency_stop_from_any_state(self):
        states_to_test = [
            CognitiveState.IDLE,
            CognitiveState.LISTENING,
            CognitiveState.THINKING,
            CognitiveState.SPEAKING,
            CognitiveState.EXECUTING,
            CognitiveState.WAITING,
            CognitiveState.ERROR,
        ]

        for s in states_to_test:
            fsm = InteractionFSM(initial_state=CognitiveState.BOOT)
            fsm.transition_to(CognitiveState.IDLE)
            if s != CognitiveState.IDLE:
                if s in [CognitiveState.LISTENING, CognitiveState.THINKING, CognitiveState.SPEAKING, CognitiveState.EXECUTING, CognitiveState.WAITING]:
                    fsm.transition_to(CognitiveState.LISTENING)
                    if s != CognitiveState.LISTENING:
                        fsm.transition_to(CognitiveState.THINKING)
                        if s in [CognitiveState.SPEAKING, CognitiveState.EXECUTING, CognitiveState.WAITING]:
                            fsm.transition_to(CognitiveState.EXECUTING)
                            if s == CognitiveState.WAITING:
                                fsm.transition_to(CognitiveState.WAITING)
                elif s == CognitiveState.ERROR:
                    fsm.transition_to(CognitiveState.ERROR)

            # Trigger emergency stop
            fsm.emergency_stop(reason="Test E-STOP")
            self.assertEqual(fsm.state, CognitiveState.EMERGENCY_STOP)
            self.assertEqual(fsm.expression, Expression.ANGRY)

    def test_decoupling_state_and_expression(self):
        self.fsm.transition_to(CognitiveState.IDLE)
        self.fsm.transition_to(CognitiveState.EXECUTING)
        self.assertEqual(self.fsm.state, CognitiveState.EXECUTING)

        # Override expression explicitly to HAPPY without changing state
        self.fsm.set_expression(Expression.HAPPY, reason="Destination spotted")
        self.assertEqual(self.fsm.state, CognitiveState.EXECUTING)
        self.assertEqual(self.fsm.expression, Expression.HAPPY)

    def test_listeners_notified(self):
        transitions = []
        self.fsm.add_listener(lambda prev, curr, exp, reason: transitions.append((prev, curr, exp, reason)))

        self.fsm.transition_to(CognitiveState.IDLE, reason="Booted")
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0][0], CognitiveState.BOOT)
        self.assertEqual(transitions[0][1], CognitiveState.IDLE)


if __name__ == "__main__":
    unittest.main()
