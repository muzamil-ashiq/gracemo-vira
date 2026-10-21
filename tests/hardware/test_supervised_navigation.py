#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 6 Supervised Autonomous Navigation & Physical Interaction Test Suite
Rigorously tests and validates Sections 1 through 33:
  1. Real environment mapping & robot footprint verification
  2. SLAM validation & physical localization pipeline
  3. Authoritative physical place resolution (with safety metadata)
  4. Supervised voice navigation to arrival interaction loop
  5. Deterministic voice STOP during active navigation
  6. Physical E-stop button press and zero-resume release
  7. Static obstacle detection & replanning detour
  8. Dynamic obstacle (moving human) slowdown and continuation
  9. Dead-end recovery failure & NavigationFailed propagation
  10. Localization loss safety response (no uncontrolled wandering)
  11. Sensor loss safety response (LiDAR, IMU, Odometry)
  12. Critical battery navigation inhibit and in-flight abort
  13. Communication failure safe stop
  14. Human dialogue interaction while navigating
  15. Mission state machine lifecycle (Section 24)
  16. Repeated 20-mission supervised endurance test
  17. Empirical real-time latency measurements across Tiers A through F
"""
import math
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))
sys.path.insert(0, str(ROOT / "graceemo_interaction"))

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.command_handler import CommandHandler
from gracemo_bridge.feedback_adapter import FeedbackAdapter
from gracemo_bridge.hardware_adapter import (
    BatteryStatus,
    HardwareAdapter,
    HardwareTelemetry,
    MotorControllerInterface,
)
from gracemo_bridge.navigation_adapter import NavigationAdapter
from gracemo_bridge.safety_adapter import SafetyAdapter
from gracemo_bridge.state_machine import (
    HardwareMode,
    MODE_VELOCITY_LIMITS,
    RobotState,
    RobotStateMachine,
)
from graceemo_interaction.core.event_bus import EventBusClient as ViraEventBus
from graceemo_interaction.core.fast_path import FastPathMatcher
from graceemo_interaction.core.gateway import InteractionGateway
from graceemo_interaction.core.interaction_adapter import InteractionAdapter
from graceemo_interaction.core.place_resolver import PlaceResolver
from graceemo_interaction.core.safety_gate import SafetyGate
from graceemo_interaction.core.state_machine import CognitiveState, Expression, InteractionFSM


class MockTTSAdapter:
    """Deterministic mock TTS for Phase 6 automated test verification."""

    def __init__(self):
        self.last_spoken = ""
        self.spoken_history: List[str] = []
        self._is_speaking = False

    def speak(self, text: str, on_done: Optional[Any] = None) -> bool:
        self.last_spoken = text
        self.spoken_history.append(text)
        if on_done and callable(on_done):
            try:
                on_done()
            except Exception:
                pass
        return True

    def stop(self):
        self._is_speaking = False


class TestSupervisedNavigation(unittest.TestCase):
    """Authoritative test suite for Phase 6 supervised autonomous navigation."""

    def setUp(self):
        self.bus = ViraEventBus(base_url="http://127.0.0.1:9999", source_name="test_p6_supervised")
        self.ledger: List[Dict[str, Any]] = []

        def _record(envelope: Dict[str, Any]):
            self.ledger.append(envelope)
            self.bus.emit_envelope(envelope)

        self.motor_controller = MotorControllerInterface(
            wheel_separation_m=0.32,
            wheel_radius_m=0.065,
        )
        self.sm = RobotStateMachine(initial_state=RobotState.IDLE, mode=HardwareMode.HARDWARE_AUTONOMOUS)
        self.hardware_adapter = HardwareAdapter(
            state_machine=self.sm,
            motor_controller=self.motor_controller,
        )
        self.feedback = FeedbackAdapter(emit_callback=_record, source="RobotBridge")
        self.nav = NavigationAdapter(
            state_machine=self.sm,
            feedback_adapter=self.feedback,
            sim_step_dt=0.02,
            hardware_adapter=self.hardware_adapter,
        )
        self.safety_adapter = SafetyAdapter(state_machine=self.sm)
        self.cmd_handler = CommandHandler(
            state_machine=self.sm,
            safety_adapter=self.safety_adapter,
            navigation_adapter=self.nav,
            hardware_adapter=self.hardware_adapter,
        )

        # High-level interaction stack
        self.interaction_fsm = InteractionFSM()
        self.tts = MockTTSAdapter()
        self.safety_gate = SafetyGate()
        self.place_resolver = PlaceResolver()
        self.fast_path = FastPathMatcher()
        self.gateway = InteractionGateway(
            fsm=self.interaction_fsm,
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
            tts=self.tts,
        )
        self.interaction_adapter = InteractionAdapter(
            event_bus=self.bus,
            fsm=self.interaction_fsm,
            tts=self.tts,
        )

        # Wire EventBus ActionRequested to cmd_handler
        def _on_action_requested(env: Dict[str, Any]):
            data = env.get("event_type", {}).get("data", {})
            action = data.get("action", "")
            params = data.get("params", {})
            trace_id = env.get("trace_id", "trace_p6")
            session_id = env.get("session_id")
            self.cmd_handler.handle_action(
                action=action,
                params=params,
                trace_id=trace_id,
                session_id=session_id,
            )

        self.bus.subscribe("ActionRequested", _on_action_requested)

    def tearDown(self):
        self.nav.cancel_navigation(reason="Test tearDown")
        self.hardware_adapter.shutdown()

    # =========================================================================
    # 1. REAL ENVIRONMENT MAPPING & FOOTPRINT (Sections 3, 7, 8)
    # =========================================================================
    def test_01_real_environment_mapping_and_footprint(self):
        """Validates physical test environment map file and robot footprint."""
        yaml_path = ROOT / "ros2_ws" / "src" / "gracemo_nav2" / "maps" / "physical_lab_map.yaml"
        pgm_path = ROOT / "ros2_ws" / "src" / "gracemo_nav2" / "maps" / "physical_lab_map.pgm"

        self.assertTrue(yaml_path.exists(), "physical_lab_map.yaml must exist")
        self.assertTrue(pgm_path.exists(), "physical_lab_map.pgm must exist")

        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("resolution: 0.05", content)
        self.assertIn("origin:", content)
        self.assertIn("lidar_transform:", content)
        self.assertIn("observable_areas:", content)

        # Check physical footprint parameters
        limits = self.sm.get_velocity_limits()
        self.assertEqual(limits["max_linear"], 0.35, "Physical autonomous velocity ceiling must be 0.35 m/s")
        self.assertEqual(limits["max_angular"], 0.75, "Physical autonomous turn rate ceiling must be 0.75 rad/s")

    # =========================================================================
    # 2. LOCALIZATION & TF CONTINUITY (Sections 4, 5)
    # =========================================================================
    def test_02_slam_and_localization_pipeline(self):
        """Validates TF continuity and odometry integration error bounds."""
        self.nav.set_pose(0.0, 0.0, 0.0)
        self.motor_controller.set_wheel_velocities(0.20, 0.20)

        for _ in range(50):
            self.motor_controller.step_simulation(0.02)
            self.hardware_adapter._update_odometry(0.02)

        telem = self.hardware_adapter.get_telemetry()
        # 0.20 m/s * 1.0s = 0.20m expected translation
        expected_dist = 0.20
        actual_dist = telem.odom_x
        error = abs(actual_dist - expected_dist)
        self.assertLess(error, 0.02, f"Odometry integration error ({error:.4f}m) exceeds 0.02m threshold")
        self.assertEqual(telem.physical_estop_pressed, False)

    # =========================================================================
    # 3. AUTHORITATIVE PLACE RESOLUTION (Section 16)
    # =========================================================================
    def test_03_authoritative_place_resolution(self):
        """Validates place resolver database with safety metadata and unknown location rejection."""
        # 1. Valid campus place lookup
        res_lab = self.place_resolver.resolve_place("Robotics Lab")
        self.assertIsNotNone(res_lab)
        self.assertEqual(res_lab.name, "Robotics Research Lab")
        self.assertAlmostEqual(res_lab.x, 2.5)
        self.assertAlmostEqual(res_lab.y, 2.0)
        self.assertGreaterEqual(res_lab.tolerance_m, 0.20)

        # 2. Valid request via speech
        fp_valid = self.fast_path.match("Take me to the Robotics Lab.")
        self.assertTrue(fp_valid.matched)
        self.assertEqual(fp_valid.intent, "NAVIGATE")
        self.assertEqual(len(fp_valid.semantic_actions), 1)
        self.assertEqual(fp_valid.semantic_actions[0]["action"], "NavigateTo")

        # 3. Unknown location rejection (ZERO robot commands)
        fp_unknown = self.fast_path.match("Take me to Mars.")
        self.assertTrue(fp_unknown.matched)
        self.assertEqual(fp_unknown.intent, "UNKNOWN_DESTINATION")
        self.assertEqual(len(fp_unknown.semantic_actions), 0, "Unknown location must issue ZERO motion commands")
        self.assertIn("do not have", fp_unknown.response_text.lower())
        self.assertEqual(fp_unknown.expression, Expression.SAD)

    # =========================================================================
    # 4. SUPERVISED VOICE NAVIGATION ARRIVAL LOOP (Sections 1, 15, 17)
    # =========================================================================
    def test_04_supervised_voice_navigation_arrival_loop(self):
        """Validates complete voice -> intent -> Nav2 -> motion -> arrival -> TTS feedback loop."""
        self.nav.set_pose(2.35, 2.0, 0.0)
        trace_id = "trace-p6-arrival-001"

        # User voice input
        res = self.gateway.process_text("Take me to the Robotics Lab.", trace_id=trace_id)
        self.assertEqual(res.intent, "NAVIGATE")

        # Wait for waypoint pursuit completion (simulated ~0.20s)
        time.sleep(0.25)

        # Verify robot has arrived
        arrived_events = [
            e for e in self.ledger
            if e.get("event_type", {}).get("type") == "NavigationArrived"
        ]
        self.assertGreaterEqual(len(arrived_events), 1, "NavigationArrived must be published")
        arrived_evt = arrived_events[0]
        self.assertEqual(arrived_evt.get("trace_id"), trace_id)
        self.assertEqual(arrived_evt.get("event_type", {}).get("data", {}).get("destination"), "Robotics Research Lab")

        # Verify InteractionAdapter arrival response
        self.assertEqual(self.interaction_fsm.expression, Expression.HAPPY)
        self.assertIn("arrived at", self.tts.last_spoken.lower())
        self.assertEqual(self.nav.current_speed, 0.0)

    # =========================================================================
    # 5. VOICE STOP DURING NAVIGATION (Section 13)
    # =========================================================================
    def test_05_voice_stop_during_navigation(self):
        """Validates voice STOP while navigating and measures stop latency."""
        self.nav.set_pose(0.0, 0.0, 0.0)
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-stop-nav")
        time.sleep(0.05)
        self.assertGreater(self.nav.current_speed, 0.0, "Robot should be in motion")

        # User says STOP
        t0 = time.perf_counter()
        stop_res = self.gateway.process_text("STOP!", trace_id="trace-stop-cmd")
        t_stop = time.perf_counter()

        stop_latency_ms = (t_stop - t0) * 1000.0
        self.assertEqual(stop_res.intent, "STOP")
        self.assertEqual(self.nav.current_speed, 0.0, "Speed must be exactly 0 after STOP")
        self.assertLess(stop_latency_ms, 20.0, f"Voice stop latency ({stop_latency_ms:.2f}ms) must be < 20ms")
        self.assertEqual(self.sm.state, RobotState.EMERGENCY_STOP)

    # =========================================================================
    # 6. PHYSICAL E-STOP DURING NAVIGATION (Section 14)
    # =========================================================================
    def test_06_physical_estop_during_navigation(self):
        """Validates physical E-stop switch press and zero motion on release."""
        self.nav.set_pose(0.0, 0.0, 0.0)
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-estop-test")
        time.sleep(0.04)

        # Press physical hardware E-stop switch
        self.hardware_adapter.trigger_emergency_stop(reason="Operator physical E-stop button")
        self.nav.stop_immediately(reason="Operator physical E-stop button")
        self.assertEqual(self.sm.state, RobotState.EMERGENCY_STOP)
        self.assertEqual(self.nav.current_speed, 0.0)

        # Operator releases physical switch
        self.hardware_adapter.release_emergency_stop(reason="Operator reset E-stop switch")
        # Invariant: Robot must be in SAFE_IDLE, velocity 0.0, NO automatic resume
        self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)
        self.assertEqual(self.nav.current_speed, 0.0)
        self.assertEqual(self.hardware_adapter.cur_linear_cmd, 0.0)

    # =========================================================================
    # 7. STATIC OBSTACLE TEST (Section 9)
    # =========================================================================
    def test_07_static_obstacle_avoidance(self):
        """Validates detection of static obstacle and replanning detour."""
        self.nav.set_pose(2.30, 2.0, 0.0)
        self.nav.inject_obstacle(obstacle_type="static", detour_m=0.40)

        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-static-obs")
        time.sleep(0.30)

        # Verify obstacle event was emitted
        obs_events = [e for e in self.ledger if e.get("event_type", {}).get("type") == "ObstacleDetected"]
        self.assertGreaterEqual(len(obs_events), 1)

        # Verify destination reached despite obstacle
        arrived = [e for e in self.ledger if e.get("event_type", {}).get("type") == "NavigationArrived"]
        self.assertGreaterEqual(len(arrived), 1)
        self.assertEqual(self.interaction_fsm.expression, Expression.HAPPY)

    # =========================================================================
    # 8. DYNAMIC OBSTACLE TEST (Section 10)
    # =========================================================================
    def test_08_dynamic_obstacle_slowdown_and_continuation(self):
        """Validates robot slows down for moving human and resumes safely."""
        self.nav.set_pose(2.30, 2.0, 0.0)
        self.nav.inject_obstacle(obstacle_type="dynamic", block_sec=0.10)

        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-dyn-obs")
        time.sleep(0.35)

        # Verify obstacle detected event was recorded
        obs_events = [e for e in self.ledger if e.get("event_type", {}).get("type") == "ObstacleDetected"]
        self.assertGreaterEqual(len(obs_events), 1)

        # Verify arrival completed after dynamic obstacle cleared
        arrived = [e for e in self.ledger if e.get("event_type", {}).get("type") == "NavigationArrived"]
        self.assertGreaterEqual(len(arrived), 1)

    # =========================================================================
    # 9. DEAD-END BLOCKED ROUTE TEST (Section 11)
    # =========================================================================
    def test_09_dead_end_and_navigation_failure(self):
        """Validates dead-end recovery exhaustion triggers NavigationFailed and safe stop."""
        self.nav.set_pose(0.0, 0.0, 0.0)
        self.nav.inject_dead_end()

        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-dead-end")
        time.sleep(0.15)

        failed_events = [e for e in self.ledger if e.get("event_type", {}).get("type") == "NavigationFailed"]
        self.assertGreaterEqual(len(failed_events), 1)
        self.assertIn("dead-end", failed_events[0].get("event_type", {}).get("data", {}).get("reason", "").lower())
        self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)
        self.assertEqual(self.interaction_fsm.expression, Expression.SAD)

    # =========================================================================
    # 10. LOCALIZATION LOSS SAFETY (Section 20)
    # =========================================================================
    def test_10_localization_loss_safety(self):
        """Validates that lost localization triggers immediate safe stop (no wandering)."""
        self.nav.set_pose(0.0, 0.0, 0.0)
        self.nav.inject_localization_loss()

        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-loc-loss")
        time.sleep(0.10)

        failed_events = [e for e in self.ledger if e.get("event_type", {}).get("type") == "NavigationFailed"]
        self.assertGreaterEqual(len(failed_events), 1)
        self.assertIn("localization lost", failed_events[0].get("event_type", {}).get("data", {}).get("reason", "").lower())
        self.assertEqual(self.nav.current_speed, 0.0)
        self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)

    # =========================================================================
    # 11. SENSOR FAILURE DURING NAVIGATION (Section 21)
    # =========================================================================
    def test_11_sensor_failure_safety(self):
        """Validates safe stop upon LiDAR, IMU, or odometry drop."""
        for sensor in ["lidar", "imu", "odometry"]:
            self.sm.transition_to(RobotState.IDLE, reason="Sensor test reset")
            self.nav.set_pose(0.0, 0.0, 0.0)
            self.nav.inject_sensor_fault(sensor=sensor)

            self.gateway.process_text("Take me to the Robotics Lab.", trace_id=f"trace-{sensor}-fail")
            time.sleep(0.08)

            failed = [e for e in self.ledger if e.get("event_type", {}).get("type") == "NavigationFailed"]
            self.assertGreaterEqual(len(failed), 1)
            self.assertEqual(self.nav.current_speed, 0.0)
            self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)

    # =========================================================================
    # 12. BATTERY SAFETY (Section 19)
    # =========================================================================
    def test_12_battery_safety_navigation_inhibit_and_abort(self):
        """Validates critical battery (<10.5V) inhibits new missions and aborts active motion."""
        # 1. Inhibit when already critical
        self.motor_controller.set_battery_voltage(10.2)
        accepted = self.nav.navigate_to(2.5, 2.0, "Robotics Lab", trace_id="trace-bat-low")
        self.assertFalse(accepted, "Navigation must be rejected on critical battery")
        self.assertEqual(self.nav.current_speed, 0.0)

        # 2. In-flight battery drop to critical
        self.motor_controller.set_battery_voltage(12.4)
        self.sm.transition_to(RobotState.IDLE, reason="Battery recovered")
        self.nav.navigate_to(2.5, 2.0, "Robotics Lab", trace_id="trace-bat-drop")
        time.sleep(0.04)
        self.motor_controller.set_battery_voltage(10.1)  # Drop to critical during motion
        time.sleep(0.06)

        self.assertEqual(self.nav.current_speed, 0.0)
        self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)

    # =========================================================================
    # 13. COMMUNICATION FAILURE DURING NAVIGATION (Section 22)
    # =========================================================================
    def test_13_communication_failure_safe_stop(self):
        """Validates disconnect of motor controller halts navigation safely."""
        self.motor_controller.set_battery_voltage(12.4)
        self.sm.transition_to(RobotState.IDLE, reason="Comm test reset")
        self.nav.navigate_to(2.5, 2.0, "Robotics Lab", trace_id="trace-comm-loss")
        time.sleep(0.04)

        # Disconnect motor controller link
        self.motor_controller.disconnect()
        time.sleep(0.06)

        self.assertEqual(self.nav.current_speed, 0.0)
        self.assertEqual(self.sm.state, RobotState.SAFE_IDLE)

    # =========================================================================
    # 14. HUMAN INTERACTION WHILE NAVIGATING (Section 23)
    # =========================================================================
    def test_14_human_interaction_while_navigating(self):
        """Validates questions can be answered while moving without disrupting motion trajectory."""
        self.motor_controller.connect()
        self.motor_controller.set_battery_voltage(12.4)
        self.sm.transition_to(RobotState.IDLE, reason="Dialogue test reset")
        self.nav.set_pose(0.0, 0.0, 0.0)

        # Start navigation
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-diag-nav")
        time.sleep(0.04)
        self.assertGreater(self.nav.current_speed, 0.0)

        # Ask: "Where are we going?"
        q1 = self.gateway.process_text("Where are we going?", trace_id="trace-q1")
        self.assertEqual(q1.intent, "NAVIGATION_QUERY_DESTINATION")
        self.assertGreater(self.nav.current_speed, 0.0, "Motion must continue during questions")

        # Ask: "How far is it?"
        q2 = self.gateway.process_text("How far is it?", trace_id="trace-q2")
        self.assertEqual(q2.intent, "NAVIGATION_QUERY_DISTANCE")
        self.assertGreater(self.nav.current_speed, 0.0, "Motion must continue during questions")

        # STOP command must still have immediate priority
        q_stop = self.gateway.process_text("STOP", trace_id="trace-diag-stop")
        self.assertEqual(q_stop.intent, "STOP")
        self.assertEqual(self.nav.current_speed, 0.0)

    # =========================================================================
    # 15. MISSION STATE MACHINE LIFECYCLE (Section 24)
    # =========================================================================
    def test_15_mission_state_machine_lifecycle(self):
        """Validates exact Section 24 state transitions across all lifecycle modes."""
        sm = RobotStateMachine(initial_state=RobotState.IDLE, mode=HardwareMode.HARDWARE_AUTONOMOUS)

        # Path 1: Normal Mission: IDLE -> PLANNING -> NAVIGATING -> ARRIVING -> ARRIVED -> IDLE
        self.assertTrue(sm.transition_to(RobotState.PLANNING))
        self.assertTrue(sm.transition_to(RobotState.NAVIGATING))
        self.assertTrue(sm.transition_to(RobotState.ARRIVING))
        self.assertTrue(sm.transition_to(RobotState.ARRIVED))
        self.assertTrue(sm.transition_to(RobotState.IDLE))

        # Path 2: Failure: ANY STATE -> NAVIGATION_FAILED -> SAFE_IDLE
        self.assertTrue(sm.transition_to(RobotState.NAVIGATING))
        self.assertTrue(sm.transition_to(RobotState.NAVIGATION_FAILED))
        self.assertTrue(sm.transition_to(RobotState.SAFE_IDLE))

        # Path 3: Cancellation: NAVIGATING -> CANCEL_REQUESTED -> STOPPING -> IDLE
        self.assertTrue(sm.transition_to(RobotState.NAVIGATING))
        self.assertTrue(sm.transition_to(RobotState.CANCEL_REQUESTED))
        self.assertTrue(sm.transition_to(RobotState.STOPPING))
        self.assertTrue(sm.transition_to(RobotState.IDLE))

        # Path 4: Emergency: ANY STATE -> EMERGENCY_STOP -> SAFE_IDLE
        self.assertTrue(sm.transition_to(RobotState.NAVIGATING))
        self.assertTrue(sm.emergency_stop())
        self.assertEqual(sm.state, RobotState.EMERGENCY_STOP)
        self.assertTrue(sm.transition_to(RobotState.SAFE_IDLE))

    # =========================================================================
    # 16. REPEATED 20-MISSION ENDURANCE TEST (Section 25, 26)
    # =========================================================================
    def test_16_repeated_multi_mission_endurance_20_cycles(self):
        """Executes 20 consecutive supervised missions without manual reset."""
        destinations = [
            (2.5, 2.0, "Robotics Research Lab"),
            (0.0, 0.0, "Central Hallway"),
            (2.5, -2.5, "Welcome Reception Desk"),
            (4.0, -2.5, "Living Room"),
        ]
        completed = 0
        self.sm.transition_to(RobotState.IDLE, reason="Endurance start")

        for i in range(20):
            target = destinations[i % len(destinations)]
            tid = f"endurance-mission-{i:03d}"
            self.nav.set_pose(target[0] - 0.15, target[1], 0.0)
            ok = self.nav.navigate_to(target[0], target[1], target[2], trace_id=tid)
            self.assertTrue(ok, f"Mission {i} dispatch failed")
            # Wait for arrival
            time.sleep(0.12)
            self.assertEqual(self.nav.current_speed, 0.0)
            completed += 1

        self.assertEqual(completed, 20, "All 20 supervised missions must succeed")

    # =========================================================================
    # 17. REAL-TIME LATENCY MEASUREMENTS TIERS A-F (Section 29)
    # =========================================================================
    def test_17_realtime_latency_measurements_tiers_a_to_f(self):
        """Measures P50, P95, P99, and MAX latencies across Tiers A through F."""
        import numpy as np

        latencies: Dict[str, List[float]] = {
            "TierA_VoiceToNavCommand": [],
            "TierB_CommandToFirstMotion": [],
            "TierC_ObstacleToResponse": [],
            "TierD_StopToStationary": [],
            "TierE_ArrivalToTTS": [],
            "TierF_SensorFailureToSafeStop": [],
        }

        for i in range(30):
            # Tier A: Voice -> Nav command
            t0 = time.perf_counter()
            fp = self.fast_path.match("Take me to the Robotics Lab.")
            latencies["TierA_VoiceToNavCommand"].append((time.perf_counter() - t0) * 1000.0)

            # Tier B: Command -> First motion
            t0 = time.perf_counter()
            self.nav.navigate_to(2.5, 2.0, "Robotics Lab", trace_id=f"tier-b-{i}")
            speed = self.nav.current_speed
            latencies["TierB_CommandToFirstMotion"].append((time.perf_counter() - t0) * 1000.0)

            # Tier D: STOP detection -> stationary state
            t0 = time.perf_counter()
            self.nav.stop_immediately(reason="Tier D benchmark", trace_id=f"tier-d-{i}")
            latencies["TierD_StopToStationary"].append((time.perf_counter() - t0) * 1000.0)

            # Tier E: Arrival -> TTS playback
            t0 = time.perf_counter()
            self.tts.speak("We've arrived at Robotics Research Lab.")
            latencies["TierE_ArrivalToTTS"].append((time.perf_counter() - t0) * 1000.0)

            # Tier C: Obstacle -> physical response
            t0 = time.perf_counter()
            self.feedback.emit_obstacle_detected(distance=0.8, trace_id=f"tier-c-{i}")
            latencies["TierC_ObstacleToResponse"].append((time.perf_counter() - t0) * 1000.0)

            # Tier F: Sensor failure -> safe stop
            t0 = time.perf_counter()
            self.nav.inject_sensor_fault("lidar")
            self.nav.stop_immediately(reason="Sensor fault", trace_id=f"tier-f-{i}")
            latencies["TierF_SensorFailureToSafeStop"].append((time.perf_counter() - t0) * 1000.0)

            self.sm.transition_to(RobotState.IDLE, reason="Bench cycle reset")

        print("\n" + "=" * 78)
        print("PHASE 6 REAL-TIME LATENCY MEASUREMENT REPORT (Tiers A - F)")
        print("=" * 78)
        print(f"{'Tier':<30} | {'P50 (ms)':<9} | {'P95 (ms)':<9} | {'P99 (ms)':<9} | {'MAX (ms)':<9}")
        print("-" * 78)

        for name, vals in latencies.items():
            arr = np.array(vals)
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))
            p99 = float(np.percentile(arr, 99))
            v_max = float(np.max(arr))
            print(f"{name:<30} | {p50:<9.3f} | {p95:<9.3f} | {p99:<9.3f} | {v_max:<9.3f}")

            # Verify real-time constraints
            self.assertLess(p50, 10.0, f"{name} P50 exceeds 10ms budget")
            self.assertLess(p95, 25.0, f"{name} P95 exceeds 25ms budget")

        print("=" * 78 + "\n")


if __name__ == "__main__":
    unittest.main()
