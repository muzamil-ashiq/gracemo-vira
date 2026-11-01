#!/usr/bin/env python3
"""
GRaCEmo ViRa — Robot Bridge Feedback Adapter
Translates low-level Nav2/Controller feedback and state changes into canonical
VIRA event envelopes with strictly preserved trace_ids.
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional

log = logging.getLogger("gracemo.bridge.feedback")


class FeedbackAdapter:
    """
    Constructs and emits canonical VIRA event envelopes for navigation feedback.
    Guarantees trace_id propagation through all feedback events.
    """

    def __init__(self, emit_callback: Callable[[Dict[str, Any]], None], source: str = "RobotBridge"):
        self.emit_callback = emit_callback
        self.source = source

    def _build_envelope(self, event_type: str, data: Dict[str, Any], trace_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "trace_id": trace_id or str(uuid.uuid4()),
            "session_id": session_id or "session_default",
            "timestamp": int(time.time()),
            "source": self.source,
            "observed_by": "RobotBridge",
            "event_type": {
                "type": event_type,
                "data": data,
            },
            "parent_event_id": None,
        }

    def emit_navigation_started(
        self,
        destination: str,
        target_x: float,
        target_y: float,
        trace_id: str,
        estimated_duration_sec: float = 10.0,
        session_id: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="NavigationStarted",
            data={
                "destination": destination,
                "target_x": round(float(target_x), 3),
                "target_y": round(float(target_y), 3),
                "estimated_duration_sec": round(float(estimated_duration_sec), 1),
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        log.info(f"📤 [FEEDBACK] NavigationStarted: {destination} (trace={trace_id[:8]})")
        self.emit_callback(envelope)

    def emit_navigation_progress(
        self,
        destination: str,
        current_x: float,
        current_y: float,
        distance_remaining_m: float,
        fraction_completed: float,
        trace_id: str,
        waypoint_idx: int = 1,
        session_id: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="NavigationProgress",
            data={
                "destination": destination,
                "current_x": round(float(current_x), 3),
                "current_y": round(float(current_y), 3),
                "distance_remaining_m": max(0.0, round(float(distance_remaining_m), 3)),
                "fraction_completed": min(1.0, max(0.0, round(float(fraction_completed), 3))),
                "current_waypoint_idx": waypoint_idx,
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        self.emit_callback(envelope)

    def emit_navigation_arrived(
        self,
        destination: str,
        x: float,
        y: float,
        trace_id: str,
        session_id: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="NavigationArrived",
            data={
                "destination": destination,
                "success": True,
                "x": round(float(x), 3),
                "y": round(float(y), 3),
                "error": None,
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        log.info(f"🎯 [FEEDBACK] NavigationArrived at '{destination}' (trace={trace_id[:8]})")
        self.emit_callback(envelope)

    def emit_navigation_failed(
        self,
        destination: str,
        reason: str,
        stuck_x: float,
        stuck_y: float,
        trace_id: str,
        recovery_attempts: int = 0,
        session_id: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="NavigationFailed",
            data={
                "destination": destination,
                "reason": reason,
                "stuck_at_x": round(float(stuck_x), 3),
                "stuck_at_y": round(float(stuck_y), 3),
                "recovery_attempts": recovery_attempts,
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        log.warning(f"❌ [FEEDBACK] NavigationFailed: '{destination}' ({reason}) (trace={trace_id[:8]})")
        self.emit_callback(envelope)

    def emit_robot_stopped(
        self,
        reason: str,
        x: float,
        y: float,
        trace_id: str,
        emergency: bool = False,
        session_id: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="RobotStopped",
            data={
                "reason": reason,
                "x": round(float(x), 3),
                "y": round(float(y), 3),
                "emergency": emergency,
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        log.info(f"🛑 [FEEDBACK] RobotStopped: {reason} (emergency={emergency}, trace={trace_id[:8]})")
        self.emit_callback(envelope)

    def emit_robot_position(
        self,
        x: float,
        y: float,
        theta: float,
        speed: float,
        trace_id: str,
        current_room: Optional[str] = None,
    ):
        envelope = self._build_envelope(
            event_type="RobotPosition",
            data={
                "x": round(float(x), 3),
                "y": round(float(y), 3),
                "theta": round(float(theta), 3),
                "speed": round(float(speed), 3),
                "current_room": current_room or "Unspecified",
            },
            trace_id=trace_id,
        )
        self.emit_callback(envelope)

    def emit_obstacle_detected(
        self,
        distance: float = 0.8,
        direction: str = "front",
        trace_id: str = "",
        session_id: Optional[str] = None,
        emergency_brake_triggered: bool = False,
    ):
        envelope = self._build_envelope(
            event_type="ObstacleDetected",
            data={
                "distance": round(float(distance), 2),
                "direction": direction,
                "emergency_brake_triggered": emergency_brake_triggered,
            },
            trace_id=trace_id,
            session_id=session_id,
        )
        log.warning(f"⚠️ [FEEDBACK] ObstacleDetected: {distance:.2f}m in {direction} direction (trace={trace_id[:8]})")
        self.emit_callback(envelope)
