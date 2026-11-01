"""
Engineering Status Indicator and Badge Widget for GRaCEmo ViRa.
Supports realistic states: NOT CONNECTED, INITIALIZING, READY, STALE DATA, ERROR.
Includes clickable navigation shortcuts to relevant diagnostic views.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QBrush, QCursor

from ..resources.styles.tokens import (
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_SUCCESS_BORDER,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    COLOR_WARNING_BORDER,
    COLOR_ERROR,
    COLOR_ERROR_BG,
    COLOR_ERROR_BORDER,
    COLOR_OFFLINE,
    COLOR_OFFLINE_BG,
    COLOR_OFFLINE_BORDER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BRAND_ORANGE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_BORDER,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
)


class StatusIndicator(QFrame):
    """Clickable engineering status indicator pill with LED dot and label."""

    clicked = Signal(str)  # Emits target page identifier on click

    STATE_NOT_CONNECTED = "NOT CONNECTED"
    STATE_INITIALIZING = "INITIALIZING"
    STATE_READY = "READY"
    STATE_STALE = "STALE DATA"
    STATE_ERROR = "ERROR"

    STATE_COLORS = {
        STATE_NOT_CONNECTED: COLOR_OFFLINE,
        STATE_INITIALIZING: COLOR_WARNING,
        STATE_READY: COLOR_SUCCESS,
        STATE_STALE: COLOR_WARNING,
        STATE_ERROR: COLOR_ERROR,
    }

    STATE_BACKGROUNDS = {
        STATE_NOT_CONNECTED: COLOR_OFFLINE_BG,
        STATE_INITIALIZING: COLOR_WARNING_BG,
        STATE_READY: COLOR_SUCCESS_BG,
        STATE_STALE: COLOR_WARNING_BG,
        STATE_ERROR: COLOR_ERROR_BG,
    }

    STATE_BORDERS = {
        STATE_NOT_CONNECTED: COLOR_OFFLINE_BORDER,
        STATE_INITIALIZING: COLOR_WARNING_BORDER,
        STATE_READY: COLOR_SUCCESS_BORDER,
        STATE_STALE: COLOR_WARNING_BORDER,
        STATE_ERROR: COLOR_ERROR_BORDER,
    }

    def __init__(self, title: str, initial_state: str = STATE_NOT_CONNECTED, target_page: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.current_state = initial_state
        self.target_page = target_page

        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("statusIndicatorPill")
        self.setCursor(QCursor(Qt.PointingHandCursor if target_page else Qt.ArrowCursor))

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 10, 4)
        self.layout.setSpacing(6)

        # LED Indicator Dot
        self.dot_widget = QWidget(self)
        self.dot_widget.setFixedSize(8, 8)
        self.dot_widget.paintEvent = self._paint_dot
        self.layout.addWidget(self.dot_widget)

        # Title Label
        self.title_label = QLabel(self.title, self)
        self.title_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px;")
        self.layout.addWidget(self.title_label)

        # State Value Badge
        self.state_label = QLabel(self.current_state, self)
        self.state_label.setStyleSheet(self._get_state_style(self.current_state))
        self.layout.addWidget(self.state_label)

        self._update_container_style()

    def _get_state_style(self, state: str) -> str:
        color = self.STATE_COLORS.get(state, COLOR_OFFLINE)
        return f"color: {color}; font-family: {FONT_FAMILY_MONO}; font-size: 11px; font-weight: 700;"

    def _update_container_style(self):
        bg = self.STATE_BACKGROUNDS.get(self.current_state, COLOR_OFFLINE_BG)
        border = self.STATE_BORDERS.get(self.current_state, COLOR_OFFLINE_BORDER)
        hover_border = COLOR_ACCENT_PRIMARY if self.target_page else border

        self.setStyleSheet(f"""
            QFrame#statusIndicatorPill {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QFrame#statusIndicatorPill:hover {{
                border-color: {hover_border};
            }}
        """)

    def _paint_dot(self, event):
        painter = QPainter(self.dot_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(self.STATE_COLORS.get(self.current_state, COLOR_OFFLINE))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 8, 8)

    def set_state(self, new_state: str, details: str = ""):
        """Update current status state."""
        if new_state not in self.STATE_COLORS:
            new_state = self.STATE_NOT_CONNECTED
        self.current_state = new_state
        self.state_label.setText(new_state)
        self.state_label.setStyleSheet(self._get_state_style(new_state))
        self._update_container_style()
        self.dot_widget.update()
        if details:
            self.setToolTip(f"{self.title}: {new_state}\n{details}")
        else:
            self.setToolTip(f"{self.title}: {new_state}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.target_page:
            self.clicked.emit(self.target_page)
        super().mousePressEvent(event)
