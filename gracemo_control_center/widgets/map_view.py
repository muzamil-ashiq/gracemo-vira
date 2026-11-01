"""
Interactive 2D Occupancy Grid Navigation Map Widget for GRaCEmo ViRa.
Renders static map, global plan path, authoritative destination markers,
robot pose with heading cone, and provides interactive pan/zoom.
"""

from PySide6.QtWidgets import QWidget, QFrame
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QImage, QColor, QPen, QBrush, QFont, QPolygonF

import math
import numpy as np
from typing import Dict, List, Tuple, Optional

from ..resources.styles.tokens import (
    COLOR_BG_DARK,
    COLOR_PANEL_MAIN,
    COLOR_BORDER,
    COLOR_ACCENT_ORANGE,
    COLOR_ACCENT_WHITE,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
)


class MapViewWidget(QFrame):
    """Interactive 2D Nav2 occupancy grid and multi-room map viewer."""

    destination_clicked = Signal(str) # Emits destination key if clicked on map

    def __init__(self, parent=None):
        super().__init__(parent)
        self.map_image: Optional[QImage] = None
        self.map_width = 0
        self.map_height = 0
        self.map_resolution = 0.05 # meters/pixel
        self.origin_x = 0.0
        self.origin_y = 0.0

        # Robot Pose
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        self.has_robot_pose = False

        # Global Path
        self.global_path: List[Tuple[float, float]] = []

        # Configured Destinations
        self.destinations: Dict[str, Dict] = {}
        self.active_goal_key: Optional[str] = None

        # Viewport Pan & Zoom
        self.zoom_scale = 1.0 # Multiplier over native map scale
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._dragging = False
        self._last_mouse_pos = None

        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumSize(400, 350)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #0D141B;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
            }}
        """)

    def set_map(self, width: int, height: int, resolution: float, origin_x: float, origin_y: float, data: List[int]):
        """Load and convert ROS 2 OccupancyGrid into displayable QImage."""
        self.map_width = width
        self.map_height = height
        self.map_resolution = resolution
        self.origin_x = origin_x
        self.origin_y = origin_y

        # Convert 1D occupancy grid to 8-bit grayscale image
        # -1 = unknown (#18222A), 0 = free (#364958), 100 = occupied (#FFFFFF)
        arr = np.array(data, dtype=np.int8).reshape((height, width))
        img_data = np.zeros((height, width, 4), dtype=np.uint8)

        # Free space (0): Slate dark (#2D3D4B)
        free_mask = (arr == 0)
        img_data[free_mask] = [45, 61, 75, 255]

        # Occupied space (>50): Solid White / Bright obstacle (#F0F4F8)
        occ_mask = (arr > 50)
        img_data[occ_mask] = [240, 244, 248, 255]

        # Unknown space (-1): Void Background (#101820)
        unk_mask = (arr == -1)
        img_data[unk_mask] = [16, 24, 32, 255]

        # In ROS, row 0 is bottom of map. Flip vertically for Qt coordinate system
        img_data = np.ascontiguousarray(np.flipud(img_data))

        # Construct QImage
        qimg = QImage(img_data.data, width, height, width * 4, QImage.Format_RGBA8888).copy()
        self.map_image = qimg
        self.reset_view()
        self.update()

    def set_robot_pose(self, x: float, y: float, yaw: float):
        """Update current localized robot pose."""
        self.robot_x = x
        self.robot_y = y
        self.robot_yaw = yaw
        self.has_robot_pose = True
        self.update()

    def set_global_path(self, waypoints: List[Tuple[float, float]]):
        """Update active Nav2 planned path."""
        self.global_path = waypoints
        self.update()

    def set_destinations(self, dests: Dict[str, Dict]):
        """Set known destinations from destinations.json."""
        self.destinations = dests
        self.update()

    def set_active_goal(self, key: Optional[str]):
        """Highlight currently active navigation destination."""
        self.active_goal_key = key
        self.update()

    def reset_view(self):
        """Auto-fit map to current widget bounds."""
        if not self.map_image or self.map_width == 0 or self.map_height == 0:
            return
        fit_w = self.width() / float(self.map_width)
        fit_h = self.height() / float(self.map_height)
        self.zoom_scale = min(fit_w, fit_h) * 0.90
        self.pan_offset_x = (self.width() - (self.map_width * self.zoom_scale)) / 2.0
        self.pan_offset_y = (self.height() - (self.map_height * self.zoom_scale)) / 2.0

    def world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        """Convert ROS world coordinates (meters) to Qt widget screen pixels."""
        if not self.map_image or self.map_resolution == 0:
            return 0.0, 0.0
        # Map pixel coords (origin is at bottom-left in ROS map)
        mx = (wx - self.origin_x) / self.map_resolution
        my = self.map_height - ((wy - self.origin_y) / self.map_resolution)
        # Apply screen zoom & pan
        sx = self.pan_offset_x + (mx * self.zoom_scale)
        sy = self.pan_offset_y + (my * self.zoom_scale)
        return sx, sy

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse_pos = event.pos()
        elif event.button() == Qt.RightButton:
            self.reset_view()
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_mouse_pos:
            delta = event.pos() - self._last_mouse_pos
            self.pan_offset_x += delta.x()
            self.pan_offset_y += delta.y()
            self._last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._last_mouse_pos = None

    def wheelEvent(self, event):
        """Zoom in/out around cursor."""
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 0.85
        new_scale = max(0.1, min(10.0, self.zoom_scale * zoom_factor))

        # Anchor zoom at mouse position
        mx = event.position().x()
        my = event.position().y()
        self.pan_offset_x = mx - (mx - self.pan_offset_x) * (new_scale / self.zoom_scale)
        self.pan_offset_y = my - (my - self.pan_offset_y) * (new_scale / self.zoom_scale)
        self.zoom_scale = new_scale
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        if self.map_image:
            # Draw Occupancy Grid Image with pan and zoom
            target_rect = QRectF(
                self.pan_offset_x,
                self.pan_offset_y,
                self.map_width * self.zoom_scale,
                self.map_height * self.zoom_scale
            )
            painter.drawImage(target_rect, self.map_image)

            # Draw Global Planned Path
            if len(self.global_path) > 1:
                path_pen = QPen(QColor(COLOR_INFO), 2.5, Qt.DashLine)
                painter.setPen(path_pen)
                for i in range(len(self.global_path) - 1):
                    x1, y1 = self.world_to_screen(self.global_path[i][0], self.global_path[i][1])
                    x2, y2 = self.world_to_screen(self.global_path[i+1][0], self.global_path[i+1][1])
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # Draw Configured Destination Markers
            for dest_key, dest_data in self.destinations.items():
                gx = dest_data.get("x", 0.0)
                gy = dest_data.get("y", 0.0)
                dname = dest_data.get("name", dest_key)
                sx, sy = self.world_to_screen(gx, gy)

                is_active = (dest_key == self.active_goal_key)
                marker_color = QColor(COLOR_ACCENT_ORANGE if is_active else COLOR_SUCCESS)

                # Outer ring
                painter.setPen(QPen(marker_color, 2))
                painter.setBrush(QBrush(QColor(marker_color.red(), marker_color.green(), marker_color.blue(), 60)))
                painter.drawEllipse(QPointF(sx, sy), 8, 8)

                # Label text
                painter.setPen(QColor(COLOR_ACCENT_WHITE))
                painter.setFont(QFont(FONT_FAMILY_PRIMARY, 9, QFont.Bold))
                painter.drawText(int(sx + 10), int(sy + 4), dname)

            # Draw Robot Pose Marker & Heading
            if self.has_robot_pose:
                rx, ry = self.world_to_screen(self.robot_x, self.robot_y)

                # Robot Body Circle
                painter.setBrush(QBrush(QColor(COLOR_ACCENT_WHITE)))
                painter.setPen(QPen(QColor(COLOR_ACCENT_ORANGE), 2))
                painter.drawEllipse(QPointF(rx, ry), 8, 8)

                # Heading Arrow / Line (pointing along robot_yaw)
                # In screen space: angle increases clockwise because Y is down
                screen_yaw = -self.robot_yaw
                hx = rx + 18.0 * math.cos(screen_yaw)
                hy = ry + 18.0 * math.sin(screen_yaw)
                painter.setPen(QPen(QColor(COLOR_ACCENT_ORANGE), 3))
                painter.drawLine(QPointF(rx, ry), QPointF(hx, hy))

                # Heading Cone
                cone_len = 26.0
                left_angle = screen_yaw - 0.4
                right_angle = screen_yaw + 0.4
                cone = QPolygonF([
                    QPointF(rx, ry),
                    QPointF(rx + cone_len * math.cos(left_angle), ry + cone_len * math.sin(left_angle)),
                    QPointF(rx + cone_len * math.cos(right_angle), ry + cone_len * math.sin(right_angle))
                ])
                painter.setBrush(QBrush(QColor(242, 140, 40, 50)))
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(cone)
        else:
            # Map Not Loaded Placeholder
            painter.setPen(QColor(COLOR_TEXT_SECONDARY))
            painter.setFont(QFont(FONT_FAMILY_MONO, 12, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, "2D OCCUPANCY MAP\n[WAITING FOR /map TOPIC]")

        # Overlay Controls / Legend
        painter.fillRect(10, 10, 190, 24, QColor(16, 24, 32, 210))
        painter.setPen(QColor(COLOR_ACCENT_ORANGE))
        painter.setFont(QFont(FONT_FAMILY_PRIMARY, 9, QFont.Bold))
        painter.drawText(16, 26, "MAP VIEW  |  Drag: Pan  Scroll: Zoom")
