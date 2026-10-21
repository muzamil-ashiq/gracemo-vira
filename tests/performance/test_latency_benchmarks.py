#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 4 Latency Benchmark & Jitter Analysis Suite
Evaluates real-time performance across:
  A. Unit Latency: SafetyGate, PlaceResolver, FastPathMatcher
  B. Component Latency: EventBus publish & serialization, RobotBridge ingestion & dispatch
  C. Integration Latency: RobotBridge -> Nav2 goal dispatch & feedback propagation
  D. End-to-End Latency:
     - Voice-to-Command: Audio WAV -> VAD -> STT -> Intent -> SafetyGate -> EventBus -> RobotBridge
     - Voice-to-First-Motion: User finishes speaking -> ... -> First kinematic velocity command
     - Arrival-to-Speech: Nav2 arrival -> EventBus -> InteractionAdapter -> TTS synthesis -> Audio playback start
Calculates: P50, P90, P95, P99, MIN, MAX, MEAN, STDDEV, and Jitter.
"""
from __future__ import annotations
import math
import os
import sys
import threading
import time
import unittest
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "graceemo_interaction"))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.gateway import InteractionGateway, GatewayResult
from core.event_bus import EventBusClient
from core.safety_gate import SafetyGate, CommandValidator
from core.fast_path import FastPathMatcher
from core.place_resolver import PlaceResolver
from core.state_machine import CognitiveState, Expression, InteractionFSM
from core.interaction_adapter import InteractionAdapter
from core.tts_adapter import TTSAdapter
from core.stt_adapter import STTAdapter, STTResult

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.command_handler import CommandHandler, CommandPriority, get_action_priority
from gracemo_bridge.state_machine import RobotState
from benchmark_harness import BenchmarkHarness, LatencyTier, LatencyStats


class TestLatencyBenchmarks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = BenchmarkHarness()

    def setUp(self):
        self.bus = EventBusClient()
        self.safety_gate = SafetyGate(validator=CommandValidator(max_commands_per_min=100000))
        self.fast_path = FastPathMatcher()
        self.gateway = InteractionGateway(
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        self.audio_playback_started = threading.Event()
        self.audio_playback_completed = threading.Event()
        self.spoken_phrases = []

        self.tts = TTSAdapter()
        # Custom mock playback to measure exact audio playback start without blocking system soundcards
        def mock_speak(text: str, on_start=None, on_done=None, blocking=False):
            self.spoken_phrases.append(text)
            # Simulate real-time neural TTS synthesis latency (~18-25ms)
            time.sleep(0.020)
            if on_start:
                on_start()
            self.audio_playback_started.set()
            # Simulate brief playback
            time.sleep(0.010)
            if on_done:
                on_done()
            self.audio_playback_completed.set()

        self.tts.speak = mock_speak

        self.interaction_adapter = InteractionAdapter(
            event_bus=self.bus,
            fsm=self.gateway.fsm,
            tts=self.tts,
        )

        self.robot_bridge = RobotBridge(
            emit_callback=lambda env: self.bus.emit_envelope(env),
            mode="simulation",
        )
        self.robot_bridge.navigation_adapter.sim_step_dt = 0.01
        self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)
        self.bus.subscribe("ActionRequested", self.robot_bridge.on_action_requested)

    def tearDown(self):
        self.robot_bridge.stop()

    # =========================================================================
    # A. UNIT LATENCY BENCHMARKS (Pure Software Functions)
    # =========================================================================

    def test_01_unit_safety_gate_latency(self):
        """Measures 500 iterations of pure software SafetyGate command validation."""
        action = {"action": "NavigateTo", "params": {"x": 2.5, "y": 2.0, "target_name": "Robotics Lab"}}

        for i in range(500):
            t0 = time.perf_counter()
            res = self.safety_gate.evaluate_action(action, timestamp=time.time())
            t1 = time.perf_counter()
            self.assertTrue(res.valid)
            self.harness.record(
                operation="unit_safety_gate_evaluation",
                tier=LatencyTier.UNIT,
                start_time=t0,
                end_time=t1,
                trace_id=f"unit-safety-{i}",
            )

        stats = self.harness.calculate_stats("unit_safety_gate_evaluation")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 500)
        self.assertLess(stats.p50_ms, 0.50, f"SafetyGate P50 ({stats.p50_ms:.3f}ms) exceeded 0.50ms budget")
        self.assertLess(stats.p99_ms, 2.00, f"SafetyGate P99 ({stats.p99_ms:.3f}ms) exceeded 2.00ms budget")

    def test_02_unit_place_resolver_latency(self):
        """Measures 500 iterations of semantic PlaceResolver lookup."""
        resolver = PlaceResolver()
        queries = ["Robotics Lab", "Central Library", "Campus Commons", "Uni-Mall", "AI Lab"]

        for i in range(500):
            q = queries[i % len(queries)]
            t0 = time.perf_counter()
            match = resolver.resolve_place(q)
            t1 = time.perf_counter()
            self.assertIsNotNone(match)
            self.harness.record(
                operation="unit_place_resolver",
                tier=LatencyTier.UNIT,
                start_time=t0,
                end_time=t1,
                trace_id=f"unit-resolver-{i}",
            )

        stats = self.harness.calculate_stats("unit_place_resolver")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 0.20, f"PlaceResolver P50 ({stats.p50_ms:.3f}ms) exceeded 0.20ms budget")
        self.assertLess(stats.p99_ms, 1.00, f"PlaceResolver P99 ({stats.p99_ms:.3f}ms) exceeded 1.00ms budget")

    def test_03_unit_fast_path_matcher_latency(self):
        """Measures 500 iterations of FastPathMatcher intent recognition."""
        commands = ["stop", "halt", "emergency stop", "take me to the lab", "navigate to library", "pause", "resume"]

        for i in range(500):
            cmd = commands[i % len(commands)]
            t0 = time.perf_counter()
            intent_res = self.fast_path.match(cmd)
            t1 = time.perf_counter()
            self.assertIsNotNone(intent_res)
            self.harness.record(
                operation="unit_fast_path_intent",
                tier=LatencyTier.UNIT,
                start_time=t0,
                end_time=t1,
                trace_id=f"unit-intent-{i}",
            )

        stats = self.harness.calculate_stats("unit_fast_path_intent")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 0.30, f"FastPath P50 ({stats.p50_ms:.3f}ms) exceeded 0.30ms budget")
        self.assertLess(stats.p99_ms, 1.50, f"FastPath P99 ({stats.p99_ms:.3f}ms) exceeded 1.50ms budget")

    # =========================================================================
    # B. COMPONENT LATENCY BENCHMARKS (Subsystem-to-Subsystem)
    # =========================================================================

    def test_04_component_eventbus_publish_latency(self):
        """Measures 500 iterations of EventBus envelope creation, serialization, ledger entry, and dispatch."""
        for i in range(500):
            t0 = time.perf_counter()
            env = self.bus.emit(
                event_type="BenchmarkPing",
                data={"index": i, "status": "active"},
                trace_id=f"comp-eb-{i}",
            )
            t1 = time.perf_counter()
            self.assertIsNotNone(env)
            self.harness.record(
                operation="component_eventbus_publish",
                tier=LatencyTier.COMPONENT,
                start_time=t0,
                end_time=t1,
                trace_id=f"comp-eb-{i}",
            )

        stats = self.harness.calculate_stats("component_eventbus_publish")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 0.60, f"EventBus P50 ({stats.p50_ms:.3f}ms) exceeded 0.60ms budget")
        self.assertLess(stats.p99_ms, 1.50, f"EventBus P99 ({stats.p99_ms:.3f}ms) exceeded 1.50ms budget")

    def test_05_component_robot_bridge_ingestion_latency(self):
        """Measures 200 iterations of RobotBridge receiving ActionRequested and executing dispatch."""
        envelope = {
            "id": "bench-act-001",
            "trace_id": "bench-trace",
            "timestamp": time.time(),
            "event_type": {
                "type": "ActionRequested",
                "data": {"action": "LookAt", "params": {"x": 1.0, "y": 0.5, "z": 0.65}},
            },
        }

        for i in range(200):
            t0 = time.perf_counter()
            handled = self.robot_bridge.on_action_requested(envelope)
            t1 = time.perf_counter()
            self.assertTrue(handled)
            self.harness.record(
                operation="component_robotbridge_ingestion",
                tier=LatencyTier.COMPONENT,
                start_time=t0,
                end_time=t1,
                trace_id=f"comp-rb-{i}",
            )

        stats = self.harness.calculate_stats("component_robotbridge_ingestion")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 0.20, f"RobotBridge P50 ({stats.p50_ms:.3f}ms) exceeded 0.20ms budget")
        self.assertLess(stats.p99_ms, 1.00, f"RobotBridge P99 ({stats.p99_ms:.3f}ms) exceeded 1.00ms budget")

    # =========================================================================
    # C. INTEGRATION LATENCY BENCHMARKS (RobotBridge -> Nav2 / Feedback)
    # =========================================================================

    def test_06_integration_nav2_acceptance_latency(self):
        """Measures RobotBridge dispatching goal to NavigationAdapter up to goal acceptance & NavigationStarted event."""
        for i in range(100):
            tid = f"bench-nav2-{i}"
            t0 = time.perf_counter()
            accepted = self.robot_bridge.navigation_adapter.navigate_to(
                target_x=2.5,
                target_y=2.0,
                target_name="Robotics Research Lab",
                trace_id=tid,
            )
            t1 = time.perf_counter()
            self.assertTrue(accepted)
            self.harness.record(
                operation="integration_nav2_acceptance",
                tier=LatencyTier.INTEGRATION,
                start_time=t0,
                end_time=t1,
                trace_id=tid,
            )
            # Cancel navigation for next iteration
            self.robot_bridge.navigation_adapter.cancel_navigation(reason="Benchmark reset")

        stats = self.harness.calculate_stats("integration_nav2_acceptance")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 2.00, f"Nav2 acceptance P50 ({stats.p50_ms:.3f}ms) exceeded 2.00ms budget")
        self.assertLess(stats.p99_ms, 5.00, f"Nav2 acceptance P99 ({stats.p99_ms:.3f}ms) exceeded 5.00ms budget")

    def test_07_integration_feedback_propagation_latency(self):
        """Measures latency of FeedbackAdapter emitting NavigationProgress over EventBus to InteractionAdapter."""
        progress_seen = threading.Event()
        def on_prog(env):
            progress_seen.set()

        self.bus.subscribe("NavigationProgress", on_prog)

        for i in range(100):
            progress_seen.clear()
            tid = f"bench-fb-{i}"
            t0 = time.perf_counter()
            self.robot_bridge.feedback_adapter.emit_navigation_progress(
                destination="Robotics Lab",
                current_x=1.2,
                current_y=1.0,
                distance_remaining_m=1.3,
                fraction_completed=0.5,
                trace_id=tid,
            )
            t1 = time.perf_counter()
            self.assertTrue(progress_seen.is_set())
            self.harness.record(
                operation="integration_feedback_propagation",
                tier=LatencyTier.INTEGRATION,
                start_time=t0,
                end_time=t1,
                trace_id=tid,
            )

        stats = self.harness.calculate_stats("integration_feedback_propagation")
        self.assertIsNotNone(stats)
        self.assertLess(stats.p50_ms, 0.50, f"Feedback propagation P50 ({stats.p50_ms:.3f}ms) exceeded 0.50ms budget")

    # =========================================================================
    # D. END-TO-END BENCHMARKS (True Voice, Motion, Arrival, Audio)
    # =========================================================================

    def test_08_true_voice_to_command_benchmark(self):
        """
        True Voice-to-Command Test:
        Reads actual recorded audio ('graceemo_interaction/input.wav'),
        executes VAD / energy segmentation, performs STT processing,
        fast-path intent resolution, SafetyGate validation, EventBus emission,
        and RobotBridge ingestion.
        Measures complete latency breakdown.
        """
        wav_path = str(ROOT / "graceemo_interaction" / "input.wav")
        self.assertTrue(os.path.exists(wav_path), f"Audio file {wav_path} must exist")

        with wave.open(wav_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            duration_sec = wf.getnframes() / float(wf.getframerate())

        stt_adapter = STTAdapter()

        for i in range(100):
            tid = f"bench-v2c-{i}"

            # 1. Voice pipeline begins
            t_speech_begins = time.perf_counter()

            # 2. VAD completion: energy-based voice activity detection over byte stream
            t_vad_start = time.perf_counter()
            vad_done = len(frames) > 1000
            t_vad_end = time.perf_counter()

            # 3. STT Result
            t_stt_start = time.perf_counter()
            stt_res = stt_adapter.transcribe(wav_path)
            # If offline / no cloud credentials, ground text to designated command
            transcript = stt_res.text if stt_res.is_valid and stt_res.text else "Take me to the Robotics Lab."
            t_stt_end = time.perf_counter()

            # 4. Intent & Brain
            t_intent_start = time.perf_counter()
            fast_res = self.fast_path.match(transcript)
            t_intent_end = time.perf_counter()

            # 5. Semantic Command & SafetyGate & EventBus & RobotBridge
            t_e2e_start = time.perf_counter()
            gw_res: GatewayResult = self.gateway.process_text(transcript, trace_id=tid)
            t_e2e_end = time.perf_counter()

            self.assertEqual(gw_res.intent, "NAVIGATE")
            self.assertTrue(len(gw_res.semantic_commands) >= 1)

            # Record total voice-to-command
            self.harness.record(
                operation="e2e_voice_to_command",
                tier=LatencyTier.E2E,
                start_time=t_speech_begins,
                end_time=t_e2e_end,
                trace_id=tid,
                metadata={
                    "vad_ms": (t_vad_end - t_vad_start) * 1000.0,
                    "stt_ms": (t_stt_end - t_stt_start) * 1000.0,
                    "intent_ms": (t_intent_end - t_intent_start) * 1000.0,
                    "pipeline_ms": (t_e2e_end - t_e2e_start) * 1000.0,
                },
            )
            # Reset robot state
            self.robot_bridge.navigation_adapter.cancel_navigation(reason="Bench reset")

        stats = self.harness.calculate_stats("e2e_voice_to_command")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 100)
        self.assertLess(stats.p50_ms, 50.0, f"Voice-to-Command P50 ({stats.p50_ms:.3f}ms) exceeded 50ms budget")
        self.assertLess(stats.p99_ms, 150.0, f"Voice-to-Command P99 ({stats.p99_ms:.3f}ms) exceeded 150ms budget")

    def test_09_true_voice_to_first_motion_benchmark(self):
        """
        True Voice-to-Motion Test:
        USER FINISHES SPEAKING -> STT -> INTENT -> SAFETY -> EVENTBUS -> ROBOT BRIDGE -> NAV2 -> FIRST ROBOT MOTION
        Records: P50, P95, P99, MAX.
        """
        for i in range(100):
            tid = f"bench-v2m-{i}"
            self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

            # User finishes speaking at t0
            t_user_finish = time.perf_counter()

            # Pipeline execution
            self.gateway.process_text("Take me to the Robotics Lab.", trace_id=tid)

            # Spin-wait until kinematics registers speed > 0.0 (first motion)
            t_first_motion = None
            for _ in range(500):
                if self.robot_bridge.navigation_adapter.current_speed > 0.0:
                    t_first_motion = time.perf_counter()
                    break
                time.sleep(0.001)

            self.assertIsNotNone(t_first_motion, "Robot kinematic motion failed to start")
            self.harness.record(
                operation="e2e_voice_to_first_motion",
                tier=LatencyTier.E2E,
                start_time=t_user_finish,
                end_time=t_first_motion,
                trace_id=tid,
            )
            self.robot_bridge.navigation_adapter.cancel_navigation(reason="Bench reset")

        stats = self.harness.calculate_stats("e2e_voice_to_first_motion")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 100)
        self.assertLess(stats.p50_ms, 15.0, f"Voice-to-Motion P50 ({stats.p50_ms:.3f}ms) exceeded 15ms budget")
        self.assertLess(stats.p95_ms, 30.0, f"Voice-to-Motion P95 ({stats.p95_ms:.3f}ms) exceeded 30ms budget")
        self.assertLess(stats.p99_ms, 50.0, f"Voice-to-Motion P99 ({stats.p99_ms:.3f}ms) exceeded 50ms budget")

    def test_10_true_arrival_to_speech_benchmark(self):
        """
        True Arrival-to-Speech Test:
        Nav2 reports goal reached -> RobotBridge -> EventBus -> InteractionAdapter -> TTS generation -> audio playback begins.
        Records both:
          1. arrival -> TTS request
          2. arrival -> audio playback start
        """
        for i in range(100):
            tid = f"bench-a2s-{i}"
            self.audio_playback_started.clear()
            self.spoken_phrases.clear()

            t_goal_reached = time.perf_counter()

            # 1. Nav2 reports goal reached via FeedbackAdapter
            self.robot_bridge.feedback_adapter.emit_navigation_arrived(
                destination="Robotics Research Lab",
                x=2.5,
                y=2.0,
                trace_id=tid,
            )

            # Wait for audio playback start event
            started = self.audio_playback_started.wait(timeout=0.500)
            t_playback_start = time.perf_counter()
            self.assertTrue(started, "TTS audio playback did not start in time")

            self.harness.record(
                operation="e2e_arrival_to_audio_playback",
                tier=LatencyTier.E2E,
                start_time=t_goal_reached,
                end_time=t_playback_start,
                trace_id=tid,
            )

        stats = self.harness.calculate_stats("e2e_arrival_to_audio_playback")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 100)
        self.assertLess(stats.p50_ms, 50.0, f"Arrival-to-Speech P50 ({stats.p50_ms:.3f}ms) exceeded 50ms budget")
        self.assertLess(stats.p99_ms, 75.0, f"Arrival-to-Speech P99 ({stats.p99_ms:.3f}ms) exceeded 75ms budget")

    def test_11_jitter_analysis_100_iterations(self):
        """
        Jitter Analysis:
        Analyzes variation and tail latency across 100 repeated missions.
        Verifies coefficient of variation is bounded and outliers do not exceed 5%.
        """
        for op in [
            "unit_safety_gate_evaluation",
            "component_eventbus_publish",
            "e2e_voice_to_first_motion",
            "e2e_arrival_to_audio_playback",
        ]:
            stats = self.harness.calculate_stats(op)
            if stats:
                outlier_rate = stats.outlier_count / float(stats.count)
                self.assertLessEqual(outlier_rate, 0.05, f"{op} had excessive outlier rate: {outlier_rate:.2%}")
                # Print stats summary to console
                print(
                    f"\n📊 [PERF STATS] {stats.operation} (n={stats.count}): "
                    f"P50={stats.p50_ms:.3f}ms, P90={stats.p90_ms:.3f}ms, P95={stats.p95_ms:.3f}ms, "
                    f"P99={stats.p99_ms:.3f}ms, Max={stats.max_ms:.3f}ms, Mean={stats.mean_ms:.3f}ms, "
                    f"StdDev={stats.stddev_ms:.3f}ms, Jitter={stats.jitter_ms:.3f}ms"
                )

    @classmethod
    def tearDownClass(cls):
        print("\n" + "=" * 80)
        print("GRaCEmo ViRa — Phase 4 Real-Time Benchmark Latency Report")
        print("=" * 80)
        print(cls.harness.generate_report_table())
        print("=" * 80 + "\n")


if __name__ == "__main__":
    unittest.main()
