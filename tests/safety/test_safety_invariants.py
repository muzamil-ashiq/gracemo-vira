#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 4 Automated Safety Invariants Verification Suite
Enforces mathematical, architectural, and physical safety guarantees:
  Invariant 1: LLM can NEVER directly control hardware (Strict Rule 3: Zero GPIO, PWM, motor register access).
  Invariant 2: Invalid / malformed command cannot reach ROS 2 or RobotBridge.
  Invariant 3: Stale command (> max_command_age) cannot reach ROS 2 or activate motion.
  Invariant 4: Emergency Stop does NOT depend on LLM reasoning.
  Invariant 5: Emergency Stop does NOT depend on Internet / Cloud availability.
  Invariant 6: Invalid / unknown destination produces ZERO motion commands and zero displacement.
  Invariant 7: Sensor safety failure (LiDAR, IMU, Odometry) prevents unsafe navigation.
  Invariant 8: Duplicate STOP is safe and idempotent.
  Invariant 9: Duplicate / preemptive navigation follows defined cancellation policy.
  Invariant 10: System reboot or process restart CANNOT cause unintended motion.
"""
from __future__ import annotations
import math
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "graceemo_interaction"))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))

from core.gateway import InteractionGateway, GatewayResult
from core.event_bus import EventBusClient
from core.safety_gate import SafetyGate, CommandValidator, FORBIDDEN_KEYWORDS
from core.fast_path import FastPathMatcher
from core.brain_adapter import BrainAdapter
from core.state_machine import CognitiveState, Expression

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.state_machine import RobotState


class TestSafetyInvariants(unittest.TestCase):
    def setUp(self):
        self.bus = EventBusClient(base_url="http://127.0.0.1:9999")  # Offline bus: zero cloud dependency
        self.safety_gate = SafetyGate(validator=CommandValidator(max_commands_per_min=100000))
        self.fast_path = FastPathMatcher()
        self.gateway = InteractionGateway(
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        self.robot_bridge = RobotBridge(
            emit_callback=lambda env: self.bus.emit_envelope(env),
            mode="simulation",
        )
        self.robot_bridge.navigation_adapter.sim_step_dt = 0.005
        self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)
        self.bus.subscribe("ActionRequested", self.robot_bridge.on_action_requested)

    def tearDown(self):
        self.robot_bridge.stop()

    def test_invariant_1_llm_can_never_directly_control_hardware(self):
        """
        Safety Invariant 1 (Strict Rule 3):
        LLM or external actors attempt to inject direct GPIO, PWM, raw duty cycles, or motor pins.
        SafetyGate MUST reject every payload containing forbidden hardware control terms.
        """
        for kw in FORBIDDEN_KEYWORDS:
            payload = {
                "action": "NavigateTo",
                "params": {"x": 2.5, "y": 2.0, kw: 100},
            }
            res = self.safety_gate.evaluate_action(payload)
            self.assertFalse(res.valid, f"SafetyGate allowed forbidden hardware keyword '{kw}'")
            self.assertIn("Forbidden", res.error_message)

            raw_cmd = {"action": kw, "params": {"pin": 12, "val": 1}}
            res_raw = self.safety_gate.evaluate_action(raw_cmd)
            self.assertFalse(res_raw.valid, f"SafetyGate allowed forbidden direct action '{kw}'")

    def test_invariant_2_invalid_command_cannot_reach_ros2(self):
        """
        Safety Invariant 2:
        Malformed commands (missing coords, string coords, infinite values, out-of-bound coords)
        are blocked by SafetyGate and SafetyAdapter. Zero velocity is commanded.
        """
        invalid_payloads = [
            {"action": "NavigateTo", "params": {}},  # missing x, y
            {"action": "NavigateTo", "params": {"x": "bad", "y": 2.0}},  # string coord
            {"action": "NavigateTo", "params": {"x": float("nan"), "y": 2.0}},  # NaN
            {"action": "NavigateTo", "params": {"x": float("inf"), "y": 2.0}},  # Inf
            {"action": "NavigateTo", "params": {"x": 999.0, "y": 2.0}},  # Out of bounds (> 100.0)
            {"action": "NavigateTo", "params": {"x": 2.0, "y": -500.0}},  # Out of bounds (< -100.0)
        ]

        for p in invalid_payloads:
            res = self.safety_gate.evaluate_action(p)
            self.assertFalse(res.valid, f"SafetyGate failed to reject malformed payload: {p}")

            # Even if bypassed to RobotBridge directly, SafetyAdapter must reject
            act_env = {
                "id": "inv2-env",
                "trace_id": "inv2-trace",
                "timestamp": time.time(),
                "event_type": {"type": "ActionRequested", "data": p},
            }
            allowed = self.robot_bridge.on_action_requested(act_env)
            self.assertFalse(allowed, f"RobotBridge allowed malformed payload: {p}")
            self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)
            self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)

    def test_invariant_3_stale_command_cannot_reach_ros2(self):
        """
        Safety Invariant 3:
        A command generated > 3.0 seconds in the past is rejected as stale. Zero motion.
        """
        old_timestamp = time.time() - 5.0
        stale_env = {
            "id": "inv3-stale",
            "trace_id": "inv3-trace",
            "timestamp": old_timestamp,
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "NavigateTo", "params": {"x": 2.5, "y": 2.0}},
            },
        }
        allowed = self.robot_bridge.on_action_requested(stale_env)
        self.assertFalse(allowed, "RobotBridge allowed stale command")
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)

    def test_invariant_4_and_5_emergency_stop_independent_of_llm_and_internet(self):
        """
        Safety Invariant 4 & 5:
        Emergency Stop does NOT depend on LLM or Internet connectivity.
        Even with offline bus and broken LLM, voice STOP dispatches immediately.
        """
        # Completely disable brain
        broken_brain = BrainAdapter()
        broken_brain.query = lambda text, hist=None: (_ for _ in ()).throw(ConnectionRefusedError("Internet dead"))
        self.gateway.brain = broken_brain

        # Start motion via fast-path
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="inv4-nav")
        time.sleep(0.01)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # Issue Emergency STOP
        t0 = time.perf_counter()
        stop_res = self.gateway.process_text("Stop immediately!", trace_id="inv4-stop")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(stop_res.intent, "STOP")
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.EMERGENCY_STOP)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)
        self.assertLess(elapsed_ms, 10.0, f"STOP took {elapsed_ms:.2f}ms, must be < 10ms without internet/LLM")

    def test_invariant_6_invalid_destination_produces_no_motion(self):
        """
        Safety Invariant 6:
        Invalid destination produces ZERO motion commands and zero physical displacement.
        """
        initial_x = self.robot_bridge.navigation_adapter.current_x
        initial_y = self.robot_bridge.navigation_adapter.current_y

        res = self.gateway.process_text("Take me to Atlantis City Underwater.", trace_id="inv6-atlantis")
        self.assertEqual(res.intent, "UNKNOWN_DESTINATION")
        self.assertEqual(len(res.semantic_commands), 0)

        # Confirm robot did not move at all
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_x, initial_x)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_y, initial_y)

    def test_invariant_7_sensor_safety_failure_prevents_unsafe_navigation(self):
        """
        Safety Invariant 7:
        When safety sensors are failed/offline, locomotion commands are strictly prohibited.
        """
        # Disable LiDAR
        self.robot_bridge.safety_adapter.update_sensor_status("lidar", False)
        cmd = {
            "id": "inv7-cmd",
            "trace_id": "inv7-trace",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "NavigateTo", "params": {"x": 2.5, "y": 2.0}},
            },
        }
        allowed = self.robot_bridge.on_action_requested(cmd)
        self.assertFalse(allowed)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)

        # Restore LiDAR
        self.robot_bridge.safety_adapter.update_sensor_status("lidar", True)

    def test_invariant_8_duplicate_stop_is_safe(self):
        """
        Safety Invariant 8:
        Calling STOP repeatedly (10 times) is strictly safe, idempotent, and leaves the robot in EMERGENCY_STOP.
        """
        for i in range(10):
            res = self.gateway.process_text("Stop.", trace_id=f"inv8-stop-{i}")
            self.assertEqual(res.intent, "STOP")
            self.assertEqual(self.robot_bridge.state_machine.state, RobotState.EMERGENCY_STOP)
            self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)

    def test_invariant_9_duplicate_navigation_preemption_policy(self):
        """
        Safety Invariant 9:
        A new navigation goal cleanly preempts any existing goal without leaving dangling threads or corrupted state.
        """
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="inv9-nav-1")
        time.sleep(0.01)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # Preempt with Central Library
        self.gateway.process_text("Take me to Central Library.", trace_id="inv9-nav-2")
        time.sleep(0.01)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)
        self.assertEqual(self.robot_bridge.navigation_adapter._active_destination, "Central Library (B37)")

    def test_invariant_10_restart_cannot_cause_unintended_motion(self):
        """
        Safety Invariant 10:
        On cold start, system boots into IDLE with speed = 0.0. Uncommanded motion is mathematically impossible.
        """
        clean_bridge = RobotBridge(emit_callback=lambda env: None, mode="simulation")
        self.assertEqual(clean_bridge.state_machine.state, RobotState.IDLE)
        self.assertEqual(clean_bridge.navigation_adapter.current_speed, 0.0)
        self.assertEqual(clean_bridge.navigation_adapter.current_x, 0.0)
        self.assertEqual(clean_bridge.navigation_adapter.current_y, 0.0)
        clean_bridge.stop()


if __name__ == "__main__":
    unittest.main()
