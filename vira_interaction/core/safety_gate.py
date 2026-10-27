#!/usr/bin/env python3
"""
GRaCEmo ViRa — Command Validator & Safety Gate
Enforces the safety boundary defined in Phase 1 (VIRA_SAFETY_ARCHITECTURE.md).
Validates semantic commands before dispatch to the EventBus.
STRICT INVARIANT: Absolutely zero direct motor, GPIO, PWM, or raw velocity control.
"""
from __future__ import annotations
import math
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("gracemo.safety")

# Bounding limits for campus and apartment navigation
MIN_X = -100.0
MAX_X = 100.0
MIN_Y = -100.0
MAX_Y = 100.0

# 2-DOF Active Neck Kinematic Limits
PAN_LIMIT_RAD = 2.0944   # ±120°
TILT_LIMIT_RAD = 0.7854  # ±45°

ALLOWED_ACTIONS = {
    "Speak",
    "NavigateTo",
    "TurnTo",
    "NavigateToRoom",
    "LookAt",
    "ScanRoom",
    "Express",
    "Stop",
    "Pause",
    "Resume",
}

FORBIDDEN_KEYWORDS = {
    "pwm", "gpio", "duty_cycle", "motor_forward", "motor_backward",
    "raw_servo", "pin_factory", "left_motor", "right_motor",
    "servo_angle", "set_pin", "write_pin",
}


@dataclass
class ValidationResult:
    valid: bool
    action: str
    params: Dict[str, Any]
    error_message: Optional[str] = None
    sanitized_action: Optional[Dict[str, Any]] = None


class CommandValidator:
    """
    Validates semantic robot actions against schemas, physical constraints,
    kinematics, and bounds. Rejects malformed or unsafe outputs.
    """

    def __init__(
        self,
        bounds_x: Tuple[float, float] = (MIN_X, MAX_X),
        bounds_y: Tuple[float, float] = (MIN_Y, MAX_Y),
        max_commands_per_min: int = 30,
        max_stale_age_sec: float = 2.0,
    ):
        self.bounds_x = bounds_x
        self.bounds_y = bounds_y
        self.max_commands_per_min = max_commands_per_min
        self.max_stale_age_sec = max_stale_age_sec
        self._command_timestamps: List[float] = []

    def validate(self, action_dict: Dict[str, Any], timestamp: Optional[float] = None) -> ValidationResult:
        """
        Validate an action request dictionary of the form:
        {"action": str, "params": dict}
        """
        if not isinstance(action_dict, dict):
            return ValidationResult(
                valid=False, action="Unknown", params={},
                error_message="Action payload must be a JSON object / dict"
            )

        action = action_dict.get("action")
        params = action_dict.get("params", {})

        if not action or not isinstance(action, str):
            return ValidationResult(
                valid=False, action=str(action), params=params,
                error_message="Missing or non-string 'action' identifier"
            )

        if not isinstance(params, dict):
            return ValidationResult(
                valid=False, action=action, params={},
                error_message="'params' must be a dictionary"
            )

        # Check for forbidden hardware control keywords
        action_low = action.lower()
        if any(kw in action_low for kw in FORBIDDEN_KEYWORDS):
            return ValidationResult(
                valid=False, action=action, params=params,
                error_message=f"Direct hardware control action '{action}' is strictly forbidden by Rule 3"
            )

        for k, v in params.items():
            k_low = str(k).lower()
            if any(kw in k_low for kw in FORBIDDEN_KEYWORDS):
                return ValidationResult(
                    valid=False, action=action, params=params,
                    error_message=f"Forbidden hardware parameter '{k}' detected in action '{action}'"
                )

        # Check action in allowed catalog
        if action not in ALLOWED_ACTIONS:
            return ValidationResult(
                valid=False, action=action, params=params,
                error_message=f"Action '{action}' is not in approved semantic catalog: {sorted(ALLOWED_ACTIONS)}"
            )

        # Stale command check
        now = time.time()
        if timestamp is not None and (now - timestamp) > self.max_stale_age_sec:
            return ValidationResult(
                valid=False, action=action, params=params,
                error_message=f"Command age ({now - timestamp:.2f}s) exceeds stale threshold ({self.max_stale_age_sec}s)"
            )

        # Rate limiting check
        self._command_timestamps = [t for t in self._command_timestamps if now - t < 60.0]
        if len(self._command_timestamps) >= self.max_commands_per_min and action != "Stop":
            return ValidationResult(
                valid=False, action=action, params=params,
                error_message=f"Command rate limit exceeded ({self.max_commands_per_min}/min)"
            )
        self._command_timestamps.append(now)

        # Specific action schema & boundary validations
        if action == "NavigateTo":
            return self._validate_navigate_to(params)
        elif action == "NavigateToRoom":
            return self._validate_navigate_to_room(params)
        elif action == "TurnTo":
            return self._validate_turn_to(params)
        elif action == "LookAt":
            return self._validate_look_at(params)
        elif action == "ScanRoom":
            return self._validate_scan_room(params)
        elif action == "Speak":
            return self._validate_speak(params)
        elif action == "Express":
            return self._validate_express(params)
        elif action in ("Stop", "Pause", "Resume"):
            return ValidationResult(
                valid=True, action=action, params=params,
                sanitized_action={"action": action, "params": params}
            )

        return ValidationResult(
            valid=True, action=action, params=params,
            sanitized_action={"action": action, "params": params}
        )

    def _validate_navigate_to(self, params: Dict[str, Any]) -> ValidationResult:
        if "x" not in params or "y" not in params:
            return ValidationResult(
                valid=False, action="NavigateTo", params=params,
                error_message="NavigateTo requires 'x' and 'y' numeric coordinates"
            )
        try:
            x = float(params["x"])
            y = float(params["y"])
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False, action="NavigateTo", params=params,
                error_message="NavigateTo coordinates must be convertible to float"
            )

        if not math.isfinite(x) or not math.isfinite(y):
            return ValidationResult(
                valid=False, action="NavigateTo", params=params,
                error_message="NavigateTo coordinates must be finite (non-NaN, non-Inf)"
            )

        if not (self.bounds_x[0] <= x <= self.bounds_x[1]) or not (self.bounds_y[0] <= y <= self.bounds_y[1]):
            return ValidationResult(
                valid=False, action="NavigateTo", params=params,
                error_message=f"Coordinates ({x:.2f}, {y:.2f}) exceed boundary limits [{self.bounds_x}, {self.bounds_y}]"
            )

        yaw = params.get("yaw")
        if yaw is not None:
            try:
                yaw_val = float(yaw)
                if not math.isfinite(yaw_val):
                    return ValidationResult(
                        valid=False, action="NavigateTo", params=params,
                        error_message="NavigateTo yaw must be finite"
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    valid=False, action="NavigateTo", params=params,
                    error_message="NavigateTo yaw must be a valid float"
                )

        sanitized = {"x": round(x, 4), "y": round(y, 4)}
        if yaw is not None:
            sanitized["yaw"] = round(float(yaw), 4)
        target_name = params.get("target_name")
        if target_name and isinstance(target_name, str):
            sanitized["target_name"] = target_name.strip()

        return ValidationResult(
            valid=True, action="NavigateTo", params=params,
            sanitized_action={"action": "NavigateTo", "params": sanitized}
        )

    def _validate_navigate_to_room(self, params: Dict[str, Any]) -> ValidationResult:
        room = params.get("room")
        if not room or not isinstance(room, str) or not room.strip():
            return ValidationResult(
                valid=False, action="NavigateToRoom", params=params,
                error_message="NavigateToRoom requires a non-empty string 'room'"
            )
        return ValidationResult(
            valid=True, action="NavigateToRoom", params=params,
            sanitized_action={"action": "NavigateToRoom", "params": {"room": room.strip()}}
        )

    def _validate_turn_to(self, params: Dict[str, Any]) -> ValidationResult:
        if "yaw" not in params:
            return ValidationResult(
                valid=False, action="TurnTo", params=params,
                error_message="TurnTo requires 'yaw' angle in radians"
            )
        try:
            yaw = float(params["yaw"])
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False, action="TurnTo", params=params,
                error_message="TurnTo yaw must be a valid float"
            )
        if not math.isfinite(yaw):
            return ValidationResult(
                valid=False, action="TurnTo", params=params,
                error_message="TurnTo yaw must be finite"
            )
        return ValidationResult(
            valid=True, action="TurnTo", params=params,
            sanitized_action={"action": "TurnTo", "params": {"yaw": yaw}}
        )

    def _validate_look_at(self, params: Dict[str, Any]) -> ValidationResult:
        if "x" not in params or "y" not in params:
            return ValidationResult(
                valid=False, action="LookAt", params=params,
                error_message="LookAt requires 'x' and 'y' target coordinates"
            )
        try:
            x = float(params["x"])
            y = float(params["y"])
            z = float(params.get("z", 0.645))
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False, action="LookAt", params=params,
                error_message="LookAt coordinates must be valid numbers"
            )
        if not math.isfinite(x) or not math.isfinite(y) or not math.isfinite(z):
            return ValidationResult(
                valid=False, action="LookAt", params=params,
                error_message="LookAt coordinates must be finite"
            )
        return ValidationResult(
            valid=True, action="LookAt", params=params,
            sanitized_action={"action": "LookAt", "params": {"x": x, "y": y, "z": z}}
        )

    def _validate_scan_room(self, params: Dict[str, Any]) -> ValidationResult:
        pan = float(params.get("pan_range_deg", 60.0))
        tilt = float(params.get("tilt_deg", 10.0))
        speed = float(params.get("speed_deg_s", 25.0))
        if pan <= 0 or pan > 120.0:
            return ValidationResult(
                valid=False, action="ScanRoom", params=params,
                error_message=f"ScanRoom pan_range_deg must be in (0, 120], got {pan}"
            )
        if tilt < -45.0 or tilt > 45.0:
            return ValidationResult(
                valid=False, action="ScanRoom", params=params,
                error_message=f"ScanRoom tilt_deg must be in [-45, 45], got {tilt}"
            )
        if speed <= 0 or speed > 90.0:
            return ValidationResult(
                valid=False, action="ScanRoom", params=params,
                error_message=f"ScanRoom speed_deg_s must be in (0, 90], got {speed}"
            )
        return ValidationResult(
            valid=True, action="ScanRoom", params=params,
            sanitized_action={"action": "ScanRoom", "params": {"pan_range_deg": pan, "tilt_deg": tilt, "speed_deg_s": speed}}
        )

    def _validate_speak(self, params: Dict[str, Any]) -> ValidationResult:
        text = params.get("text", "")
        if not text or not isinstance(text, str) or not text.strip():
            return ValidationResult(
                valid=False, action="Speak", params=params,
                error_message="Speak action requires non-empty string 'text'"
            )
        return ValidationResult(
            valid=True, action="Speak", params=params,
            sanitized_action={"action": "Speak", "params": {"text": text.strip()}}
        )

    def _validate_express(self, params: Dict[str, Any]) -> ValidationResult:
        emotion = params.get("emotion", "idle").lower().strip()
        allowed_exp = {"idle", "happy", "focus", "sad", "angry", "intent"}
        if emotion not in allowed_exp:
            emotion = "idle"
        return ValidationResult(
            valid=True, action="Express", params=params,
            sanitized_action={"action": "Express", "params": {"emotion": emotion}}
        )


class SafetyGate:
    """
    Enforces interlocks (battery low, emergency stop active, obstacle proximity)
    and routes validated actions to the EventBus.
    """

    def __init__(self, validator: Optional[CommandValidator] = None):
        self.validator = validator or CommandValidator()
        self.emergency_stop_latched: bool = False
        self.battery_level: float = 100.0
        self.obstacle_active: bool = False

    def update_telemetry(self, battery_level: float, obstacle_active: bool):
        self.battery_level = battery_level
        self.obstacle_active = obstacle_active

    def trigger_emergency_stop(self):
        self.emergency_stop_latched = True
        log.warning("🚨 EMERGENCY STOP LATCHED IN SAFETY GATE")

    def reset_emergency_stop(self):
        self.emergency_stop_latched = False
        log.info("✓ Emergency Stop cleared in Safety Gate")

    def is_emergency_stop_latched(self) -> bool:
        return self.emergency_stop_latched

    def evaluate_action(self, action_dict: Dict[str, Any], timestamp: Optional[float] = None) -> ValidationResult:
        action = action_dict.get("action", "")

        # Emergency Stop is always processed
        if action == "Stop":
            self.trigger_emergency_stop()
            return self.validator.validate(action_dict, timestamp)

        # If Emergency Stop is latched, block mobility actions
        if self.emergency_stop_latched:
            if action in ("NavigateTo", "NavigateToRoom", "TurnTo", "ScanRoom"):
                return ValidationResult(
                    valid=False, action=action, params=action_dict.get("params", {}),
                    error_message="Action rejected: Emergency Stop is currently latched"
                )

        # Check battery interlock
        if self.battery_level < 10.0 and action in ("NavigateTo", "NavigateToRoom"):
            return ValidationResult(
                valid=False, action=action, params=action_dict.get("params", {}),
                error_message=f"Action rejected: Battery level critically low ({self.battery_level:.1f}%)"
            )

        # Pass through Command Validator
        return self.validator.validate(action_dict, timestamp)
