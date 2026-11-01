"""
Standardized Reusable UI Components for GRaCEmo ViRa UARCC.
Includes PageHeader, SectionHeader, MetricDisplay, EmptyState,
AlertBanner, and ConfirmationDialog.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QDialog, QDialogButtonBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ..resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_ACCENT_PRIMARY,
    COLOR_BRAND_ORANGE,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    COLOR_ERROR,
    COLOR_ERROR_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)
from .status_indicator import StatusIndicator


class PageHeader(QFrame):
    """Clean, consistent header for all module views."""

    def __init__(self, title: str, subtitle: str, badge_title: str = "", initial_state: str = "", target_page: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("pageHeader")
        self.setStyleSheet(f"""
            QFrame#pageHeader {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_MD}px;
                padding: 12px 16px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        self.lbl_title = QLabel(title, self)
        self.lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLOR_TEXT_PRIMARY};")
        title_box.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(subtitle, self)
        self.lbl_subtitle.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY};")
        title_box.addWidget(self.lbl_subtitle)

        layout.addLayout(title_box)
        layout.addStretch()

        # Optional Context Badge
        self.badge = None
        if badge_title:
            self.badge = StatusIndicator(badge_title, initial_state or StatusIndicator.STATE_NOT_CONNECTED, target_page, self)
            layout.addWidget(self.badge)

    def set_title(self, title: str):
        self.lbl_title.setText(title)

    def set_subtitle(self, subtitle: str):
        self.lbl_subtitle.setText(subtitle)

    def set_badge_state(self, state: str, details: str = ""):
        if self.badge:
            self.badge.set_state(state, details)


class SectionHeader(QWidget):
    """Standardized subsection header with clean typography."""

    def __init__(self, title: str, action_widget=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self.lbl_title = QLabel(title.upper(), self)
        self.lbl_title.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLOR_TEXT_SECONDARY};
            letter-spacing: 0.8px;
        """)
        layout.addWidget(self.lbl_title)
        layout.addStretch()

        if action_widget:
            layout.addWidget(action_widget)


class MetricDisplay(QFrame):
    """Compact engineering telemetry card with large readout value."""

    def __init__(self, label: str, initial_value: str = "--", unit: str = "", status_color: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("metricDisplayCard")
        self.status_color = status_color or COLOR_TEXT_PRIMARY

        self.setStyleSheet(f"""
            QFrame#metricDisplayCard {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_SM}px;
                padding: 8px 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.lbl_label = QLabel(label.upper(), self)
        self.lbl_label.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLOR_TEXT_SECONDARY}; letter-spacing: 0.5px;")
        layout.addWidget(self.lbl_label)

        val_row = QHBoxLayout()
        val_row.setSpacing(4)

        self.lbl_value = QLabel(initial_value, self)
        self.lbl_value.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 18px; font-weight: 700; color: {self.status_color};")
        val_row.addWidget(self.lbl_value)

        if unit:
            self.lbl_unit = QLabel(unit, self)
            self.lbl_unit.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {COLOR_TEXT_MUTED};")
            val_row.addWidget(self.lbl_unit)

        val_row.addStretch()
        layout.addLayout(val_row)

    def set_value(self, val: str, status_color: str = None):
        self.lbl_value.setText(val)
        if status_color:
            self.status_color = status_color
            self.lbl_value.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 18px; font-weight: 700; color: {status_color};")


class EmptyState(QFrame):
    """Clean placeholder for uninitialized or disconnected subsystems."""

    def __init__(self, title: str, description: str, action_btn: QPushButton = None, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateFrame")
        self.setStyleSheet(f"""
            QFrame#emptyStateFrame {{
                background-color: {COLOR_PANEL_SECONDARY};
                border: 1px dashed {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_MD}px;
                padding: 24px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(description, self)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY};")
        lbl_desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_desc)

        if action_btn:
            layout.addSpacing(4)
            layout.addWidget(action_btn, alignment=Qt.AlignCenter)


class AlertBanner(QFrame):
    """Full-width high-visibility alert banner."""

    def __init__(self, message: str, level: str = "info", action_btn: QPushButton = None, parent=None):
        super().__init__(parent)
        self.setObjectName("alertBanner")

        if level == "error":
            bg = COLOR_ERROR_BG
            border_c = COLOR_ERROR
            txt_c = COLOR_ERROR
        elif level == "warning":
            bg = COLOR_WARNING_BG
            border_c = COLOR_WARNING
            txt_c = COLOR_WARNING
        elif level == "brand":
            bg = "#FFF3E0"
            border_c = COLOR_BRAND_ORANGE
            txt_c = COLOR_BRAND_ORANGE
        else:
            bg = "#EAF2FA"
            border_c = COLOR_ACCENT_PRIMARY
            txt_c = COLOR_ACCENT_PRIMARY

        self.setStyleSheet(f"""
            QFrame#alertBanner {{
                background-color: {bg};
                border: 1px solid {COLOR_BORDER};
                border-left: 4px solid {border_c};
                border-radius: {BORDER_RADIUS_SM}px;
                padding: 8px 14px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.lbl_msg = QLabel(message, self)
        self.lbl_msg.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {txt_c};")
        layout.addWidget(self.lbl_msg)

        layout.addStretch()

        if action_btn:
            layout.addWidget(action_btn)

    def set_message(self, message: str):
        self.lbl_msg.setText(message)


class ConfirmationDialog(QDialog):
    """Clean modal dialog for confirming consequential operations."""

    def __init__(self, title: str, message: str, confirm_label: str = "Confirm", is_danger: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 180)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_SURFACE};
                font-family: {FONT_FAMILY_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel(title, self)
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_title)

        lbl_msg = QLabel(message, self)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(f"font-size: 13px; color: {COLOR_TEXT_SECONDARY}; line-height: 1.4;")
        layout.addWidget(lbl_msg)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.setProperty("class", "secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton(confirm_label, self)
        if is_danger:
            btn_confirm.setProperty("class", "dangerButton")
        else:
            btn_confirm.setProperty("class", "primaryButton")
        btn_confirm.clicked.connect(self.accept)
        btn_box.addWidget(btn_confirm)

        layout.addLayout(btn_box)
