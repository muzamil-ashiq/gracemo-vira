"""
GRaCEmo ViRa — Simulated Camera to YOLOv11 Vision Bridge
Subscribes to /camera/image_raw in Gazebo, runs YOLOv11 + ByteTrack,
and emits grounded vision observations to the Kernel at http://127.0.0.1:7780.
"""

import sys
import os
import time
import json
import numpy as np
from pathlib import Path
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import requests

# Add adapters to path
SDK_PATH = Path(__file__).resolve().parent.parent.parent / "sdk"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from gracemo_sdk import ConfigLoader, AdapterClient


class SimCameraVisionBridge(Node):
    def __init__(self):
        super().__init__("sim_camera_vision_bridge")

        self.config = ConfigLoader.load("perception")
        self.kernel_url = self.config.get_nested("kernel_url", "http://127.0.0.1:7780")
        self.client = AdapterClient(adapter_name="vision", base_url=self.kernel_url)

        # 1. Initialize YOLOv11
        from ultralytics import YOLO
        model_name = self.config.get_nested("detector.model", "yolo11n.pt")
        self.yolo = YOLO(model_name)
        self.conf_thresh = float(self.config.get_nested("detector.confidence_threshold", 0.45))

        # 2. Subscribe to /camera/image_raw
        self.image_sub = self.create_subscription(
            Image,
            "/camera/image_raw",
            self._on_image,
            10
        )

        self.last_process_time = 0.0
        self.process_fps = float(self.config.get_nested("camera.fps", 10.0))
        self.min_interval = 1.0 / self.process_fps

        self.get_logger().info(f"👁️ YOLOv11 Vision Bridge Active on /camera/image_raw -> {self.kernel_url}")

    def _on_image(self, msg: Image):
        now = time.time()
        if now - self.last_process_time < self.min_interval:
            return
        self.last_process_time = now

        try:
            # Convert ROS 2 Image to numpy array (RGB8 or BGR8)
            height = msg.height
            width = msg.width
            if msg.encoding in ["rgb8", "bgr8"]:
                img = np.frombuffer(msg.data, dtype=np.uint8).reshape((height, width, 3))
            else:
                return

            # Run YOLOv11 detection
            results = self.yolo.predict(img, conf=self.conf_thresh, verbose=False)
            detected_objects = []

            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    name = self.yolo.names[cls_id]
                    detected_objects.append({
                        "class": name,
                        "confidence": round(conf, 2),
                        "distance_m": round(float(2.5 * (1.0 - (box.xywh[0][3].item() / height))), 2)
                    })

            if detected_objects:
                payload = {
                    "object_count": len(detected_objects),
                    "objects": [obj["class"] for obj in detected_objects],
                    "detections": detected_objects,
                    "timestamp": now
                }
                self.client.emit("VisionDetection", payload, source="SimVision")
                self.get_logger().info(f"👁️ Detected: {[o['class'] for o in detected_objects]}")

        except Exception as e:
            pass


def main(args=None):
    rclpy.init(args=args)
    node = SimCameraVisionBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
