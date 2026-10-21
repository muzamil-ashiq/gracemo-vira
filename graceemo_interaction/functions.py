#!/usr/bin/env python3
"""
GRaCEmo ViRa — Safe Semantic Robot Functions (Phase 2 Refactor)
Enforces Rule 3 (No direct LLM motor control):
Direct GPIO/PWM control has been decoupled from interaction logic.
Functions now route semantic actions through the VIRA Safety Gateway and EventBus.
"""
import logging
import time
from typing import Optional

log = logging.getLogger("gracemo.functions")

_EVENT_BUS = None


def _get_event_bus():
    global _EVENT_BUS
    if _EVENT_BUS is None:
        try:
            from core.event_bus import EventBusClient
            _EVENT_BUS = EventBusClient(source_name="FunctionsBridge")
        except Exception:
            _EVENT_BUS = None
    return _EVENT_BUS


def motor_forward():
    """Semantic translation: Forward request routed to safety-monitored navigation."""
    log.info("🤖 [SEMANTIC ACTION] Motor forward requested -> Routed via EventBus")
    eb = _get_event_bus()
    if eb:
        eb.emit("ActionRequested", {"action": "Move", "params": {"linear_x": 0.25, "angular_z": 0.0}})
        time.sleep(1.0)
        eb.emit("ActionRequested", {"action": "Stop", "params": {"reason": "Forward pulse complete"}})


def motor_backward():
    """Semantic translation: Backward request routed to safety-monitored navigation."""
    log.info("🤖 [SEMANTIC ACTION] Motor backward requested -> Routed via EventBus")
    eb = _get_event_bus()
    if eb:
        eb.emit("ActionRequested", {"action": "Move", "params": {"linear_x": -0.25, "angular_z": 0.0}})
        time.sleep(1.0)
        eb.emit("ActionRequested", {"action": "Stop", "params": {"reason": "Backward pulse complete"}})


def rotate_servo_to_180():
    """Semantic translation: Hand Up / High greeting."""
    log.info("🤖 [SEMANTIC ACTION] Hand Hi / Up requested -> Routed via EventBus")
    eb = _get_event_bus()
    if eb:
        eb.emit("ActionRequested", {"action": "Express", "params": {"emotion": "happy"}})


def rotate_servo_to_0():
    """Semantic translation: Hand Down / Rest."""
    log.info("🤖 [SEMANTIC ACTION] Hand Down requested -> Routed via EventBus")
    eb = _get_event_bus()
    if eb:
        eb.emit("ActionRequested", {"action": "Express", "params": {"emotion": "idle"}})


def shake_servo(times=2):
    """Semantic translation: Hand wave / greeting."""
    log.info(f"🤖 [SEMANTIC ACTION] Hand wave requested ({times} times) -> Routed via EventBus")
    eb = _get_event_bus()
    if eb:
        eb.emit("ActionRequested", {"action": "Express", "params": {"emotion": "happy"}})