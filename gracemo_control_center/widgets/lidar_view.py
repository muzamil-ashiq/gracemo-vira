"""
360-Degree LiDAR Polar/Cartesian Radar Viewer Widget for GRaCEmo ViRa.
Renders range rings, robot center, forward heading indicator,
dynamic obstacle points, and safety/warning envelope overlays.
"""

from PySide6.QtWidgets import QWidget, QFrame
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF

import math
import time
from typing import List, Tuple, Optional

from ..resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_OFFLINE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
)


class LidarViewWidget(QFrame):
    """360-degree real-time LiDAR point cloud radar display."""

    def __init__(self, title: str = "360° PLANAR LIDAR (lidar_link)", parent=None):
        super().__init__(parent)
        self.title = title
        self.points_cartesian: List[Tuple[float, float]] = []  # (x, y) in meters relative to robot
        self.min_range = 0.0
        self.max_range = 0.0
        self.scan_frequency = 10.0
        self.last_scan_time = 0.0
        self.is_connected = False
        self.max_view_range_meters = 8.0  # Display zoom radius
        self.safety_zone_meters = 0.35    # Emergency stop perimeter
        self.warning_zone_meters = 0.80   # Slowdown warning perimeter
        self.stale_threshold_sec = 2.0

        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumSize(320, 320)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #121A22;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self._check_freshness)
        self.watchdog_timer.start(500)

    def update_scan(self, cartesian_points: List[Tuple[float, float]], min_r: float, max_r: float, freq: float, timestamp: float):
        self.points_cartesian = cartesian_points
        self.min_range = min_r
        self.max_range = max_r
        self.scan_frequency = freq
        self.last_scan_time = timestamp
        self.is_connected = True
        self.update()

    def set_max_range(self, meters: float):
        """Set visual zoom range in meters."""
        self.max_view_range_meters = max(2.0, meters)
        self.update()

    def _check_freshness(self):
        if self.is_connected and (time.time() - self.last_scan_time > self.stale_threshold_sec):
            self.is_connected = False
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        radius_px = min(w, h) / 2.0 - 32.0
        if radius_px < 20:
            return

        scale = radius_px / self.max_view_range_meters

        # 1. Background Grid & Concentric Range Rings (1m, 2m, 4m, 6m, 8m)
        ring_steps = [1.0, 2.0, 4.0, 6.0, 8.0]
        painter.setFont(QFont(FONT_FAMILY_MONO, 8))

        for r_m in ring_steps:
            if r_m <= self.max_view_range_meters:
                r_px = r_m * scale
                painter.setPen(QPen(QColor(50, 68, 86, 160), 1, Qt.DotLine))
                painter.drawEllipse(QPointF(cx, cy), r_px, r_px)
                # Meter label
                painter.setPen(QColor(COLOR_TEXT_MUTED))
                painter.drawText(int(cx + 4), int(cy - r_px - 2), f"{r_m:.0f}m")

        # Crosshairs
        painter.setPen(QPen(QColor(50, 68, 86, 120), 1, Qt.DashLine))
        painter.drawLine(int(cx), int(cy - radius_px), int(cx), int(cy + radius_px))
        painter.drawLine(int(cx - radius_px), int(cy), int(cx + radius_px), int(cy))

        # 2. Safety and Warning Zone Overlays
        # Warning Zone (0.80m)
        warn_px = self.warning_zone_meters * scale
        painter.setPen(QPen(QColor(217, 154, 43, 160), 1, Qt.SolidLine))
        painter.setBrush(QBrush(QColor(217, 154, 43, 20)))
        painter.drawEllipse(QPointF(cx, cy), warn_px, warn_px)

        # Safety Zone (0.35m)
        safe_px = self.safety_zone_meters * scale
        painter.setPen(QPen(QColor(199, 71, 71, 200), 1, Qt.SolidLine))
        painter.setBrush(QBrush(QColor(199, 71, 71, 35)))
        painter.drawEllipse(QPointF(cx, cy), safe_px, safe_px)
        painter.setBrush(Qt.NoBrush)

        # 3. Obstacle Points Rendering
        if self.is_connected and self.points_cartesian:
            pen_obstacle = QPen(QColor(COLOR_ACCENT_PRIMARY), 2)
            pen_breach = QPen(QColor(COLOR_ERROR), 3)

            for x_m, y_m in self.points_cartesian:
                px = cx - (y_m * scale)
                py = cy - (x_m * scale)

                dist = math.hypot(x_m, y_m)
                if dist <= self.safety_zone_meters:
                    painter.setPen(pen_breach)
                else:
                    painter.setPen(pen_obstacle)

                painter.drawPoint(QPointF(px, py))
        elif not self.is_connected:
            painter.setPen(QColor(COLOR_TEXT_MUTED))
            font = QFont(FONT_FAMILY_MONO, 11, QFont.Bold)
            painter.setFont(font)
            msg = "STALE DATA" if self.points_cartesian else "NOT CONNECTED"
            painter.drawText(self.rect(), Qt.AlignCenter, f"\n\n\n[{msg}]")

        # 4. Robot Center & Forward Heading Arrow
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(QPen(QColor(COLOR_BRAND_ORANGE), 1.5))
        painter.drawEllipse(QPointF(cx, cy), 6, 6)

        arrow = QPolygonF([
            QPointF(cx, cy - 14),
            QPointF(cx - 5, cy - 6),
            QPointF(cx + 5, cy - 6)
        ])
        painter.setBrush(QBrush(QColor(COLOR_BRAND_ORANGE)))
        painter.drawPolygon(arrow)

        # 5. Header Banner
        painter.fillRect(0, 0, w, 28, QColor(23, 33, 43, 210))
        painter.setPen(QColor("#FFFFFF"))
        hdr_font = QFont()
        hdr_font.setFamily(FONT_FAMILY_PRIMARY)
        hdr_font.setBold(True)
        hdr_font.setPointSize(10)
        painter.setFont(hdr_font)
        painter.drawText(10, 19, self.title)

        status_text = "● LIVE" if self.is_connected else ("● STALE" if self.points_cartesian else "○ OFFLINE")
        status_color = QColor(COLOR_SUCCESS if self.is_connected else (COLOR_WARNING if self.points_cartesian else COLOR_OFFLINE))
        painter.setPen(status_color)
        painter.drawText(w - 76, 19, status_text)

        # 6. Bottom Range Telemetry
        painter.fillRect(0, h - 24, w, 24, QColor(23, 33, 43, 210))
        painter.setPen(QColor("#D6E0EA"))
        info_font = QFont(FONT_FAMILY_MONO, 9)
        painter.setFont(info_font)
        diag_str = f"Min: {self.min_range:.2f}m  |  Max: {self.max_range:.2f}m  |  Pts: {len(self.points_cartesian)}  |  Freq: {self.scan_frequency:.1f}Hz  |  Safe: {self.safety_zone_meters:.2f}m"
        painter.drawText(10, h - 7, diag_str)
