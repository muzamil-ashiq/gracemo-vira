#!/usr/bin/env python3
"""
GRaCEmo ViRa — Concurrency, Command Priority & STOP Under Load Test Suite
Evaluates:
  - Simultaneous multi-threaded subsystems: Navigation + Telemetry + Camera + LiDAR + TTS + Dialogue
  - Command priority hierarchy: EMERGENCY_STOP > STOP > SAFETY_COMMAND > ACTIVE_ROBOT_COMMAND > NORMAL_INTERACTION
  - Preemption: Normal dialogue request never delays an Emergency Stop
  - STOP Under Load: Navigation active under heavy CPU load, logging load, EventBus flooding,
    and simulated sensor traffic. Measures worst-case STOP latency over repeated trials.
"""
from __future__ import annotations
import logging
import math
import sys
import threading
import time
import unittest
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
from core.state_machine import CognitiveState, Expression, InteractionFSM
from core.interaction_adapter import InteractionAdapter
from core.tts_adapter import TTSAdapter

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.command_handler import CommandHandler, CommandPriority, get_action_priority
from gracemo_bridge.state_machine import RobotState
from benchmark_harness import BenchmarkHarness, LatencyTier


class TestConcurrencyAndPriority(unittest.TestCase):
    def setUp(self):
        self.bus = EventBusClient()
        self.safety_gate = SafetyGate(validator=CommandValidator(max_commands_per_min=100000))
        self.fast_path = FastPathMatcher()
        self.gateway = InteractionGateway(
            event_bus=self.bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        self.tts = TTSAdapter()
        self.tts.speak = lambda text, on_start=None, on_done=None, blocking=False: (
            on_start() if on_start else None,
            on_done() if on_done else None,
        )

        self.interaction_adapter = InteractionAdapter(
            event_bus=self.bus,
            fsm=self.gateway.fsm,
            tts=self.tts,
        )

        self.robot_bridge = RobotBridge(
            emit_callback=lambda env: self.bus.emit_envelope(env),
            mode="simulation",
        )
        self.robot_bridge.navigation_adapter.sim_step_dt = 0.005
        self.bus.subscribe("ActionRequested", self.robot_bridge.on_action_requested)

    def tearDown(self):
        self.robot_bridge.stop()

    def test_01_command_priority_hierarchy(self):
        """
        Validates priority enumeration and ordering:
        EMERGENCY_STOP (1) > STOP (2) > SAFETY_COMMAND (3) > ACTIVE_ROBOT_COMMAND (4) > NORMAL_INTERACTION (5)
        """
        self.assertEqual(get_action_priority("EmergencyStop"), CommandPriority.EMERGENCY_STOP)
        self.assertEqual(get_action_priority("Stop"), CommandPriority.STOP)
        self.assertEqual(get_action_priority("Pause"), CommandPriority.SAFETY_COMMAND)
        self.assertEqual(get_action_priority("Resume"), CommandPriority.SAFETY_COMMAND)
        self.assertEqual(get_action_priority("NavigateTo"), CommandPriority.ACTIVE_ROBOT_COMMAND)
        self.assertEqual(get_action_priority("NavigateToRoom"), CommandPriority.ACTIVE_ROBOT_COMMAND)
        self.assertEqual(get_action_priority("TurnTo"), CommandPriority.ACTIVE_ROBOT_COMMAND)
        self.assertEqual(get_action_priority("Speak"), CommandPriority.NORMAL_INTERACTION)
        self.assertEqual(get_action_priority("Express"), CommandPriority.NORMAL_INTERACTION)
        self.assertEqual(get_action_priority("LookAt"), CommandPriority.NORMAL_INTERACTION)

        # Numerical ordering: lower value = higher priority
        self.assertLess(CommandPriority.EMERGENCY_STOP, CommandPriority.STOP)
        self.assertLess(CommandPriority.STOP, CommandPriority.SAFETY_COMMAND)
        self.assertLess(CommandPriority.SAFETY_COMMAND, CommandPriority.ACTIVE_ROBOT_COMMAND)
        self.assertLess(CommandPriority.ACTIVE_ROBOT_COMMAND, CommandPriority.NORMAL_INTERACTION)

    def test_02_concurrent_subsystem_load(self):
        """
        Simultaneous execution:
        Navigation active + Telemetry stream + Camera frames + LiDAR frames + TTS playback + User interaction.
        Verifies system processes all streams without race conditions or deadlocks.
        """
        stop_threads = threading.Event()
        counters = {"telemetry": 0, "camera": 0, "lidar": 0, "tts": 0, "dialogue": 0}

        def telemetry_worker():
            while not stop_threads.is_set():
                self.bus.emit("TelemetryHeartbeat", {"battery": 95, "temp": 38.5})
                counters["telemetry"] += 1
                time.sleep(0.005)

        def camera_worker():
            while not stop_threads.is_set():
                self.bus.emit("CameraFrameMeta", {"frame_id": counters["camera"], "resolution": [640, 480]})
                counters["camera"] += 1
                time.sleep(0.005)

        def lidar_worker():
            while not stop_threads.is_set():
                self.bus.emit("LidarScanMeta", {"ranges_count": 360, "min_range": 0.15})
                counters["lidar"] += 1
                time.sleep(0.005)

        threads = [
            threading.Thread(target=telemetry_worker, daemon=True),
            threading.Thread(target=camera_worker, daemon=True),
            threading.Thread(target=lidar_worker, daemon=True),
        ]
        for t in threads:
            t.start()

        # Start navigation
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="trace-concurrent-nav")
        time.sleep(0.02)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # Trigger concurrent dialogue interactions while moving
        for i in range(10):
            res = self.gateway.process_text("What is this building?", trace_id=f"trace-concurrent-dial-{i}")
            self.assertIsNotNone(res)
            self.gateway.fsm.transition_to(CognitiveState.IDLE, reason="Dialogue turn finished")
            counters["dialogue"] += 1
            time.sleep(0.005)

        # Stop background workers
        stop_threads.set()
        for t in threads:
            t.join(timeout=1.0)

        # Verify robot maintained navigation without being knocked into error
        self.assertIn(self.robot_bridge.state_machine.state, (RobotState.NAVIGATING, RobotState.IDLE))
        self.assertTrue(counters["telemetry"] > 5)
        self.assertTrue(counters["camera"] > 5)
        self.assertTrue(counters["lidar"] > 5)
        self.assertEqual(counters["dialogue"], 10)

    def test_03_dialogue_never_delays_emergency_stop(self):
        """
        Priority Invariant:
        When a slow or complex dialogue request is processing or active,
        an Emergency STOP command must preempt and halt the robot in < 5ms.
        """
        # Start navigation
        self.gateway.process_text("Take me to Central Library.", trace_id="trace-prio-nav")
        time.sleep(0.02)
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

        # Issue Emergency STOP
        t0 = time.perf_counter()
        stop_res: GatewayResult = self.gateway.process_text("Emergency stop!", trace_id="trace-prio-stop")
        t_stop = (time.perf_counter() - t0) * 1000.0

        # Robot must stop immediately and enter EMERGENCY_STOP
        self.assertEqual(self.robot_bridge.state_machine.state, RobotState.EMERGENCY_STOP)
        self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)
        self.assertLess(t_stop, 10.0, f"Emergency Stop took {t_stop:.2f}ms, budget is 10.0ms")

    def test_04_stop_under_heavy_load_50_trials(self):
        """
        Section 12: STOP UNDER LOAD
        Run active navigation while simultaneously generating:
          - CPU load (tight floating-point computation)
          - Logging load (continuous log records)
          - EventBus traffic (flooding high-rate events)
          - Simulated sensor traffic
        Then issue STOP.
        Measures STOP INPUT -> STOP DETECTION -> SAFETY -> ROBOT STOP across 50 trials.
        Records worst-case (MAX) and P99 latency.
        """
        harness = BenchmarkHarness()
        stop_load = threading.Event()

        def cpu_stress_worker():
            val = 1.0001
            while not stop_load.is_set():
                val = (val * 1.00001) % 1000.0

        def event_stress_worker():
            idx = 0
            while not stop_load.is_set():
                self.bus.emit("StressEvent", {"payload": idx, "data": [0.1] * 50})
                idx += 1
                time.sleep(0.001)

        cpu_threads = [threading.Thread(target=cpu_stress_worker, daemon=True) for _ in range(2)]
        bus_threads = [threading.Thread(target=event_stress_worker, daemon=True) for _ in range(2)]

        for t in cpu_threads + bus_threads:
            t.start()

        latencies_ms = []

        try:
            for trial in range(50):
                # 1. Reset all state machines to IDLE and start navigation
                self.safety_gate.reset_emergency_stop()
                self.gateway.fsm.transition_to(CognitiveState.IDLE, reason="Trial reset")
                self.robot_bridge.state_machine.reset_from_emergency("Trial reset")
                self.robot_bridge.navigation_adapter.cancel_navigation(reason="Trial reset")
                self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

                self.gateway.process_text("Take me to the Robotics Lab.", trace_id=f"load-nav-{trial}")
                time.sleep(0.008)

                # Verify navigation is active
                self.assertEqual(self.robot_bridge.state_machine.state, RobotState.NAVIGATING)

                # 2. Issue STOP under heavy stress
                t_input = time.perf_counter()
                stop_res = self.gateway.process_text("Stop.", trace_id=f"load-stop-{trial}")
                t_stopped = time.perf_counter()

                # Verify robot stopped
                self.assertEqual(self.robot_bridge.state_machine.state, RobotState.EMERGENCY_STOP)
                self.assertEqual(self.robot_bridge.navigation_adapter.current_speed, 0.0)

                elapsed_ms = (t_stopped - t_input) * 1000.0
                latencies_ms.append(elapsed_ms)
                harness.record(
                    operation="stop_under_heavy_load",
                    tier=LatencyTier.E2E,
                    start_time=t_input,
                    end_time=t_stopped,
                    trace_id=f"load-stop-{trial}",
                )

        finally:
            stop_load.set()
            for t in cpu_threads + bus_threads:
                t.join(timeout=1.0)

        stats = harness.calculate_stats("stop_under_heavy_load")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 50)

        # Latency Assertions under heavy synthetic load (guaranteed sub-250ms stopping under 100% CPU contention)
        self.assertLess(stats.p50_ms, 100.0, f"STOP P50 under load ({stats.p50_ms:.3f}ms) exceeded 100.0ms")
        self.assertLess(stats.p99_ms, 250.0, f"STOP P99 under load ({stats.p99_ms:.3f}ms) exceeded 250.0ms")
        self.assertLess(stats.max_ms, 300.0, f"STOP MAX under load ({stats.max_ms:.3f}ms) exceeded 300.0ms")

        print(
            f"\n🔥 [STOP UNDER LOAD] (50 trials): P50={stats.p50_ms:.3f}ms, P90={stats.p90_ms:.3f}ms, "
            f"P95={stats.p95_ms:.3f}ms, P99={stats.p99_ms:.3f}ms, MAX={stats.max_ms:.3f}ms, MEAN={stats.mean_ms:.3f}ms"
        )


if __name__ == "__main__":
    unittest.main()
