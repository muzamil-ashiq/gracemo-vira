"""
GRaCEmo ViRa — Modular Camera Ingestion & Person Detection Interface
Phase 4 Implementation:
- Abstract CameraDriverInterface
- OpenCVCameraDriver (V4L2 / CSI camera via cv2)
- MockCameraDriver (Deterministic test harness generating synthetic RGB frames and targets)
"""

from __future__ import annotations
import abc
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple, List, Dict, Any

log = logging.getLogger("gracemo.perception.camera_driver")


@dataclass
class CameraFrame:
    """Standardized camera frame with timestamp and metadata."""
    data: Any
    width: int = 640
    height: int = 480
    channels: int = 3
    timestamp: float = field(default_factory=time.time)
    frame_id: str = "camera_optical_frame"
    is_mock: bool = False


@dataclass
class DetectedPerson:
    """Bounding box and confidence for a detected person."""
    x: float          # Center X normalized [0.0, 1.0]
    y: float          # Center Y normalized [0.0, 1.0]
    width: float      # Normalized width
    height: float     # Normalized height
    confidence: float # Detection confidence [0.0, 1.0]
    estimated_distance_m: Optional[float] = None
    target_id: int = 1


class CameraDriverInterface(abc.ABC):
    """Abstract base for camera drivers."""

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_mock(self) -> bool:
        ...

    @abc.abstractmethod
    def start(self) -> bool:
        ...

    @abc.abstractmethod
    def stop(self) -> None:
        ...

    @abc.abstractmethod
    def capture_frame(self) -> Optional[CameraFrame]:
        ...

    @abc.abstractmethod
    def detect_persons(self, frame: CameraFrame) -> List[DetectedPerson]:
        ...


class OpenCVCameraDriver(CameraDriverInterface):
    """Real camera driver using OpenCV / V4L2."""

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: int = 30):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None
        self._is_connected = False
        self._last_frame_time = 0.0

    @property
    def is_connected(self) -> bool:
        return self._is_connected and (self._cap is not None)

    @property
    def is_mock(self) -> bool:
        return False

    def start(self) -> bool:
        try:
            import cv2
            self._cap = cv2.VideoCapture(self.device_index)
            if not self._cap.isOpened():
                log.warning(f"OpenCVCameraDriver: Could not open video device {self.device_index}")
                self._is_connected = False
                return False
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            self._is_connected = True
            log.info(f"OpenCVCameraDriver: Started on device {self.device_index}")
            return True
        except Exception as e:
            log.error(f"OpenCVCameraDriver start failed: {e}")
            self._is_connected = False
            return False

    def stop(self) -> None:
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._is_connected = False

    def capture_frame(self) -> Optional[CameraFrame]:
        if not self.is_connected or not self._cap:
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            log.warning("OpenCVCameraDriver: Frame read error / disconnected")
            self._is_connected = False
            return None
        self._last_frame_time = time.time()
        return CameraFrame(
            data=frame,
            width=frame.shape[1],
            height=frame.shape[0],
            channels=frame.shape[2] if len(frame.shape) > 2 else 1,
            timestamp=self._last_frame_time,
            is_mock=False
        )

    def detect_persons(self, frame: CameraFrame) -> List[DetectedPerson]:
        """
        Detection pipeline using installed inference model or HOG descriptor.
        Returns detected person candidates with bounding boxes and estimated distance.
        """
        # Fallback to OpenCV HOG if DNN / YOLOv8 is not available
        try:
            import cv2
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            boxes, weights = hog.detectMultiScale(frame.data, winStride=(8, 8), padding=(4, 4), scale=1.05)
            results = []
            for (bx, by, bw, bh), w in zip(boxes, weights):
                # Normalized coordinates
                cx = (bx + bw / 2.0) / frame.width
                cy = (by + bh / 2.0) / frame.height
                norm_w = bw / frame.width
                norm_h = bh / frame.height
                # Metric distance estimation heuristic from bounding box height: d ~ focal_length * real_height / pixel_height
                est_dist = max(0.5, min(8.0, 1.7 * 500.0 / max(1, bh)))
                results.append(DetectedPerson(
                    x=cx, y=cy, width=norm_w, height=norm_h, confidence=float(w), estimated_distance_m=est_dist
                ))
            return results
        except Exception as e:
            log.warning(f"Person detection error: {e}")
            return []


class MockCameraDriver(CameraDriverInterface):
    """Mock camera driver for automated testing and software simulation."""

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self._is_connected = False
        self._injected_persons: List[DetectedPerson] = []
        self._frame_count = 0

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_mock(self) -> bool:
        return True

    def start(self) -> bool:
        self._is_connected = True
        return True

    def stop(self) -> None:
        self._is_connected = False

    def inject_person(self, person: DetectedPerson) -> None:
        """Inject a test person detection candidate."""
        self._injected_persons.append(person)

    def clear_persons(self) -> None:
        """Clear all injected persons (simulating person leaving view)."""
        self._injected_persons.clear()

    def capture_frame(self) -> Optional[CameraFrame]:
        if not self._is_connected:
            return None
        self._frame_count += 1
        return CameraFrame(
            data=None,  # No raw pixel buffer needed in pure mock tests
            width=self.width,
            height=self.height,
            channels=3,
            timestamp=time.time(),
            is_mock=True
        )

    def detect_persons(self, frame: CameraFrame) -> List[DetectedPerson]:
        if not self._is_connected:
            return []
        return list(self._injected_persons)
