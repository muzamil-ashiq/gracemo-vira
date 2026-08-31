"""
GRaCEmo ViRa — 3D Spatial Coordinate & Distance Estimator
Calculates real-world (X, Y, Z) in meters relative to robot camera/base frame.
"""

from typing import Tuple, Dict, Any


class SpatialEstimator:
    def __init__(self, config: Dict[str, Any]):
        spatial_conf = config.get("spatial", {})
        self.enabled = spatial_conf.get("estimate_3d", True)
        self.focal_length_px = float(spatial_conf.get("camera_focal_length_px", 550.0))
        self.ref_face_width_m = float(spatial_conf.get("reference_face_width_m", 0.15))
        self.min_dist = float(spatial_conf.get("min_distance_m", 0.3))
        self.max_dist = float(spatial_conf.get("max_distance_m", 5.0))

    def estimate_from_box(self, box_w_px: float, box_center_x_px: float, img_w: int = 640) -> Tuple[float, float, float]:
        """
        Estimate 3D position (X=lateral, Y=depth/distance, Z=height) in meters.
        Using pinhole camera model: Distance Z = (Real_Width * Focal_Length) / Bounding_Box_Width_px.
        """
        if not self.enabled or box_w_px <= 0:
            return (0.0, 1.2, 0.0)

        # Depth (distance forward from camera)
        depth_m = (self.ref_face_width_m * self.focal_length_px) / float(box_w_px)
        depth_m = max(self.min_dist, min(self.max_dist, round(depth_m, 2)))

        # Lateral offset (left is negative X, right is positive X)
        center_offset_px = box_center_x_px - (img_w / 2.0)
        x_m = round((center_offset_px * depth_m) / self.focal_length_px, 2)

        return (x_m, depth_m, 0.0)
