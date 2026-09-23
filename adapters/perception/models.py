"""
GRaCEmo ViRa — Perception Data Models
Defines structured representations for 2D detections, 3D points, and canonical perception events.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Tuple, Dict, Any, Optional, List


@dataclass
class BoundingBox:
    """Represents a 2D bounding box in pixel coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float
    cx: float = 0.0
    cy: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def __post_init__(self):
        self.width = max(0.0, float(self.x2 - self.x1))
        self.height = max(0.0, float(self.y2 - self.y1))
        self.cx = float(self.x1 + self.width / 2.0)
        self.cy = float(self.y1 + self.height / 2.0)

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def xmin(self) -> float:
        return self.x1

    @property
    def ymin(self) -> float:
        return self.y1

    @property
    def xmax(self) -> float:
        return self.x2

    @property
    def ymax(self) -> float:
        return self.y2

    def to_dict(self) -> Dict[str, float]:
        return {
            "x1": round(self.x1, 1),
            "y1": round(self.y1, 1),
            "x2": round(self.x2, 1),
            "y2": round(self.y2, 1),
            "cx": round(self.cx, 1),
            "cy": round(self.cy, 1),
            "width": round(self.width, 1),
            "height": round(self.height, 1),
        }


@dataclass
class Point3D:
    """Represents a 3D position in metric space with its associated coordinate frame."""
    x: float
    y: float
    z: float
    frame_id: str = "camera_optical_link"

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": round(float(self.x), 3),
            "y": round(float(self.y), 3),
            "z": round(float(self.z), 3),
        }


@dataclass
class Detection:
    """
    Structured perception object containing 2D visual, metric depth, and 3D spatial data.
    """
    class_name: str
    confidence: float
    bbox: BoundingBox
    depth_m: float
    position_camera: Point3D
    position_world: Point3D
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 3),
            "bbox": self.bbox.to_dict(),
            "depth_m": round(float(self.depth_m), 3),
            "position_camera": self.position_camera.to_dict(),
            "position_world": self.position_world.to_dict(),
            "timestamp": self.timestamp,
        }

    def to_canonical_event(self, source: str = "Vision", observed_by: str = "perception_service") -> Dict[str, Any]:
        """
        Formats detection as canonical Rust Kernel Event envelope:
        EventType::ObjectDetected { class_name, confidence, x, y, z, bbox, depth_m, frame_id }
        where (x, y, z) are the metric coordinates in the world frame.
        """
        return {
            "id": str(uuid.uuid4()),
            "timestamp": int(self.timestamp),
            "source": source,
            "observed_by": observed_by,
            "event_type": {
                "type": "ObjectDetected",
                "data": {
                    "class_name": self.class_name,
                    "confidence": round(float(self.confidence), 2),
                    "x": round(float(self.position_world.x), 2),
                    "y": round(float(self.position_world.y), 2),
                    "z": round(float(self.position_world.z), 2),
                    "bbox": [
                        round(float(self.bbox.xmin), 1),
                        round(float(self.bbox.ymin), 1),
                        round(float(self.bbox.xmax), 1),
                        round(float(self.bbox.ymax), 1),
                    ],
                    "depth_m": round(float(self.depth_m), 3),
                    "frame_id": "world",
                },
            },
            "parent_event_id": None,
        }


@dataclass
class PerceptionResult:
    """Aggregated perception output for a single processed image frame."""
    detections: List[Detection] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    frame_width: int = 640
    frame_height: int = 480
    depth_width: int = 320
    depth_height: int = 240
    annotated_frame: Optional[Any] = None

    @property
    def count(self) -> int:
        return len(self.detections)

    def primary_detection(self) -> Optional[Detection]:
        """Returns highest confidence detection if any."""
        if not self.detections:
            return None
        return max(self.detections, key=lambda d: d.confidence)
