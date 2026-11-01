#!/usr/bin/env python3
"""
GRaCEmo ViRa — Authoritative Robot State Machine
Manages physical robot lifecycle states and validates operational preconditions.

States:
  OFFLINE, INITIALIZING, IDLE, NAVIGATING, PAUSED, STOPPING, ERROR, EMERGENCY_STOP
"""
from __future__ import annotations
import enum
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("gracemo.robot_state")


class RobotState(str, enum.Enum):
    OFFLINE = "OFFLINE"
    INITIALIZING = "INITIALIZING"
    IDLE = "IDLE"
    SAFE_IDLE = "SAFE_IDLE"
    TEST_AUTHORIZED = "TEST_AUTHORIZED"
    MOVING = "MOVING"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    ARRIVING = "ARRIVING"
    ARRIVED = "ARRIVED"
    PAUSED = "PAUSED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    STOPPING = "STOPPING"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    ERROR = "ERROR"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class HardwareMode(str, enum.Enum):
    SIMULATION = "SIMULATION"
    HARDWARE_SAFE = "HARDWARE_SAFE"
    HARDWARE_TEST = "HARDWARE_TEST"
    HARDWARE_TELEOP = "HARDWARE_TELEOP"
    HARDWARE_AUTONOMOUS = "HARDWARE_AUTONOMOUS"


MODE_VELOCITY_LIMITS: Dict[HardwareMode, Dict[str, float]] = {
    HardwareMode.HARDWARE_SAFE: {"max_linear": 0.0, "max_angular": 0.0},
    HardwareMode.HARDWARE_TEST: {"max_linear": 0.10, "max_angular": 0.25},
    HardwareMode.HARDWARE_TELEOP: {"max_linear": 0.25, "max_angular": 0.50},
    HardwareMode.HARDWARE_AUTONOMOUS: {"max_linear": 0.35, "max_angular": 0.75},
    HardwareMode.SIMULATION: {"max_linear": 0.45, "max_angular": 0.85},
}


ALLOWED_TRANSITIONS: Dict[RobotState, Set[RobotState]] = {
    RobotState.OFFLINE: {RobotState.INITIALIZING, RobotState.ERROR},
    RobotState.INITIALIZING: {RobotState.IDLE, RobotState.SAFE_IDLE, RobotState.ERROR, RobotState.OFFLINE},
    RobotState.IDLE: {
        RobotState.SAFE_IDLE,
        RobotState.TEST_AUTHORIZED,
        RobotState.MOVING,
        RobotState.PLANNING,
        RobotState.NAVIGATING,
        RobotState.PAUSED,
        RobotState.STOPPING,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
        RobotState.OFFLINE,
    },
    RobotState.SAFE_IDLE: {
        RobotState.IDLE,
        RobotState.TEST_AUTHORIZED,
        RobotState.MOVING,
        RobotState.PLANNING,
        RobotState.NAVIGATING,
        RobotState.PAUSED,
        RobotState.STOPPING,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
        RobotState.OFFLINE,
    },
    RobotState.TEST_AUTHORIZED: {
        RobotState.MOVING,
        RobotState.PLANNING,
        RobotState.NAVIGATING,
        RobotState.STOPPING,
        RobotState.SAFE_IDLE,
        RobotState.IDLE,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.MOVING: {
        RobotState.STOPPING,
        RobotState.SAFE_IDLE,
        RobotState.IDLE,
        RobotState.PAUSED,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.PLANNING: {
        RobotState.NAVIGATING,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.STOPPING,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.NAVIGATING: {
        RobotState.ARRIVING,
        RobotState.ARRIVED,
        RobotState.CANCEL_REQUESTED,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.PAUSED,
        RobotState.STOPPING,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.ARRIVING: {
        RobotState.ARRIVED,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.STOPPING,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.ARRIVED: {
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.CANCEL_REQUESTED: {
        RobotState.STOPPING,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.PAUSED: {
        RobotState.NAVIGATING,
        RobotState.MOVING,
        RobotState.STOPPING,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.STOPPING: {
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.NAVIGATION_FAILED,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.NAVIGATION_FAILED: {
        RobotState.SAFE_IDLE,
        RobotState.IDLE,
        RobotState.ERROR,
        RobotState.EMERGENCY_STOP,
    },
    RobotState.ERROR: {
        RobotState.INITIALIZING,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.EMERGENCY_STOP,
        RobotState.OFFLINE,
    },
    RobotState.EMERGENCY_STOP: {
        RobotState.INITIALIZING,
        RobotState.IDLE,
        RobotState.SAFE_IDLE,
        RobotState.OFFLINE,
    },
}


class RobotStateMachine:
    """
    Authoritative thread-safe state machine for the VIRA physical/simulated robot.
    """

    def __init__(
        self,
        initial_state: RobotState = RobotState.IDLE,
        mode: Optional[HardwareMode] = None,
    ):
        self._lock = threading.RLock()
        self._state: RobotState = initial_state
        if mode is not None:
            self._mode = mode
        else:
            vira_mode = os.environ.get("VIRA_MODE", "simulation").lower()
            self._mode = HardwareMode.SIMULATION if vira_mode == "simulation" else HardwareMode.HARDWARE_SAFE

        self._listeners: List[Callable[[RobotState, RobotState, str], None]] = []
        self._history: List[Tuple[float, RobotState, str]] = [(time.time(), initial_state, "Startup")]
        self._motion_authorized: bool = False

    @property
    def motion_authorized(self) -> bool:
        with self._lock:
            return self._motion_authorized

    @motion_authorized.setter
    def motion_authorized(self, val: bool) -> None:
        with self._lock:
            self._motion_authorized = bool(val)

    @property
    def mode(self) -> HardwareMode:
        with self._lock:
            return self._mode

    def set_hardware_mode(self, mode: HardwareMode, reason: str = "") -> bool:
        """Sets active hardware operational mode."""
        with self._lock:
            old_mode = self._mode
            self._mode = mode
            log.info(f"⚙️ HardwareMode changed: {old_mode.value} ──► {mode.value} [{reason}]")
            return True

    def get_velocity_limits(self) -> Dict[str, float]:
        """Returns the conservative velocity limits for the current hardware mode."""
        with self._lock:
            return dict(MODE_VELOCITY_LIMITS.get(self._mode, MODE_VELOCITY_LIMITS[HardwareMode.HARDWARE_SAFE]))

    def authorize_test_motion(self, reason: str = "Authorized by test operator") -> bool:
        """Authorizes physical motion for controlled hardware testing."""
        with self._lock:
            if self._mode == HardwareMode.HARDWARE_SAFE:
                log.warning("Cannot authorize motion while in HARDWARE_SAFE mode. Switch to HARDWARE_TEST first.")
                return False
            if self._state in (RobotState.IDLE, RobotState.SAFE_IDLE):
                return self.transition_to(RobotState.TEST_AUTHORIZED, reason=reason)
            return False

    def revoke_test_authorization(self, reason: str = "Test authorization revoked") -> bool:
        """Revokes test motion authorization, returning to SAFE_IDLE."""
        with self._lock:
            if self._state == RobotState.TEST_AUTHORIZED:
                return self.transition_to(RobotState.SAFE_IDLE, reason=reason)
            return True

    @property
    def state(self) -> RobotState:
        with self._lock:
            return self._state

    def add_listener(self, callback: Callable[[RobotState, RobotState, str], None]):
        with self._lock:
            self._listeners.append(callback)

    def can_transition(self, target_state: RobotState) -> bool:
        with self._lock:
            if target_state in (RobotState.EMERGENCY_STOP, RobotState.NAVIGATION_FAILED):
                return True
            allowed = ALLOWED_TRANSITIONS.get(self._state, set())
            return target_state in allowed

    def transition_to(self, target_state: RobotState, reason: str = "") -> bool:
        with self._lock:
            if target_state == self._state:
                return True

            if not self.can_transition(target_state):
                log.warning(
                    f"⚠️ Illegal RobotState transition rejected: {self._state.value} -> {target_state.value} ({reason})"
                )
                return False

            old_state = self._state
            self._state = target_state
            self._history.append((time.time(), target_state, reason))
            log.info(f"🔄 RobotState: {old_state.value} ──► {target_state.value} [{reason}]")

            # Notify listeners outside the lock
            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(old_state, target_state, reason)
            except Exception as e:
                log.error(f"Listener error during robot transition to {target_state}: {e}")

        return True

    def emergency_stop(self, reason: str = "Emergency Stop Latched") -> bool:
        """Immediate transition to EMERGENCY_STOP, bypassing regular restrictions."""
        with self._lock:
            old_state = self._state
            self._state = RobotState.EMERGENCY_STOP
            self._history.append((time.time(), RobotState.EMERGENCY_STOP, reason))
            log.critical(f"🚨 RobotState EMERGENCY_STOP ACTIVATED [{reason}]")
            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(old_state, RobotState.EMERGENCY_STOP, reason)
            except Exception as e:
                log.error(f"Listener error during emergency stop: {e}")
        return True

    def reset_from_emergency(self, reason: str = "Manual Reset") -> bool:
        with self._lock:
            if self._state != RobotState.EMERGENCY_STOP:
                return True
            return self.transition_to(RobotState.IDLE, reason=reason)

    # Alias transition to transition_to for interoperability
    transition = transition_to
    reset_emergency_stop = reset_from_emergency

