"""
GRaCEmo ViRa — Phase 4 Step 1 Perception Foundation Package
RGB + Depth -> Object Detection -> 3D Coordinate -> TF World Transform -> Kernel Ingestion & LookAt
"""

from .models import BoundingBox, Point3D, Detection, PerceptionResult
from .detector import ObjectDetector
from .depth_estimator import DepthEstimator
from .coordinate_transformer import CoordinateTransformer
from .visualizer import PerceptionVisualizer
from .perception_service import PerceptionService
from .gaze_bridge import GazeBridge

__all__ = [
    "BoundingBox",
    "Point3D",
    "Detection",
    "PerceptionResult",
    "ObjectDetector",
    "DepthEstimator",
    "CoordinateTransformer",
    "PerceptionVisualizer",
    "PerceptionService",
    "GazeBridge",
]
