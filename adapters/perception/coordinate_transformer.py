"""
GRaCEmo ViRa — TF Coordinate Transformer
Transforms 3D points from camera_optical_link to the canonical world frame
using the existing ROS 2 TF tree.
"""

import math
import logging
from typing import Optional, Tuple
import numpy as np

from .models import Point3D

logger = logging.getLogger("perception.transformer")


def quaternion_rotate_vector(q: Tuple[float, float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Rotates a 3D vector v = (vx, vy, vz) by quaternion q = (qx, qy, qz, qw).
    Uses Hamilton product v' = q * v * q^-1.
    """
    qx, qy, qz, qw = q
    vx, vy, vz = v

    # t = 2 * cross(q.xyz, v)
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)

    # v' = v + qw * t + cross(q.xyz, t)
    vpx = vx + qw * tx + (qy * tz - qz * ty)
    vpy = vy + qw * ty + (qz * tx - qx * tz)
    vpz = vz + qw * tz + (qx * ty - qy * tx)

    return (vpx, vpy, vpz)


class CoordinateTransformer:
    """
    Manages transformations across the ROS 2 TF tree.
    Canonical output frame is strictly 'world'.
    """

    def __init__(self, target_frame: str = "world", node=None):
        self.target_frame = target_frame
        self.node = node
        self.tf_buffer = None
        self.tf_listener = None

        if node is not None:
            self._init_tf()

    def _init_tf(self):
        """Initializes tf2_ros buffer and listener if running inside ROS 2 node."""
        try:
            import tf2_ros
            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)
            logger.info(f"✓ TF2 Buffer & TransformListener initialized with target frame '{self.target_frame}'")
        except Exception as e:
            logger.warning(f"Could not initialize TF2 buffer ({e}). Manual transform overrides can still be supplied.")

    def transform_to_world(
        self,
        point_camera: Point3D,
        fallback_transform: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]] = None,
    ) -> Optional[Point3D]:
        """
        Transforms a Point3D from its source frame (e.g. 'camera_optical_link') to 'world'.

        If ROS 2 TF is active, queries the latest transform from the tf_buffer.
        If fallback_transform is provided ((tx, ty, tz), (qx, qy, qz, qw)), applies it directly.

        Returns:
            Point3D in world frame, or None if transformation failed.
        """
        source_frame = point_camera.frame_id or "camera_optical_link"

        # 1. Try querying live ROS 2 TF buffer
        if self.tf_buffer is not None:
            try:
                import rclpy.time
                # Lookup latest available transform
                t = self.tf_buffer.lookup_transform(
                    self.target_frame,
                    source_frame,
                    rclpy.time.Time(),
                )
                trans = t.transform.translation
                rot = t.transform.rotation
                t_xyz = (float(trans.x), float(trans.y), float(trans.z))
                q_xyzw = (float(rot.x), float(rot.y), float(rot.z), float(rot.w))

                return self.apply_transform(point_camera, t_xyz, q_xyzw, target_frame=self.target_frame)
            except Exception as e:
                logger.debug(f"TF lookup from '{source_frame}' to '{self.target_frame}' failed: {e}")

        # 2. Fallback / manual transform (used in unit tests or when TF is mocked)
        if fallback_transform is not None:
            t_xyz, q_xyzw = fallback_transform
            return self.apply_transform(point_camera, t_xyz, q_xyzw, target_frame=self.target_frame)

        return None

    @staticmethod
    def apply_transform(
        point: Point3D,
        translation: Tuple[float, float, float],
        rotation_xyzw: Tuple[float, float, float, float],
        target_frame: str = "world",
    ) -> Point3D:
        """
        Applies rigid 3D transform (rotation by quaternion + translation) to a Point3D.
        P_world = R(q) * P_source + translation
        """
        rot_v = quaternion_rotate_vector(rotation_xyzw, (point.x, point.y, point.z))
        wx = rot_v[0] + translation[0]
        wy = rot_v[1] + translation[1]
        wz = rot_v[2] + translation[2]

        return Point3D(
            x=float(wx),
            y=float(wy),
            z=float(wz),
            frame_id=target_frame,
        )
