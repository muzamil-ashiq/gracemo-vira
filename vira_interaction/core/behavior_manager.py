#!/usr/bin/env python3
"""
GRaCEmo ViRa — Human-Interaction Behavior Manager
Implements Section 7 of the Autonomous Chassis & Human-Interaction Architecture:
  States: IDLE, PERSON_DETECTED, OBSERVATION_60S, INTERACTION,
          MANUAL_COMMAND, FOLLOW_PERSON, SAFE_STOP, FAULT.

Safety Invariants:
  1. Detecting a person is a perception event, NOT consent or authorization to move.
  2. Observation phase holds robot strictly stationary for up to 60 seconds.
  3. Interaction requires an explicit trigger (wake phrase or physical button).
  4. Stop commands, physical e-stops, and faults take priority over all ordinary behaviors.
  5. Target loss in FOLLOW_PERSON immediately asserts a safe stop.
"""
from __future__ import annotations
import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("gracemo.behavior_manager")


class BehaviorState(str, enum.Enum):
    IDLE = "IDLE"
    PERSON_DETECTED = "PERSON_DETECTED"
    OBSERVATION_60S = "OBSERVATION_60S"
    INTERACTION = "INTERACTION"
    MANUAL_COMMAND = "MANUAL_COMMAND"
    FOLLOW_PERSON = "FOLLOW_PERSON"
    SAFE_STOP = "SAFE_STOP"
    FAULT = "FAULT"


@dataclass
class PersonDetection:
    person_id: str
    confidence: float
    distance_m: float
    bearing_rad: float
    confirmed: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class StructuredMotionRequest:
    command_type: str  # "STOP", "MANUAL", "FOLLOW", "NAVIGATE"
    linear_mps: float = 0.0
    angular_rps: float = 0.0
    duration_sec: float = 0.0
    is_authorized: bool = False
    rejection_reason: str = ""


class HumanInteractionBehaviorManager:
    """
    Authoritative state supervisor for human-aware autonomous interaction.
    """

    def __init__(
        self,
        observation_timeout_sec: float = 60.0,
        tracking_loss_timeout_sec: float = 0.50,
        max_safe_linear_mps: float = 0.35,
        max_safe_angular_rps: float = 0.75,
        min_follow_distance_m: float = 0.80,
        max_follow_distance_m: float = 3.50,
    ):
        self._lock = threading.RLock()
        self._state: BehaviorState = BehaviorState.IDLE
        self.observation_timeout_sec = observation_timeout_sec
        self.tracking_loss_timeout_sec = tracking_loss_timeout_sec
        self.max_safe_linear = max_safe_linear_mps
        self.max_safe_angular = max_safe_angular_rps
        self.min_follow_dist = min_follow_distance_m
        self.max_follow_dist = max_follow_distance_m

        self._observation_start_t: float = 0.0
        self._last_target_update_t: float = 0.0
        self._active_target: Optional[PersonDetection] = None
        self._last_fault_reason: str = ""

        # Motion outputs
        self._cmd_linear: float = 0.0
        self._cmd_angular: float = 0.0

        # Observers
        self._listeners: List[Callable[[BehaviorState, BehaviorState, str], None]] = []

    def connect_event_bus(self, event_bus: Any):
        """
        Subscribes to EventBus perception events (e.g. PersonVisible from vision adapter)
        and feeds them into the behavior supervisor.
        """
        def on_event(event: Dict[str, Any]):
            event_type = event.get("event_type", {})
            t = event_type.get("type") if isinstance(event_type, dict) else str(event_type)
            if t in ("PersonVisible", "PersonDetected"):
                data = event_type.get("data", {}) if isinstance(event_type, dict) else event.get("data", {})
                dist = float(data.get("distance_m", 1.8))
                bearing = float(data.get("bearing_rad", 0.0))
                conf = float(data.get("confidence", 0.85))
                pid = str(data.get("person_id", "person_auto"))
                detection = PersonDetection(
                    person_id=pid,
                    confidence=conf,
                    distance_m=dist,
                    bearing_rad=bearing,
                    confirmed=(conf >= 0.70),
                )
                self.on_person_detected(detection)
            elif t in ("ActionRequested", "CommandReceived"):
                data = event_type.get("data", {}) if isinstance(event_type, dict) else event.get("data", {})
                action = data.get("action", "")
                if action == "Stop":
                    self.request_stop("Stop action on EventBus")

        if hasattr(event_bus, "subscribe"):
            event_bus.subscribe(on_event)

    @property
    def state(self) -> BehaviorState:
        with self._lock:
            return self._state

    @property
    def current_velocity(self) -> Tuple[float, float]:
        with self._lock:
            return self._cmd_linear, self._cmd_angular

    def add_listener(self, callback: Callable[[BehaviorState, BehaviorState, str], None]):
        with self._lock:
            self._listeners.append(callback)

    def _transition_to(self, new_state: BehaviorState, reason: str = "") -> bool:
        if new_state == self._state:
            return True

        old_state = self._state
        self._state = new_state
        log.info(f"🎭 Behavior State: {old_state.value} -> {new_state.value} [{reason}]")

        listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(old_state, new_state, reason)
            except Exception as e:
                log.error(f"Error in behavior listener: {e}")

        return True

    def on_person_detected(self, detection: PersonDetection) -> bool:
        """
        Called when perception detects a person.
        Robot remains stationary. Does NOT infer consent to move or converse.
        """
        with self._lock:
            if self._state in (BehaviorState.SAFE_STOP, BehaviorState.FAULT):
                return False

            self._active_target = detection
            self._last_target_update_t = detection.timestamp

            if self._state == BehaviorState.IDLE:
                self._transition_to(BehaviorState.PERSON_DETECTED, reason=f"Person {detection.person_id} detected")

            if self._state == BehaviorState.PERSON_DETECTED and detection.confirmed:
                self._observation_start_t = time.time()
                self._transition_to(
                    BehaviorState.OBSERVATION_60S,
                    reason=f"Detection confirmed. Stationary observation timer started ({self.observation_timeout_sec}s)"
                )
                self._zero_motion()
                return True

            if self._state == BehaviorState.FOLLOW_PERSON:
                # Update tracking stream
                self._update_follow_kinematics(detection)

            return True

    def on_wake_trigger(self, source: str = "wake_word") -> bool:
        """
        Explicit interaction trigger (e.g. 'Hello GraceEMO' or tactile push button).
        Confirms human consent for interaction.
        """
        with self._lock:
            if self._state in (BehaviorState.SAFE_STOP, BehaviorState.FAULT):
                log.warning(f"Wake trigger ignored: System in {self._state.value}")
                return False

            if self._state in (BehaviorState.IDLE, BehaviorState.PERSON_DETECTED, BehaviorState.OBSERVATION_60S):
                self._zero_motion()
                return self._transition_to(BehaviorState.INTERACTION, reason=f"Consent confirmed via {source}")

            return True

    def process_voice_command(self, text: str) -> StructuredMotionRequest:
        """
        Parses and validates voice command through safety supervisor.
        Stop commands have immediate priority (<50ms).
        """
        cleaned = text.strip().lower()

        with self._lock:
            # 1. Stop command override: Immediate priority
            if any(stop_word in cleaned for stop_word in ("stop", "halt", "cancel", "emergency", "freeze")):
                self.request_stop(reason=f"Voice STOP keyword detected in '{text}'")
                return StructuredMotionRequest(
                    command_type="STOP",
                    linear_mps=0.0,
                    angular_rps=0.0,
                    is_authorized=True,
                )

            # 2. Gate non-stop commands by state
            if self._state != BehaviorState.INTERACTION:
                return StructuredMotionRequest(
                    command_type="REJECTED",
                    is_authorized=False,
                    rejection_reason=f"Commands prohibited while in state {self._state.value}. Requires active INTERACTION.",
                )

            # 3. Follow Person Command
            if "follow" in cleaned:
                if not self._active_target or (time.time() - self._last_target_update_t) > self.tracking_loss_timeout_sec:
                    return StructuredMotionRequest(
                        command_type="FOLLOW",
                        is_authorized=False,
                        rejection_reason="Cannot follow: No active target being tracked",
                    )
                if self._active_target.distance_m < self.min_follow_dist:
                    return StructuredMotionRequest(
                        command_type="FOLLOW",
                        is_authorized=False,
                        rejection_reason=f"Target too close ({self._active_target.distance_m:.2f}m < {self.min_follow_dist}m)",
                    )
                if self._active_target.distance_m > self.max_follow_dist:
                    return StructuredMotionRequest(
                        command_type="FOLLOW",
                        is_authorized=False,
                        rejection_reason=f"Target out of tracking range ({self._active_target.distance_m:.2f}m > {self.max_follow_dist}m)",
                    )

                self._transition_to(BehaviorState.FOLLOW_PERSON, reason="Operator commanded follow person")
                self._update_follow_kinematics(self._active_target)
                return StructuredMotionRequest(command_type="FOLLOW", is_authorized=True)

            # 4. Manual Motion Commands (e.g., 'move forward', 'turn left')
            if "forward" in cleaned:
                lin = min(0.20, self.max_safe_linear)
                self._transition_to(BehaviorState.MANUAL_COMMAND, reason="Voice manual forward")
                self._set_motion(lin, 0.0)
                return StructuredMotionRequest(
                    command_type="MANUAL",
                    linear_mps=lin,
                    angular_rps=0.0,
                    duration_sec=2.0,
                    is_authorized=True,
                )

            if "backward" in cleaned or "back" in cleaned:
                lin = max(-0.15, -self.max_safe_linear)
                self._transition_to(BehaviorState.MANUAL_COMMAND, reason="Voice manual reverse")
                self._set_motion(lin, 0.0)
                return StructuredMotionRequest(
                    command_type="MANUAL",
                    linear_mps=lin,
                    angular_rps=0.0,
                    duration_sec=2.0,
                    is_authorized=True,
                )

            if "left" in cleaned:
                ang = min(0.40, self.max_safe_angular)
                self._transition_to(BehaviorState.MANUAL_COMMAND, reason="Voice manual turn left")
                self._set_motion(0.0, ang)
                return StructuredMotionRequest(
                    command_type="MANUAL",
                    linear_mps=0.0,
                    angular_rps=ang,
                    duration_sec=1.5,
                    is_authorized=True,
                )

            if "right" in cleaned:
                ang = max(-0.40, -self.max_safe_angular)
                self._transition_to(BehaviorState.MANUAL_COMMAND, reason="Voice manual turn right")
                self._set_motion(0.0, ang)
                return StructuredMotionRequest(
                    command_type="MANUAL",
                    linear_mps=0.0,
                    angular_rps=ang,
                    duration_sec=1.5,
                    is_authorized=True,
                )

            # Informational / dialogue commands do not alter motion
            return StructuredMotionRequest(
                command_type="DIALOGUE",
                is_authorized=True,
                rejection_reason="No motion requested",
            )

    def request_stop(self, reason: str = "Stop requested") -> bool:
        """Immediate transition to SAFE_STOP with zero velocity."""
        with self._lock:
            self._zero_motion()
            return self._transition_to(BehaviorState.SAFE_STOP, reason=reason)

    def raise_fault(self, reason: str) -> bool:
        """Transitions to FAULT state on hardware or safety anomaly."""
        with self._lock:
            self._zero_motion()
            self._last_fault_reason = reason
            return self._transition_to(BehaviorState.FAULT, reason=reason)

    def reset_to_idle(self, reason: str = "Manual reset to IDLE") -> bool:
        """Recovers from SAFE_STOP or FAULT to IDLE only if robot is stationary."""
        with self._lock:
            self._zero_motion()
            self._active_target = None
            return self._transition_to(BehaviorState.IDLE, reason=reason)

    def update_tick(self, now: Optional[float] = None):
        """Periodic supervisor check: enforces observation timer and target loss."""
        if now is None:
            now = time.time()

        with self._lock:
            # 1. 60-second observation timer expiration check
            if self._state == BehaviorState.OBSERVATION_60S:
                elapsed = now - self._observation_start_t
                if elapsed >= self.observation_timeout_sec:
                    self._transition_to(
                        BehaviorState.IDLE,
                        reason=f"Observation window ({self.observation_timeout_sec}s) expired without wake trigger"
                    )
                    self._active_target = None

            # 2. Tracking freshness check in FOLLOW_PERSON
            if self._state == BehaviorState.FOLLOW_PERSON:
                tracking_age = now - self._last_target_update_t
                if tracking_age > self.tracking_loss_timeout_sec:
                    self._zero_motion()
                    self._transition_to(
                        BehaviorState.SAFE_STOP,
                        reason=f"Target tracking lost ({tracking_age:.2f}s > {self.tracking_loss_timeout_sec}s)"
                    )

    def _update_follow_kinematics(self, target: PersonDetection):
        """Differential velocity calculation to maintain standoff distance."""
        # Simple proportional controller bounded to safe limits
        dist_err = target.distance_m - 1.50  # maintain 1.5m standoff
        k_v = 0.3
        k_w = 0.8

        target_v = max(-0.10, min(self.max_safe_linear, k_v * dist_err))
        target_w = max(-self.max_safe_angular, min(self.max_safe_angular, k_w * target.bearing_rad))
        self._set_motion(target_v, target_w)

    def _set_motion(self, linear: float, angular: float):
        self._cmd_linear = max(-self.max_safe_linear, min(self.max_safe_linear, float(linear)))
        self._cmd_angular = max(-self.max_safe_angular, min(self.max_safe_angular, float(angular)))

    def _zero_motion(self):
        self._cmd_linear = 0.0
        self._cmd_angular = 0.0
