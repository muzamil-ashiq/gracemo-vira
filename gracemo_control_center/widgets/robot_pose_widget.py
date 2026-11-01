"""
Robot Pose & Odometry Telemetry Widget for GRaCEmo ViRa.
Displays real-time X/Y/Yaw coordinates, linear/angular velocity bars,
covariance matrix bounds, and directional heading compass.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QProgressBar
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF

import math
from ..resources.styles.tokens import (
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_BORDER,
    COLOR_ACCENT_ORANGE,
    COLOR_ACCENT_WHITE,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
)


class CompassWidget(QWidget):
    """Circular compass displaying robot yaw orientation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.yaw_rad = 0.0
        self.setFixedSize(70, 70)

    def set_yaw(self, yaw_rad: float):
        self.yaw_rad = yaw_rad
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = 28.0

        # Dial Ring
        painter.setPen(QPen(QColor(COLOR_BORDER), 2))
        painter.setBrush(QBrush(QColor(COLOR_PANEL_SECONDARY)))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # Cardinal Tick Labels (N, S, E, W)
        painter.setPen(QColor(COLOR_TEXT_MUTED))
        painter.setFont(QFont(FONT_FAMILY_PRIMARY, 7, QFont.Bold))
        painter.drawText(int(cx - 3), int(cy - r + 9), "N")
        painter.drawText(int(cx - 3), int(cy + r - 3), "S")
        painter.drawText(int(cx + r - 9), int(cy + 3), "E")
        painter.drawText(int(cx - r + 3), int(cy + 3), "W")

        # Heading Needle (Rotated by yaw)
        # 0 rad in ROS is pointing East (+X), but in compass standard 0 is North
        # Here robot forward (+X) is North on screen when yaw = 0
        angle = -self.yaw_rad # In Qt clockwise is positive
        nx = cx + 20.0 * math.cos(angle - math.pi / 2.0)
        ny = cy + 20.0 * math.sin(angle - math.pi / 2.0)

        # North pointer (Orange)
        painter.setPen(QPen(QColor(COLOR_ACCENT_ORANGE), 2.5))
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

        # Pivot Dot
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.setBrush(QBrush(QColor(COLOR_ACCENT_ORANGE)))
        painter.drawEllipse(QPointF(cx, cy), 3, 3)


class RobotPoseWidget(QFrame):
    """Comprehensive pose, odometry velocity, and covariance monitoring card."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_MAIN};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with Compass
        header_layout = QHBoxLayout()
        title_col = QVBoxLayout()
        title_lbl = QLabel("ROBOT POSE & ODOMETRY", self)
        title_lbl.setStyleSheet(f"color: {COLOR_ACCENT_ORANGE}; font-weight: 700; font-size: 12px; letter-spacing: 0.5px;")
        subtitle_lbl = QLabel("Frames: map → odom → base_footprint", self)
        subtitle_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(subtitle_lbl)
        header_layout.addLayout(title_col)

        header_layout.addStretch()
        self.compass = CompassWidget(self)
        header_layout.addWidget(self.compass)
        layout.addLayout(header_layout)

        # Coordinate Grid Readouts
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        # X, Y, Yaw
        self.lbl_x = QLabel("X: +0.000 m", self)
        self.lbl_y = QLabel("Y: +0.000 m", self)
        self.lbl_yaw = QLabel("Yaw: +0.0° (0.00 rad)", self)

        for lbl in (self.lbl_x, self.lbl_y, self.lbl_yaw):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 13px; font-weight: 600; color: {COLOR_TEXT_PRIMARY};")

        grid.addWidget(self.lbl_x, 0, 0)
        grid.addWidget(self.lbl_y, 0, 1)
        grid.addWidget(self.lbl_yaw, 1, 0, 1, 2)

        # Velocities
        self.lbl_vx = QLabel("Lin Vel (v): 0.000 m/s", self)
        self.lbl_wz = QLabel("Ang Vel (ω): 0.000 rad/s", self)
        for lbl in (self.lbl_vx, self.lbl_wz):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_SECONDARY};")

        grid.addWidget(self.lbl_vx, 2, 0)
        grid.addWidget(self.lbl_wz, 2, 1)

        # Covariance Bounds
        self.lbl_cov = QLabel("Variance: σx²=0.000, σy²=0.000, σθ²=0.000", self)
        self.lbl_cov.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; color: {COLOR_TEXT_MUTED};")
        grid.addWidget(self.lbl_cov, 3, 0, 1, 2)

        layout.addLayout(grid)

    def update_amcl_pose(self, x: float, y: float, yaw: float, var_x: float, var_y: float, var_yaw: float):
        self.lbl_x.setText(f"X: {x:+.3f} m")
        self.lbl_y.setText(f"Y: {y:+.3f} m")
        deg = math.degrees(yaw)
        self.lbl_yaw.setText(f"Yaw: {deg:+.1f}° ({yaw:+.2f} rad)")
        self.lbl_cov.setText(f"Variance: σx²={var_x:.3f}, σy²={var_y:.3f}, σθ²={var_yaw:.3f}")
        self.compass.set_yaw(yaw)

    def update_odometry(self, vx: float, vy: float, wz: float):
        self.lbl_vx.setText(f"Lin Vel (v): {vx:+.3f} m/s")
        self.lbl_wz.setText(f"Ang Vel (ω): {wz:+.3f} rad/s")
