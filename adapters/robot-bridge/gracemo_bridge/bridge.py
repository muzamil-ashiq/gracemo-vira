#!/usr/bin/env python3
"""
GRaCEmo ViRa — Authoritative Robot Bridge Coordinator
Unifies command handling, safety validation, navigation execution,
telemetry publishing, and feedback generation.
"""
from __future__ import annotations
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional
from .command_handler import CommandHandler
from .feedback_adapter import FeedbackAdapter
from .hardware_adapter import HardwareAdapter
from .navigation_adapter import NavigationAdapter
from .safety_adapter import SafetyAdapter
from .state_machine import RobotState, RobotStateMachine
from .state_publisher import StatePublisher

log = logging.getLogger("gracemo.bridge")


class RobotBridge:
    """
    Main Robot Bridge orchestrator.
    Bridges between the VIRA Kernel/EventBus and the robot navigation subsystem (Nav2/Gazebo).
    """

    def __init__(
        self,
        emit_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        mode: str = "simulation",
    ):
        self.mode = os.environ.get("VIRA_MODE", mode)
        self._emit_callback = emit_callback or (lambda env: None)

        # 1. Authoritative State Machine
        self.state_machine = RobotStateMachine(initial_state=RobotState.IDLE)

        # 2. Sub-adapters
        self.safety_adapter = SafetyAdapter(state_machine=self.state_machine)
        self.feedback_adapter = FeedbackAdapter(emit_callback=self._emit_event, source="RobotBridge")
        self.navigation_adapter = NavigationAdapter(
            state_machine=self.state_machine,
            feedback_adapter=self.feedback_adapter,
        )
        self.hardware_adapter = HardwareAdapter(state_machine=self.state_machine)
        self.navigation_adapter.set_hardware_adapter(self.hardware_adapter)
        self.command_handler = CommandHandler(
            state_machine=self.state_machine,
            safety_adapter=self.safety_adapter,
            navigation_adapter=self.navigation_adapter,
            hardware_adapter=self.hardware_adapter,
        )
        self.state_publisher = StatePublisher(
            state_machine=self.state_machine,
            emit_callback=self._emit_event,
        )

        log.info(f"🤖 RobotBridge initialized in mode: {self.mode.upper()}")

    def _emit_event(self, envelope: Dict[str, Any]):
        try:
            self._emit_callback(envelope)
        except Exception as e:
            log.error(f"Error in RobotBridge emit_callback: {e}")

    def set_emit_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self._emit_callback = callback
        self.feedback_adapter.emit_callback = callback
        self.state_publisher.emit_callback = callback

    def start(self):
        self.state_publisher.start()
        log.info("🤖 RobotBridge started")

    def stop(self):
        self.navigation_adapter.cancel_navigation(reason="Bridge shutdown")
        if hasattr(self, "hardware_adapter") and self.hardware_adapter:
            self.hardware_adapter.shutdown()
        self.state_publisher.stop()
        log.info("🤖 RobotBridge stopped")

    def stop_immediately(self, reason: str = "Emergency Stop", trace_id: Optional[str] = None) -> bool:
        """Immediately halts robot motion and enters EMERGENCY_STOP."""
        return self.navigation_adapter.stop_immediately(reason=reason, trace_id=trace_id)

    def run_preflight(self) -> Dict[str, Any]:
        """Runs the 15-subsystem preflight check and returns a dict report."""
        from .preflight import PreflightValidator
        validator = PreflightValidator(bridge=self)
        report = validator.execute_preflight()
        return report.to_dict()

    def on_action_requested(self, event_envelope: Dict[str, Any]) -> bool:
        """
        Receives an ActionRequested canonical envelope from EventBus and dispatches it.
        Envelope format:
        {
            "id": "...",
            "trace_id": "...",
            "timestamp": ...,
            "event_type": {
                "type": "ActionRequested",
                "data": { "action": "NavigateTo", "params": {...} }
            }
        }
        """
        trace_id = event_envelope.get("trace_id") or "trace_unknown"
        timestamp = event_envelope.get("timestamp")
        session_id = event_envelope.get("session_id")
        event_type = event_envelope.get("event_type", {})

        action_data = {}
        if isinstance(event_type, dict) and event_type.get("type") == "ActionRequested":
            action_data = event_type.get("data", {})
        elif isinstance(event_envelope.get("data"), dict):
            action_data = event_envelope["data"]

        action = action_data.get("action")
        params = action_data.get("params", {})

        if not action:
            log.warning(f"⚠️ ActionRequested envelope missing 'action': {event_envelope}")
            return False

        log.info(f"📥 [BRIDGE] Received action: {action} (trace={trace_id[:8]})")
        return self.command_handler.handle_action(
            action=action,
            params=params,
            trace_id=trace_id,
            timestamp=timestamp,
            session_id=session_id,
        )
