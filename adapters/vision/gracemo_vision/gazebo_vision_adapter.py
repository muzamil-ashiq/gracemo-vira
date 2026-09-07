#!/usr/bin/env python3
"""
GRaCEmo ViRa — Real Gazebo Harmonic Perception Adapter
Subscribes to live Gazebo camera stream (/camera/image_raw),
runs real YOLOv11 inference, filters out duplicate frame noise,
and feeds grounded observations into the MNSE Kernel Ledger & Graph.
"""

import os
import sys
import time
import signal
import threading
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))
from gracemo_sdk import AdapterClient, VisionNoiseGate

KERNEL_URL = os.getenv("GRACEMO_KERNEL_URL", "http://127.0.0.1:7780")
YOLO_MODEL_PATH = str(ROOT / "yolo11n.pt")


def determine_room(x: float, y: float) -> str:
    if y > 1.3:
        return "Master Bedroom" if x < -0.5 else "Kitchen & Dining"
    elif y < -1.3:
        return "Home Study" if x < -0.5 else "Living Room"
    return "Central Hallway"


class GazeboVisionAdapter:
    def __init__(self):
        self.running = True
        self.client = AdapterClient(adapter_name="Gazebo-Vision", base_url=KERNEL_URL)
        self.noise_gate = VisionNoiseGate(confidence_threshold=0.35, cooldown_sec=3.0)

        # Load real YOLOv11
        print(f"👁️ Loading YOLOv11 model from {YOLO_MODEL_PATH}...")
        self.model = YOLO(YOLO_MODEL_PATH)
        print("✓ YOLOv11 model loaded successfully.")

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_room = "Central Hallway"
        self.latest_frame = None
        self.lock = threading.Lock()

        # Connect Gazebo Transport
        import gz.transport13 as gz_t
        from gz.msgs10.image_pb2 import Image as GzImage
        from gz.msgs10.odometry_pb2 import Odometry as GzOdometry

        self.node = gz_t.Node()
        self.node.subscribe(GzImage, "/camera/image_raw", self._on_image)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)

        signal.signal(signal.SIGINT, self._sigint)
        signal.signal(signal.SIGTERM, self._sigint)

    def _sigint(self, sig, frame):
        self.running = False

    def _on_odom(self, msg):
        self.cur_x = msg.pose.position.x
        self.cur_y = msg.pose.position.y
        self.cur_room = determine_room(self.cur_x, self.cur_y)

    def _on_image(self, msg):
        import cv2
        arr = np.frombuffer(msg.data, dtype=np.uint8)
        if len(arr) == msg.height * msg.width * 3:
            raw_rgb = arr.reshape((msg.height, msg.width, 3))
            img = cv2.cvtColor(raw_rgb, cv2.COLOR_RGB2BGR)
            with self.lock:
                self.latest_frame = img

    def start(self):
        print(f"🚀 Gazebo Vision Adapter active! Connecting to Kernel at {KERNEL_URL}...")
        self.client.emit("AdapterConnected", {"name": "vision_gazebo"}, source="Vision")

        fps_timer = time.time()
        frames_processed = 0

        while self.running:
            frame = None
            with self.lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                    self.latest_frame = None

            if frame is None:
                time.sleep(0.03)
                continue

            # Run real YOLOv11 inference
            results = self.model(frame, verbose=False)[0]
            frames_processed += 1

            for box in results.boxes:
                cls_id = int(box.cls[0])
                class_name = self.model.names[cls_id]
                conf = float(box.conf[0])

                # Pass through Noise Gate
                if self.noise_gate.should_emit(class_name, conf, self.cur_room):
                    # Calculate center coordinates in image
                    xyxy = box.xyxy[0].tolist()
                    cx = (xyxy[0] + xyxy[2]) / 2.0
                    cy = (xyxy[1] + xyxy[3]) / 2.0

                    print(f"🎯 [DISCOVERY] Camera detected '{class_name}' in {self.cur_room} (conf: {conf:.2f}, pos: {self.cur_x:.1f},{self.cur_y:.1f})")

                    # Emit canonical ObjectDetected event to Kernel
                    self.client.emit("ObjectDetected", {
                        "class_name": class_name,
                        "confidence": conf,
                        "x": cx,
                        "y": cy,
                    }, source="Vision")

            time.sleep(0.04)

        print("\nStopping Gazebo Vision Adapter.")


def main():
    adapter = GazeboVisionAdapter()
    adapter.start()


if __name__ == "__main__":
    main()
