#!/usr/bin/env python3
"""
GRaCEmo ViRa — Robot Bridge Safety Adapter
Verifies command validity against current RobotState, freshness timestamps,
battery thresholds, and spatial boundary constraints.
"""
from __future__ import annotations
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from .state_machine import RobotState, RobotStateMachine

log = logging.getLogger("gracemo.bridge.safety")


@dataclass
class BridgeValidationResult:
    allowed: bool
    reason: str
    action: str
    params: Dict[str, Any]


class SafetyAdapter:
    """
    Evaluates semantic commands against robot operational constraints.
    Rejects actions if robot is OFFLINE, EMERGENCY_STOPPED, or low battery.
    """

    def __init__(
        self,
        state_machine: RobotStateMachine,
        max_command_age_sec: float = 3.0,
        min_battery_percent: int = 15,
        bounds_x: Tuple[float, float] = (-100.0, 100.0),
        bounds_y: Tuple[float, float] = (-100.0, 100.0),
    ):
        self.sm = state_machine
        self.max_command_age_sec = max_command_age_sec
        self.min_battery_percent = min_battery_percent
        self.bounds_x = bounds_x
        self.bounds_y = bounds_y
        self.battery_level = 100
        self.charging = False
        self.sensor_health: Dict[str, bool] = {
            "lidar": True,
            "odometry": True,
            "imu": True,
            "camera": True,
        }
        self.sensor_quality: Dict[str, float] = {
            "lidar": 1.0,
            "odometry": 1.0,
            "imu": 1.0,
            "camera": 1.0,
        }

    def update_battery(self, level: int, charging: bool = False):
        self.battery_level = level
        self.charging = charging

    def update_sensor_status(self, sensor_name: str, is_healthy: bool, quality: float = 1.0):
        """Updates health status and quality metric [0.0, 1.0] for a sensor."""
        self.sensor_health[sensor_name.lower()] = is_healthy
        self.sensor_quality[sensor_name.lower()] = max(0.0, min(1.0, float(quality)))

    def validate_sensor_data(self, sensor_name: str, data: Any) -> Tuple[bool, str]:
        """Validates raw sensor frame for corrupt, NaN, zero, or degraded data."""
        name = sensor_name.lower()
        if not self.sensor_health.get(name, True):
            return False, f"Sensor {name} marked offline"

        if name == "lidar":
            # Check for empty or invalid ranges
            if isinstance(data, (list, tuple)):
                if not data:
                    return False, "LiDAR frame empty"
                non_zero = [r for r in data if r is not None and not math.isnan(r) and not math.isinf(r) and r > 0.05]
                if len(non_zero) < 0.1 * len(data):
                    return False, "LiDAR dropout / zero ranges exceed threshold"
            return True, "LiDAR valid"

        if name == "imu":
            if isinstance(data, dict):
                # Check for NaN / Inf acceleration or orientation
                for k, v in data.items():
                    if isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v) or abs(v) > 200.0):
                        return False, f"IMU spike / invalid value in {k}: {v}"
            return True, "IMU valid"

        if name == "odometry":
            if isinstance(data, dict):
                x = data.get("x", 0.0)
                y = data.get("y", 0.0)
                if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                    return False, "Odometry pose contains NaN or Inf"
            return True, "Odometry valid"

        return True, f"{sensor_name} valid"

    def validate_command(
        self, action: str, params: Dict[str, Any], timestamp: Optional[float] = None
    ) -> BridgeValidationResult:
        current_state = self.sm.state

        # 1. STOP & EMERGENCY STOP are ALWAYS allowed
        if action in ("Stop", "EmergencyStop"):
            return BridgeValidationResult(allowed=True, reason="Stop always permitted", action=action, params=params)

        # 2. Check Emergency Stop or Offline state
        if current_state == RobotState.EMERGENCY_STOP:
            return BridgeValidationResult(
                allowed=False,
                reason=f"Rejected: Robot is in EMERGENCY_STOP state. Reset required.",
                action=action,
                params=params,
            )

        if current_state == RobotState.OFFLINE:
            return BridgeValidationResult(
                allowed=False,
                reason=f"Rejected: Robot is OFFLINE. Initialization required.",
                action=action,
                params=params,
            )

        # 3. Freshness check
        if timestamp is not None:
            age = time.time() - timestamp
            if age > self.max_command_age_sec:
                return BridgeValidationResult(
                    allowed=False,
                    reason=f"Command timestamp stale ({age:.2f}s > {self.max_command_age_sec}s threshold)",
                    action=action,
                    params=params,
                )

        # 4. Low battery interlock (locomotion disallowed if < threshold and not charging)
        if action in ("NavigateTo", "NavigateToRoom", "TurnTo", "Move") and not self.charging:
            if self.battery_level < self.min_battery_percent:
                return BridgeValidationResult(
                    allowed=False,
                    reason=f"Battery too low for locomotion ({self.battery_level}% < {self.min_battery_percent}%)",
                    action=action,
                    params=params,
                )

        # 5. Critical sensor availability interlock
        if action in ("NavigateTo", "NavigateToRoom", "TurnTo", "Move"):
            for critical_sensor in ("lidar", "odometry", "imu"):
                if not self.sensor_health.get(critical_sensor, True):
                    return BridgeValidationResult(
                        allowed=False,
                        reason=f"Rejected: Critical sensor '{critical_sensor}' is offline or failed",
                        action=action,
                        params=params,
                    )
                if self.sensor_quality.get(critical_sensor, 1.0) < 0.20:
                    return BridgeValidationResult(
                        allowed=False,
                        reason=f"Rejected: Critical sensor '{critical_sensor}' quality degraded ({self.sensor_quality.get(critical_sensor):.2f} < 0.20)",
                        action=action,
                        params=params,
                    )

        # 6. Coordinate boundary checks for NavigateTo
        if action == "NavigateTo":
            if "x" not in params or "y" not in params:
                return BridgeValidationResult(
                    allowed=False, reason="NavigateTo requires 'x' and 'y' coordinates", action=action, params=params
                )

            try:
                x = float(params["x"])
                y = float(params["y"])
            except (ValueError, TypeError):
                return BridgeValidationResult(
                    allowed=False, reason="Coordinates x, y must be valid numbers", action=action, params=params
                )

            if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
                return BridgeValidationResult(
                    allowed=False, reason="Coordinates x, y must be finite numbers", action=action, params=params
                )

            if not (self.bounds_x[0] <= x <= self.bounds_x[1]) or not (self.bounds_y[0] <= y <= self.bounds_y[1]):
                return BridgeValidationResult(
                    allowed=False,
                    reason=f"Coordinates ({x:.2f}, {y:.2f}) exceed safety limits [{self.bounds_x}, {self.bounds_y}]",
                    action=action,
                    params=params,
                )

        return BridgeValidationResult(allowed=True, reason="Validation passed", action=action, params=params)
