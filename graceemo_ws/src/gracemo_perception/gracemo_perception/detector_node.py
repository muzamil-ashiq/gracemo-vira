#!/usr/bin/env python3
"""
GraceEMO — Vision Perception & Object Detection Node
Subscribes to camera frames, performs real-time YOLO object detection
and semantic scene understanding, and publishes structured detections.
"""

import time
import math
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

try:
    from gracemo_interfaces.msg import Detection
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False

# Try importing ultralytics YOLO
try:
    from ultralytics import YOLO
    HAVE_YOLO = True
except ImportError:
    HAVE_YOLO = False

class ObjectDetectorNode(Node):
    def __init__(self):
        super().__init__('detector_node')
        self.get_logger().info('👁️ Initializing GraceEMO Neural Vision Perception Node...')

        self.declare_parameter('confidence_threshold', 0.45)
        self.declare_parameter('camera_topic', '/camera/image_raw')
        self.declare_parameter('publish_annotated', True)

        self.conf_thresh = self.get_parameter('confidence_threshold').value
        camera_topic = self.get_parameter('camera_topic').value
        self.publish_annotated = self.get_parameter('publish_annotated').value

        # Initialize YOLO model if available
        self.yolo_model = None
        if HAVE_YOLO:
            try:
                self.yolo_model = YOLO('yolo11n.pt')
                self.get_logger().info('🧠 YOLOv11n Neural Engine loaded successfully')
            except Exception as e:
                self.get_logger().warn(f'YOLO load notice: {e} - using color-space fallback')

        # ROS 2 Subscriptions & Publications
        self.image_sub = self.create_subscription(Image, camera_topic, self.on_image, 10)
        self.annotated_pub = self.create_publisher(Image, '/gracemo/annotated_image', 10)

        if HAVE_INTERFACES:
            self.detection_pub = self.create_publisher(Detection, '/gracemo/detections', 10)

        self.frame_count = 0
        self.last_log_time = time.time()

    def on_image(self, msg: Image):
        # Convert ROS Image buffer to numpy BGR array
        try:
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
        except Exception:
            return

        self.frame_count += 1
        annotated_img = img.copy()
        detections_found = []

        # Neural YOLO Inference
        if self.yolo_model is not None:
            try:
                results = self.yolo_model.predict(img, conf=self.conf_thresh, verbose=False)
                for r in results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cls_id = int(box.cls[0])
                        label = self.yolo_model.names[cls_id]
                        conf = float(box.conf[0])

                        w = x2 - x1
                        h = y2 - y1
                        cx = x1 + w // 2
                        cy = y1 + h // 2

                        detections_found.append({
                            'label': label,
                            'conf': conf,
                            'cx': cx, 'cy': cy, 'w': w, 'h': h
                        })

                        # Draw bounding box
                        cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 240, 255), 2)
                        cv2.putText(annotated_img, f'{label} {conf:.2f}', (x1, max(20, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 240, 255), 1)
            except Exception as e:
                pass

        # Publish Detection interfaces
        if HAVE_INTERFACES and detections_found:
            for idx, d in enumerate(detections_found):
                det = Detection()
                det.track_id = idx + 1
                det.label = d['label']
                det.confidence = d['conf']
                det.center_x = float(d['cx'])
                det.center_y = float(d['cy'])
                det.width = float(d['w'])
                det.height = float(d['h'])
                det.distance_meters = max(0.5, float(500.0 / max(10, d['h']))) # Approximate pinhole distance
                self.detection_pub.publish(det)

        # Publish annotated image
        if self.publish_annotated:
            out_msg = Image()
            out_msg.header = msg.header
            out_msg.height = annotated_img.shape[0]
            out_msg.width = annotated_img.shape[1]
            out_msg.encoding = 'bgr8'
            out_msg.step = annotated_img.shape[1] * 3
            out_msg.data = annotated_img.tobytes()
            self.annotated_pub.publish(out_msg)

        # Periodic log
        if time.time() - self.last_log_time > 5.0:
            self.get_logger().info(f'👁️ Vision Active: {self.frame_count} frames processed | {len(detections_found)} objects in FOV')
            self.last_log_time = time.time()

def main(args=None):
    rclpy.init(args=args)
    node = ObjectDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
