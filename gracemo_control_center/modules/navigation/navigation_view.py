"""
Module 3: Autonomous Navigation Center for GRaCEmo ViRa UARCC.
Interactive 2D Occupancy Grid map, authoritative 6-destination selector,
coordinator-mediated action dispatch, cancellation, and arrival verification.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QComboBox, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import json
import time
from typing import Dict, Any, Optional

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
from ...widgets.map_view import MapViewWidget
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay
from ...config.settings import Settings
from ...core.event_bus import bus


class NavigationView(QWidget):
    """Module 3: Autonomous Navigation Command & Tracking Center."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.destinations = settings.destinations

        self.active_destination_key: Optional[str] = None
        self.navigation_start_time: Optional[float] = None
        self.coordinator_state = "IDLE"
        self.has_localization = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Page Header
        self.header = PageHeader(
            title="Autonomous Navigation",
            subtitle="2D Occupancy Grid mapping, waypoint routing, Nav2 tracking, and safe-stop action",
            badge_title="Nav2 State",
            initial_state=StatusIndicator.STATE_READY,
            target_page="Navigation",
            parent=self
        )
        self.ind_nav_state = self.header.badge
        layout.addWidget(self.header)

        # 2. Main Body Splitter/Layout (Map on Left, Controls on Right)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        # === LEFT: Interactive 2D Map (65% width) ===
        map_container = QFrame(self)
        map_container.setProperty("class", "cardPanel")
        mc_layout = QVBoxLayout(map_container)
        mc_layout.setContentsMargins(12, 12, 12, 12)
        mc_layout.setSpacing(8)

        map_hdr = SectionHeader("Occupancy Grid Map & Global Path", parent=self)
        mc_layout.addWidget(map_hdr)

        self.map_view = MapViewWidget(self)
        self.map_view.set_destinations(self.destinations)
        mc_layout.addWidget(self.map_view, stretch=1)

        body_layout.addWidget(map_container, stretch=3)

        # === RIGHT: Command & Telemetry Column (35% width) ===
        control_panel = QFrame(self)
        control_panel.setProperty("class", "cardPanel")
        cp_layout = QVBoxLayout(control_panel)
        cp_layout.setContentsMargins(14, 14, 14, 14)
        cp_layout.setSpacing(14)

        # Sub-header
        cp_hdr = SectionHeader("Waypoint Dispatch & Control", parent=self)
        cp_layout.addWidget(cp_hdr)

        # Status Pill Bar
        st_row = QHBoxLayout()
        self.ind_loc_ready = StatusIndicator("Localization", StatusIndicator.STATE_NOT_CONNECTED, target_page="Localization")
        st_row.addWidget(self.ind_loc_ready)
        st_row.addStretch()
        cp_layout.addLayout(st_row)

        # Destination Selection Card
        dest_box = QFrame(self)
        dest_box.setProperty("class", "wellPanel")
        db_layout = QVBoxLayout(dest_box)
        db_layout.setSpacing(8)

        lbl_select = QLabel("Target Apartment Destination:")
        lbl_select.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLOR_TEXT_SECONDARY}; text-transform: uppercase;")
        db_layout.addWidget(lbl_select)

        self.dest_combo = QComboBox(self)
        for d_key, d_info in self.destinations.items():
            name = d_info.get("name", d_key)
            coords = f"({d_info.get('x', 0.0):.1f}, {d_info.get('y', 0.0):.1f})"
            self.dest_combo.addItem(f"{name} {coords}", userData=d_key)
        self.dest_combo.currentIndexChanged.connect(self._on_dest_selected)
        db_layout.addWidget(self.dest_combo)

        # Display Selected Coordinates
        self.lbl_selected_coords = QLabel("Target: X=0.00 m, Y=0.00 m, Yaw=0.00 rad", self)
        self.lbl_selected_coords.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_PRIMARY};")
        db_layout.addWidget(self.lbl_selected_coords)

        cp_layout.addWidget(dest_box)

        # Command Action Buttons
        btn_grid = QGridLayout()
        btn_grid.setSpacing(8)

        self.btn_dispatch = QPushButton("▶ Dispatch Goal", self)
        self.btn_dispatch.setProperty("class", "primaryButton")
        self.btn_dispatch.clicked.connect(self._dispatch_navigation_goal)
        btn_grid.addWidget(self.btn_dispatch, 0, 0)

        self.btn_cancel = QPushButton("⏹ Cancel Goal", self)
        self.btn_cancel.setProperty("class", "secondaryButton")
        self.btn_cancel.clicked.connect(self._cancel_navigation_goal)
        btn_grid.addWidget(self.btn_cancel, 0, 1)

        self.btn_estop = QPushButton("🚨 EMERGENCY STOP", self)
        self.btn_estop.setProperty("class", "dangerButton")
        self.btn_estop.clicked.connect(self._trigger_emergency_stop)
        btn_grid.addWidget(self.btn_estop, 1, 0, 1, 2)

        cp_layout.addLayout(btn_grid)

        # Active Mission Telemetry
        telem_box = QFrame(self)
        telem_box.setProperty("class", "wellPanel")
        tb_layout = QVBoxLayout(telem_box)
        tb_layout.setSpacing(6)

        tb_hdr = SectionHeader("Active Mission Progress", parent=self)
        tb_layout.addWidget(tb_hdr)

        self.lbl_active_dest = QLabel("Destination: None")
        self.lbl_dist_remaining = QLabel("Distance Remaining: 0.00 m")
        self.lbl_elapsed_time = QLabel("Elapsed Time: 0.0 s")
        self.lbl_arrival_status = QLabel("Arrival Verification: IDLE")

        for lbl in (self.lbl_active_dest, self.lbl_dist_remaining, self.lbl_elapsed_time, self.lbl_arrival_status):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_PRIMARY};")
            tb_layout.addWidget(lbl)

        cp_layout.addWidget(telem_box)

        # Coordinator Verification & Feedback Log
        fb_hdr = SectionHeader("Coordinator Feedback Stream", parent=self)
        cp_layout.addWidget(fb_hdr)

        self.txt_feedback = QTextEdit(self)
        self.txt_feedback.setReadOnly(True)
        self.txt_feedback.setMaximumHeight(140)
        self.txt_feedback.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_PANEL_SECONDARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-family: {FONT_FAMILY_MONO};
                font-size: 11px;
                padding: 6px;
            }}
        """)
        cp_layout.addWidget(self.txt_feedback)

        body_layout.addWidget(control_panel, stretch=2)
        layout.addLayout(body_layout)

        # Elapsed time timer
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)

        # Connect bus signals
        bus.map_ready.connect(self._on_map_ready)
        bus.amcl_pose_ready.connect(self._on_amcl_pose)
        bus.global_path_ready.connect(self.map_view.set_global_path)
        bus.coordinator_feedback_ready.connect(self._on_coordinator_feedback)

        self._on_dest_selected(0)

    def _on_dest_selected(self, index: int):
        d_key = self.dest_combo.currentData()
        if d_key in self.destinations:
            d = self.destinations[d_key]
            self.lbl_selected_coords.setText(
                f"Target: X={d.get('x', 0.0):+.2f} m, Y={d.get('y', 0.0):+.2f} m, Yaw={d.get('yaw', 0.0):+.2f} rad"
            )

    def _on_map_ready(self, map_dict: dict):
        self.map_view.set_map(
            map_dict["width"], map_dict["height"],
            map_dict["resolution"], map_dict["origin_x"], map_dict["origin_y"],
            map_dict["data"]
        )

    def _on_amcl_pose(self, x, y, yaw, vx, vy, vyaw):
        self.has_localization = True
        self.ind_loc_ready.set_state(StatusIndicator.STATE_READY)
        self.map_view.set_robot_pose(x, y, yaw)

    def _on_coordinator_feedback(self, state: str, speech: str, details: dict, ts: float):
        self.coordinator_state = state
        self.ind_nav_state.set_state(StatusIndicator.STATE_READY)

        self.txt_feedback.append(f"[{state}] {speech}")

        dist = details.get("distance", None)
        if dist is not None:
            self.lbl_dist_remaining.setText(f"Distance Remaining: {dist:.2f} m")

        dest = details.get("destination", None)
        if dest:
            self.lbl_active_dest.setText(f"Destination: {dest}")

        if state == "NAVIGATING":
            if not self.elapsed_timer.isActive():
                self.navigation_start_time = time.time()
                self.elapsed_timer.start(500)
            self.lbl_arrival_status.setText("Arrival Verification: IN TRANSIT")
            self.lbl_arrival_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_WARNING};")
        elif state == "SUCCEEDED":
            self.elapsed_timer.stop()
            self.lbl_arrival_status.setText("Arrival Verification: ARRIVED & SAFE HALT ✅")
            self.lbl_arrival_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_SUCCESS};")
            self.active_destination_key = None
            self.map_view.set_active_goal(None)
        elif state in ("FAILED", "CANCELED", "IDLE"):
            self.elapsed_timer.stop()
            if state == "FAILED":
                self.lbl_arrival_status.setText("Arrival Verification: ACTION FAILED ❌")
                self.lbl_arrival_status.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_ERROR};")
            self.active_destination_key = None
            self.map_view.set_active_goal(None)

    def _update_elapsed_time(self):
        if self.navigation_start_time:
            dt = time.time() - self.navigation_start_time
            self.lbl_elapsed_time.setText(f"Elapsed Time: {dt:.1f} s")

    def _dispatch_navigation_goal(self):
        """Dispatch navigation goal strictly through authoritative coordinator."""
        if not self.has_localization:
            QMessageBox.warning(self, "Navigation Safety Gate", "Cannot dispatch goal: AMCL localization has not established a valid map pose!")
            return

        d_key = self.dest_combo.currentData()
        if not d_key or d_key not in self.destinations:
            return

        dest = self.destinations[d_key]
        self.active_destination_key = d_key
        self.map_view.set_active_goal(d_key)

        bus.navigation_goal_dispatched.emit(
            dest.get("name", d_key), dest.get("x", 0.0), dest.get("y", 0.0), dest.get("yaw", 0.0)
        )
        self.txt_feedback.append(f"[DISPATCH] Sent goal for '{dest.get('name', d_key)}' to coordinator.")

    def _cancel_navigation_goal(self):
        """Cancel navigation safely through coordinator."""
        self.txt_feedback.append("[CANCEL] Sending cancellation request to coordinator...")
        bus.navigation_cancel_requested.emit()
        bus.user_input_received.emit("cancel navigation", "TEXT")

    def _trigger_emergency_stop(self):
        """Trigger immediate emergency stop via authoritative terrain gate."""
        self.txt_feedback.append("🚨 [EMERGENCY STOP] Triggering emergency stop!")
        bus.emergency_stop_state.emit(True, "GUI_ESTOP_BUTTON")
