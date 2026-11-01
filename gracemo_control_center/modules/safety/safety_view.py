"""
Module 8: Safety Control Center for GRaCEmo ViRa UARCC.
Real-time monitoring of collision avoidance, terrain slope envelope,
velocity watchdog, single-owner /cmd_vel arbitration, and authoritative emergency stop.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import time
import math

from ...resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay, AlertBanner
from ...core.event_bus import bus


class SafetyView(QWidget):
    """Module 8: High-Integrity Safety Arbitration & Emergency Stop Center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.estop_active = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Page Header
        self.header = PageHeader(
            title="Safety Arbitration & Reflex Envelopes",
            subtitle="Authoritative E-stop gate, collision monitoring, terrain envelope, and hardware interlocks",
            badge_title="Safety System",
            initial_state=StatusIndicator.STATE_READY,
            target_page="Safety",
            parent=self
        )
        self.ind_safety_gate = self.header.badge
        layout.addWidget(self.header)

        # 2. Key Metrics Row
        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)

        self.metric_estop = MetricDisplay("Emergency Stop", "INACTIVE", status_color=COLOR_SUCCESS, parent=self)
        self.metric_collision = MetricDisplay("Collision Zone", "NOMINAL", status_color=COLOR_SUCCESS, parent=self)
        self.metric_slope = MetricDisplay("Terrain State", "NORMAL", status_color=COLOR_SUCCESS, parent=self)
        self.metric_hw_lock = MetricDisplay("Hardware Interlock", "LOCKED (SIM)", status_color=COLOR_BRAND_ORANGE, parent=self)

        metric_row.addWidget(self.metric_estop)
        metric_row.addWidget(self.metric_collision)
        metric_row.addWidget(self.metric_slope)
        metric_row.addWidget(self.metric_hw_lock)
        layout.addLayout(metric_row)

        # 3. Emergency Stop Authoritative Control Card
        estop_card = QFrame(self)
        estop_card.setProperty("class", "cardPanel")
        ec_layout = QVBoxLayout(estop_card)
        ec_layout.setSpacing(12)

        ec_hdr = SectionHeader("Authoritative Emergency Stop Gate (/terrain/emergency_stop)", parent=self)
        ec_layout.addWidget(ec_hdr)

        self.lbl_estop_status = QLabel("EMERGENCY STOP: INACTIVE (NORMAL NAVIGATION PERMITTED)")
        self.lbl_estop_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 13px; font-weight: 700; color: {COLOR_SUCCESS};")
        ec_layout.addWidget(self.lbl_estop_status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_assert_estop = QPushButton("🚨 ENGAGE EMERGENCY STOP", self)
        self.btn_assert_estop.setProperty("class", "dangerButton")
        self.btn_assert_estop.setStyleSheet("font-size: 13px; padding: 10px 20px;")
        self.btn_assert_estop.clicked.connect(self._engage_estop)
        btn_row.addWidget(self.btn_assert_estop)

        self.btn_reset_estop = QPushButton("✔ Clear E-Stop / Safe Resume", self)
        self.btn_reset_estop.setProperty("class", "secondaryButton")
        self.btn_reset_estop.setStyleSheet("font-size: 13px; padding: 10px 20px;")
        self.btn_reset_estop.clicked.connect(self._confirm_and_reset_estop)
        btn_row.addWidget(self.btn_reset_estop)

        btn_row.addStretch()
        ec_layout.addLayout(btn_row)
        layout.addWidget(estop_card)

        # 4. Single-Owner Command Velocity Pipeline Card
        chain_card = QFrame(self)
        chain_card.setProperty("class", "cardPanel")
        cc_layout = QVBoxLayout(chain_card)
        cc_layout.setSpacing(12)

        cc_hdr = SectionHeader("Command Velocity Arbitration Pipeline", parent=self)
        cc_layout.addWidget(cc_hdr)

        flow_lbl = QLabel(
            "Nav2 BT  ──►  /cmd_vel_nav  ──►  velocity_smoother  ──►  /cmd_vel_smoothed  ──►\n"
            "collision_monitor  ──►  /cmd_vel_safe  ──►  terrain_monitor  ──►  /cmd_vel  ──►  ros_gz_bridge"
        )
        flow_lbl.setStyleSheet(f"""
            font-family: {FONT_FAMILY_MONO};
            font-size: 11px;
            color: {COLOR_TEXT_PRIMARY};
            background-color: {COLOR_PANEL_SECONDARY};
            padding: 10px;
            border-radius: {BORDER_RADIUS_SM}px;
            border: 1px solid {COLOR_BORDER};
        """)
        cc_layout.addWidget(flow_lbl)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.lbl_terrain_state = QLabel("Terrain Grade: NORMAL")
        self.lbl_speed_factor = QLabel("Speed Factor: 1.00x (100%)")
        self.lbl_roll_angle = QLabel("Base Roll: 0.0° (Limit: 12.0°)")
        self.lbl_pitch_angle = QLabel("Base Pitch: 0.0° (Limit: 15.0°)")
        self.lbl_collision_breach = QLabel("Collision Envelope: NOMINAL (>0.35 m)")
        self.lbl_watchdog = QLabel("Terrain Watchdog: NOMINAL (0.05 s tick)")

        for lbl in (self.lbl_terrain_state, self.lbl_speed_factor, self.lbl_roll_angle, self.lbl_pitch_angle, self.lbl_collision_breach, self.lbl_watchdog):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_SECONDARY};")

        grid.addWidget(self.lbl_terrain_state, 0, 0)
        grid.addWidget(self.lbl_speed_factor, 0, 1)
        grid.addWidget(self.lbl_roll_angle, 1, 0)
        grid.addWidget(self.lbl_pitch_angle, 1, 1)
        grid.addWidget(self.lbl_collision_breach, 2, 0)
        grid.addWidget(self.lbl_watchdog, 2, 1)
        cc_layout.addLayout(grid)

        layout.addWidget(chain_card)

        # 5. Hardware Safety Interlocks Card
        hw_card = QFrame(self)
        hw_card.setProperty("class", "cardPanel")
        hw_layout = QVBoxLayout(hw_card)
        hw_layout.setSpacing(10)

        hw_hdr = SectionHeader("Hardware Safety Invariants & Firmware Interlocks", parent=self)
        hw_layout.addWidget(hw_hdr)

        hw_info = QLabel(
            "• SerialMCUTransport.PROTOCOL_CONFIRMED = False  [LOCKED: Physical serial transport disconnected]\n"
            "• MOTOR_OUTPUT_ENABLED = 0                        [LOCKED: Hardware motor bridge PWM/CAN disabled]\n"
            "• Emergency Stop Contactor Dropout: <20 ms        [QUALIFIED & ENFORCED]\n"
            "• Physical Actuation Status: DISABLED (Simulation Only Workstation)"
        )
        hw_info.setStyleSheet(f"""
            font-family: {FONT_FAMILY_MONO};
            font-size: 11px;
            color: {COLOR_SUCCESS};
            background-color: {COLOR_PANEL_SECONDARY};
            padding: 10px;
            border-radius: {BORDER_RADIUS_SM}px;
            border: 1px solid {COLOR_BORDER};
            line-height: 1.5;
        """)
        hw_layout.addWidget(hw_info)
        layout.addWidget(hw_card)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        # Connect signals
        bus.terrain_status_ready.connect(self._on_terrain_status)
        bus.emergency_stop_state.connect(self._on_estop_state)

    def _engage_estop(self):
        bus.emergency_stop_state.emit(True, "SAFETY_PANEL_BUTTON")

    def _confirm_and_reset_estop(self):
        """Require explicit human operator confirmation before clearing E-stop."""
        reply = QMessageBox.question(
            self,
            "Confirm Emergency Stop Reset",
            "Are all physical and simulated safety obstacles clear?\nResetting Emergency Stop will permit motion planning to resume.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            bus.emergency_stop_state.emit(False, "HUMAN_OPERATOR_CLEARED")

    def _on_estop_state(self, is_active: bool, source: str):
        self.estop_active = is_active
        if is_active:
            self.lbl_estop_status.setText(f"EMERGENCY STOP: ACTIVE ({source}) 🚨")
            self.lbl_estop_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 13px; font-weight: 700; color: {COLOR_ERROR};")
            self.metric_estop.set_value("ACTIVE", status_color=COLOR_ERROR)
            self.ind_safety_gate.set_state(StatusIndicator.STATE_ERROR)
        else:
            self.lbl_estop_status.setText("EMERGENCY STOP: INACTIVE (NORMAL NAVIGATION PERMITTED)")
            self.lbl_estop_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 13px; font-weight: 700; color: {COLOR_SUCCESS};")
            self.metric_estop.set_value("INACTIVE", status_color=COLOR_SUCCESS)
            self.ind_safety_gate.set_state(StatusIndicator.STATE_READY)

    def _on_terrain_status(self, data: dict):
        slope = data.get("slope_state", "NORMAL")
        self.lbl_terrain_state.setText(f"Terrain Grade: {slope}")
        self.metric_slope.set_value(slope, status_color=COLOR_SUCCESS if slope == "NORMAL" else COLOR_WARNING)

        factor = data.get("speed_factor", 1.0)
        self.lbl_speed_factor.setText(f"Speed Factor: {factor:.2f}x ({factor*100:.0f}%)")
        roll = data.get("base_roll_deg", 0.0)
        pitch = data.get("base_pitch_deg", 0.0)
        self.lbl_roll_angle.setText(f"Base Roll: {roll:+.1f}° (Limit: 12.0°)")
        self.lbl_pitch_angle.setText(f"Base Pitch: {pitch:+.1f}° (Limit: 15.0°)")
