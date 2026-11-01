"""
Subsystem Health Monitor for GRaCEmo ViRa UARCC.
Evaluates empirical data freshness across sensor streams and ROS topics.
Implements the zero-fabrication invariant:
Reports NOT CONNECTED, INITIALIZING, STALE DATA, ERROR, or READY
based strictly on verified timestamp intervals.
"""

from PySide6.QtCore import QObject, QTimer
import time
from typing import Dict, Any

from .event_bus import bus
from ..widgets.status_indicator import StatusIndicator


class HealthMonitor(QObject):
    """Audits data freshness and generates subsystem readiness states."""

    def __init__(self, stale_timeout_sec: float = 2.0, parent=None):
        super().__init__(parent)
        self.stale_timeout_sec = stale_timeout_sec

        # Timestamps of latest received messages
        self.last_seen: Dict[str, float] = {
            "clock": 0.0,
            "scan": 0.0,
            "odom": 0.0,
            "imu": 0.0,
            "camera_rgb": 0.0,
            "camera_depth": 0.0,
            "amcl_pose": 0.0,
            "map": 0.0,
            "coordinator": 0.0,
            "interaction": 0.0,
            "terrain": 0.0,
        }

        # Subsystem error flags
        self.error_flags: Dict[str, bool] = {
            "terrain": False,
            "coordinator": False,
        }

        # Periodic audit timer (runs at 2 Hz)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._audit_health)
        self.timer.start(500)

    def record_heartbeat(self, subsystem: str, is_error: bool = False):
        """Record receipt of a live message for a given subsystem."""
        self.last_seen[subsystem] = time.time()
        self.error_flags[subsystem] = is_error

    def _audit_health(self):
        now = time.time()
        health_states = {}

        for sub, last_ts in self.last_seen.items():
            if self.error_flags.get(sub, False):
                health_states[sub] = StatusIndicator.STATE_ERROR
            elif last_ts == 0.0:
                health_states[sub] = StatusIndicator.STATE_NOT_CONNECTED
            elif now - last_ts > self.stale_timeout_sec:
                health_states[sub] = StatusIndicator.STATE_STALE
            else:
                health_states[sub] = StatusIndicator.STATE_READY

        # Emit updated health matrix on event bus
        bus.subsystem_health_updated.emit(health_states)

        # Update high-level Gazebo and ROS connectivity
        gz_ok = (health_states.get("clock") == StatusIndicator.STATE_READY)
        bus.gazebo_connected.emit(gz_ok)
