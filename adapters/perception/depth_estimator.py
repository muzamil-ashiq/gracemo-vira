"""
GRaCEmo ViRa — Depth Association & 3D Pinhole Back-Projection
Extracts robust metric depth around bounding-box center and converts pixel coordinates
to metric 3D camera-frame coordinates (X, Y, Z) using actual ROS 2 CameraInfo intrinsics.
"""

import math
import logging
from typing import Optional, Tuple, Dict, Any
import numpy as np

from .models import BoundingBox, Point3D

logger = logging.getLogger("perception.depth")

# Valid depth operational range for simulation sensors
MIN_VALID_DEPTH_M = 0.05
MAX_VALID_DEPTH_M = 15.0


class DepthEstimator:
    """
    Associates 2D detections on RGB frames with aligned depth images (32FC1),
    applies robust spatial median filtering, and back-projects to 3D metric coordinates.
    """

    def __init__(self, neighborhood_size: int = 7):
        self.neighborhood_size = neighborhood_size
        self.camera_info: Optional[Any] = None
        self.fx: Optional[float] = None
        self.fy: Optional[float] = None
        self.cx: Optional[float] = None
        self.cy: Optional[float] = None
        self.camera_frame_id: str = "camera_optical_link"

    def update_camera_info(self, camera_info_msg: Any):
        """
        Updates camera intrinsics directly from sensor_msgs/msg/CameraInfo.
        Does NOT hardcode any focal lengths or optical centers.
        """
        self.camera_info = camera_info_msg
        if hasattr(camera_info_msg, "header") and camera_info_msg.header.frame_id:
            self.camera_frame_id = camera_info_msg.header.frame_id

        # K matrix format: [fx, 0, cx, 0, fy, cy, 0, 0, 1]
        if hasattr(camera_info_msg, "k") and len(camera_info_msg.k) == 9:
            self.fx = float(camera_info_msg.k[0])
            self.cx = float(camera_info_msg.k[2])
            self.fy = float(camera_info_msg.k[4])
            self.cy = float(camera_info_msg.k[5])
        elif hasattr(camera_info_msg, "p") and len(camera_info_msg.p) == 12:
            # P matrix projection format: [fx, 0, cx, Tx, 0, fy, cy, Ty, 0, 0, 1, 0]
            self.fx = float(camera_info_msg.p[0])
            self.cx = float(camera_info_msg.p[2])
            self.fy = float(camera_info_msg.p[5])
            self.cy = float(camera_info_msg.p[6])

    def sample_median_depth(
        self,
        depth_img: np.ndarray,
        u_depth: float,
        v_depth: float,
    ) -> Optional[float]:
        """
        Samples metric depth in a window around (u_depth, v_depth) on the depth image.
        Uses robust median filter over valid pixels (rejecting NaN, Inf, <=0.05m, >15m).
        """
        if depth_img is None:
            return None

        h, w = depth_img.shape[:2]
        center_u = int(round(u_depth))
        center_v = int(round(v_depth))

        if center_u < 0 or center_u >= w or center_v < 0 or center_v >= h:
            return None

        half = max(1, self.neighborhood_size // 2)
        u_min = max(0, center_u - half)
        u_max = min(w, center_u + half + 1)
        v_min = max(0, center_v - half)
        v_max = min(h, center_v + half + 1)

        patch = depth_img[v_min:v_max, u_min:u_max]
        if patch.size == 0:
            return None

        # Filter valid depth elements
        valid_mask = np.isfinite(patch) & (patch >= MIN_VALID_DEPTH_M) & (patch <= MAX_VALID_DEPTH_M)
        valid_depths = patch[valid_mask]

        if len(valid_depths) == 0:
            return None

        return float(np.median(valid_depths))

    def estimate_3d_position(
        self,
        bbox: BoundingBox,
        depth_img: np.ndarray,
        rgb_width: int = 640,
        rgb_height: int = 480,
    ) -> Tuple[Optional[float], Optional[Point3D]]:
        """
        Calculates metric depth and 3D camera-frame coordinates for a 2D detection.

        Explicitly accounts for dimension differences between RGB (640x480) and Depth (320x240):
            scale_u = depth_width / rgb_width
            scale_v = depth_height / rgb_height
            u_depth = bbox.cx * scale_u
            v_depth = bbox.cy * scale_v

        Pinhole inverse projection:
            Z = depth
            X = (bbox.cx - cx) * Z / fx
            Y = (bbox.cy - cy) * Z / fy

        Returns:
            (depth_m, Point3D(X, Y, Z, frame_id)) or (None, None) if depth invalid.
        """
        if depth_img is None or self.fx is None or self.fy is None:
            return None, None

        depth_h, depth_w = depth_img.shape[:2]

        # Resolution scaling from RGB image coordinate space to Depth coordinate space
        scale_u = float(depth_w) / float(rgb_width) if rgb_width > 0 else 1.0
        scale_v = float(depth_h) / float(rgb_height) if rgb_height > 0 else 1.0

        u_depth = bbox.cx * scale_u
        v_depth = bbox.cy * scale_v

        depth_m = self.sample_median_depth(depth_img, u_depth, v_depth)
        if depth_m is None or depth_m <= 0:
            return None, None

        # Camera frame coordinates using pinhole model:
        # Note: in standard optical frame (camera_optical_link):
        # +Z points forward, +X points right, +Y points down.
        # Intrinsics are defined relative to the RGB camera image plane:
        z_c = depth_m
        x_c = (bbox.cx - self.cx) * z_c / self.fx
        y_c = (bbox.cy - self.cy) * z_c / self.fy

        point_camera = Point3D(
            x=float(x_c),
            y=float(y_c),
            z=float(z_c),
            frame_id=self.camera_frame_id,
        )

        return depth_m, point_camera
