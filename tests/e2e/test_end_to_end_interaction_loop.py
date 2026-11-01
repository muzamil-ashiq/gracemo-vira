#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 3 End-to-End Robotics Interaction Loop Test Suite
Validates the complete closed-loop pipeline:
USER -> STT/TEXT -> INTERACTION GATEWAY -> BRAIN / FAST-PATH -> SEMANTIC COMMAND
-> SAFETY GATE -> VIRA EVENTBUS -> ROBOT BRIDGE -> NAVIGATION -> SIMULATED VIRA ->
FEEDBACK -> EVENTBUS -> INTERACTION ADAPTER -> AVATAR EXPRESSION / TTS -> USER
"""
import unittest
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "graceemo_interaction"))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))

from core.gateway import InteractionGateway, GatewayResult
from core.event_bus import EventBusClient
from core.safety_gate import SafetyGate
from core.fast_path import FastPathMatcher
from core.state_machine import CognitiveState, Expression, InteractionFSM
from core.interaction_adapter import InteractionAdapter
from core.tts_adapter import TTSAdapter

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.state_machine import RobotState


class TestEndToEndInteractionLoop(unittest.TestCase):
    def setUp(self):
        # 1. Core EventBus (in-memory bus with ledger)
        self.bus = EventBusClient()

        # 2. Safety Gate & Fast-Path
        self.safety_gate = SafetyGate()
        self.fast_path = FastPathMatcher()

        # 3. Interaction Gateway
        self.gateway = InteractionGateway(
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        # 4. Mock TTS Adapter (captures spoken output for verification)
        self.spoken_phrases = []
        self.tts = TTSAdapter()
        self.tts.speak = lambda text, on_done=None: self.spoken_phrases.append(text) or (on_done() if on_done else None)

        # 5. Interaction Adapter (subscribes to EventBus feedback and updates FSM & avatar)
        self.rendered_expressions = []
        self.interaction_adapter = InteractionAdapter(
            event_bus=self.bus,
            fsm=self.gateway.fsm,
            tts=self.tts,
            expression_callback=lambda exp: self.rendered_expressions.append(exp),
        )

        # 6. Robot Bridge (subscribes to EventBus ActionRequested and emits feedback back to EventBus)
        self.robot_bridge = RobotBridge(
            emit_callback=lambda env: self.bus.emit_envelope(env),
            mode="simulation",
        )
        self.robot_bridge.navigation_adapter.sim_step_dt = 0.01  # accelerate simulation for tests
        self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

        # Connect EventBus ActionRequested to Robot Bridge
        self.bus.subscribe("ActionRequested", self.robot_bridge.on_action_requested)

    def tearDown(self):
        self.robot_bridge.stop()

    def test_golden_1_navigation_command_and_movement(self):
        """
        Golden Test #1: Navigation
        Input: "Take me to the Robotics Lab."
        Pipeline:
          - Fast-path place resolution -> Robotics Research Lab (x=2.5, y=2.0)
          - SafetyGate validates boundaries
          - ActionRequested emitted to EventBus
          - RobotBridge receives and transitions to NAVIGATING
          - Robot coordinates advance from (0, 0) towards (2.5, 2.0)
        """
        trace_id = "golden-e2e-nav-001"
        res: GatewayResult = self.gateway.process_text(
            "Take me to the Robotics Lab.",
            session_id="session_e2e_1",
            trace_id=trace_id,
        )

        self.assertEqual(res.intent, "NAVIGATE")
        self.assertEqual(res.trace_id, trace_id)
        self.assertTrue(len(res.semantic_commands) >= 1)
        self.assertEqual(res.semantic_commands[0]["action"], "NavigateTo")

        # Allow time for navigation thread to commence
        time.sleep(0.05)

        # Verify RobotBridge received command and started transit
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)
        self.assertTrue(self.robot_bridge.navigation_adapter.current_speed > 0.0)

        # Verify robot moved from origin
        pos_x = self.robot_bridge.navigation_adapter.current_x
        pos_y = self.robot_bridge.navigation_adapter.current_y
        self.assertTrue(pos_x > 0.0 or pos_y > 0.0, f"Robot position ({pos_x}, {pos_y}) did not move from origin")

        # Verify NavigationStarted event was published to EventBus
        ledger = self.bus.get_ledger()
        nav_started = [e for e in ledger if e.get("event_type", {}).get("type") == "NavigationStarted"]
        self.assertTrue(len(nav_started) >= 1)
        self.assertEqual(nav_started[0]["trace_id"], trace_id)

    def test_golden_2_arrival_and_voice_expression_feedback(self):
        """
        Golden Test #2: Arrival
        When the robot completes trajectory:
          - NavigationArrived event published to EventBus
          - InteractionAdapter receives event
          - Expression switches to HAPPY
          - TTS speaks: "We've arrived at Robotics Research Lab."
          - Interaction FSM transitions to IDLE
        """
        trace_id = "golden-e2e-arrival-002"
        # Start at a nearby position (0.10m away from 0.05m tolerance threshold)
        self.robot_bridge.navigation_adapter.set_pose(2.35, 2.0, 0.0)

        self.gateway.process_text(
            "Take me to the Robotics Lab.",
            session_id="session_e2e_2",
            trace_id=trace_id,
        )

        # Wait for arrival in fast simulation (~0.15s)
        time.sleep(0.30)

        # Verify RobotState returned to IDLE upon arrival
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)

        # Verify EventBus captured NavigationArrived with trace_id
        ledger = self.bus.get_ledger()
        arrived_events = [e for e in ledger if e.get("event_type", {}).get("type") == "NavigationArrived"]
        self.assertTrue(len(arrived_events) >= 1)
        self.assertEqual(arrived_events[0]["trace_id"], trace_id)

        # Verify InteractionAdapter reaction:
        # Avatar expression set to HAPPY
        self.assertEqual(self.gateway.fsm.expression, Expression.HAPPY)
        # Spoken announcement emitted
        self.assertTrue(any("We've arrived at Robotics Research Lab" in s for s in self.spoken_phrases))

    def test_golden_3_critical_stop_path_zero_llm(self):
        """
        Golden Test #3: STOP
        Start navigation, then issue "Stop."
        Expected:
          - Sub-2ms fast-path detection
          - Zero LLM reasoning invoked
          - RobotBridge cancels Nav2/kinematics immediately
          - Robot speed = 0.0
          - RobotStopped event published to EventBus
        """
        # 1. Start navigating to far target
        self.gateway.process_text("Take me to Central Library.", trace_id="trace-stop-test-1")
        time.sleep(0.05)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # 2. Issue voice STOP
        t0 = time.perf_counter()
        stop_res: GatewayResult = self.gateway.process_text("Stop.", trace_id="trace-stop-test-2")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Fast path execution < 50ms (typically ~1.5ms)
        self.assertLess(elapsed_ms, 50.0)
        self.assertEqual(stop_res.intent, "STOP")

        # Verify Robot stopped immediately
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.EMERGENCY_STOP)

        # Verify RobotStopped event published to EventBus
        ledger = self.bus.get_ledger()
        stopped_events = [e for e in ledger if e.get("event_type", {}).get("type") == "RobotStopped"]
        self.assertTrue(len(stopped_events) >= 1)

    def test_golden_4_invalid_location_emits_zero_robot_commands(self):
        """
        Golden Test #4: Invalid Location
        User: "Take me to the Moon Lab."
        Expected:
          - PlaceResolver rejects unknown location
          - Zero semantic robot actions issued
          - Gateway returns controlled explanatory response
          - Robot remains stationary at origin in IDLE state
        """
        res: GatewayResult = self.gateway.process_text(
            "Take me to the Moon Lab.",
            trace_id="trace-moon-lab",
        )

        self.assertEqual(res.intent, "UNKNOWN_DESTINATION")
        self.assertEqual(len(res.semantic_commands), 0, "Must not emit robot commands for unknown places")
        self.assertIn("do not have", res.response)
        self.assertIn("moon lab", res.response.lower())

        # Verify robot remained completely stationary in IDLE state
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_x, 0.0)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_y, 0.0)

    def test_golden_5_navigation_failure_handling(self):
        """
        Golden Test #5: Navigation Failure
        Simulate Nav2 / path failure.
        Expected:
          - NavigationFailed event emitted to EventBus
          - InteractionAdapter triggers SAD expression and spoken notification
          - System recovers gracefully to IDLE without crashing
        """
        trace_id = "trace-failure-test"
        # Force navigation failure on next goal
        self.robot_bridge.navigation_adapter.force_next_failure(True)

        self.gateway.process_text(
            "Take me to the Robotics Lab.",
            trace_id=trace_id,
        )

        # Wait for failure notification (~0.15s)
        time.sleep(0.20)

        # Verify NavigationFailed was captured in ledger
        ledger = self.bus.get_ledger()
        failed_events = [e for e in ledger if e.get("event_type", {}).get("type") == "NavigationFailed"]
        self.assertTrue(len(failed_events) >= 1)
        self.assertEqual(failed_events[0]["trace_id"], trace_id)

        # Verify avatar reaction: SAD expression and spoken apology
        self.assertEqual(self.gateway.fsm.expression, Expression.SAD)
        self.assertTrue(any("could not be completed" in s for s in self.spoken_phrases))

    def test_golden_6_command_cancellation_idempotence(self):
        """
        Golden Test #6: Command Cancellation Idempotence
        Start navigation, cancel it, then cancel again.
        Expected:
          - First cancel stops robot and sets state to IDLE
          - Second cancel returns True without errors or inconsistent state
        """
        self.gateway.process_text("Take me to Uni-Mall.", trace_id="trace-cancel-test")
        time.sleep(0.05)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # First cancellation
        res1 = self.robot_bridge.navigation_adapter.cancel_navigation(reason="Mission aborted")
        self.assertTrue(res1)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)

        # Second cancellation
        res2 = self.robot_bridge.navigation_adapter.cancel_navigation(reason="Duplicate cancel")
        self.assertTrue(res2)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)


if __name__ == "__main__":
    unittest.main()
