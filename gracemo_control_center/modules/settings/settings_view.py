"""
Module 11: Settings & Configuration View for GRaCEmo ViRa UARCC.
Configures UI refresh rates, sensor visualization settings, and logging,
organized into structured engineering sections with absolute hardware safety locks enforced.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QSpinBox, QCheckBox, QComboBox, QPushButton, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt

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
from ...widgets.common_components import PageHeader, SectionHeader, AlertBanner
from ...config.settings import Settings


class SettingsView(QWidget):
    """Module 11: Settings and Configuration Management."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

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
            title="Application Settings & Preferences",
            subtitle="Telemetry refresh intervals, sensor visualizer toggles, middleware defaults, and safety guardrails",
            badge_title="Settings State",
            initial_state=StatusIndicator.STATE_READY,
            target_page="Settings",
            parent=self
        )
        layout.addWidget(self.header)

        # 2. Section 1: Telemetry Refresh Rates Card
        rate_card = QFrame(self)
        rate_card.setProperty("class", "cardPanel")
        r_layout = QVBoxLayout(rate_card)
        r_layout.setSpacing(12)

        r_hdr = SectionHeader("Application Telemetry & UI Refresh Rates", parent=self)
        r_layout.addWidget(r_hdr)

        grid = QGridLayout()
        grid.setSpacing(12)

        # UI Update Rate (ms)
        lbl_ui_rate = QLabel("UI Refresh Interval (ms):")
        lbl_ui_rate.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;")
        self.spin_ui_rate = QSpinBox()
        self.spin_ui_rate.setRange(20, 200)
        self.spin_ui_rate.setValue(self.settings.ui_update_rate_ms)
        self.spin_ui_rate.setSuffix(" ms (20 Hz default)")
        grid.addWidget(lbl_ui_rate, 0, 0)
        grid.addWidget(self.spin_ui_rate, 0, 1)

        # System Telemetry Rate (ms)
        lbl_sys_rate = QLabel("Host System Monitor Interval (ms):")
        lbl_sys_rate.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;")
        self.spin_sys_rate = QSpinBox()
        self.spin_sys_rate.setRange(500, 5000)
        self.spin_sys_rate.setValue(self.settings.system_monitor_rate_ms)
        self.spin_sys_rate.setSuffix(" ms (1 Hz default)")
        grid.addWidget(lbl_sys_rate, 1, 0)
        grid.addWidget(self.spin_sys_rate, 1, 1)

        # Camera Max Framerate
        lbl_cam_fps = QLabel("Camera Video FPS Cap:")
        lbl_cam_fps.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;")
        self.spin_cam_fps = QSpinBox()
        self.spin_cam_fps.setRange(5, 60)
        self.spin_cam_fps.setValue(30)
        self.spin_cam_fps.setSuffix(" FPS")
        grid.addWidget(lbl_cam_fps, 2, 0)
        grid.addWidget(self.spin_cam_fps, 2, 1)

        r_layout.addLayout(grid)
        layout.addWidget(rate_card)

        # 3. Section 2: Sensor Visualization Settings Card
        vis_card = QFrame(self)
        vis_card.setProperty("class", "cardPanel")
        v_layout = QVBoxLayout(vis_card)
        v_layout.setSpacing(12)

        v_hdr = SectionHeader("Sensor Visualization & Viewport Preferences", parent=self)
        v_layout.addWidget(v_hdr)

        self.chk_rgb = QCheckBox("Enable Live RGB Camera Decoding & Display", self)
        self.chk_rgb.setChecked(True)
        v_layout.addWidget(self.chk_rgb)

        self.chk_depth = QCheckBox("Enable Live Depth Camera Turbo Colormapping", self)
        self.chk_depth.setChecked(True)
        v_layout.addWidget(self.chk_depth)

        self.chk_lidar = QCheckBox("Enable 360° LiDAR Point Cloud Polar Radar", self)
        self.chk_lidar.setChecked(True)
        v_layout.addWidget(self.chk_lidar)

        layout.addWidget(vis_card)

        # 4. Section 3: Middleware & Simulation Defaults Card
        mw_card = QFrame(self)
        mw_card.setProperty("class", "cardPanel")
        mw_layout = QVBoxLayout(mw_card)
        mw_layout.setSpacing(10)

        mw_hdr = SectionHeader("ROS 2 & Gazebo Harmonic Middleware Defaults", parent=self)
        mw_layout.addWidget(mw_hdr)

        mw_grid = QGridLayout()
        mw_grid.setSpacing(8)

        lbl_dds = QLabel("ROS Automatic Discovery Range: LOCALHOST (Loopback Isolated)")
        lbl_dom = QLabel("ROS Domain ID: 0 (Default)")
        lbl_part = QLabel("Gazebo Partition: gracemo")
        lbl_ip = QLabel("Gazebo IP Binding: 127.0.0.1")

        for lbl in (lbl_dds, lbl_dom, lbl_part, lbl_ip):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_PRIMARY};")

        mw_grid.addWidget(lbl_dds, 0, 0)
        mw_grid.addWidget(lbl_dom, 0, 1)
        mw_grid.addWidget(lbl_part, 1, 0)
        mw_grid.addWidget(lbl_ip, 1, 1)
        mw_layout.addLayout(mw_grid)
        layout.addWidget(mw_card)

        # 5. Section 4: Hardware Safety Interlocks Guard (Permanently Locked)
        safety_card = QFrame(self)
        safety_card.setProperty("class", "cardPanel")
        s_layout = QVBoxLayout(safety_card)
        s_layout.setSpacing(10)

        s_hdr = SectionHeader("Hardware Safety Interlocks (Permanently Immutable)", parent=self)
        s_layout.addWidget(s_hdr)

        s_info = QLabel(
            "• SerialMCUTransport.PROTOCOL_CONFIRMED = False  [LOCKED: Cannot be modified from GUI]\n"
            "• MOTOR_OUTPUT_ENABLED = 0                        [LOCKED: Physical motor actuation prohibited]\n"
            "• Authoritative Destinations File: config/destinations.json [READ-ONLY]"
        )
        s_info.setStyleSheet(f"""
            font-family: {FONT_FAMILY_MONO};
            font-size: 11px;
            color: {COLOR_SUCCESS};
            background-color: {COLOR_PANEL_SECONDARY};
            padding: 10px;
            border-radius: {BORDER_RADIUS_SM}px;
            border: 1px solid {COLOR_BORDER};
            line-height: 1.5;
        """)
        s_layout.addWidget(s_info)
        layout.addWidget(safety_card)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_save = QPushButton("Save Preferences", self)
        btn_save.setProperty("class", "primaryButton")
        btn_save.clicked.connect(self._save_preferences)
        btn_box.addWidget(btn_save)

        btn_box.addStretch()
        layout.addLayout(btn_box)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

    def _save_preferences(self):
        self.settings.ui_update_rate_ms = self.spin_ui_rate.value()
        self.settings.system_monitor_rate_ms = self.spin_sys_rate.value()
        QMessageBox.information(self, "Settings Saved", "Display and refresh preferences applied successfully.")
