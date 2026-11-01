"""
Live Depth Camera Viewer Widget for GRaCEmo ViRa.
Visualizes colormapped depth image (e.g. Turbo/Inferno colormapping)
with minimum, maximum, and center-point physical depth probe readout.
"""

from PySide6.QtWidgets import QWidget, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QImage, QColor, QFont

import time
from ..resources.styles.tokens import (
    COLOR_BORDER,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_OFFLINE,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
)


class DepthViewWidget(QFrame):
    """Visualizes live depth camera stream with metric distance overlays."""

    def __init__(self, title: str = "DEPTH CAMERA (RGB-D)", parent=None):
        super().__init__(parent)
        self.title = title
        self.latest_image: QImage = None
        self.min_depth = 0.0
        self.max_depth = 0.0
        self.center_depth = 0.0
        self.last_frame_time = 0.0
        self.is_connected = False
        self.stale_threshold_sec = 2.0

        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumSize(320, 240)
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

    def update_depth(self, qimage: QImage, min_m: float, max_m: float, timestamp: float):
        self.latest_image = qimage
        self.min_depth = min_m
        self.max_depth = max_m
        self.center_depth = (min_m + max_m) / 2.0
        self.last_frame_time = timestamp
        self.is_connected = True
        self.update()

    def _check_freshness(self):
        if self.is_connected and (time.time() - self.last_frame_time > self.stale_threshold_sec):
            self.is_connected = False
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        if self.latest_image and not self.latest_image.isNull() and self.is_connected:
            scaled = self.latest_image.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x_offset = (w - scaled.width()) // 2
            y_offset = (h - scaled.height()) // 2
            painter.drawImage(x_offset, y_offset, scaled)

            # Center Reticle
            cx = w // 2
            cy = h // 2
            painter.setPen(QColor(COLOR_BRAND_ORANGE))
            painter.drawLine(cx - 8, cy, cx + 8, cy)
            painter.drawLine(cx, cy - 8, cx, cy + 8)
        else:
            painter.setPen(QColor(COLOR_TEXT_MUTED))
            font = QFont()
            font.setFamily(FONT_FAMILY_MONO)
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            msg = "STALE DATA" if (self.latest_image and not self.is_connected) else "NOT CONNECTED"
            painter.drawText(self.rect(), Qt.AlignCenter, f"{self.title}\n[{msg}]")

        # Top Banner
        painter.fillRect(0, 0, w, 28, QColor(23, 33, 43, 210))
        painter.setPen(QColor("#FFFFFF"))
        hdr_font = QFont()
        hdr_font.setFamily(FONT_FAMILY_PRIMARY)
        hdr_font.setBold(True)
        hdr_font.setPointSize(10)
        painter.setFont(hdr_font)
        painter.drawText(10, 19, self.title)

        status_text = "● LIVE" if self.is_connected else ("● STALE" if self.latest_image else "○ OFFLINE")
        status_color = QColor(COLOR_SUCCESS if self.is_connected else (COLOR_WARNING if self.latest_image else COLOR_OFFLINE))
        painter.setPen(status_color)
        painter.drawText(w - 76, 19, status_text)

        # Bottom Metric Range Bar
        painter.fillRect(0, h - 24, w, 24, QColor(23, 33, 43, 210))
        painter.setPen(QColor("#D6E0EA"))
        info_font = QFont()
        info_font.setFamily(FONT_FAMILY_MONO)
        info_font.setPointSize(9)
        painter.setFont(info_font)
        diag_str = f"Range: [{self.min_depth:.2f} m – {self.max_depth:.2f} m]  |  Turbo Depth Map  |  Raw Float"
        painter.drawText(10, h - 7, diag_str)
