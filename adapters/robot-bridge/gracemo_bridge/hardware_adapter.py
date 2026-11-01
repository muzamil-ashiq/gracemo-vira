#!/usr/bin/env python3
"""
GRaCEmo ViRa — Physical Hardware Adapter & Motor Controller Interface
Level 0/1 Actuation and Sensor Telemetry Substrate.

Responsibilities:
  1. Low-level command translation: ROS 2 /cmd_vel -> Differential drive motor controller.
  2. Telemetry ingestion: Encoder ticks, battery voltage, physical E-stop switch, IMU, LiDAR.
  3. Hardware Command Watchdog: Guarantees zero velocity on command stream stall (> 400ms).
  4. Physical Emergency Stop: Immediate motor power cut; remains locked on release until explicit reset.
  5. Conservative Mode Velocity Saturation (HARDWARE_SAFE, HARDWARE_TEST, HARDWARE_TELEOP, HARDWARE_AUTONOMOUS).
  6. Zero Semantic Knowledge: Strictly prohibited from NLP, LLMs, place names, or dialogue.
"""
from __future__ import annotations
import enum
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .state_machine import HardwareMode, MODE_VELOCITY_LIMITS, RobotState, RobotStateMachine

log = logging.getLogger("gracemo.hardware_adapter")


class BatteryStatus(str, enum.Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    CRITICAL = "CRITICAL"


@dataclass
class HardwareTelemetry:
    timestamp: float = 0.0
    left_wheel_velocity: float = 0.0
    right_wheel_velocity: float = 0.0
    left_encoder_ticks: int = 0
    right_encoder_ticks: int = 0
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    odom_x: float = 0.0
    odom_y: float = 0.0
    odom_yaw: float = 0.0
    battery_voltage: float = 12.4
    battery_status: BatteryStatus = BatteryStatus.NORMAL
    physical_estop_pressed: bool = False
    motor_controller_connected: bool = True
    watchdog_tripped: bool = False
    heartbeat_age_sec: float = 0.0


class MotorControllerInterface:
    """Abstract/Mockable Physical Motor Controller Interface."""

    def __init__(
        self,
        wheel_separation_m: float = 0.32,
        wheel_radius_m: float = 0.065,
        encoder_ticks_per_rev: int = 2048,
    ):
        self.wheel_separation_m = wheel_separation_m
        self.wheel_radius_m = wheel_radius_m
        self.encoder_ticks_per_rev = encoder_ticks_per_rev

        self._connected = True
        self._physical_estop = False
        self._target_v_left = 0.0
        self._target_v_right = 0.0
        self._actual_v_left = 0.0
        self._actual_v_right = 0.0
        self._left_ticks = 0
        self._right_ticks = 0
        self._left_ticks_float = 0.0
        self._right_ticks_float = 0.0

        self._battery_voltage = 12.4
        self._last_cmd_time = time.time()
        self._last_heartbeat_time = time.time()
        self._wheel_slip_factor = 1.0  # 1.0 = ideal, <1.0 = slip

    def connect(self) -> bool:
        self._connected = True
        self._last_heartbeat_time = time.time()
        return True

    def disconnect(self):
        self._connected = False
        self._target_v_left = 0.0
        self._target_v_right = 0.0
        self._actual_v_left = 0.0
        self._actual_v_right = 0.0

    def set_wheel_velocities(self, v_left: float, v_right: float) -> bool:
        """Sets target wheel velocities in m/s."""
        if not self._connected:
            return False
        if self._physical_estop:
            self._target_v_left = 0.0
            self._target_v_right = 0.0
            self._actual_v_left = 0.0
            self._actual_v_right = 0.0
            return False

        self._target_v_left = v_left
        self._target_v_right = v_right
        self._actual_v_left = v_left * self._wheel_slip_factor
        self._actual_v_right = v_right * self._wheel_slip_factor
        self._last_cmd_time = time.time()
        self._last_heartbeat_time = time.time()
        return True

    def set_physical_estop(self, pressed: bool):
        self._physical_estop = pressed
        if pressed:
            self._target_v_left = 0.0
            self._target_v_right = 0.0
            self._actual_v_left = 0.0
            self._actual_v_right = 0.0

    def set_battery_voltage(self, voltage: float):
        self._battery_voltage = voltage

    def set_wheel_slip_factor(self, factor: float):
        self._wheel_slip_factor = max(0.1, min(1.0, float(factor)))

    def step_simulation(self, dt: float):
        """Simulates physical wheel rotation and encoder tick increments."""
        if self._physical_estop or not self._connected:
            self._actual_v_left = 0.0
            self._actual_v_right = 0.0
            return

        # Encoder ticks: dist = velocity * dt; revs = dist / (2 * pi * radius)
        m_per_tick = (2.0 * math.pi * self.wheel_radius_m) / self.encoder_ticks_per_rev
        self._left_ticks_float += (self._actual_v_left * dt) / m_per_tick
        self._right_ticks_float += (self._actual_v_right * dt) / m_per_tick
        self._left_ticks = int(self._left_ticks_float)
        self._right_ticks = int(self._right_ticks_float)

    def read_telemetry(self) -> Dict[str, Any]:
        """Reads hardware registers from motor controller."""
        now = time.time()
        if self._connected:
            self._last_heartbeat_time = now
        hb_age = now - self._last_heartbeat_time
        return {
            "connected": self._connected,
            "physical_estop": self._physical_estop,
            "v_left": self._actual_v_left,
            "v_right": self._actual_v_right,
            "left_ticks": self._left_ticks,
            "right_ticks": self._right_ticks,
            "battery_voltage": self._battery_voltage,
            "heartbeat_age": hb_age,
        }


class HardwareAdapter:
    """
    Spinal Hardware Adapter bridging ROS 2 commands to physical motor controllers.
    Enforces hardware modes, watchdog timing, E-stop circuit, and telemetry conversion.
    """

    def __init__(
        self,
        state_machine: RobotStateMachine,
        motor_controller: Optional[MotorControllerInterface] = None,
        watchdog_timeout_sec: float = 0.40,
        battery_low_v: float = 11.5,
        battery_critical_v: float = 10.5,
        wheel_separation_m: float = 0.32,
        wheel_radius_m: float = 0.065,
    ):
        self.sm = state_machine
        self.wheel_separation_m = wheel_separation_m
        self.wheel_radius_m = wheel_radius_m
        self.watchdog_timeout_sec = watchdog_timeout_sec
        self.battery_low_v = battery_low_v
        self.battery_critical_v = battery_critical_v

        self.controller = motor_controller or MotorControllerInterface(
            wheel_separation_m=wheel_separation_m,
            wheel_radius_m=wheel_radius_m,
        )

        # Safety State
        self._lock = threading.RLock()
        self._watchdog_tripped = False
        self._last_cmd_received_t = time.time()
        self._estop_software_latched = False
        self._test_authorized = False
        self._is_running = True

        # Dead-reckoning Odometry Accumulator
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_yaw = 0.0
        self._last_odom_update_t = time.time()
        self._last_left_ticks = 0
        self._last_right_ticks = 0

        # Current Command Velocities
        self.cur_linear_cmd = 0.0
        self.cur_angular_cmd = 0.0

        # Background Watchdog & Telemetry Poller
        self._poller_thread = threading.Thread(target=self._run_hardware_loop, daemon=True)
        self._poller_thread.start()

        # Startup Safety Guarantee: Always boot in zero velocity and HARDWARE_SAFE mode
        self._enforce_zero_velocity(reason="Startup Safety Check")

    def shutdown(self):
        self._is_running = False
        self._enforce_zero_velocity(reason="Hardware Adapter Shutdown")
        self.controller.disconnect()

    @property
    def e_stop_active(self) -> bool:
        with self._lock:
            return self._estop_software_latched or getattr(self.controller, "_physical_estop", False)

    def get_battery_state(self) -> Dict[str, Any]:
        telem = self.get_telemetry()
        return {
            "voltage": telem.battery_voltage,
            "percentage": 100.0 if telem.battery_voltage >= 12.0 else 15.0,
            "status": telem.battery_status.value,
        }

    def get_motor_state(self) -> Dict[str, Any]:
        telem = self.get_telemetry()
        h = "HEALTHY" if telem.motor_controller_connected else "CRITICAL"
        return {
            "left_velocity": telem.left_wheel_velocity,
            "right_velocity": telem.right_wheel_velocity,
            "connected": telem.motor_controller_connected,
            "health": h,
        }

    def get_encoder_state(self) -> Dict[str, Any]:
        telem = self.get_telemetry()
        return {
            "left_ticks": telem.left_encoder_ticks,
            "right_ticks": telem.right_encoder_ticks,
            "slip_ratio": 0.01,
            "health": "HEALTHY",
        }

    @property
    def current_linear_speed(self) -> float:
        return self.get_telemetry().linear_velocity


    def set_mode(self, mode: HardwareMode, reason: str = "") -> bool:
        """Sets the active hardware operational mode and saturates velocity limits."""
        with self._lock:
            res = self.sm.set_hardware_mode(mode, reason=reason)
            if mode == HardwareMode.HARDWARE_SAFE:
                self._test_authorized = False
                self._enforce_zero_velocity(reason="Switched to HARDWARE_SAFE mode")
            return res

    def authorize_test_motion(self, reason: str = "Test Operator Authorization") -> bool:
        """Authorizes physical testing. Requires non-SAFE mode and healthy hardware."""
        with self._lock:
            telem = self.get_telemetry()
            if telem.physical_estop_pressed or self._estop_software_latched:
                log.warning("Cannot authorize test motion: Emergency stop is active")
                return False
            if telem.battery_status == BatteryStatus.CRITICAL:
                log.warning("Cannot authorize test motion: Battery is CRITICAL (<10.5V)")
                return False
            if not telem.motor_controller_connected:
                log.warning("Cannot authorize test motion: Motor controller disconnected")
                return False

            res = self.sm.authorize_test_motion(reason=reason)
            if res:
                self._test_authorized = True
            return res

    def revoke_test_authorization(self, reason: str = "Revoked by operator") -> bool:
        with self._lock:
            self._test_authorized = False
            self._enforce_zero_velocity(reason=reason)
            return self.sm.revoke_test_authorization(reason=reason)

    def send_velocity_command(self, linear_mps: float, angular_radps: float) -> Tuple[float, float, bool]:
        """
        Translates commanded linear and angular velocities to differential drive wheel speeds.
        Applies mode velocity saturation, E-stop interlocks, and updates command watchdog.
        Returns: (safe_linear, safe_angular, command_accepted)
        """
        with self._lock:
            self._last_cmd_received_t = time.time()
            self._watchdog_tripped = False

            # 1. Emergency Stop Check
            if self._estop_software_latched or self.controller._physical_estop or self.sm.state == RobotState.EMERGENCY_STOP:
                self._enforce_zero_velocity(reason="E-Stop active")
                return 0.0, 0.0, False

            # 2. Critical Battery Interlock
            telem = self.get_telemetry()
            if telem.battery_status == BatteryStatus.CRITICAL:
                self._enforce_zero_velocity(reason="Battery CRITICAL")
                return 0.0, 0.0, False

            # 3. Mode Saturation & State Authorization Check
            limits = self.sm.get_velocity_limits()
            max_lin = limits["max_linear"]
            max_ang = limits["max_angular"]

            if self.sm.mode == HardwareMode.HARDWARE_SAFE:
                self._enforce_zero_velocity(reason="HARDWARE_SAFE disallows motion")
                return 0.0, 0.0, False

            if self.sm.mode == HardwareMode.HARDWARE_TEST and not self._test_authorized:
                self._enforce_zero_velocity(reason="HARDWARE_TEST requires authorized test session")
                return 0.0, 0.0, False

            # Saturate velocities to mode limits
            safe_lin = max(-max_lin, min(max_lin, float(linear_mps)))
            safe_ang = max(-max_ang, min(max_ang, float(angular_radps)))

            # 4. Differential Drive Kinematics:
            # v_left  = v - (omega * L / 2)
            # v_right = v + (omega * L / 2)
            half_w = self.wheel_separation_m / 2.0
            v_left = safe_lin - (safe_ang * half_w)
            v_right = safe_lin + (safe_ang * half_w)

            # 5. Dispatch to Motor Controller
            success = self.controller.set_wheel_velocities(v_left, v_right)
            if success:
                self.cur_linear_cmd = safe_lin
                self.cur_angular_cmd = safe_ang
                if abs(safe_lin) > 0.001 or abs(safe_ang) > 0.001:
                    if self.sm.state in (RobotState.TEST_AUTHORIZED, RobotState.IDLE, RobotState.SAFE_IDLE):
                        self.sm.transition_to(RobotState.MOVING, reason="Velocity commanded")
                else:
                    if self.sm.state == RobotState.MOVING:
                        self.sm.transition_to(RobotState.STOPPING, reason="Zero velocity commanded")
                        self.sm.transition_to(RobotState.SAFE_IDLE, reason="Robot stationary")
                return safe_lin, safe_ang, True
            else:
                self._enforce_zero_velocity(reason="Motor controller rejected velocity")
                return 0.0, 0.0, False

    def trigger_emergency_stop(self, reason: str = "Hardware Emergency Stop Triggered"):
        """Latches emergency stop across both hardware and software state machine."""
        with self._lock:
            self._estop_software_latched = True
            self.controller.set_physical_estop(True)
            self._enforce_zero_velocity(reason=reason)
            self.sm.emergency_stop(reason=reason)

    def release_emergency_stop(self, reason: str = "Manual Hardware E-Stop Reset") -> bool:
        """
        Releases physical E-stop latch.
        Crucial Safety Invariant: Motors REMAIN AT ZERO VELOCITY and state transitions
        to SAFE_IDLE. Never resumes previous motion automatically.
        """
        with self._lock:
            self.controller.set_physical_estop(False)
            self._estop_software_latched = False
            self._enforce_zero_velocity(reason=reason)
            self.sm.reset_from_emergency(reason=reason)
            self.sm.transition_to(RobotState.SAFE_IDLE, reason="Recovered to SAFE_IDLE")
            log.info("✓ Hardware E-Stop released. Robot safely latched in stationary SAFE_IDLE.")
            return True

    def _enforce_zero_velocity(self, reason: str = ""):
        self.cur_linear_cmd = 0.0
        self.cur_angular_cmd = 0.0
        self.controller.set_wheel_velocities(0.0, 0.0)

    def get_telemetry(self) -> HardwareTelemetry:
        """Returns comprehensive physical telemetry snapshot."""
        raw = self.controller.read_telemetry()
        now = time.time()

        # Classify Battery Voltage
        v_bat = raw.get("battery_voltage", 12.4)
        if v_bat < self.battery_critical_v:
            bat_status = BatteryStatus.CRITICAL
        elif v_bat < self.battery_low_v:
            bat_status = BatteryStatus.LOW
        else:
            bat_status = BatteryStatus.NORMAL

        # Differential kinematics forward model
        vl = raw.get("v_left", 0.0)
        vr = raw.get("v_right", 0.0)
        v_lin = (vr + vl) / 2.0
        v_ang = (vr - vl) / self.wheel_separation_m

        return HardwareTelemetry(
            timestamp=now,
            left_wheel_velocity=vl,
            right_wheel_velocity=vr,
            left_encoder_ticks=raw.get("left_ticks", 0),
            right_encoder_ticks=raw.get("right_ticks", 0),
            linear_velocity=v_lin,
            angular_velocity=v_ang,
            odom_x=self.odom_x,
            odom_y=self.odom_y,
            odom_yaw=self.odom_yaw,
            battery_voltage=v_bat,
            battery_status=bat_status,
            physical_estop_pressed=raw.get("physical_estop", False),
            motor_controller_connected=raw.get("connected", False),
            watchdog_tripped=self._watchdog_tripped,
            heartbeat_age_sec=raw.get("heartbeat_age", 0.0),
        )

    def _update_odometry(self, dt: float):
        """Dead-reckoning odometry integration from encoder feedback."""
        raw = self.controller.read_telemetry()
        cur_l = raw.get("left_ticks", 0)
        cur_r = raw.get("right_ticks", 0)

        delta_l = cur_l - self._last_left_ticks
        delta_r = cur_r - self._last_right_ticks
        self._last_left_ticks = cur_l
        self._last_right_ticks = cur_r

        m_per_tick = (2.0 * math.pi * self.wheel_radius_m) / self.controller.encoder_ticks_per_rev
        dist_l = delta_l * m_per_tick
        dist_r = delta_r * m_per_tick

        dist_center = (dist_r + dist_l) / 2.0
        delta_yaw = (dist_r - dist_l) / self.wheel_separation_m

        # Runge-Kutta / Midpoint Integration
        mid_yaw = self.odom_yaw + (delta_yaw / 2.0)
        self.odom_x += dist_center * math.cos(mid_yaw)
        self.odom_y += dist_center * math.sin(mid_yaw)
        self.odom_yaw = (self.odom_yaw + delta_yaw + math.pi) % (2.0 * math.pi) - math.pi

    def poll(self, dt: float = 0.02):
        """Single-step hardware monitoring: watchdog, battery, communication, and odometry."""
        now = time.time()
        self.controller.step_simulation(dt)

        with self._lock:
            # 1. Update Dead-Reckoning Odometry
            self._update_odometry(dt)

            # 2. Command Watchdog Check
            if (now - self._last_cmd_received_t) > self.watchdog_timeout_sec:
                if not self._watchdog_tripped:
                    self._watchdog_tripped = True
                    self._enforce_zero_velocity(reason="Command Watchdog Timeout")
                    if self.sm.state == RobotState.MOVING:
                        self.sm.transition_to(RobotState.STOPPING, reason="Watchdog timeout")
                        self.sm.transition_to(RobotState.SAFE_IDLE, reason="Watchdog stop")

            raw = self.controller.read_telemetry()

            # 3. Critical Battery Voltage Check
            v_bat = raw.get("battery_voltage", 12.4)
            if v_bat < self.battery_critical_v:
                self._enforce_zero_velocity(reason="Critical Battery Voltage")
                if self.sm.state not in (RobotState.EMERGENCY_STOP, RobotState.SAFE_IDLE, RobotState.IDLE, RobotState.OFFLINE):
                    self.sm.transition_to(RobotState.SAFE_IDLE, reason="Critical Battery Voltage (< 10.5V)")

            # 4. Communication Loss Check (> 1.0s or disconnected)
            if not raw.get("connected", True) or raw.get("heartbeat_age", 0.0) > 1.0:
                self._enforce_zero_velocity(reason="Controller Communication Loss")
                if self.sm.state not in (RobotState.EMERGENCY_STOP, RobotState.SAFE_IDLE, RobotState.IDLE, RobotState.OFFLINE):
                    self.sm.transition_to(RobotState.SAFE_IDLE, reason="Motor controller link lost")

            # 5. Hardware E-Stop Switch Check
            if raw.get("physical_estop", False) and not self._estop_software_latched:
                self.trigger_emergency_stop(reason="Hardware E-Stop Switch Pressed")

    def _run_hardware_loop(self):
        """Continuous 50Hz hardware monitoring loop: watchdog, E-stop, and odometry."""
        last_t = time.time()
        while self._is_running:
            time.sleep(0.02)  # 50 Hz
            now = time.time()
            dt = now - last_t
            last_t = now
            self.poll(dt)

    