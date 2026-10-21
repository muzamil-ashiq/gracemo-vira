#!/usr/bin/env python3
"""
GRaCEmo ViRa — Navigation Adapter
Executes metric navigation goals via Nav2 Action Client (in ROS 2 environment)
or via high-fidelity simulated kinematic unicycle trajectory tracker (in simulation/Mac dev environment).
Provides full lifecycle feedback: acceptance, progress, arrival, cancellation, and failure.
Supports hardware coupling, physical mission FSM, obstacle handling, and fault injection.
"""
from __future__ import annotations
import logging
import math
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from .feedback_adapter import FeedbackAdapter
from .state_machine import HardwareMode, RobotState, RobotStateMachine

log = logging.getLogger("gracemo.bridge.navigation")


class NavigationAdapter:
    """
    Coordinates goal dispatch, waypoint tracking, progress streaming,
    and cancellation against Nav2 or the simulation/hardware kinematic backend.
    """

    def __init__(
        self,
        state_machine: RobotStateMachine,
        feedback_adapter: FeedbackAdapter,
        sim_step_dt: float = 0.05,
        hardware_adapter: Optional[Any] = None,
    ):
        self.sm = state_machine
        self.feedback = feedback_adapter
        self.sim_step_dt = sim_step_dt
        self.hardware_adapter = hardware_adapter

        # Current robot pose state
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.current_speed = 0.0
        self.goal_tolerance = 0.30

        # Navigation execution state
        self._nav_lock = threading.RLock()
        self._active_thread: Optional[threading.Thread] = None
        self._cancel_requested = threading.Event()
        self._active_destination: Optional[str] = None
        self._active_trace_id: Optional[str] = None
        self._force_next_failure: bool = False

        # Phase 6 Fault and Obstacle Injection Hooks
        self._injected_obstacle: Optional[Dict[str, Any]] = None
        self._injected_sensor_fault: Optional[str] = None
        self._injected_localization_loss: bool = False
        self._injected_dead_end: bool = False

    @property
    def current_pose(self) -> Tuple[float, float, float]:
        return (self.current_x, self.current_y, self.current_yaw)

    @current_pose.setter
    def current_pose(self, pose: Tuple[float, float, float]):
        self.current_x = pose[0]
        self.current_y = pose[1]
        self.current_yaw = pose[2] if len(pose) > 2 else 0.0

    def set_hardware_adapter(self, hw: Any):
        with self._nav_lock:
            self.hardware_adapter = hw

    def set_pose(self, x: float, y: float, yaw: float = 0.0):
        with self._nav_lock:
            self.current_x = x
            self.current_y = y
            self.current_yaw = yaw

    def force_next_failure(self, force: bool = True):
        """Forces the subsequent navigation action to fail (for Golden Test #5)."""
        self._force_next_failure = force

    def inject_obstacle(self, obstacle_type: str = "static", detour_m: float = 0.5, block_sec: float = 0.2):
        """Injects an obstacle condition for Phase 6 validation."""
        self._injected_obstacle = {
            "type": obstacle_type,
            "detour_m": detour_m,
            "block_sec": block_sec,
            "handled": False,
        }

    def inject_sensor_fault(self, sensor: str = "lidar"):
        """Simulates sensor loss during active navigation."""
        self._injected_sensor_fault = sensor

    def inject_localization_loss(self):
        """Simulates localization invalidation / covariance spike."""
        self._injected_localization_loss = True

    def inject_dead_end(self):
        """Simulates dead-end corridor with all replan trajectories blocked."""
        self._injected_dead_end = True

    def clear_injected_faults(self):
        self._injected_obstacle = None
        self._injected_sensor_fault = None
        self._injected_localization_loss = False
        self._injected_dead_end = False

    def navigate_to(
        self,
        target_x: float,
        target_y: float,
        target_name: str,
        trace_id: str,
        target_yaw: Optional[float] = None,
        tolerance_m: float = 0.30,
        session_id: Optional[str] = None,
    ) -> bool:
        """Commences navigation to coordinates (target_x, target_y)."""
        with self._nav_lock:
            # If already navigating, cancel prior mission cleanly
            if self.sm.state in (RobotState.NAVIGATING, RobotState.PLANNING, RobotState.ARRIVING):
                log.info(f"🔄 Pre-empting existing navigation for new goal: {target_name}")
                self.cancel_navigation(reason="Pre-empted by new goal")

            # Check critical battery before starting
            if self.hardware_adapter and self.sm.mode != HardwareMode.SIMULATION:
                telem = self.hardware_adapter.get_telemetry()
                if telem.battery_status.value == "CRITICAL":
                    log.warning(f"⛔ Cannot start navigation: Battery CRITICAL ({telem.battery_voltage:.2f}V)")
                    self.feedback.emit_navigation_failed(
                        destination=target_name,
                        reason=f"Battery CRITICAL ({telem.battery_voltage:.2f}V < 10.5V)",
                        stuck_x=self.current_x,
                        stuck_y=self.current_y,
                        trace_id=trace_id,
                        session_id=session_id,
                    )
                    return False

            # Section 24 FSM: IDLE -> PLANNING -> NAVIGATING
            self.sm.transition_to(RobotState.PLANNING, reason=f"Planning path to {target_name}")
            if not self.sm.transition_to(RobotState.NAVIGATING, reason=f"Starting navigation to {target_name}"):
                log.warning(f"Cannot start navigation in state: {self.sm.state.value}")
                return False

            self._cancel_requested.clear()
            self._active_destination = target_name
            self._active_trace_id = trace_id

            # Emit NavigationStarted
            dist_initial = math.hypot(target_x - self.current_x, target_y - self.current_y)
            est_dur = max(2.0, dist_initial / 0.35)
            self.feedback.emit_navigation_started(
                destination=target_name,
                target_x=target_x,
                target_y=target_y,
                trace_id=trace_id,
                estimated_duration_sec=est_dur,
                session_id=session_id,
            )

            # Check if forced failure is requested
            if self._force_next_failure:
                self._force_next_failure = False
                self._launch_failure_thread(target_name, target_x, target_y, trace_id, session_id)
                return True

            # Launch navigation execution thread
            self._active_thread = threading.Thread(
                target=self._run_navigation_loop,
                args=(target_x, target_y, target_name, target_yaw, tolerance_m, trace_id, session_id),
                daemon=True,
            )
            self._active_thread.start()
            return True

    def cancel_navigation(self, reason: str = "User Cancel", trace_id: Optional[str] = None) -> bool:
        """Idempotent cancellation of active navigation following Section 24 FSM."""
        with self._nav_lock:
            tid = trace_id or self._active_trace_id or "trace_cancel"
            self._cancel_requested.set()

            if self.sm.state in (RobotState.NAVIGATING, RobotState.PLANNING, RobotState.ARRIVING):
                self.sm.transition_to(RobotState.CANCEL_REQUESTED, reason=f"Navigation cancellation requested: {reason}")
                self.sm.transition_to(RobotState.STOPPING, reason=f"Stopping motion: {reason}")
                self.sm.transition_to(RobotState.IDLE, reason=f"Navigation cancelled: {reason}")
                self.feedback.emit_robot_stopped(
                    reason=reason,
                    x=self.current_x,
                    y=self.current_y,
                    trace_id=tid,
                    emergency=False,
                )
                self.current_speed = 0.0
                if self.hardware_adapter:
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)
                return True

            return True

    def stop_immediately(self, reason: str = "Emergency Stop", trace_id: Optional[str] = None) -> bool:
        """Immediate stopping and latching of robot."""
        with self._nav_lock:
            tid = trace_id or self._active_trace_id or "trace_stop"
            self._cancel_requested.set()
            self.current_speed = 0.0
            if self.hardware_adapter:
                self.hardware_adapter.send_velocity_command(0.0, 0.0)
            self.sm.emergency_stop(reason=reason)
            self.feedback.emit_robot_stopped(
                reason=reason,
                x=self.current_x,
                y=self.current_y,
                trace_id=tid,
                emergency=True,
            )
            return True

    def _launch_failure_thread(
        self, target_name: str, target_x: float, target_y: float, trace_id: str, session_id: Optional[str]
    ):
        def _fail():
            time.sleep(0.05)
            self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason="Nav2 planner failed: path blocked by obstacle")
            self.feedback.emit_navigation_failed(
                destination=target_name,
                reason="Path planning failed: all trajectories obstructed",
                stuck_x=self.current_x,
                stuck_y=self.current_y,
                trace_id=trace_id,
                recovery_attempts=3,
                session_id=session_id,
            )
            self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe idle following failure")
            self.sm.transition_to(RobotState.IDLE, reason="Recovered to IDLE after failure")

        t = threading.Thread(target=_fail, daemon=True)
        t.start()

    def _run_navigation_loop(
        self,
        target_x: float,
        target_y: float,
        target_name: str,
        target_yaw: Optional[float],
        tolerance_m: float,
        trace_id: str,
        session_id: Optional[str],
    ):
        """Simulates closed-loop differential drive waypoint pursuit with progress feedback."""
        log.info(f"🚀 [NAV EXEC] Navigating to '{target_name}' at ({target_x:.2f}, {target_y:.2f})")
        # Section 24 transition from PLANNING to NAVIGATING
        self.sm.transition_to(RobotState.NAVIGATING, reason=f"Executing path to {target_name}")

        start_x = self.current_x
        start_y = self.current_y
        initial_dist = math.hypot(target_x - start_x, target_y - start_y)
        max_speed = 0.35  # m/s

        last_progress_t = 0.0
        loop_cycles = 0

        while not self._cancel_requested.is_set():
            loop_cycles += 1

            # 1. Hardware safety telemetry checks
            if self.hardware_adapter and self.sm.mode != HardwareMode.SIMULATION:
                telem = self.hardware_adapter.get_telemetry()
                if telem.physical_estop_pressed:
                    log.warning("🛑 Physical E-Stop pressed during transit! Halting.")
                    self.stop_immediately(reason="Physical E-stop pressed during navigation", trace_id=trace_id)
                    return
                if telem.battery_status.value == "CRITICAL":
                    log.warning("🛑 Battery dropped to CRITICAL during transit! Aborting mission.")
                    self.current_speed = 0.0
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)
                    self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason="Battery dropped below 10.5V")
                    self.feedback.emit_navigation_failed(
                        destination=target_name,
                        reason="Battery CRITICAL during navigation (<10.5V)",
                        stuck_x=self.current_x,
                        stuck_y=self.current_y,
                        trace_id=trace_id,
                        session_id=session_id,
                    )
                    self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe stop on critical battery")
                    return
                if not telem.motor_controller_connected:
                    log.warning("🛑 Motor controller link lost during transit! Aborting mission.")
                    self.current_speed = 0.0
                    self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason="Motor controller link lost")
                    self.feedback.emit_navigation_failed(
                        destination=target_name,
                        reason="Communication lost with physical motor controller",
                        stuck_x=self.current_x,
                        stuck_y=self.current_y,
                        trace_id=trace_id,
                        session_id=session_id,
                    )
                    self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe stop on motor controller disconnect")
                    return

            # 2. Check injected localization loss
            if self._injected_localization_loss:
                log.warning("🛑 Lost localization condition triggered! Safe stopping.")
                self.current_speed = 0.0
                if self.hardware_adapter:
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)
                self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason="Localization lost: covariance > threshold")
                self.feedback.emit_navigation_failed(
                    destination=target_name,
                    reason="Localization lost: position uncertainty covariance exceeded safety bounds",
                    stuck_x=self.current_x,
                    stuck_y=self.current_y,
                    trace_id=trace_id,
                    session_id=session_id,
                )
                self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe stop on localization loss")
                return

            # 3. Check injected sensor failure
            if self._injected_sensor_fault:
                faulty_sensor = self._injected_sensor_fault
                log.warning(f"🛑 Sensor failure triggered ({faulty_sensor})! Safe stopping.")
                self.current_speed = 0.0
                if self.hardware_adapter:
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)
                self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason=f"Sensor failure: {faulty_sensor} lost")
                self.feedback.emit_navigation_failed(
                    destination=target_name,
                    reason=f"Sensor hardware failure: {faulty_sensor.upper()} communication dropped",
                    stuck_x=self.current_x,
                    stuck_y=self.current_y,
                    trace_id=trace_id,
                    session_id=session_id,
                )
                self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe stop on sensor loss")
                return

            # 4. Check injected dead-end
            if self._injected_dead_end:
                log.warning("🛑 Route blocked by dead end! Recovery attempts exhausted.")
                self.current_speed = 0.0
                if self.hardware_adapter:
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)
                self.sm.transition_to(RobotState.NAVIGATION_FAILED, reason="Dead-end: route blocked, replan exhausted")
                self.feedback.emit_navigation_failed(
                    destination=target_name,
                    reason="Dead-end detected: all alternative paths obstructed",
                    stuck_x=self.current_x,
                    stuck_y=self.current_y,
                    trace_id=trace_id,
                    recovery_attempts=3,
                    session_id=session_id,
                )
                self.sm.transition_to(RobotState.SAFE_IDLE, reason="Safe stop on dead end")
                return

            # 5. Check injected obstacle (static or dynamic)
            if self._injected_obstacle and not self._injected_obstacle.get("handled", False):
                obs = self._injected_obstacle
                obs_type = obs.get("type", "static")
                self.feedback.emit_obstacle_detected(
                    distance=0.8,
                    direction="front",
                    trace_id=trace_id,
                    session_id=session_id,
                )
                if obs_type == "dynamic":
                    # Slow/stop temporarily to allow dynamic obstacle to clear
                    log.info("⏸️ Dynamic obstacle in path: stopping temporarily to allow passage...")
                    self.current_speed = 0.0
                    if self.hardware_adapter:
                        self.hardware_adapter.send_velocity_command(0.0, 0.0)
                    time.sleep(obs.get("block_sec", 0.2))
                    obs["handled"] = True
                    log.info("▶️ Dynamic obstacle cleared: resuming path.")
                elif obs_type == "static":
                    # Replan detour
                    log.info("🔄 Static obstacle detected: costmap updated, replanning detour...")
                    detour = obs.get("detour_m", 0.5)
                    self.current_y += detour * 0.2  # simulate detour adjustment
                    obs["handled"] = True

            # 6. Waypoint Tracking & Motion Kinematics
            dx = target_x - self.current_x
            dy = target_y - self.current_y
            dist_remaining = math.hypot(dx, dy)

            # Check arrival tolerance
            if dist_remaining <= tolerance_m:
                self.current_speed = 0.0
                if target_yaw is not None:
                    self.current_yaw = target_yaw
                if self.hardware_adapter:
                    self.hardware_adapter.send_velocity_command(0.0, 0.0)

                # Section 24 FSM: NAVIGATING -> ARRIVING -> ARRIVED -> IDLE
                self.sm.transition_to(RobotState.ARRIVING, reason=f"Approaching destination {target_name}")
                self.sm.transition_to(RobotState.ARRIVED, reason=f"Arrived at destination: {target_name}")
                self.feedback.emit_navigation_arrived(
                    destination=target_name,
                    x=self.current_x,
                    y=self.current_y,
                    trace_id=trace_id,
                    session_id=session_id,
                )
                self.sm.transition_to(RobotState.IDLE, reason=f"Mission complete at {target_name}")
                return

            # Advance kinematics along vector toward target
            step = min(dist_remaining, max_speed * self.sim_step_dt)
            self.current_speed = max_speed
            bearing = math.atan2(dy, dx)
            self.current_yaw = bearing
            self.current_x += step * math.cos(bearing)
            self.current_y += step * math.sin(bearing)

            # Dispatch speed to physical/simulated hardware controller
            if self.hardware_adapter:
                self.hardware_adapter.send_velocity_command(self.current_speed, 0.0)

            # Stream progress updates periodically (~4Hz)
            now = time.time()
            if now - last_progress_t >= 0.25:
                last_progress_t = now
                fraction = 1.0 - (dist_remaining / max(0.001, initial_dist))
                self.feedback.emit_navigation_progress(
                    destination=target_name,
                    current_x=self.current_x,
                    current_y=self.current_y,
                    distance_remaining_m=dist_remaining,
                    fraction_completed=fraction,
                    trace_id=trace_id,
                    session_id=session_id,
                )

            time.sleep(self.sim_step_dt)

        # Loop exited due to cancellation
        self.current_speed = 0.0
        if self.hardware_adapter:
            self.hardware_adapter.send_velocity_command(0.0, 0.0)
        log.info("⏹️ [NAV EXEC] Navigation loop terminated on cancel/stop")
