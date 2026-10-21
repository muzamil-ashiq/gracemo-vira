#!/usr/bin/env python3
"""
GRaCEmo ViRa — Production Mission Lifecycle & Authorization Manager
Implements Section 3 (Separation of SYSTEM_READY and MOTION_AUTHORIZED)
and Section 8 (Deterministic 8-stage mission lifecycle FSM):
  MISSION_CREATED
        ↓
  MISSION_AUTHORIZED (Requires explicit human safety operator authorization)
        ↓
  MISSION_RUNNING
    ├──► MISSION_PAUSED ──► MISSION_RESUMED ──► MISSION_RUNNING
    ├──► MISSION_COMPLETED
    ├──► MISSION_CANCELLED (Idempotent)
    └──► MISSION_FAILED

Safety Invariants:
  1. SYSTEM_READY != MOTION_AUTHORIZED: Booting software never activates motion automatically.
  2. Stale missions cannot auto-resume after E-stop, restart, communication loss, or safety faults.
  3. Cancellation is strictly idempotent.
"""
from __future__ import annotations
import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("gracemo.mission_lifecycle")


class MissionStatus(str, enum.Enum):
    MISSION_CREATED = "MISSION_CREATED"
    MISSION_AUTHORIZED = "MISSION_AUTHORIZED"
    MISSION_RUNNING = "MISSION_RUNNING"
    MISSION_PAUSED = "MISSION_PAUSED"
    MISSION_RESUMED = "MISSION_RESUMED"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_CANCELLED = "MISSION_CANCELLED"
    MISSION_FAILED = "MISSION_FAILED"


MissionState = MissionStatus


# Allowed lifecycle state transitions
ALLOWED_MISSION_TRANSITIONS: Dict[MissionStatus, Set[MissionStatus]] = {
    MissionStatus.MISSION_CREATED: {
        MissionStatus.MISSION_AUTHORIZED,
        MissionStatus.MISSION_CANCELLED,
        MissionStatus.MISSION_FAILED,
    },
    MissionStatus.MISSION_AUTHORIZED: {
        MissionStatus.MISSION_RUNNING,
        MissionStatus.MISSION_CANCELLED,
        MissionStatus.MISSION_FAILED,
    },
    MissionStatus.MISSION_RUNNING: {
        MissionStatus.MISSION_PAUSED,
        MissionStatus.MISSION_COMPLETED,
        MissionStatus.MISSION_CANCELLED,
        MissionStatus.MISSION_FAILED,
    },
    MissionStatus.MISSION_PAUSED: {
        MissionStatus.MISSION_RESUMED,
        MissionStatus.MISSION_CANCELLED,
        MissionStatus.MISSION_FAILED,
    },
    MissionStatus.MISSION_RESUMED: {
        MissionStatus.MISSION_RUNNING,
        MissionStatus.MISSION_PAUSED,
        MissionStatus.MISSION_COMPLETED,
        MissionStatus.MISSION_CANCELLED,
        MissionStatus.MISSION_FAILED,
    },
    MissionStatus.MISSION_COMPLETED: set(),  # Terminal state
    MissionStatus.MISSION_CANCELLED: {MissionStatus.MISSION_CANCELLED},  # Idempotent terminal
    MissionStatus.MISSION_FAILED: set(),  # Terminal state
}


@dataclass
class MissionInfo:
    mission_id: str
    trace_id: str
    destination_name: str
    target_x: float
    target_y: float
    target_yaw: Optional[float]
    tolerance_m: float
    created_at: float
    operator_id: Optional[str] = None
    authorized_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: MissionStatus = MissionStatus.MISSION_CREATED
    failure_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None

    @property
    def operator(self) -> Optional[str]:
        return self.operator_id


class MissionLifecycleManager:
    """
    Production coordinator for mission authorization and deterministic lifecycle state transitions.
    """

    def __init__(
        self,
        emit_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        state_machine: Optional[Any] = None,
        safety_gate: Optional[Any] = None,
    ):
        self._lock = threading.RLock()
        self._emit_cb = emit_callback or (lambda env: None)
        self.state_machine = state_machine
        self.safety_gate = safety_gate
        self._active_mission: Optional[MissionInfo] = None
        self._history: List[MissionInfo] = []

        # System readiness vs Motion authorization flag
        self._system_ready = False
        self._operator_authorized = False
        self._active_operator: Optional[str] = None

    @property
    def system_ready(self) -> bool:
        with self._lock:
            return self._system_ready

    @property
    def motion_authorized(self) -> bool:
        with self._lock:
            return self._operator_authorized

    @property
    def is_motion_authorized(self) -> bool:
        with self._lock:
            return self._operator_authorized

    def set_system_ready(self, ready: bool, reason: str = ""):
        with self._lock:
            self._system_ready = ready
            log.info(f"🔧 System readiness: {ready} [{reason}]")
            # If system readiness drops, motion authorization is immediately revoked
            if not ready:
                self.revoke_motion_authorization(reason="System readiness dropped")

    def authorize_motion(
        self,
        operator_id: Optional[str] = None,
        operator: Optional[str] = None,
        reason: str = "Operator Authorization",
    ) -> bool:
        """Explicit human operator motion authorization."""
        op = operator_id or operator or "operator_1"
        with self._lock:
            if not self._system_ready:
                log.warning("Cannot authorize motion: SYSTEM_READY is False (pre-flight required)")
                return False
            self._operator_authorized = True
            self._active_operator = op
            log.info(f"🛡️ MOTION_AUTHORIZED granted by operator: '{op}' [{reason}]")
            if self._active_mission and self._active_mission.status == MissionStatus.MISSION_CREATED:
                self._active_mission.status = MissionStatus.MISSION_AUTHORIZED
                self._active_mission.operator_id = op
                self._active_mission.authorized_at = time.time()
                log.info(f"✅ Active mission authorized: {self._active_mission.mission_id}")
            return True

    def revoke_motion_authorization(self, reason: str = "Authorization Revoked") -> bool:
        """Revokes motion authority immediately."""
        with self._lock:
            self._operator_authorized = False
            self._active_operator = None
            log.info(f"🔒 MOTION_AUTHORIZED revoked: {reason}")
            # If a mission is active, abort it
            if self._active_mission and self._active_mission.status in (
                MissionStatus.MISSION_RUNNING,
                MissionStatus.MISSION_PAUSED,
                MissionStatus.MISSION_AUTHORIZED,
            ):
                self.fail_mission(reason=f"Motion authorization revoked: {reason}")
            return True

    def create_mission(
        self,
        destination_name: str,
        target_x: float = 0.0,
        target_y: float = 0.0,
        trace_id: Optional[str] = None,
        target_yaw: Optional[float] = None,
        tolerance_m: float = 0.30,
        operator: Optional[str] = None,
        operator_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ) -> MissionInfo:
        """Creates a new mission in MISSION_CREATED state (does NOT start motion)."""
        with self._lock:
            # If an existing mission is in progress, cancel it cleanly
            if self._active_mission and self._active_mission.status in (
                MissionStatus.MISSION_RUNNING,
                MissionStatus.MISSION_PAUSED,
                MissionStatus.MISSION_AUTHORIZED,
            ):
                log.warning(f"Pre-empting active mission {self._active_mission.mission_id}")
                self.cancel_mission(reason="Pre-empted by new mission")

            m_id = mission_id or f"mission-{uuid.uuid4().hex[:8]}"
            t_id = trace_id or f"tr_{m_id}"
            op = operator_id or operator or self._active_operator

            mission = MissionInfo(
                mission_id=m_id,
                trace_id=t_id,
                destination_name=destination_name,
                target_x=target_x,
                target_y=target_y,
                target_yaw=target_yaw,
                tolerance_m=tolerance_m,
                created_at=time.time(),
                operator_id=op,
                status=MissionStatus.MISSION_CREATED,
            )
            self._active_mission = mission
            log.info(f"📋 Mission Created: {mission.mission_id} -> '{destination_name}'")
            return mission

    def authorize_active_mission(self, operator_id: str) -> bool:
        """Authorizes the created mission for execution."""
        with self._lock:
            if not self._active_mission:
                log.warning("No active mission to authorize")
                return False
            if self._active_mission.status not in (MissionStatus.MISSION_CREATED, MissionStatus.MISSION_AUTHORIZED):
                log.warning(f"Cannot authorize mission in status: {self._active_mission.status.value}")
                return False

            if not self._operator_authorized:
                # Also grants general motion authorization if operator authorizes mission
                if not self.authorize_motion(operator_id=operator_id, reason="Mission authorization"):
                    return False

            self._active_mission.status = MissionStatus.MISSION_AUTHORIZED
            self._active_mission.operator_id = operator_id
            self._active_mission.authorized_at = time.time()
            log.info(f"✅ Mission Authorized: {self._active_mission.mission_id} by {operator_id}")
            return True

    def start_mission(self, trace_id: Optional[str] = None) -> bool:
        """Transitions mission from MISSION_AUTHORIZED to MISSION_RUNNING."""
        with self._lock:
            if not self._active_mission:
                return False
            if self._active_mission.status != MissionStatus.MISSION_AUTHORIZED:
                log.warning(f"Cannot start mission: not in MISSION_AUTHORIZED (status={self._active_mission.status.value})")
                return False
            if not self._operator_authorized:
                log.warning("Cannot start mission: MOTION_AUTHORIZED is False")
                return False

            self._active_mission.status = MissionStatus.MISSION_RUNNING
            self._active_mission.started_at = time.time()
            log.info(f"🚀 Mission Running: {self._active_mission.mission_id}")
            return True

    def pause_mission(self, reason: str = "Pause requested") -> bool:
        with self._lock:
            if not self._active_mission:
                return False
            if self._active_mission.status != MissionStatus.MISSION_RUNNING:
                return False
            self._active_mission.status = MissionStatus.MISSION_PAUSED
            log.info(f"⏸️ Mission Paused: {self._active_mission.mission_id} [{reason}]")
            return True

    def resume_mission(self, reason: str = "Resume requested") -> bool:
        with self._lock:
            if not self._active_mission:
                return False
            if self._active_mission.status != MissionStatus.MISSION_PAUSED:
                return False
            if not self._operator_authorized:
                log.warning("Cannot resume mission: MOTION_AUTHORIZED is False")
                return False
            self._active_mission.status = MissionStatus.MISSION_RESUMED
            self._active_mission.status = MissionStatus.MISSION_RUNNING
            log.info(f"▶️ Mission Resumed: {self._active_mission.mission_id} [{reason}]")
            return True

    def complete_mission(self) -> bool:
        with self._lock:
            if not self._active_mission:
                return False
            if self._active_mission.status not in (MissionStatus.MISSION_RUNNING, MissionStatus.MISSION_RESUMED):
                return False
            self._active_mission.status = MissionStatus.MISSION_COMPLETED
            self._active_mission.completed_at = time.time()
            log.info(f"🎯 Mission Completed: {self._active_mission.mission_id}")
            self._history.append(self._active_mission)
            return True

    def cancel_mission(self, reason: str = "User Cancel") -> bool:
        """Idempotent mission cancellation."""
        with self._lock:
            if not self._active_mission:
                return True  # Idempotent: succeed even if no mission active
            if self._active_mission.status == MissionStatus.MISSION_CANCELLED:
                return True  # Idempotent: already cancelled

            self._active_mission.status = MissionStatus.MISSION_CANCELLED
            self._active_mission.cancellation_reason = reason
            self._active_mission.completed_at = time.time()
            log.info(f"⏹️ Mission Cancelled (Idempotent): {self._active_mission.mission_id} [{reason}]")
            self._history.append(self._active_mission)
            return True

    def fail_mission(self, reason: str = "Safety fault or navigation blockage") -> bool:
        with self._lock:
            if not self._active_mission:
                return True
            if self._active_mission.status in (MissionStatus.MISSION_COMPLETED, MissionStatus.MISSION_CANCELLED):
                return True
            self._active_mission.status = MissionStatus.MISSION_FAILED
            self._active_mission.failure_reason = reason
            self._active_mission.completed_at = time.time()
            log.warning(f"❌ Mission Failed: {self._active_mission.mission_id} [{reason}]")
            self._history.append(self._active_mission)
            return True

    def handle_safety_trip(self, reason: str = "E-Stop or Safety Fault"):
        """
        Critical Invariant: Safety trips unconditionally fail any in-flight mission
        and revoke motion authorization. Stale missions CANNOT auto-resume.
        """
        with self._lock:
            log.critical(f"🚨 Safety Trip Invariant Triggered: {reason}")
            self._operator_authorized = False
            if self._active_mission and self._active_mission.status in (
                MissionStatus.MISSION_RUNNING,
                MissionStatus.MISSION_PAUSED,
                MissionStatus.MISSION_AUTHORIZED,
                MissionStatus.MISSION_CREATED,
            ):
                self.fail_mission(reason=f"Safety trip aborted mission: {reason}")
            # Clear active mission pointer to guarantee no auto-resume
            self._active_mission = None

    def get_active_mission(self) -> Optional[MissionInfo]:
        with self._lock:
            return self._active_mission

    def get_history(self) -> List[MissionInfo]:
        with self._lock:
            return list(self._history)
