#!/usr/bin/env python3
"""
GRaCEmo ViRa — Interaction Adapter
Subscribes to EventBus events and coordinates physical feedback:
  - Updates facial avatar emotion (Expression)
  - Triggers TTS speech playback
  - Handles arrival announcements and obstacle alerts
Strictly decoupled: Display failure never stops robot operation.
"""
from __future__ import annotations
import logging
from typing import Any, Callable, Dict, Optional

from .state_machine import CognitiveState, Expression, InteractionFSM
from .event_bus import EventBusClient
from .tts_adapter import TTSAdapter

log = logging.getLogger("gracemo.interaction_adapter")


class InteractionAdapter:
    """
    Translates robot and system events into human-facing avatar and voice reactions.
    """

    def __init__(
        self,
        event_bus: EventBusClient,
        fsm: InteractionFSM,
        tts: TTSAdapter,
        expression_callback: Optional[Callable[[Expression], None]] = None,
    ):
        self.event_bus = event_bus
        self.fsm = fsm
        self.tts = tts
        self.expression_callback = expression_callback
        self._processed_event_ids = set()

        # Wire EventBus subscriptions
        self.event_bus.subscribe("ActionRequested", self._on_action_requested)
        self.event_bus.subscribe("NavigationStarted", self._on_navigation_started)
        self.event_bus.subscribe("NavigationProgress", self._on_navigation_progress)
        self.event_bus.subscribe("NavigationArrived", self._on_navigation_arrived)
        self.event_bus.subscribe("NavigationFailed", self._on_navigation_failed)
        self.event_bus.subscribe("RobotStopped", self._on_robot_stopped)
        self.event_bus.subscribe("ObstacleDetected", self._on_obstacle_detected)
        self.event_bus.subscribe("PersonVisible", self._on_person_visible)

        # Wire FSM expression changes to visual callback
        self.fsm.add_expression_listener(self._on_fsm_expression_changed)

    def set_expression_callback(self, cb: Callable[[Expression], None]):
        self.expression_callback = cb

    def _on_fsm_expression_changed(self, prev: Expression, curr: Expression, reason: str):
        if self.expression_callback:
            try:
                self.expression_callback(curr)
            except Exception as e:
                log.warning(f"Expression render callback error (safe degradation): {e}")

    def _on_action_requested(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        action = data.get("action", "")
        params = data.get("params", {})

        if action == "Speak":
            text = params.get("text", "")
            if text:
                self.fsm.transition_to(CognitiveState.SPEAKING, reason="ActionRequested: Speak")
                self.tts.speak(
                    text,
                    on_done=lambda: self.fsm.transition_to(CognitiveState.IDLE, reason="Speech completed"),
                )

        elif action == "Express":
            emotion_str = params.get("emotion", "idle")
            try:
                exp = Expression(emotion_str)
                self.fsm.set_expression(exp, reason="ActionRequested: Express")
            except ValueError:
                pass

        elif action == "Stop":
            self.tts.stop()
            self.fsm.emergency_stop(reason="ActionRequested: Stop")

    def _on_navigation_started(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "destination")
        log.info(f"🚀 [INTERACTION] NavigationStarted to {dest}")
        self.fsm.transition_to(CognitiveState.EXECUTING, reason=f"Navigating to {dest}")
        self.fsm.set_expression(Expression.FOCUS, reason="Transit started")

    def _on_navigation_progress(self, envelope: Dict[str, Any]):
        # Keep focus expression alive during active transit
        if self.fsm.expression != Expression.FOCUS:
            self.fsm.set_expression(Expression.FOCUS, reason="Transit progress")

    def _on_navigation_arrived(self, envelope: Dict[str, Any]):
        evt_id = envelope.get("id")
        if evt_id:
            if evt_id in self._processed_event_ids:
                log.info(f"Duplicate NavigationArrived event ignored: {evt_id}")
                return
            self._processed_event_ids.add(evt_id)
            if len(self._processed_event_ids) > 1000:
                self._processed_event_ids.clear()

        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "the destination")
        success = data.get("success", True)

        if success:
            log.info(f"🎯 NavigationArrived at {dest} -> happy expression + announcement")
            self.fsm.transition_to(CognitiveState.IDLE, reason="Navigation completed successfully", expression=Expression.HAPPY)
            self.tts.speak(f"We've arrived at {dest}.")
        else:
            self.fsm.transition_to(CognitiveState.IDLE, reason="Navigation unfulfilled", expression=Expression.SAD)
            self.tts.speak(f"I was unable to complete navigation to {dest}.")

    def _on_navigation_failed(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "destination")
        reason = data.get("reason", "unknown error")
        log.warning(f"❌ [INTERACTION] NavigationFailed: {dest} ({reason})")
        self.fsm.transition_to(CognitiveState.ERROR, reason=f"Navigation failed: {reason}", expression=Expression.SAD)
        self.tts.speak(f"Navigation to {dest} could not be completed. Path is obstructed.")
        # Recover to IDLE preserving SAD expression
        self.fsm.transition_to(CognitiveState.IDLE, reason="Recovered from navigation error", expression=Expression.SAD)

    def _on_robot_stopped(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        reason = data.get("reason", "Stopped")
        emergency = data.get("emergency", False)
        log.info(f"🛑 [INTERACTION] RobotStopped received: {reason}")
        self.tts.stop()
        if emergency:
            self.fsm.emergency_stop(reason=f"Robot stopped: {reason}")
            self.fsm.set_expression(Expression.IDLE, reason="E-Stop active")
        else:
            self.fsm.transition_to(CognitiveState.IDLE, reason=f"Robot stopped: {reason}")
            self.fsm.set_expression(Expression.IDLE, reason="Stopped")

    def _on_obstacle_detected(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dist = data.get("distance", 0.0)
        direction = data.get("direction", "front")
        log.warning(f"⚠️ Obstacle alert: {dist:.2f}m in {direction} direction")
        self.fsm.set_expression(Expression.FOCUS, reason="Obstacle detected")

    def _on_person_visible(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        identity = data.get("identity", "Guest")
        log.info(f"👤 Person spotted: {identity}")
        if self.fsm.state == CognitiveState.IDLE:
            self.fsm.set_expression(Expression.HAPPY, reason=f"Spotted {identity}")
