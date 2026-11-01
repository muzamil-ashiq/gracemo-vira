"""
Module 1: Overview Dashboard for GRaCEmo ViRa UARCC.
Primary landing page delivering immediate operational condition within 5 seconds:
Robot connection, ROS 2, Gazebo, Navigation summary, Subsystem matrix,
live pose, and live camera preview.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

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
from ...widgets.camera_view import CameraViewWidget
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay, AlertBanner
from ...core.event_bus import bus


class OverviewView(QWidget):
    """Module 1: High-level overview and subsystem health hub."""

    request_page = Signal(str)

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

        # 1. Standard Page Header
        self.header = PageHeader(
            title="System Overview",
            subtitle="Autonomous service robot operational condition, subsystem matrix, and mission status",
            badge_title="System Health",
            initial_state=StatusIndicator.STATE_READY,
            target_page="Diagnostics",
            parent=self
        )
        layout.addWidget(self.header)

        # 2. Key Metrics Row
        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)

        self.metric_robot_state = MetricDisplay("Robot State", "IDLE", status_color=COLOR_SUCCESS, parent=self)
        self.metric_dest = MetricDisplay("Target Waypoint", "None", status_color=COLOR_ACCENT_PRIMARY, parent=self)
        self.metric_loc = MetricDisplay("Localization", "NOT LOCKED", status_color=COLOR_WARNING, parent=self)
        self.metric_safety = MetricDisplay("Safety Gate", "CLEARED", status_color=COLOR_SUCCESS, parent=self)

        metric_row.addWidget(self.metric_robot_state)
        metric_row.addWidget(self.metric_dest)
        metric_row.addWidget(self.metric_loc)
        metric_row.addWidget(self.metric_safety)
        layout.addLayout(metric_row)

        # 3. Main Two-Column Body
        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        # === LEFT COLUMN: Subsystem Health & Live Pose ===
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # Subsystems Health Matrix Card
        subsystems_frame = QFrame(self)
        subsystems_frame.setProperty("class", "cardPanel")
        sub_layout = QVBoxLayout(subsystems_frame)
        sub_layout.setSpacing(12)

        sub_header = SectionHeader("Subsystem Readiness Matrix (Click to Inspect)", parent=self)
        sub_layout.addWidget(sub_header)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Indicators
        self.ind_ros = StatusIndicator("ROS 2 Graph", StatusIndicator.STATE_NOT_CONNECTED, "Diagnostics")
        self.ind_gazebo = StatusIndicator("Gazebo Clock", StatusIndicator.STATE_NOT_CONNECTED, "Simulation")
        self.ind_autonomous = StatusIndicator("Autonomous FSM", StatusIndicator.STATE_NOT_CONNECTED, "Navigation")
        self.ind_localization = StatusIndicator("AMCL Localization", StatusIndicator.STATE_NOT_CONNECTED, "Localization")
        self.ind_lidar = StatusIndicator("Planar LiDAR", StatusIndicator.STATE_NOT_CONNECTED, "Sensors")
        self.ind_rgb = StatusIndicator("RGB Camera", StatusIndicator.STATE_NOT_CONNECTED, "Sensors")
        self.ind_depth = StatusIndicator("Depth Camera", StatusIndicator.STATE_NOT_CONNECTED, "Sensors")
        self.ind_imu = StatusIndicator("IMU Attitude", StatusIndicator.STATE_NOT_CONNECTED, "Sensors")
        self.ind_voice = StatusIndicator("Voice & Whisper", StatusIndicator.STATE_NOT_CONNECTED, "Voice & Interaction")
        self.ind_mnse = StatusIndicator("MNSE / K Kernel", StatusIndicator.STATE_NOT_CONNECTED, "Cognitive System")
        self.ind_collision = StatusIndicator("Collision Monitor", StatusIndicator.STATE_NOT_CONNECTED, "Safety")
        self.ind_terrain = StatusIndicator("Terrain Gate", StatusIndicator.STATE_NOT_CONNECTED, "Safety")

        indicators = [
            (self.ind_ros, 0, 0), (self.ind_gazebo, 0, 1), (self.ind_autonomous, 0, 2), (self.ind_localization, 0, 3),
            (self.ind_lidar, 1, 0), (self.ind_rgb, 1, 1), (self.ind_depth, 1, 2), (self.ind_imu, 1, 3),
            (self.ind_voice, 2, 0), (self.ind_mnse, 2, 1), (self.ind_collision, 2, 2), (self.ind_terrain, 2, 3),
        ]

        for ind, r, c in indicators:
            ind.clicked.connect(self._on_indicator_clicked)
            grid.addWidget(ind, r, c)

        sub_layout.addLayout(grid)
        left_col.addWidget(subsystems_frame)

        # Robot Pose & Odometry Widget
        self.pose_widget = RobotPoseWidget(self)
        left_col.addWidget(self.pose_widget)

        body_layout.addLayout(left_col, stretch=3)

        # === RIGHT COLUMN: Live Camera Preview & Mission Summary ===
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # Live RGB Camera Preview Card
        cam_card = QFrame(self)
        cam_card.setProperty("class", "cardPanel")
        cc_layout = QVBoxLayout(cam_card)
        cc_layout.setSpacing(10)

        cam_hdr = SectionHeader("Live Vision Feed Preview", parent=self)
        cc_layout.addWidget(cam_hdr)

        self.camera_preview = CameraViewWidget("RGB FORWARD CAMERA", self)
        self.camera_preview.setMaximumHeight(230)
        cc_layout.addWidget(self.camera_preview)
        right_col.addWidget(cam_card)

        # Navigation & Mission Summary Card
        nav_card = QFrame(self)
        nav_card.setProperty("class", "cardPanel")
        nc_layout = QVBoxLayout(nav_card)
        nc_layout.setSpacing(12)

        nc_hdr = SectionHeader("Navigation & Autonomous Mission State", parent=self)
        nc_layout.addWidget(nc_hdr)

        nc_grid = QGridLayout()
        nc_grid.setSpacing(8)

        self.lbl_coord_state = QLabel("Coordinator State: IDLE")
        self.lbl_active_dest = QLabel("Active Destination: None")
        self.lbl_nav_progress = QLabel("Remaining Distance: 0.0 m")
        self.lbl_estop = QLabel("Emergency Stop: INACTIVE")

        for lbl in (self.lbl_coord_state, self.lbl_active_dest, self.lbl_nav_progress, self.lbl_estop):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")

        nc_grid.addWidget(self.lbl_coord_state, 0, 0)
        nc_grid.addWidget(self.lbl_active_dest, 0, 1)
        nc_grid.addWidget(self.lbl_nav_progress, 1, 0)
        nc_grid.addWidget(self.lbl_estop, 1, 1)
        nc_layout.addLayout(nc_grid)

        # Quick Navigation Actions
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        btn_go_nav = QPushButton("Open Navigation Center →", self)
        btn_go_nav.setProperty("class", "primaryButton")
        btn_go_nav.clicked.connect(lambda: self.request_page.emit("Navigation"))
        btn_bar.addWidget(btn_go_nav)

        btn_go_sensors = QPushButton("Open Sensors →", self)
        btn_go_sensors.setProperty("class", "secondaryButton")
        btn_go_sensors.clicked.connect(lambda: self.request_page.emit("Sensors"))
        btn_bar.addWidget(btn_go_sensors)

        nc_layout.addLayout(btn_bar)
        right_col.addWidget(nav_card)

        # Hardware Safety Lock Alert Banner
        safety_banner = AlertBanner(
            message="SIMULATION ONLY — PHYSICAL ACTUATION HARDWARE SAFETY LOCKED",
            level="brand",
            parent=self
        )
        right_col.addWidget(safety_banner)

        right_col.addStretch()
        body_layout.addLayout(right_col, stretch=2)

        layout.addLayout(body_layout)
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        # Connect to Event Bus signals
        bus.ros_connected.connect(self._on_ros_connected)
        bus.gazebo_connected.connect(self._on_gazebo_connected)
        bus.amcl_pose_ready.connect(self._on_amcl_pose)
        bus.odom_data_ready.connect(self._on_odom_data)
        bus.rgb_frame_ready.connect(self.camera_preview.update_frame)
        bus.coordinator_feedback_ready.connect(self._on_coordinator_feedback)
        bus.emergency_stop_state.connect(self._on_estop_state)
        bus.subsystem_health_updated.connect(self._on_subsystems_health)

    def _on_indicator_clicked(self, page_name: str):
        if page_name:
            self.request_page.emit(page_name)

    def _on_ros_connected(self, connected: bool):
        st = StatusIndicator.STATE_READY if connected else StatusIndicator.STATE_NOT_CONNECTED
        self.ind_ros.set_state(st)

    def _on_gazebo_connected(self, connected: bool):
        st = StatusIndicator.STATE_READY if connected else StatusIndicator.STATE_NOT_CONNECTED
        self.ind_gazebo.set_state(st)

    def _on_amcl_pose(self, x, y, yaw, vx, vy, vyaw):
        self.ind_localization.set_state(StatusIndicator.STATE_READY)
        self.metric_loc.set_value("LOCKED", status_color=COLOR_SUCCESS)
        self.pose_widget.update_amcl_pose(x, y, yaw, vx, vy, vyaw)

    def _on_odom_data(self, data: dict):
        self.pose_widget.update_odometry(
            data.get("vx", 0.0), data.get("vy", 0.0), data.get("wz", 0.0)
        )

    def _on_coordinator_feedback(self, state: str, speech: str, details: dict, ts: float):
        self.ind_autonomous.set_state(StatusIndicator.STATE_READY)
        self.metric_robot_state.set_value(state, status_color=COLOR_SUCCESS if state in ("IDLE", "SUCCEEDED") else COLOR_BRAND_ORANGE)
        self.lbl_coord_state.setText(f"Coordinator State: {state}")
        dest = details.get("destination", "None")
        if dest != "None":
            self.lbl_active_dest.setText(f"Active Destination: {dest}")
            self.metric_dest.set_value(dest)
        dist = details.get("distance", None)
        if dist is not None:
            self.lbl_nav_progress.setText(f"Remaining Distance: {dist:.1f} m")

    def _on_estop_state(self, is_active: bool, source: str):
        if is_active:
            self.lbl_estop.setText(f"Emergency Stop: ACTIVE ({source})")
            self.lbl_estop.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; font-weight: 700; color: {COLOR_ERROR};")
            self.metric_safety.set_value("E-STOP ASSERTED", status_color=COLOR_ERROR)
        else:
            self.lbl_estop.setText("Emergency Stop: INACTIVE")
            self.lbl_estop.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_SUCCESS};")
            self.metric_safety.set_value("CLEARED", status_color=COLOR_SUCCESS)

    def _on_subsystems_health(self, health: dict):
        """Update individual indicators from health monitor."""
        if "lidar" in health:
            self.ind_lidar.set_state(health["lidar"])
        if "camera_rgb" in health:
            self.ind_rgb.set_state(health["camera_rgb"])
        if "camera_depth" in health:
            self.ind_depth.set_state(health["camera_depth"])
        if "imu" in health:
            self.ind_imu.set_state(health["imu"])
        if "voice" in health:
            self.ind_voice.set_state(health["voice"])
        if "mnse" in health:
            self.ind_mnse.set_state(health["mnse"])
        if "collision" in health:
            self.ind_collision.set_state(health["collision"])
        if "terrain" in health:
            self.ind_terrain.set_state(health["terrain"])
