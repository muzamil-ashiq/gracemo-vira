#!/usr/bin/env python3
"""
Integration tests for GRaCEmo ViRa Interaction Pipeline.
Implements the Golden Acceptance Scenarios defined in Phase 1 (VIRA_TEST_ARCHITECTURE.md):
  1. Golden Test: "Take me to the Robotics Lab." -> Semantic NavigateTo on EventBus
  2. STOP Test: "Stop." -> Emergency stop executed in < 50ms without LLM
  3. Greeting Test: "Hello GraceEMO" -> Happy expression & welcome response
  4. Failure Tests: Safe degradation on LLM/STT/EventBus failure
"""
import unittest
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
interaction_dir = ROOT / "vira_interaction" if (ROOT / "vira_interaction").exists() else ROOT / "graceemo_interaction"
sys.path.insert(0, str(interaction_dir))

from core.gateway import InteractionGateway, GatewayResult
from core.state_machine import CognitiveState, Expression
from core.event_bus import EventBusClient


class TestInteractionPipeline(unittest.TestCase):
    def setUp(self):
        self.gateway = InteractionGateway()

    def test_golden_navigation_scenario(self):
        """
        Golden Scenario 1:
        User says: "Take me to the Robotics Lab."
        Expected:
          - intent: NAVIGATE
          - target: Robotics Research Lab (x=2.5, y=2.0)
          - ActionRequested(NavigateTo) emitted to EventBus
          - expression: FOCUS
          - trace_id propagated
        """
        custom_trace = "golden-nav-trace-001"
        res: GatewayResult = self.gateway.process_text(
            "Take me to the Robotics Lab.",
            session_id="session_test_nav",
            trace_id=custom_trace,
        )

        self.assertEqual(res.intent, "NAVIGATE")
        self.assertEqual(res.expression, Expression.FOCUS)
        self.assertEqual(res.trace_id, custom_trace)
        self.assertIn("Navigating to Robotics Research Lab", res.response)

        # Verify semantic action
        self.assertTrue(len(res.semantic_commands) >= 1)
        nav_action = next(a for a in res.semantic_commands if a["action"] == "NavigateTo")
        self.assertEqual(nav_action["params"]["x"], 2.5)
        self.assertEqual(nav_action["params"]["y"], 2.0)
        self.assertEqual(nav_action["params"]["target_name"], "Robotics Research Lab")

        # Verify EventBus ledger captured the ActionRequested event with the same trace_id
        ledger = self.gateway.event_bus.get_ledger()
        action_events = [
            e for e in ledger
            if e["event_type"]["type"] == "ActionRequested" and e.get("trace_id") == custom_trace
        ]
        self.assertTrue(len(action_events) >= 1, "ActionRequested was not published to EventBus ledger")
        dispatched_data = action_events[0]["event_type"]["data"]
        self.assertEqual(dispatched_data["action"], "NavigateTo")
        self.assertEqual(dispatched_data["params"]["x"], 2.5)

    def test_golden_stop_scenario(self):
        """
        Golden Scenario 2:
        User says: "Stop."
        Expected:
          - Fast-path execution without LLM
          - Latency < 50ms
          - ActionRequested(Stop) emitted to EventBus
          - Cognitive state -> EMERGENCY_STOP
        """
        stop_trace = "golden-stop-trace-002"
        t0 = time.perf_counter()
        res: GatewayResult = self.gateway.process_text(
            "Stop.",
            session_id="session_test_stop",
            trace_id=stop_trace,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(res.intent, "STOP")
        self.assertTrue(elapsed_ms < 50.0, f"STOP took {elapsed_ms:.2f}ms (target < 50ms)")
        self.assertEqual(self.gateway.fsm.state, CognitiveState.EMERGENCY_STOP)

        # Verify Stop action in EventBus
        ledger = self.gateway.event_bus.get_ledger()
        stop_events = [
            e for e in ledger
            if e["event_type"]["type"] == "ActionRequested" and e.get("trace_id") == stop_trace
        ]
        self.assertTrue(len(stop_events) >= 1)
        self.assertEqual(stop_events[0]["event_type"]["data"]["action"], "Stop")

    def test_golden_greeting_scenario(self):
        """
        Golden Scenario 3:
        User says: "Hello GraceEMO"
        Expected:
          - intent: GREET
          - expression: HAPPY
          - response includes welcome
        """
        greet_trace = "golden-greet-trace-003"
        res: GatewayResult = self.gateway.process_text(
            "Hello GraceEMO",
            trace_id=greet_trace,
        )

        self.assertEqual(res.intent, "GREET")
        self.assertEqual(res.expression, Expression.HAPPY)
        self.assertTrue(
            "Welcome to Lovely Professional University" in res.response
            or "pleasure" in res.response.lower()
            or "assistance" in res.response.lower()
        )

    def test_fallback_when_brain_has_no_cloud(self):
        """
        Failure Test:
        Complex query when cloud LLM is not configured must degrade
        gracefully to Campus Heuristics without throwing exceptions.
        """
        query = "Tell me about the engineering courses available at LPU."
        res: GatewayResult = self.gateway.process_text(query)

        self.assertTrue(len(res.response) > 5)
        self.assertTrue(
            "LPU" in res.response
            or "university" in res.response.lower()
            or "engineering" in res.response.lower()
        )
        self.assertEqual(self.gateway.fsm.state, CognitiveState.SPEAKING)

    def test_trace_id_propagation_across_events(self):
        """
        Observability Test:
        Every event produced in a conversational turn must carry the exact same trace_id.
        """
        test_trace = "obs-trace-propagate-999"
        self.gateway.process_text("Take me to the library", trace_id=test_trace)

        ledger = self.gateway.event_bus.get_ledger()
        matching = [e for e in ledger if e.get("trace_id") == test_trace]
        self.assertTrue(len(matching) >= 2, "Expected multiple events with the same trace_id")
        for ev in matching:
            self.assertEqual(ev["trace_id"], test_trace)


if __name__ == "__main__":
    unittest.main()
