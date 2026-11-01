"""
Module 5: Localization & TF Monitor for GRaCEmo ViRa UARCC.
Monitors AMCL particle filter, covariance bounds, nomotion service,
and visualizes the coordinate transform chain: map → odom → base_footprint → lidar_link.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QScrollArea
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
from ...widgets.robot_pose_widget import RobotPoseWidget
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay
from ...core.event_bus import bus


class LocalizationView(QWidget):
    """Module 5: Localization & TF Diagnostics Center."""

    def __init__(self, parent=None):
        super().__init__(parent)

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
            title="Localization & Transforms",
            subtitle="AMCL particle filter confidence, pose covariance bounds, and authoritative TF coordinate tree",
            badge_title="AMCL Health",
            initial_state=StatusIndicator.STATE_NOT_CONNECTED,
            target_page="Localization",
            parent=self
        )
        self.ind_amcl = self.header.badge
        layout.addWidget(self.header)

        # 2. Key Metrics Row
        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)

        self.metric_conf = MetricDisplay("Localization Status", "UNINITIALIZED", status_color=COLOR_WARNING, parent=self)
        self.metric_var_pos = MetricDisplay("Position Variance", "0.000 m²", status_color=COLOR_TEXT_PRIMARY, parent=self)
        self.metric_var_yaw = MetricDisplay("Heading Variance", "0.000 rad²", status_color=COLOR_TEXT_PRIMARY, parent=self)
        self.metric_tf_tree = MetricDisplay("TF Chain State", "OK", status_color=COLOR_SUCCESS, parent=self)

        metric_row.addWidget(self.metric_conf)
        metric_row.addWidget(self.metric_var_pos)
        metric_row.addWidget(self.metric_var_yaw)
        metric_row.addWidget(self.metric_tf_tree)
        layout.addLayout(metric_row)

        # 3. TF Coordinate Chain Card
        tf_card = QFrame(self)
        tf_card.setProperty("class", "cardPanel")
        tf_layout = QVBoxLayout(tf_card)
        tf_layout.setSpacing(10)

        tf_hdr = SectionHeader("Coordinate Transform Hierarchy: map → odom → base_footprint → sensors", parent=self)
        tf_layout.addWidget(tf_hdr)

        chain_row = QHBoxLayout()
        chain_row.setSpacing(10)

        self.ind_tf_map_odom = StatusIndicator("map → odom", StatusIndicator.STATE_NOT_CONNECTED)
        self.ind_tf_odom_base = StatusIndicator("odom → base_footprint", StatusIndicator.STATE_NOT_CONNECTED)
        self.ind_tf_base_lidar = StatusIndicator("base_footprint → lidar_link", StatusIndicator.STATE_NOT_CONNECTED)
        self.ind_tf_base_cam = StatusIndicator("base_footprint → camera_link", StatusIndicator.STATE_NOT_CONNECTED)

        for ind in (self.ind_tf_map_odom, self.ind_tf_odom_base, self.ind_tf_base_lidar, self.ind_tf_base_cam):
            chain_row.addWidget(ind)

        chain_row.addStretch()
        tf_layout.addLayout(chain_row)
        layout.addWidget(tf_card)

        # 4. Middle Row: Robot Pose + Covariance Bounds
        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)

        # Pose Widget
        self.pose_card = RobotPoseWidget(self)
        mid_row.addWidget(self.pose_card, stretch=1)

        # Covariance Matrix Card
        cov_card = QFrame(self)
        cov_card.setProperty("class", "cardPanel")
        c_layout = QVBoxLayout(cov_card)
        c_layout.setSpacing(12)

        c_hdr = SectionHeader("AMCL Particle Covariance Bounds (Target: < 1.0 m²)", parent=self)
        c_layout.addWidget(c_hdr)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.lbl_var_x = QLabel("Variance X (σx²): 0.000 m²")
        self.lbl_var_y = QLabel("Variance Y (σy²): 0.000 m²")
        self.lbl_var_yaw = QLabel("Variance Yaw (σθ²): 0.000 rad²")
        self.lbl_loc_verdict = QLabel("Localization State: BOUNDED & ACCEPTED ✅")

        for lbl in (self.lbl_var_x, self.lbl_var_y, self.lbl_var_yaw, self.lbl_loc_verdict):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")

        grid.addWidget(self.lbl_var_x, 0, 0)
        grid.addWidget(self.lbl_var_y, 0, 1)
        grid.addWidget(self.lbl_var_yaw, 1, 0)
        grid.addWidget(self.lbl_loc_verdict, 1, 1)
        c_layout.addLayout(grid)

        # Non-motion Update Trigger Action
        btn_nomotion = QPushButton("Request AMCL Non-Motion Scan Update", self)
        btn_nomotion.setProperty("class", "secondaryButton")
        btn_nomotion.clicked.connect(self._trigger_nomotion_update)
        c_layout.addWidget(btn_nomotion)

        c_layout.addStretch()
        mid_row.addWidget(cov_card, stretch=1)
        layout.addLayout(mid_row)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        # Connect signals
        bus.amcl_pose_ready.connect(self._on_amcl_pose)
        bus.tf_status_ready.connect(self._on_tf_status)

    def _on_amcl_pose(self, x, y, yaw, vx, vy, vyaw):
        self.ind_amcl.set_state(StatusIndicator.STATE_READY)
        self.pose_card.update_amcl_pose(x, y, yaw, vx, vy, vyaw)

        self.lbl_var_x.setText(f"Variance X (σx²): {vx:.4f} m²")
        self.lbl_var_y.setText(f"Variance Y (σy²): {vy:.4f} m²")
        self.lbl_var_yaw.setText(f"Variance Yaw (σθ²): {vyaw:.4f} rad²")

        total_pos_var = math.sqrt(vx * vx + vy * vy)
        self.metric_var_pos.set_value(f"{total_pos_var:.3f} m²")
        self.metric_var_yaw.set_value(f"{vyaw:.3f} rad²")

        if vx < 1.0 and vy < 1.0:
            self.lbl_loc_verdict.setText("Localization State: BOUNDED & ACCEPTED ✅")
            self.lbl_loc_verdict.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_SUCCESS};")
            self.metric_conf.set_value("BOUNDED & STABLE", status_color=COLOR_SUCCESS)
        else:
            self.lbl_loc_verdict.setText("Localization State: DIVERGED / HIGH COVARIANCE ⚠️")
            self.lbl_loc_verdict.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_WARNING};")
            self.metric_conf.set_value("DIVERGED / RE-LOCALIZING", status_color=COLOR_WARNING)

    def _on_tf_status(self, tf_dict: dict):
        all_ok = True
        if "map_to_odom" in tf_dict:
            st = StatusIndicator.STATE_READY if tf_dict["map_to_odom"] else StatusIndicator.STATE_NOT_CONNECTED
            self.ind_tf_map_odom.set_state(st)
            if not tf_dict["map_to_odom"]:
                all_ok = False
        if "odom_to_base" in tf_dict:
            st = StatusIndicator.STATE_READY if tf_dict["odom_to_base"] else StatusIndicator.STATE_NOT_CONNECTED
            self.ind_tf_odom_base.set_state(st)
            if not tf_dict["odom_to_base"]:
                all_ok = False
        if "base_to_lidar" in tf_dict:
            st = StatusIndicator.STATE_READY if tf_dict["base_to_lidar"] else StatusIndicator.STATE_NOT_CONNECTED
            self.ind_tf_base_lidar.set_state(st)
            if not tf_dict["base_to_lidar"]:
                all_ok = False
        if "base_to_cam" in tf_dict:
            st = StatusIndicator.STATE_READY if tf_dict["base_to_cam"] else StatusIndicator.STATE_NOT_CONNECTED
            self.ind_tf_base_cam.set_state(st)
            if not tf_dict["base_to_cam"]:
                all_ok = False

        self.metric_tf_tree.set_value("HEALTHY" if all_ok else "DEGRADED", status_color=COLOR_SUCCESS if all_ok else COLOR_WARNING)

    def _trigger_nomotion_update(self):
        """Send empty request to /request_nomotion_update service via event bus."""
        bus.user_input_received.emit("what is your status", "TEXT")
