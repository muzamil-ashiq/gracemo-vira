#!/usr/bin/env python3
"""
GRaCEmo ViRa — Cognitive Interaction State Machine
Implements the production FSM defined in Phase 1 (VIRA_INTERACTION_SPEC.md).
Explicitly decouples Cognitive State from Emotional Expression.
"""
from __future__ import annotations
import enum
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("gracemo.fsm")


class CognitiveState(str, enum.Enum):
    BOOT = "BOOT"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    ERROR = "ERROR"
    RECOVERY = "RECOVERY"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SHUTDOWN = "SHUTDOWN"


class Expression(str, enum.Enum):
    IDLE = "idle"
    HAPPY = "happy"
    FOCUS = "focus"
    SAD = "sad"
    ANGRY = "angry"
    INTENT = "intent"


# Permitted state transition map
ALLOWED_TRANSITIONS: Dict[CognitiveState, Set[CognitiveState]] = {
    CognitiveState.BOOT: {
        CognitiveState.IDLE,
        CognitiveState.ERROR,
        CognitiveState.SHUTDOWN,
    },
    CognitiveState.IDLE: {
        CognitiveState.LISTENING,
        CognitiveState.THINKING,
        CognitiveState.SPEAKING,
        CognitiveState.EXECUTING,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
        CognitiveState.SHUTDOWN,
    },
    CognitiveState.LISTENING: {
        CognitiveState.THINKING,
        CognitiveState.IDLE,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.THINKING: {
        CognitiveState.SPEAKING,
        CognitiveState.EXECUTING,
        CognitiveState.IDLE,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.SPEAKING: {
        CognitiveState.WAITING,
        CognitiveState.IDLE,
        CognitiveState.LISTENING,
        CognitiveState.EXECUTING,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.EXECUTING: {
        CognitiveState.WAITING,
        CognitiveState.SPEAKING,
        CognitiveState.THINKING,
        CognitiveState.LISTENING,
        CognitiveState.IDLE,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.WAITING: {
        CognitiveState.SPEAKING,
        CognitiveState.IDLE,
        CognitiveState.EXECUTING,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.ERROR: {
        CognitiveState.RECOVERY,
        CognitiveState.IDLE,
        CognitiveState.EMERGENCY_STOP,
        CognitiveState.SHUTDOWN,
    },
    CognitiveState.RECOVERY: {
        CognitiveState.IDLE,
        CognitiveState.ERROR,
        CognitiveState.EMERGENCY_STOP,
    },
    CognitiveState.EMERGENCY_STOP: {
        CognitiveState.IDLE,
        CognitiveState.RECOVERY,
        CognitiveState.SHUTDOWN,
    },
    CognitiveState.SHUTDOWN: set(),
}

DEFAULT_EXPRESSIONS: Dict[CognitiveState, Expression] = {
    CognitiveState.BOOT: Expression.IDLE,
    CognitiveState.IDLE: Expression.IDLE,
    CognitiveState.LISTENING: Expression.FOCUS,
    CognitiveState.THINKING: Expression.INTENT,
    CognitiveState.SPEAKING: Expression.HAPPY,
    CognitiveState.EXECUTING: Expression.FOCUS,
    CognitiveState.WAITING: Expression.IDLE,
    CognitiveState.ERROR: Expression.SAD,
    CognitiveState.RECOVERY: Expression.INTENT,
    CognitiveState.EMERGENCY_STOP: Expression.ANGRY,
    CognitiveState.SHUTDOWN: Expression.IDLE,
}


class InteractionFSM:
    """
    Authoritative Finite State Machine for GRaCEmo ViRa Interaction.
    Thread-safe state transitions and observable transition listeners.
    """

    def __init__(self, initial_state: CognitiveState = CognitiveState.BOOT):
        self._lock = threading.RLock()
        self._state: CognitiveState = initial_state
        self._expression: Expression = DEFAULT_EXPRESSIONS[initial_state]
        self._state_history: List[Tuple[float, CognitiveState, str]] = [
            (time.time(), initial_state, "Initialization")
        ]
        self._listeners: List[Callable[[CognitiveState, CognitiveState, Expression, str], None]] = []
        self._expression_listeners: List[Callable[[Expression, Expression, str], None]] = []

    @property
    def state(self) -> CognitiveState:
        with self._lock:
            return self._state

    @property
    def expression(self) -> Expression:
        with self._lock:
            return self._expression

    def add_listener(self, fn: Callable[[CognitiveState, CognitiveState, Expression, str], None]):
        """Register a callback invoked on every cognitive state change."""
        with self._lock:
            self._listeners.append(fn)

    def add_expression_listener(self, fn: Callable[[Expression, Expression, str], None]):
        """Register a callback invoked on facial expression change."""
        with self._lock:
            self._expression_listeners.append(fn)

    def transition_to(
        self,
        new_state: CognitiveState,
        reason: str = "",
        expression: Optional[Expression] = None,
    ) -> bool:
        """
        Attempt transition from current state to new_state.
        Returns True if successful, False if transition is illegal.
        """
        with self._lock:
            if new_state == self._state and expression is None:
                return True

            # Emergency Stop is always allowed from any state
            if new_state != CognitiveState.EMERGENCY_STOP:
                allowed = ALLOWED_TRANSITIONS.get(self._state, set())
                if new_state not in allowed:
                    log.warning(
                        f"⚠️ Invalid state transition rejected: {self._state.value} -> {new_state.value} (reason: {reason})"
                    )
                    return False

            prev_state = self._state
            self._state = new_state
            now = time.time()
            self._state_history.append((now, new_state, reason))
            if len(self._state_history) > 100:
                self._state_history.pop(0)

            # Determine new expression
            prev_exp = self._expression
            if expression is not None:
                self._expression = expression
            elif new_state in DEFAULT_EXPRESSIONS:
                self._expression = DEFAULT_EXPRESSIONS[new_state]

            log.info(f"🔄 FSM State: {prev_state.value} -> {self._state.value} [{self._expression.value}] ({reason})")

            # Notify listeners outside lock if possible or under lock safely
            for listener in list(self._listeners):
                try:
                    listener(prev_state, new_state, self._expression, reason)
                except Exception as e:
                    log.error(f"Error in FSM listener: {e}")

            if prev_exp != self._expression:
                for exp_listener in list(self._expression_listeners):
                    try:
                        exp_listener(prev_exp, self._expression, reason)
                    except Exception as e:
                        log.error(f"Error in expression listener: {e}")

            return True

    def set_expression(self, expression: Expression, reason: str = ""):
        """Explicitly override emotional expression without altering cognitive state."""
        with self._lock:
            if expression == self._expression:
                return
            prev = self._expression
            self._expression = expression
            log.info(f"😊 FSM Expression: {prev.value} -> {expression.value} ({reason})")
            for exp_listener in list(self._expression_listeners):
                try:
                    exp_listener(prev, expression, reason)
                except Exception as e:
                    log.error(f"Error in expression listener: {e}")

    def emergency_stop(self, reason: str = "Emergency Stop Requested"):
        """Instant priority transition to EMERGENCY_STOP."""
        self.transition_to(CognitiveState.EMERGENCY_STOP, reason=reason, expression=Expression.ANGRY)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "state": self._state.value,
                "expression": self._expression.value,
                "timestamp": time.time(),
            }
