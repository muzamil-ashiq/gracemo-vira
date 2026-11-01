"""
Module 4: Live Sensor Center for GRaCEmo ViRa UARCC.
Full-screen engineering monitoring for RGB Camera, Depth Camera,
360-Degree LiDAR, IMU Attitude, and Differential-Drive Odometry.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import math
from typing import Dict, Any

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
from ...widgets.camera_view import CameraViewWidget
from ...widgets.depth_view import DepthViewWidget
from ...widgets.lidar_view import LidarViewWidget
from ...widgets.robot_pose_widget import RobotPoseWidget
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay
from ...core.event_bus import bus


class SensorsView(QWidget):
    """Module 4: Comprehensive multi-modal sensor telemetry center."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Page Header
        self.header = PageHeader(
            title="Sensor Telemetry",
            subtitle="Multi-modal perception feeds: Forward RGB, Depth map, 360° LiDAR, IMU attitude, and Odometry",
            badge_title="Perception Stream",
            initial_state=StatusIndicator.STATE_READY,
            target_page="Sensors",
            parent=self
        )
        layout.addWidget(self.header)

        # 2. Tab Widget for Sensor Views
        self.tabs = QTabWidget(self)

        # === TAB 1: Vision Center (RGB Camera + Depth Camera Side-by-Side) ===
        tab_vision = QWidget()
        v_layout = QHBoxLayout(tab_vision)
        v_layout.setContentsMargins(12, 12, 12, 12)
        v_layout.setSpacing(14)

        # RGB Camera Container
        rgb_card = QFrame(tab_vision)
        rgb_card.setProperty("class", "cardPanel")
        rgb_layout = QVBoxLayout(rgb_card)
        rgb_layout.setContentsMargins(8, 8, 8, 8)
        rgb_layout.setSpacing(8)
        rgb_hdr = SectionHeader("RGB Forward Camera (/camera/image_raw)", parent=self)
        rgb_layout.addWidget(rgb_hdr)
        self.rgb_view = CameraViewWidget("RGB FORWARD CAMERA", self)
        rgb_layout.addWidget(self.rgb_view, stretch=1)
        v_layout.addWidget(rgb_card, stretch=1)

        # Depth Sensor Container
        depth_card = QFrame(tab_vision)
        depth_card.setProperty("class", "cardPanel")
        depth_layout = QVBoxLayout(depth_card)
        depth_layout.setContentsMargins(8, 8, 8, 8)
        depth_layout.setSpacing(8)
        depth_hdr = SectionHeader("Depth Sensor (/camera/depth_image)", parent=self)
        depth_layout.addWidget(depth_hdr)
        self.depth_view = DepthViewWidget("DEPTH SENSOR", self)
        depth_layout.addWidget(self.depth_view, stretch=1)
        v_layout.addWidget(depth_card, stretch=1)

        self.tabs.addTab(tab_vision, "Vision & Depth")

        # === TAB 2: Planar LiDAR Center ===
        tab_lidar = QWidget()
        l_layout = QHBoxLayout(tab_lidar)
        l_layout.setContentsMargins(12, 12, 12, 12)
        l_layout.setSpacing(14)

        lidar_card = QFrame(tab_lidar)
        lidar_card.setProperty("class", "cardPanel")
        lc_layout = QVBoxLayout(lidar_card)
        lc_layout.setContentsMargins(8, 8, 8, 8)
        lc_layout.setSpacing(8)
        lidar_hdr = SectionHeader("360° Planar LiDAR Polar Sweep (/scan on lidar_link)", parent=self)
        lc_layout.addWidget(lidar_hdr)
        self.lidar_view = LidarViewWidget("360° PLANAR LIDAR", self)
        lc_layout.addWidget(self.lidar_view, stretch=1)
        l_layout.addWidget(lidar_card, stretch=3)

        # LiDAR Info Sidebar
        lidar_info_card = QFrame(tab_lidar)
        lidar_info_card.setProperty("class", "cardPanel")
        li_layout = QVBoxLayout(lidar_info_card)
        li_layout.setSpacing(10)

        li_hdr = SectionHeader("Sensor Specifications & Envelopes", parent=self)
        li_layout.addWidget(li_hdr)

        self.lbl_lidar_specs = QLabel(
            "Coordinate Frame: lidar_link\n"
            "Sensor Height: Z = +1.175 m\n"
            "Field of View: 360° (2π rad)\n"
            "Angular Samples: 720 rays (~0.5° res)\n"
            "Scan Rate: 10.0 Hz (100 ms)\n"
            "Safety Envelope (E-Stop): 0.35 m\n"
            "Proximity Warning Zone: 0.80 m\n"
            "Nav2 Obstacle Inflation: 0.55 m\n"
            "Reliability QoS: Best Effort"
        )
        self.lbl_lidar_specs.setStyleSheet(f"""
            font-family: {FONT_FAMILY_MONO};
            font-size: 11px;
            color: {COLOR_TEXT_PRIMARY};
            line-height: 1.6;
        """)
        li_layout.addWidget(self.lbl_lidar_specs)
        li_layout.addStretch()
        l_layout.addWidget(lidar_info_card, stretch=1)

        self.tabs.addTab(tab_lidar, "360° Planar LiDAR")

        # === TAB 3: Inertial & Odometry Center ===
        tab_imu_odom = QWidget()
        io_layout = QHBoxLayout(tab_imu_odom)
        io_layout.setContentsMargins(12, 12, 12, 12)
        io_layout.setSpacing(14)

        # Left: Odometry Pose Card
        self.pose_card = RobotPoseWidget(self)
        io_layout.addWidget(self.pose_card, stretch=1)

        # Right: IMU Attitude Card
        self.imu_card = QFrame(tab_imu_odom)
        self.imu_card.setProperty("class", "cardPanel")
        imu_layout = QVBoxLayout(self.imu_card)
        imu_layout.setSpacing(12)

        imu_hdr = SectionHeader("IMU Attitude & Accelerometer (/imu/data)", parent=self)
        imu_layout.addWidget(imu_hdr)

        self.lbl_rpy = QLabel("Attitude (RPY): Roll=0.0°, Pitch=0.0°, Yaw=0.0°")
        self.lbl_accel = QLabel("Linear Accel (m/s²): ax=0.00, ay=0.00, az=9.81")
        self.lbl_gyro = QLabel("Angular Rate (rad/s): gx=0.00, gy=0.00, gz=0.00")
        self.lbl_imu_health = QLabel("Frame: imu_link  |  Rate: ~100 Hz  |  Status: ACTIVE")

        for lbl in (self.lbl_rpy, self.lbl_accel, self.lbl_gyro, self.lbl_imu_health):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")
            imu_layout.addWidget(lbl)

        imu_layout.addStretch()
        io_layout.addWidget(self.imu_card, stretch=1)

        self.tabs.addTab(tab_imu_odom, "IMU & Odometry")
        layout.addWidget(self.tabs)

        # Connect signals
        bus.rgb_frame_ready.connect(self.rgb_view.update_frame)
        bus.depth_frame_ready.connect(self.depth_view.update_depth)
        bus.lidar_scan_ready.connect(self._on_lidar_scan)
        bus.imu_data_ready.connect(self._on_imu_data)
        bus.odom_data_ready.connect(self._on_odom_data)
        bus.amcl_pose_ready.connect(self.pose_card.update_amcl_pose)

    def _on_lidar_scan(self, scan_data: dict):
        points = scan_data.get("points", [])
        min_r = scan_data.get("min_range", 0.0)
        max_r = scan_data.get("max_range", 0.0)
        freq = scan_data.get("freq", 10.0)
        ts = scan_data.get("timestamp", 0.0)
        self.lidar_view.update_scan(points, min_r, max_r, freq, ts)

    def _on_imu_data(self, imu: dict):
        r_deg = math.degrees(imu.get("roll", 0.0))
        p_deg = math.degrees(imu.get("pitch", 0.0))
        y_deg = math.degrees(imu.get("yaw", 0.0))
        self.lbl_rpy.setText(f"Attitude (RPY): Roll={r_deg:+.1f}°, Pitch={p_deg:+.1f}°, Yaw={y_deg:+.1f}°")

        ax = imu.get("ax", 0.0)
        ay = imu.get("ay", 0.0)
        az = imu.get("az", 9.81)
        self.lbl_accel.setText(f"Linear Accel (m/s²): ax={ax:+.2f}, ay={ay:+.2f}, az={az:+.2f}")

        gx = imu.get("gx", 0.0)
        gy = imu.get("gy", 0.0)
        gz = imu.get("gz", 0.0)
        self.lbl_gyro.setText(f"Angular Rate (rad/s): gx={gx:+.3f}, gy={gy:+.3f}, gz={gz:+.3f}")

    def _on_odom_data(self, odom: dict):
        self.pose_card.update_odometry(
            odom.get("vx", 0.0), odom.get("vy", 0.0), odom.get("wz", 0.0)
        )
