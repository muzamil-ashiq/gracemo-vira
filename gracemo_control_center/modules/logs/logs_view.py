"""
Module 10: System Logs & Event History View for GRaCEmo ViRa UARCC.
Full-screen log viewer supporting multi-source log streams,
severity filtering, and log archiving.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from ...resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_PANEL_MAIN,
    COLOR_BORDER,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)
from ...widgets.log_viewer import LogViewerWidget
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader
from ...core.event_bus import bus


class LogsView(QWidget):
    """Module 10: Unified System Logs Center."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Standard Page Header
        self.header = PageHeader(
            title="System Logs & Telemetry Audit",
            subtitle="Real-time multi-subsystem event logging, severity filtering, search, and export",
            badge_title="Logger Engine",
            initial_state=StatusIndicator.STATE_READY,
            target_page="System Logs",
            parent=self
        )
        layout.addWidget(self.header)

        # Embedded Log Viewer Widget
        self.log_viewer = LogViewerWidget(self)
        layout.addWidget(self.log_viewer, stretch=1)

        # Connect bus signal
        bus.log_event_emitted.connect(self._on_log_event)

    def _on_log_event(self, entry: dict):
        self.log_viewer.add_log(
            level=entry.get("level", "INFO"),
            component=entry.get("component", "SYSTEM"),
            source=entry.get("source", "UARCC"),
            message=entry.get("message", ""),
            timestamp=entry.get("timestamp", None)
        )
