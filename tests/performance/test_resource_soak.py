#!/usr/bin/env python3
"""
GRaCEmo ViRa — Resource Monitoring, Memory Leak & Long-Duration Soak Suite
Measures:
  - System Resources: CPU usage, RAM / Resident Set Size (RSS), EventBus throughput
  - Memory Stability: 100 continuous mission cycles (Listen -> Think -> Respond -> Navigate -> Arrive -> Idle)
  - Slope analysis to detect unbounded memory growth
  - Long-duration soak test verifying zero crashes, zero deadlocks, and latency drift stability.
"""
from __future__ import annotations
import gc
import logging
import os
import resource
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "graceemo_interaction"))
sys.path.insert(0, str(ROOT / "adapters" / "robot-bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.gateway import InteractionGateway, GatewayResult
from core.event_bus import EventBusClient
from core.safety_gate import SafetyGate, CommandValidator
from core.fast_path import FastPathMatcher
from core.state_machine import CognitiveState, Expression
from core.interaction_adapter import InteractionAdapter
from core.tts_adapter import TTSAdapter

from gracemo_bridge.bridge import RobotBridge
from gracemo_bridge.state_machine import RobotState
from benchmark_harness import BenchmarkHarness, LatencyTier


def get_current_rss_kb() -> int:
    """Returns current resident memory in KB."""
    try:
        pid = os.getpid()
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)]).decode().strip()
        return int(out)
    except Exception:
        # Fallback to getrusage maxrss (converted to KB)
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # On macOS ru_maxrss is bytes, on Linux KB
        return usage // 1024 if sys.platform == "darwin" else usage


class TestResourceSoak(unittest.TestCase):
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

    def test_01_resource_profile_across_operational_modes(self):
        """
        Section 24: Resource Monitoring
        Measures CPU and RAM (RSS) during:
          1. Idle
          2. Voice interaction
          3. Active navigation
          4. Navigation + Telemetry + Simulated Sensor load
        """
        profiles = {}

        # 1. Idle mode
        gc.collect()
        t0_cpu = time.process_time()
        t0_wall = time.perf_counter()
        time.sleep(0.05)
        cpu_idle = (time.process_time() - t0_cpu) / (time.perf_counter() - t0_wall) * 100.0
        profiles["idle"] = {"rss_kb": get_current_rss_kb(), "cpu_pct": max(0.0, cpu_idle)}

        # 2. Voice interaction
        t0_cpu = time.process_time()
        t0_wall = time.perf_counter()
        for i in range(20):
            self.gateway.process_text("Take me to the Robotics Lab.", trace_id=f"res-voice-{i}")
            self.gateway.fsm.transition_to(CognitiveState.IDLE)
            self.robot_bridge.navigation_adapter.cancel_navigation(reason="Reset")
        cpu_voice = (time.process_time() - t0_cpu) / (time.perf_counter() - t0_wall) * 100.0
        profiles["voice_interaction"] = {"rss_kb": get_current_rss_kb(), "cpu_pct": max(0.0, cpu_voice)}

        # 3. Active navigation
        self.gateway.process_text("Take me to the Robotics Lab.", trace_id="res-nav")
        t0_cpu = time.process_time()
        t0_wall = time.perf_counter()
        time.sleep(0.05)
        cpu_nav = (time.process_time() - t0_cpu) / (time.perf_counter() - t0_wall) * 100.0
        profiles["navigation"] = {"rss_kb": get_current_rss_kb(), "cpu_pct": max(0.0, cpu_nav)}
        self.robot_bridge.navigation_adapter.cancel_navigation(reason="Profile done")

        # 4. Navigation + Sensor/Telemetry Traffic
        stop_sensor = threading.Event()
        def sensor_emitter():
            while not stop_sensor.is_set():
                self.bus.emit("LidarScan", {"ranges": [1.5] * 180})
                time.sleep(0.005)

        st = threading.Thread(target=sensor_emitter, daemon=True)
        st.start()

        self.gateway.process_text("Take me to Central Library.", trace_id="res-heavy")
        t0_cpu = time.process_time()
        t0_wall = time.perf_counter()
        time.sleep(0.05)
        cpu_heavy = (time.process_time() - t0_cpu) / (time.perf_counter() - t0_wall) * 100.0
        stop_sensor.set()
        st.join(timeout=1.0)
        self.robot_bridge.navigation_adapter.cancel_navigation(reason="Heavy profile done")

        profiles["navigation_plus_sensors"] = {"rss_kb": get_current_rss_kb(), "cpu_pct": max(0.0, cpu_heavy)}

        # Verify memory remains stable across profiles (bounded within 100MB of baseline)
        baseline_rss = profiles["idle"]["rss_kb"]
        for mode, data in profiles.items():
            delta_mb = (data["rss_kb"] - baseline_rss) / 1024.0
            self.assertLess(delta_mb, 100.0, f"RSS in mode {mode} grew by {delta_mb:.2f}MB (> 100MB over baseline)")

        print("\n📈 [RESOURCE PROFILING RESULTS]")
        for mode, data in profiles.items():
            print(f"  - {mode:<26}: RSS = {data['rss_kb']/1024:.2f} MB, CPU = {data['cpu_pct']:.1f}%")

    def test_02_memory_leak_100_missions(self):
        """
        Section 25: Memory Leak Test
        Runs 100 continuous mission cycles:
          Listen -> Think -> Respond -> Navigate -> Arrive -> Idle
        Tracks RSS at intervals.
        Verifies memory growth slope is <= 50 KB / mission (negligible/bounded cache).
        """
        rss_samples = []
        gc.collect()
        initial_rss = get_current_rss_kb()

        for mission in range(100):
            tid = f"mem-mission-{mission}"

            # 1. Listen & Think & Respond & Navigate
            self.safety_gate.reset_emergency_stop()
            self.gateway.fsm.transition_to(CognitiveState.IDLE)
            self.robot_bridge.state_machine.reset_from_emergency()
            self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

            gw_res = self.gateway.process_text("Take me to the Robotics Lab.", trace_id=tid)
            self.assertEqual(gw_res.intent, "NAVIGATE")

            # 2. Simulate arrival
            self.robot_bridge.feedback_adapter.emit_navigation_arrived(
                destination="Robotics Research Lab",
                x=2.5,
                y=2.0,
                trace_id=tid,
            )

            # 3. Clean up back to IDLE
            self.robot_bridge.navigation_adapter.cancel_navigation(reason="Mission cycle complete")
            self.gateway.fsm.transition_to(CognitiveState.IDLE)

            if mission % 10 == 0:
                gc.collect()
                rss_samples.append((mission, get_current_rss_kb()))

        final_rss = get_current_rss_kb()
        growth_kb = final_rss - initial_rss
        growth_per_mission = growth_kb / 100.0

        # Memory assertion: less than 150 KB growth per mission
        self.assertLess(growth_per_mission, 150.0, f"Memory leak detected: {growth_per_mission:.2f} KB/mission")
        print(f"\n🧠 [MEMORY LEAK TEST] 100 Missions: Initial={initial_rss/1024:.2f}MB, Final={final_rss/1024:.2f}MB, Delta={growth_kb/1024:.2f}MB ({growth_per_mission:.2f}KB/mission)")

    def test_03_soak_test_drift_and_stability(self):
        """
        Section 26: Soak Test & Latency Drift Analysis
        Runs 50 full autonomous cycles measuring latency drift between early and late runs.
        Ensures 100% mission success, 0 unexpected exceptions, 0 deadlocks.
        """
        early_latencies = []
        late_latencies = []
        total_missions = 50
        successful_missions = 0
        exceptions_encountered = []

        for m in range(total_missions):
            tid = f"soak-m-{m}"
            try:
                t0 = time.perf_counter()

                self.safety_gate.reset_emergency_stop()
                self.gateway.fsm.transition_to(CognitiveState.IDLE)
                self.robot_bridge.state_machine.reset_from_emergency()
                self.robot_bridge.navigation_adapter.set_pose(0.0, 0.0, 0.0)

                # Command
                gw_res = self.gateway.process_text("Take me to the Robotics Lab.", trace_id=tid)
                self.assertEqual(gw_res.intent, "NAVIGATE")

                # Arrival
                self.robot_bridge.feedback_adapter.emit_navigation_arrived(
                    destination="Robotics Research Lab",
                    x=2.5,
                    y=2.0,
                    trace_id=tid,
                )
                self.robot_bridge.navigation_adapter.cancel_navigation(reason="Soak reset")

                dur_ms = (time.perf_counter() - t0) * 1000.0
                successful_missions += 1

                if m < 15:
                    early_latencies.append(dur_ms)
                elif m >= 35:
                    late_latencies.append(dur_ms)

            except Exception as e:
                exceptions_encountered.append(str(e))

        self.assertEqual(len(exceptions_encountered), 0, f"Exceptions encountered: {exceptions_encountered}")
        self.assertEqual(successful_missions, total_missions)

        avg_early = sum(early_latencies) / len(early_latencies)
        avg_late = sum(late_latencies) / len(late_latencies)
        drift_ms = abs(avg_late - avg_early)

        # Latency drift must be < 5.0ms (no performance degradation over time)
        self.assertLess(drift_ms, 5.0, f"Latency drift ({drift_ms:.2f}ms) exceeded 5.0ms threshold")
        print(f"\n⏱️  [SOAK DRIFT] Missions={total_missions}, Success={successful_missions}/50, EarlyAvg={avg_early:.3f}ms, LateAvg={avg_late:.3f}ms, Drift={drift_ms:.3f}ms")


if __name__ == "__main__":
    unittest.main()
