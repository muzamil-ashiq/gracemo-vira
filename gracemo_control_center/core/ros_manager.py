from __future__ import annotations
"""
Authoritative ROS 2 Jazzy Integration Manager for GRaCEmo ViRa UARCC.
Runs a dedicated background ROS executor QThread, manages all subscriptions
with appropriate QoS policies, bounds high-rate camera queues, and routes
data cleanly into the event bus.
"""

from PySide6.QtCore import QThread, QTimer, QObject
from PySide6.QtGui import QImage

import os
import sys
import time
import math
import json
import numpy as np
import cv2
from typing import Optional, Dict, Any, List

# ROS 2 Jazzy Interfaces
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import (
        QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
    )
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import LaserScan, Imu, Image
    from nav_msgs.msg import Odometry, OccupancyGrid, Path
    from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
    from std_msgs.msg import String, Bool
    from std_srvs.srv import Empty
    import tf2_ros
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

from .event_bus import bus
from .health_monitor import HealthMonitor
from ..config import topic_registry as reg


class ControlCenterNode(Node if ROS2_AVAILABLE else object):
    """Authoritative ROS 2 Jazzy node for GRaCEmo ViRa Control Center."""

    def __init__(self, health_monitor: HealthMonitor):
        if not ROS2_AVAILABLE:
            return
        super().__init__("gracemo_control_center_node")
        self.health_monitor = health_monitor

        # Bounded frame rate & FPS tracking
        self.last_rgb_proc_time = 0.0
        self.rgb_fps_timer = time.time()
        self.rgb_frame_count = 0
        self.calculated_rgb_fps = 0.0

        self.last_depth_proc_time = 0.0
        self.depth_fps_timer = time.time()
        self.depth_frame_count = 0
        self.calculated_depth_fps = 0.0

        # LaserScan rate tracking
        self.last_scan_time = 0.0
        self.scan_count = 0
        self.scan_freq_timer = time.time()
        self.calculated_scan_freq = 10.0

        # QoS Profiles
        qos_transient = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        qos_reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        # TF Buffer & Listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # 1. High-frequency Sensor Subscriptions (SensorData QoS)
        self.create_subscription(Clock, reg.TOPIC_CLOCK, self._on_clock, qos_profile_sensor_data)
        self.create_subscription(LaserScan, reg.TOPIC_SCAN, self._on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, reg.TOPIC_ODOM, self._on_odom, qos_profile_sensor_data)
        self.create_subscription(Imu, reg.TOPIC_IMU, self._on_imu, qos_profile_sensor_data)
        self.create_subscription(Image, reg.TOPIC_CAMERA_RGB, self._on_camera_rgb, qos_profile_sensor_data)
        self.create_subscription(Image, reg.TOPIC_CAMERA_DEPTH, self._on_camera_depth, qos_profile_sensor_data)

        # 2. Localization & Mapping Subscriptions (Transient Local QoS)
        self.create_subscription(PoseWithCovarianceStamped, reg.TOPIC_AMCL_POSE, self._on_amcl_pose, qos_transient)
        self.create_subscription(OccupancyGrid, reg.TOPIC_MAP, self._on_map, qos_transient)
        self.create_subscription(Path, reg.TOPIC_GLOBAL_PATH, self._on_global_path, qos_reliable)

        # 3. Coordinator & Interaction Subscriptions (Reliable QoS)
        self.create_subscription(String, reg.TOPIC_COORDINATOR_FEEDBACK, self._on_coord_feedback, qos_reliable)
        self.create_subscription(String, reg.TOPIC_SPOKEN_FEEDBACK, self._on_spoken_feedback, qos_reliable)
        self.create_subscription(String, reg.TOPIC_VOICE_RECOGNIZED, self._on_voice_recognized, qos_reliable)

        # 4. Safety & Terrain Gate Subscriptions
        self.create_subscription(String, reg.TOPIC_TERRAIN_STATUS, self._on_terrain_status, qos_reliable)
        self.create_subscription(Bool, reg.TOPIC_TERRAIN_EMERGENCY_STOP, self._on_estop_topic, qos_reliable)

        # 5. Publishers
        self.coord_cmd_pub = self.create_publisher(String, reg.TOPIC_COORDINATOR_COMMAND, 10)
        self.user_input_pub = self.create_publisher(String, reg.TOPIC_USER_INPUT, 10)
        self.estop_pub = self.create_publisher(Bool, reg.TOPIC_TERRAIN_EMERGENCY_STOP, 10)

        # 6. Service Clients
        self.nomotion_cli = self.create_client(Empty, reg.SERVICE_NOMOTION_UPDATE)

        # Periodic TF Chain and Diagnostic Timer (2 Hz)
        self.diag_timer = self.create_timer(0.5, self._check_tf_and_diagnostics)

        # Wire incoming UI actions from EventBus
        bus.navigation_goal_dispatched.connect(self._dispatch_goal_to_coordinator)
        bus.navigation_cancel_requested.connect(self._dispatch_cancel_to_coordinator)
        bus.user_input_received.connect(self._publish_user_input)
        bus.emergency_stop_state.connect(self._publish_emergency_stop)

        self.get_logger().info("🛡️ GRaCEmo ViRa Control Center Node initialized on ROS 2 Jazzy.")

    def _on_clock(self, msg: Clock):
        sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9
        self.health_monitor.record_heartbeat("clock")
        bus.sim_clock_updated.emit(sim_time)

    def _on_scan(self, msg: LaserScan):
        now = time.time()
        self.scan_count += 1
        if now - self.scan_freq_timer >= 1.0:
            self.calculated_scan_freq = self.scan_count / (now - self.scan_freq_timer)
            self.scan_count = 0
            self.scan_freq_timer = now

        self.health_monitor.record_heartbeat("lidar")

        # Convert polar LaserScan to Cartesian points in robot frame (lidar_link)
        points = []
        valid_ranges = []
        angle = msg.angle_min

        for r in msg.ranges:
            if math.isfinite(r) and msg.range_min <= r <= msg.range_max:
                valid_ranges.append(r)
                # Polar to Cartesian
                x = r * math.cos(angle)
                y = r * math.sin(angle)
                points.append((x, y))
            angle += msg.angle_increment

        min_r = min(valid_ranges) if valid_ranges else 0.0
        max_r = max(valid_ranges) if valid_ranges else 0.0

        scan_payload = {
            "points": points,
            "min_range": min_r,
            "max_range": max_r,
            "freq": self.calculated_scan_freq,
            "timestamp": now
        }
        bus.lidar_scan_ready.emit(scan_payload)

    def _on_odom(self, msg: Odometry):
        self.health_monitor.record_heartbeat("odom")
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny, cosy)

        odom_payload = {
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "yaw": yaw,
            "vx": msg.twist.twist.linear.x,
            "vy": msg.twist.twist.linear.y,
            "wz": msg.twist.twist.angular.z,
            "timestamp": time.time()
        }
        bus.odom_data_ready.emit(odom_payload)

    def _on_imu(self, msg: Imu):
        self.health_monitor.record_heartbeat("imu")
        q = msg.orientation
        # Compute roll, pitch, yaw from quaternion
        sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z)
        cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        pitch = math.asin(max(-1.0, min(1.0, sinp)))

        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        imu_payload = {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "ax": msg.linear_acceleration.x,
            "ay": msg.linear_acceleration.y,
            "az": msg.linear_acceleration.z,
            "gx": msg.angular_velocity.x,
            "gy": msg.angular_velocity.y,
            "gz": msg.angular_velocity.z,
            "timestamp": time.time()
        }
        bus.imu_data_ready.emit(imu_payload)

    def _on_camera_rgb(self, msg: Image):
        # Bounded rate: limit processing to max 30 FPS to avoid stalling Qt loop
        now = time.time()
        if now - self.last_rgb_proc_time < 0.030:
            return
        self.last_rgb_proc_time = now

        self.rgb_frame_count += 1
        if now - self.rgb_fps_timer >= 1.0:
            self.calculated_rgb_fps = self.rgb_frame_count / (now - self.rgb_fps_timer)
            self.rgb_frame_count = 0
            self.rgb_fps_timer = now

        self.health_monitor.record_heartbeat("camera_rgb")

        try:
            # Parse raw buffer into QImage
            w = msg.width
            h = msg.height
            if msg.encoding in ("rgb8", "RGB8"):
                bytes_per_line = 3 * w
                qimg = QImage(msg.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            elif msg.encoding in ("bgr8", "BGR8"):
                # Convert BGR to RGB via OpenCV
                np_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
                rgb = cv2.cvtColor(np_arr, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            else:
                return

            res_str = f"{w}x{h}"
            bus.rgb_frame_ready.emit(qimg, self.calculated_rgb_fps, res_str, now)
        except Exception as e:
            pass

    def _on_camera_depth(self, msg: Image):
        # Bounded rate: limit depth colormapping to max 20 FPS
        now = time.time()
        if now - self.last_depth_proc_time < 0.045:
            return
        self.last_depth_proc_time = now

        self.depth_frame_count += 1
        if now - self.depth_fps_timer >= 1.0:
            self.calculated_depth_fps = self.depth_frame_count / (now - self.depth_fps_timer)
            self.depth_frame_count = 0
            self.depth_fps_timer = now

        self.health_monitor.record_heartbeat("camera_depth")

        try:
            w = msg.width
            h = msg.height
            if msg.encoding in ("32FC1", "32fc1"):
                depth_arr = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))
            elif msg.encoding in ("16UC1", "16uc1"):
                depth_arr = np.frombuffer(msg.data, dtype=np.uint16).reshape((h, w)).astype(np.float32) / 1000.0
            else:
                return

            # Mask invalid/inf/nan
            valid_mask = np.isfinite(depth_arr) & (depth_arr > 0.05) & (depth_arr < 15.0)
            if not np.any(valid_mask):
                return

            min_m = float(np.min(depth_arr[valid_mask]))
            max_m = float(np.max(depth_arr[valid_mask]))

            # Normalize to 0-255 and apply TURBO colormap
            norm_depth = np.clip((depth_arr - min_m) / max(0.1, (max_m - min_m)) * 255.0, 0, 255).astype(np.uint8)
            colored = cv2.applyColorMap(norm_depth, cv2.COLORMAP_TURBO)
            # Black out invalid pixels
            colored[~valid_mask] = [0, 0, 0]

            bytes_per_line = 3 * w
            qimg = QImage(colored.data, w, h, bytes_per_line, QImage.Format_BGR888).copy()
            bus.depth_frame_ready.emit(qimg, min_m, max_m, now)
        except Exception:
            pass

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped):
        self.health_monitor.record_heartbeat("amcl_pose")
        px = msg.pose.pose.position.x
        py = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny, cosy)

        cov = msg.pose.covariance
        var_x = float(cov[0])
        var_y = float(cov[7])
        var_yaw = float(cov[35])

        bus.amcl_pose_ready.emit(px, py, yaw, var_x, var_y, var_yaw)

    def _on_map(self, msg: OccupancyGrid):
        self.health_monitor.record_heartbeat("map")
        map_payload = {
            "width": msg.info.width,
            "height": msg.info.height,
            "resolution": msg.info.resolution,
            "origin_x": msg.info.origin.position.x,
            "origin_y": msg.info.origin.position.y,
            "data": list(msg.data)
        }
        bus.map_ready.emit(map_payload)

    def _on_global_path(self, msg: Path):
        waypoints = [(p.pose.position.x, p.pose.position.y) for p in msg.poses]
        bus.global_path_ready.emit(waypoints)

    def _on_coord_feedback(self, msg: String):
        self.health_monitor.record_heartbeat("coordinator")
        try:
            data = json.loads(msg.data)
            st = data.get("state", "IDLE")
            speech = data.get("speech", "")
            details = data.get("details", {})
            ts = data.get("timestamp", time.time())
            bus.coordinator_feedback_ready.emit(st, speech, details, ts)
            bus.log_event_emitted.emit({
                "level": "INFO", "component": "Coordinator", "source": "ROS2",
                "message": f"[{st}] {speech}", "timestamp": ts
            })
        except Exception:
            pass

    def _on_spoken_feedback(self, msg: String):
        self.health_monitor.record_heartbeat("interaction")
        try:
            data = json.loads(msg.data)
            text = data.get("text", "")
            st = data.get("status", "INFO")
            bus.spoken_feedback_received.emit(text, st)
            bus.log_event_emitted.emit({
                "level": "INFO", "component": "Voice", "source": "InteractionNode",
                "message": f"GRaCEmo: {text}", "timestamp": time.time()
            })
        except Exception:
            pass

    def _on_voice_recognized(self, msg: String):
        text = msg.data.strip()
        bus.voice_recognized.emit(text)
        bus.log_event_emitted.emit({
            "level": "INFO", "component": "Voice", "source": "WhisperMic",
            "message": f"Utterance: '{text}'", "timestamp": time.time()
        })

    def _on_terrain_status(self, msg: String):
        self.health_monitor.record_heartbeat("terrain")
        try:
            data = json.loads(msg.data)
            bus.terrain_status_ready.emit(data)
        except Exception:
            pass

    def _on_estop_topic(self, msg: Bool):
        bus.emergency_stop_state.emit(msg.data, "ROS_TOPIC")

    def _check_tf_and_diagnostics(self):
        """Audit coordinate transforms across the TF tree."""
        tf_status = {
            "map_to_odom": False,
            "odom_to_base": False,
            "base_to_lidar": False,
            "base_to_cam": False,
        }
        try:
            tf_status["map_to_odom"] = self.tf_buffer.can_transform("map", "odom", rclpy.time.Time())
            tf_status["odom_to_base"] = self.tf_buffer.can_transform("odom", "base_footprint", rclpy.time.Time())
            tf_status["base_to_lidar"] = self.tf_buffer.can_transform("base_footprint", "lidar_link", rclpy.time.Time())
            tf_status["base_to_cam"] = self.tf_buffer.can_transform("base_footprint", "camera_link", rclpy.time.Time())
        except Exception:
            pass
        bus.tf_status_ready.emit(tf_status)

    def _dispatch_goal_to_coordinator(self, name: str, x: float, y: float, yaw: float):
        """Dispatch goal JSON to /coordinator/command."""
        payload = {
            "intent": "NAVIGATE_TO",
            "destination_name": name,
            "destination_coords": {"x": x, "y": y, "yaw": yaw}
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.coord_cmd_pub.publish(msg)
        self.get_logger().info(f"Dispatched goal '{name}' to /coordinator/command")

    def _dispatch_cancel_to_coordinator(self):
        """Dispatch cancel intent to /coordinator/command."""
        payload = {"intent": "CANCEL_NAVIGATION"}
        msg = String()
        msg.data = json.dumps(payload)
        self.coord_cmd_pub.publish(msg)
        self.get_logger().info("Dispatched CANCEL_NAVIGATION to /coordinator/command")

    def _publish_user_input(self, text: str, source: str):
        msg = String()
        msg.data = text
        self.user_input_pub.publish(msg)

    def _publish_emergency_stop(self, is_active: bool, source: str):
        msg = Bool()
        msg.data = is_active
        self.estop_pub.publish(msg)
        self.get_logger().warn(f"Published E-Stop: {is_active} (Source: {source})")


class RosExecutorThread(QThread):
    """Dedicated background thread hosting rclpy executor."""

    def __init__(self, node: ControlCenterNode, parent=None):
        super().__init__(parent)
        self.node = node
        self._running = True

    def run(self):
        bus.ros_connected.emit(True)
        try:
            while self._running and rclpy.ok():
                rclpy.spin_once(self.node, timeout_sec=0.05)
        except Exception as e:
            pass
        finally:
            bus.ros_connected.emit(False)

    def stop(self):
        self._running = False
        self.wait(1500)


class RosManager(QObject):
    """Coordinates lifecycle of ROS node, background thread, and health monitors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node: Optional[ControlCenterNode] = None
        self.thread: Optional[RosExecutorThread] = None
        self.health_monitor = HealthMonitor(parent=self)

    def start(self):
        if not ROS2_AVAILABLE:
            print("[RosManager] rclpy not installed or not sourced. Running in offline mode.")
            return

        try:
            if not rclpy.ok():
                rclpy.init(args=None)
            self.node = ControlCenterNode(self.health_monitor)
            self.thread = RosExecutorThread(self.node, parent=self)
            self.thread.start()
            print("[RosManager] Background ROS 2 executor thread started.")
        except Exception as e:
            print(f"[RosManager] Error starting ROS 2 node: {e}")

    def stop(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        if self.node:
            try:
                self.node.destroy_node()
            except Exception:
                pass
        if ROS2_AVAILABLE and rclpy.ok():
            try:
                rclpy.shutdown()
            except Exception:
                pass
        print("[RosManager] ROS 2 node and executor stopped cleanly.")
