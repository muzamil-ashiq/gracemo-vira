#!/usr/bin/env python3
"""
Unit tests for GRaCEmo ViRa Human-Interaction Behavior Manager.
Validates:
  - 8-State Behavior Lifecycle (IDLE, PERSON_DETECTED, OBSERVATION_60S, INTERACTION,
                                MANUAL_COMMAND, FOLLOW_PERSON, SAFE_STOP, FAULT)
  - 60-Second Stationary Observation Timer & Auto-Timeout
  - Explicit Consent Requirement (Wake Word or Button) Before Interaction
  - Sub-50ms Stop Command Priority Over All Motion
  - Person-Following Target Tracking & Immediate Stop on Target Loss
  - Range Clamping to Safe Hardware Velocity Limits
"""
import time
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "vira_interaction"))

from core.behavior_manager import (
    BehaviorState,
    HumanInteractionBehaviorManager,
    PersonDetection,
    StructuredMotionRequest,
)


class TestHumanInteractionBehavior(unittest.TestCase):
    def setUp(self):
        self.mgr = HumanInteractionBehaviorManager(
            observation_timeout_sec=60.0,
            tracking_loss_timeout_sec=0.50,
            max_safe_linear_mps=0.35,
            max_safe_angular_rps=0.75,
        )

    def test_initial_state_idle_and_zero_velocity(self):
        self.assertEqual(self.mgr.state, BehaviorState.IDLE)
        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

    def test_person_detection_and_observation_phase(self):
        # 1. Unconfirmed detection moves to PERSON_DETECTED
        d1 = PersonDetection(
            person_id="person_01",
            confidence=0.75,
            distance_m=2.0,
            bearing_rad=0.0,
            confirmed=False,
            timestamp=time.time(),
        )
        self.mgr.on_person_detected(d1)
        self.assertEqual(self.mgr.state, BehaviorState.PERSON_DETECTED)
        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

        # 2. Confirmed detection enters OBSERVATION_60S
        d2 = PersonDetection(
            person_id="person_01",
            confidence=0.92,
            distance_m=2.0,
            bearing_rad=0.0,
            confirmed=True,
            timestamp=time.time(),
        )
        self.mgr.on_person_detected(d2)
        self.assertEqual(self.mgr.state, BehaviorState.OBSERVATION_60S)
        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

    def test_observation_60s_timer_expires_to_idle(self):
        # Move to OBSERVATION_60S
        d = PersonDetection(
            person_id="person_02",
            confidence=0.95,
            distance_m=2.2,
            bearing_rad=0.0,
            confirmed=True,
            timestamp=time.time(),
        )
        self.mgr.on_person_detected(d)
        self.assertEqual(self.mgr.state, BehaviorState.OBSERVATION_60S)

        # Fast forward time past 60.0 seconds
        now = time.time()
        self.mgr.update_tick(now=now + 60.5)
        self.assertEqual(self.mgr.state, BehaviorState.IDLE)

    def test_wake_trigger_initiates_interaction(self):
        # Move to OBSERVATION_60S
        d = PersonDetection(
            person_id="person_03",
            confidence=0.90,
            distance_m=1.8,
            bearing_rad=0.1,
            confirmed=True,
            timestamp=time.time(),
        )
        self.mgr.on_person_detected(d)
        self.assertEqual(self.mgr.state, BehaviorState.OBSERVATION_60S)

        # Voice commands before wake trigger must be rejected
        req = self.mgr.process_voice_command("move forward")
        self.assertFalse(req.is_authorized)
        self.assertIn("Requires active INTERACTION", req.rejection_reason)

        # User provides explicit consent via wake word ("Hello GraceEMO")
        res = self.mgr.on_wake_trigger(source="wake_phrase")
        self.assertTrue(res)
        self.assertEqual(self.mgr.state, BehaviorState.INTERACTION)

    def test_stop_command_immediate_priority(self):
        # Transition to INTERACTION
        self.mgr.on_wake_trigger(source="button")
        self.assertEqual(self.mgr.state, BehaviorState.INTERACTION)

        # Issue motion command
        req = self.mgr.process_voice_command("forward")
        self.assertTrue(req.is_authorized)
        self.assertEqual(self.mgr.state, BehaviorState.MANUAL_COMMAND)

        # Issue immediate STOP command
        t0 = time.perf_counter()
        stop_req = self.mgr.process_voice_command("Emergency stop immediately!")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertTrue(stop_req.is_authorized)
        self.assertEqual(stop_req.command_type, "STOP")
        self.assertEqual(self.mgr.state, BehaviorState.SAFE_STOP)
        self.assertTrue(elapsed_ms < 50.0, f"STOP latency {elapsed_ms:.2f}ms exceeded 50ms")

        # Velocities zeroed
        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

    def test_follow_person_and_lost_target_handling(self):
        # Setup target
        t_now = time.time()
        target = PersonDetection(
            person_id="target_01",
            confidence=0.88,
            distance_m=1.80,
            bearing_rad=0.05,
            confirmed=True,
            timestamp=t_now,
        )
        self.mgr.on_person_detected(target)
        self.mgr.on_wake_trigger(source="wake_phrase")
        self.assertEqual(self.mgr.state, BehaviorState.INTERACTION)

        # Command follow
        req = self.mgr.process_voice_command("follow me please")
        self.assertTrue(req.is_authorized)
        self.assertEqual(self.mgr.state, BehaviorState.FOLLOW_PERSON)

        # Verify safe follow velocities commanded
        lin, ang = self.mgr.current_velocity
        self.assertTrue(0.0 < lin <= self.mgr.max_safe_linear)

        # Simulate lost target (no updates for > 0.5s)
        self.mgr.update_tick(now=t_now + 0.60)
        self.assertEqual(self.mgr.state, BehaviorState.SAFE_STOP)
        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

    def test_velocity_clamping_on_manual_command(self):
        self.mgr.on_wake_trigger(source="button")
        self.assertEqual(self.mgr.state, BehaviorState.INTERACTION)

        req = self.mgr.process_voice_command("turn left")
        self.assertTrue(req.is_authorized)
        self.assertEqual(self.mgr.state, BehaviorState.MANUAL_COMMAND)

        lin, ang = self.mgr.current_velocity
        self.assertTrue(abs(lin) <= self.mgr.max_safe_linear)
        self.assertTrue(abs(ang) <= self.mgr.max_safe_angular)

    def test_fault_override_and_reset(self):
        self.mgr.on_wake_trigger()
        self.mgr.raise_fault("LiDAR connection lost")
        self.assertEqual(self.mgr.state, BehaviorState.FAULT)

        lin, ang = self.mgr.current_velocity
        self.assertEqual(lin, 0.0)
        self.assertEqual(ang, 0.0)

        # Cannot accept commands while in FAULT
        req = self.mgr.process_voice_command("move forward")
        self.assertFalse(req.is_authorized)

        # Reset to IDLE
        self.mgr.reset_to_idle("Fault cleared by supervisor")
        self.assertEqual(self.mgr.state, BehaviorState.IDLE)

    def test_event_bus_person_visible_integration(self):
        class MockEventBus:
            def __init__(self):
                self.subscriber = None

            def subscribe(self, fn):
                self.subscriber = fn

            def emit(self, event_type, data):
                if self.subscriber:
                    self.subscriber({"event_type": {"type": event_type, "data": data}})

        bus = MockEventBus()
        self.mgr.connect_event_bus(bus)

        # Emit PersonVisible from Vision
        bus.emit("PersonVisible", {
            "person_id": "operator_42",
            "confidence": 0.89,
            "distance_m": 2.1,
            "bearing_rad": -0.1,
        })
        # Should transition through PERSON_DETECTED to OBSERVATION_60S
        self.assertEqual(self.mgr.state, BehaviorState.OBSERVATION_60S)

        # Emit Stop Action on bus
        bus.emit("ActionRequested", {"action": "Stop"})
        self.assertEqual(self.mgr.state, BehaviorState.SAFE_STOP)


if __name__ == "__main__":
    unittest.main()
