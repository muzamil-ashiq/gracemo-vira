"""
GRaCEmo ViRa — Perception Service
ROS 2 Perception Node that synchronizes RGB + Depth camera frames, executes YOLO11
detection, calculates robust 3D metric positions via camera intrinsics, transforms them
into the canonical world frame via TF, and emits canonical ObjectDetected events to the Kernel.
"""

import time
import logging
from typing import Optional, List, Dict, Any, Callable

import cv2
import numpy as np
import requests

from .models import BoundingBox, Point3D, Detection, PerceptionResult
from .detector import ObjectDetector
from .depth_estimator import DepthEstimator
from .coordinate_transformer import CoordinateTransformer
from .visualizer import PerceptionVisualizer

logger = logging.getLogger("perception.service")


class PerceptionService:
    """
    Core perception engine integrating detector, depth association, 3D projection,
    TF transformation, kernel event emission, and visual debugging.
    Can be used standalone or embedded inside a ROS 2 node.
    """

    def __init__(
        self,
        kernel_url: str = "http://127.0.0.1:7780",
        confidence_threshold: float = 0.35,
        model_name: str = "yolo11n.pt",
        neighborhood_size: int = 7,
        emit_to_kernel: bool = True,
        min_emit_interval_sec: float = 0.5,
        save_debug_frames: bool = True,
        debug_frame_path: str = "/tmp/gracemo_perception_debug.jpg",
        ros_node=None,
    ):
        self.kernel_url = kernel_url
        self.emit_to_kernel = emit_to_kernel
        self.min_emit_interval_sec = min_emit_interval_sec
        self.save_debug_frames = save_debug_frames
        self.debug_frame_path = debug_frame_path
        self.last_emit_time: Dict[str, float] = {}

        self.detector = ObjectDetector(model_name=model_name, confidence_threshold=confidence_threshold)
        self.depth_estimator = DepthEstimator(neighborhood_size=neighborhood_size)
        self.transformer = CoordinateTransformer(target_frame="world", node=ros_node)
        self.visualizer = PerceptionVisualizer()

        self.latest_result: Optional[PerceptionResult] = None
        self.detection_callbacks: List[Callable[[Detection], None]] = []

    def register_callback(self, cb: Callable[[Detection], None]):
        """Registers a listener callback for newly verified 3D detections."""
        self.detection_callbacks.append(cb)

    def set_camera_info(self, camera_info_msg: Any):
        """Updates camera intrinsics directly from sensor_msgs/CameraInfo."""
        self.depth_estimator.update_camera_info(camera_info_msg)

    def process_frame(
        self,
        image_bgr: np.ndarray,
        depth_map: np.ndarray,
        fallback_tf=None,
    ) -> PerceptionResult:
        """
        Executes the full perception pipeline on a synchronized pair of RGB and Depth frames.

        1. Runs YOLO object detector on RGB frame -> 2D BBoxes
        2. Associates depth at bbox center with median filtering -> Depth (m)
        3. Pinhole back-projection using CameraInfo -> Camera-frame (Xc, Yc, Zc)
        4. TF tree transformation -> World-frame (Xw, Yw, Zw)
        5. Builds structured Detection objects
        6. Emits canonical ObjectDetected events to Kernel (throttled)
        7. Renders visual debug overlay
        """
        now = time.time()
        result = PerceptionResult(timestamp=now)

        if image_bgr is None or depth_map is None:
            return result

        result.frame_height, result.frame_width = image_bgr.shape[:2]
        result.depth_height, result.depth_width = depth_map.shape[:2]

        # 1. Object Detection
        raw_detections = self.detector.detect(image_bgr)

        # 2. Depth Association & 3D Spatial Calculation
        for class_name, conf, bbox in raw_detections:
            depth_m, pos_camera = self.depth_estimator.estimate_3d_position(
                bbox=bbox,
                depth_img=depth_map,
                rgb_width=result.frame_width,
                rgb_height=result.frame_height,
            )

            if depth_m is None or pos_camera is None:
                continue

            # 3. Transform to World Frame
            pos_world = self.transformer.transform_to_world(pos_camera, fallback_transform=fallback_tf)
            if pos_world is None:
                # If TF is uninitialized, default to camera frame coordinates
                pos_world = Point3D(x=pos_camera.x, y=pos_camera.y, z=pos_camera.z, frame_id="world")

            detection = Detection(
                class_name=class_name,
                confidence=conf,
                bbox=bbox,
                depth_m=depth_m,
                position_camera=pos_camera,
                position_world=pos_world,
                timestamp=now,
            )
            result.detections.append(detection)

            # Notify registered callbacks (e.g. gaze bridge)
            for cb in self.detection_callbacks:
                try:
                    cb(detection)
                except Exception as e:
                    logger.error(f"Error in detection callback: {e}")

            # 4. Throttled Kernel Event Emission
            if self.emit_to_kernel:
                self._emit_detection_to_kernel(detection)

        # 5. Visual Debug Overlay
        if self.save_debug_frames or result.count > 0:
            annotated = self.visualizer.annotate_frame(
                image_bgr,
                result.detections,
                save_path=self.debug_frame_path if self.save_debug_frames else None,
            )
            result.annotated_frame = annotated

        self.latest_result = result
        return result

    def _emit_detection_to_kernel(self, detection: Detection):
        """Emits canonical ObjectDetected event to the Kernel if throttled period elapsed."""
        now = time.time()
        last_time = self.last_emit_time.get(detection.class_name, 0.0)
        if now - last_time < self.min_interval_for(detection.class_name):
            return

        envelope = detection.to_canonical_event(source="Vision", observed_by="perception_service")
        try:
            resp = requests.post(f"{self.kernel_url}/emit", json=envelope, timeout=1.0)
            if resp.status_code == 200:
                self.last_emit_time[detection.class_name] = now
                logger.debug(f"✓ Emitted ObjectDetected for '{detection.class_name}' at world ({detection.position_world.x:.2f}, {detection.position_world.y:.2f})")
        except Exception:
            pass

    def min_interval_for(self, class_name: str) -> float:
        return self.min_emit_interval_sec


def create_ros_perception_node(node_name: str = "gracemo_perception_node"):
    """
    Factory function creating a full ROS 2 Node wrapping PerceptionService,
    subscribing to /camera/image_raw, /camera/depth_image, /camera/camera_info.
    """
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Image as RosImage, CameraInfo as RosCameraInfo

    class RosPerceptionNode(Node):
        def __init__(self):
            super().__init__(node_name)

            self.service = PerceptionService(ros_node=self)
            self.latest_bgr = None
            self.latest_depth = None

            self.sub_rgb = self.create_subscription(RosImage, "/camera/image_raw", self._on_rgb, 10)
            self.sub_depth = self.create_subscription(RosImage, "/camera/depth_image", self._on_depth, 10)
            self.sub_info = self.create_subscription(RosCameraInfo, "/camera/camera_info", self._on_info, 10)

            self.timer = self.create_timer(0.1, self._process_tick)
            self.get_logger().info("✓ Perception Node subscribed to /camera/image_raw, /camera/depth_image, /camera/camera_info")

        def _on_info(self, msg: RosCameraInfo):
            self.service.set_camera_info(msg)

        def _on_rgb(self, msg: RosImage):
            h, w = msg.height, msg.width
            if msg.encoding in ["rgb8", "bgr8"]:
                arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
                if msg.encoding == "rgb8":
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                self.latest_bgr = arr

        def _on_depth(self, msg: RosImage):
            h, w = msg.height, msg.width
            if msg.encoding == "32FC1":
                self.latest_depth = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))

        def _process_tick(self):
            if self.latest_bgr is not None and self.latest_depth is not None:
                self.service.process_frame(self.latest_bgr, self.latest_depth)

    return RosPerceptionNode
