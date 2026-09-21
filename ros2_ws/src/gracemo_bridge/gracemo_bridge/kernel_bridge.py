#!/usr/bin/env python3
"""
GRaCEmo ViRa — Native Gazebo Harmonic & ROS 2 to Kernel Bridge Node
Directly bridges Gazebo Sim Harmonic (gz-transport13 / gz-msgs10) and ROS 2 (rclpy)
with the GRaCEmo Kernel event bus.
Provides deterministic closed-loop autonomous waypoint navigation for high-level room dispatch.
"""

import sys
import time
import json
import math
import threading
import uuid
import requests

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Image as RosImage
from std_msgs.msg import Float64 as RosFloat64

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.twist_pb2 import Twist as GzTwist
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
    from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan
    from gz.msgs10.image_pb2 import Image as GzImage
    from gz.msgs10.pose_v_pb2 import Pose_V as GzPoseV
    from gz.msgs10.double_pb2 import Double as GzDouble
except ImportError:
    gz_transport = None
    GzDouble = None


# Phase 3 Active 2-DOF Neck Kinematics & Mechanical Limits
NECK_OFFSET_X = -0.02   # m relative to base
NECK_OFFSET_Y = 0.00    # m relative to base
NECK_OFFSET_Z = 0.645   # m above base footprint

PAN_LIMIT_RAD = 2.0944   # ±120° (±2.0944 rad)
TILT_LIMIT_RAD = 0.7854  # ±45°  (±0.7854 rad)
KINEMATIC_EPS = 1e-5     # Numerical boundary tolerance


def compute_look_at(
    target_x: float,
    target_y: float,
    target_z: float,
    robot_x: float = 0.0,
    robot_y: float = 0.0,
    robot_z: float = 0.0,
    robot_yaw: float = 0.0,
) -> dict:
    """Computes 2-DOF active neck pan and tilt angles to gaze at target (x, y, z) in world coords.

    Transform neck pivot into world coordinates:
      x_neck = x_robot - 0.02 * cos(yaw_robot)
      y_neck = y_robot - 0.02 * sin(yaw_robot)
      z_neck = z_robot + 0.645

    Transform horizontal displacement into robot-heading coordinates:
      dx_world = target_x - x_neck
      dy_world = target_y - y_neck
      dz_world = target_z - z_neck

      dx_robot = dx_world * cos(yaw_robot) + dy_world * sin(yaw_robot)
      dy_robot = -dx_world * sin(yaw_robot) + dy_world * cos(yaw_robot)
      dz_robot = dz_world

    Angles:
      pan = atan2(dy_robot, dx_robot)
      tilt = atan2(-dz_robot, sqrt(dx_robot^2 + dy_robot^2))
      (Positive tilt means looking downward)

    Limits:
      pan:  [-2.0944, +2.0944] rad ([-120°, +120°])
      tilt: [-0.7854, +0.7854] rad ([-45°, +45°])
    """
    x_neck = robot_x - 0.02 * math.cos(robot_yaw)
    y_neck = robot_y - 0.02 * math.sin(robot_yaw)
    z_neck = robot_z + 0.645

    dx_world = target_x - x_neck
    dy_world = target_y - y_neck
    dz_world = target_z - z_neck

    dx_robot = dx_world * math.cos(robot_yaw) + dy_world * math.sin(robot_yaw)
    dy_robot = -dx_world * math.sin(robot_yaw) + dy_world * math.cos(robot_yaw)
    dz_robot = dz_world

    pan = math.atan2(dy_robot, dx_robot)
    horizontal_dist = math.hypot(dx_robot, dy_robot)
    tilt = math.atan2(-dz_robot, horizontal_dist)

    pan_deg = math.degrees(pan)
    tilt_deg = math.degrees(tilt)

    # Check mechanical limits
    reasons = []
    if pan < -PAN_LIMIT_RAD - KINEMATIC_EPS or pan > PAN_LIMIT_RAD + KINEMATIC_EPS:
        reasons.append(f"pan {pan_deg:+.2f}° ({pan:+.4f} rad) outside limits [{-120.0:.1f}°, {+120.0:.1f}°]")
    if tilt < -TILT_LIMIT_RAD - KINEMATIC_EPS or tilt > TILT_LIMIT_RAD + KINEMATIC_EPS:
        reasons.append(f"tilt {tilt_deg:+.2f}° ({tilt:+.4f} rad) outside limits [{-45.0:.1f}°, {+45.0:.1f}°]")

    if reasons:
        return {
            "success": False,
            "workspace_exceeded": True,
            "target": {"x": float(target_x), "y": float(target_y), "z": float(target_z)},
            "calculated_pan": float(pan),
            "calculated_tilt": float(tilt),
            "calculated_pan_rad": float(pan),
            "calculated_tilt_rad": float(tilt),
            "calculated_pan_deg": float(pan_deg),
            "calculated_tilt_deg": float(tilt_deg),
            "pan_limit": [-PAN_LIMIT_RAD, PAN_LIMIT_RAD],
            "tilt_limit": [-TILT_LIMIT_RAD, TILT_LIMIT_RAD],
            "pan_limit_rad": [-PAN_LIMIT_RAD, PAN_LIMIT_RAD],
            "tilt_limit_rad": [-TILT_LIMIT_RAD, TILT_LIMIT_RAD],
            "pan_limit_deg": [-120.0, 120.0],
            "tilt_limit_deg": [-45.0, 45.0],
            "reason": "; ".join(reasons),
        }

    return {
        "success": True,
        "workspace_exceeded": False,
        "target": {"x": float(target_x), "y": float(target_y), "z": float(target_z)},
        "pan_rad": float(pan),
        "tilt_rad": float(tilt),
        "pan_deg": float(pan_deg),
        "tilt_deg": float(tilt_deg),
    }


class KernelBridgeNode(Node):
    def __init__(self):
        super().__init__("gracemo_kernel_bridge")

        self.declare_parameter("kernel_url", "http://127.0.0.1:7780")
        self.kernel_url = self.get_parameter("kernel_url").get_parameter_value().string_value

        self.get_logger().info(f"Starting GRaCEmo ROS 2 <-> MNSE Bridge connected to: {self.kernel_url}")

        # State tracking
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_yaw_rad = 0.0
        self.last_emit_time = 0.0
        self.running = True
        self.navigating = False
        self.nav_thread = None
        self.has_odom = False
        self.target_pan_rad = 0.0
        self.target_tilt_rad = 0.0
        self.neck_active = False

        # Camera frame caching
        self.latest_frame_path = "/tmp/gracemo_camera_latest.jpg"
        self.last_frame_save_time = 0.0
        self.frame_lock = threading.Lock()

        # 1. ROS 2 Publishers & Subscribers
        self.ros_cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.ros_odom_pub = self.create_publisher(Odometry, "/odom", 10)
        self.ros_camera_pub = self.create_publisher(RosImage, "/camera/image_raw", 10)
        self.ros_head_pan_pub = self.create_publisher(RosFloat64, "/head/pan/cmd_pos", 10)
        self.ros_head_tilt_pub = self.create_publisher(RosFloat64, "/head/tilt/cmd_pos", 10)
        self.ros_cmd_sub = self.create_subscription(Twist, "/cmd_vel", self._on_ros_cmd_vel, 10)

        # 2. Native Gazebo Harmonic Transport Bridge
        if gz_transport is not None:
            self.gz_node = gz_transport.Node()
            self.gz_cmd_pub = self.gz_node.advertise("/cmd_vel", GzTwist)
            self.gz_head_pan_pub = self.gz_node.advertise("/head/pan/cmd_pos", GzDouble)
            self.gz_head_tilt_pub = self.gz_node.advertise("/head/tilt/cmd_pos", GzDouble)
            self.gz_node.subscribe(GzOdometry, "/odom", self._on_gz_odom)
            self.gz_node.subscribe(GzImage, "/camera/image_raw", self._on_gz_camera_image)
            self.get_logger().info("✓ Connected to Gazebo Harmonic 8 via native gz-transport13!")
        else:
            self.gz_node = None
            self.gz_cmd_pub = None
            self.gz_head_pan_pub = None
            self.gz_head_tilt_pub = None
            self.get_logger().warning("⚠️ gz.transport13 not available; running in ROS2-only mode.")

        # 3. Start Kernel Action Listener thread
        threading.Thread(target=self._listen_kernel_actions, daemon=True).start()

    def _on_ros_cmd_vel(self, msg: Twist):
        """Forward ROS 2 /cmd_vel to Gazebo Harmonic."""
        if not self.navigating and self.gz_cmd_pub:
            gz_tw = GzTwist()
            gz_tw.linear.x = float(msg.linear.x)
            gz_tw.angular.z = float(msg.angular.z)
            self.gz_cmd_pub.publish(gz_tw)

    def _publish_cmd_vel(self, linear_x: float, angular_z: float):
        """Publish velocity command to both Gazebo Harmonic and ROS 2."""
        # ROS 2
        ros_tw = Twist()
        ros_tw.linear.x = float(linear_x)
        ros_tw.angular.z = float(angular_z)
        self.ros_cmd_pub.publish(ros_tw)

        # Gazebo Harmonic
        if self.gz_cmd_pub:
            gz_tw = GzTwist()
            gz_tw.linear.x = float(linear_x)
            gz_tw.angular.z = float(angular_z)
            self.gz_cmd_pub.publish(gz_tw)

    def _on_gz_odom(self, msg: GzOdometry):
        """Callback for 50Hz live odometry from Gazebo Harmonic."""
        p = msg.pose.position
        q = msg.pose.orientation
        self.current_x = p.x
        self.current_y = p.y
        self.current_z = p.z

        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_yaw_rad = math.atan2(siny, cosy)
        self.has_odom = True

        vx = msg.twist.linear.x
        vy = msg.twist.linear.y
        speed = math.hypot(vx, vy)

        now = time.time()
        if now - self.last_emit_time > 0.2:
            self._emit_event("RobotPosition", {
                "x": round(self.current_x, 3),
                "y": round(self.current_y, 3),
                "theta": round(self.current_yaw_rad, 3),
                "speed": round(speed, 3)
            })
            self.last_emit_time = now

        # Also publish to ROS 2 /odom
        ros_msg = Odometry()
        ros_msg.header.stamp = self.get_clock().now().to_msg()
        ros_msg.header.frame_id = "odom"
        ros_msg.child_frame_id = "base_footprint"
        ros_msg.pose.pose.position.x = p.x
        ros_msg.pose.pose.position.y = p.y
        ros_msg.pose.pose.position.z = p.z
        ros_msg.pose.pose.orientation.x = q.x
        ros_msg.pose.pose.orientation.y = q.y
        ros_msg.pose.pose.orientation.z = q.z
        ros_msg.pose.pose.orientation.w = q.w
        ros_msg.twist.twist.linear.x = vx
        ros_msg.twist.twist.linear.y = vy
        ros_msg.twist.twist.angular.z = msg.twist.angular.z
        self.ros_odom_pub.publish(ros_msg)

    def _on_gz_camera_image(self, msg: GzImage):
        """Bridges native Gazebo camera frame to ROS 2 and caches latest frame to disk."""
        if not self.running:
            return
        # 1. Publish to ROS 2 /camera/image_raw
        ros_img = RosImage()
        ros_img.header.stamp = self.get_clock().now().to_msg()
        ros_img.header.frame_id = "camera_optical_link"
        ros_img.height = msg.height
        ros_img.width = msg.width
        ros_img.encoding = "rgb8"
        ros_img.is_bigendian = False
        ros_img.step = msg.step or (msg.width * 3)
        ros_img.data = msg.data
        self.ros_camera_pub.publish(ros_img)

        # 2. Cache latest JPEG frame at throttled rate (max 10 Hz)
        now = time.time()
        if now - self.last_frame_save_time >= 0.1:
            self.last_frame_save_time = now
            try:
                import numpy as np
                import cv2
                arr = np.frombuffer(msg.data, dtype=np.uint8)
                if len(arr) == msg.height * msg.width * 3:
                    rgb = arr.reshape((msg.height, msg.width, 3))
                    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    with self.frame_lock:
                        cv2.imwrite(self.latest_frame_path, bgr)
            except Exception:
                pass

    def _emit_event(self, event_type: str, data: dict, source: str = "RobotBridge"):
        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "source": source,
            "observed_by": "kernel_bridge",
            "event_type": {
                "type": event_type,
                "data": data,
            },
            "parent_event_id": None,
        }
        try:
            requests.post(
                f"{self.kernel_url}/emit",
                json=envelope,
                timeout=0.2
            )
        except Exception:
            pass

    def _listen_kernel_actions(self):
        """Listen to SSE live event stream from MNSE Kernel."""
        while self.running and rclpy.ok():
            try:
                resp = requests.get(f"{self.kernel_url}/events/live", stream=True, timeout=10)
                for line in resp.iter_lines():
                    if not self.running:
                        break
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data:"):
                            data_str = decoded[5:].strip()
                            event = json.loads(data_str)
                            event_type = event.get("event_type", {})
                            if isinstance(event_type, dict) and event_type.get("type") == "ActionRequested":
                                self._handle_kernel_action(event_type.get("data", {}))
                            elif event.get("event_type") == "ActionRequested":
                                self._handle_kernel_action(event.get("payload", {}) or event.get("data", {}))
            except Exception:
                time.sleep(1.0)

    def _publish_neck_once(self, pan_rad: float, tilt_rad: float):
        """Publish a single joint position message to ROS 2 and Gazebo transport."""
        # ROS 2
        pan_msg = RosFloat64()
        pan_msg.data = float(pan_rad)
        self.ros_head_pan_pub.publish(pan_msg)

        tilt_msg = RosFloat64()
        tilt_msg.data = float(tilt_rad)
        self.ros_head_tilt_pub.publish(tilt_msg)

        # Gazebo Harmonic
        if self.gz_head_pan_pub:
            gz_pan = GzDouble()
            gz_pan.data = float(pan_rad)
            self.gz_head_pan_pub.publish(gz_pan)

        if self.gz_head_tilt_pub:
            gz_tilt = GzDouble()
            gz_tilt.data = float(tilt_rad)
            self.gz_head_tilt_pub.publish(gz_tilt)

    def publish_neck_command(self, pan_rad: float, tilt_rad: float, stream_sec: float = 3.0):
        """Publish neck joint position commands to both Gazebo Harmonic and ROS 2.
        CRITICAL: Does NOT touch /cmd_vel - base must remain completely stationary.
        Streams setpoint for stream_sec (default 3.0s) at 20Hz in background to ensure PID convergence.
        """
        self.target_pan_rad = float(pan_rad)
        self.target_tilt_rad = float(tilt_rad)
        self.neck_active = True

        # Immediate single publish
        self._publish_neck_once(self.target_pan_rad, self.target_tilt_rad)

        # Background stream thread to ensure setpoint arrival over best-effort transport
        def _stream():
            start_t = time.time()
            while self.running and (time.time() - start_t < stream_sec):
                time.sleep(0.05)
                self._publish_neck_once(self.target_pan_rad, self.target_tilt_rad)

        threading.Thread(target=_stream, daemon=True).start()

    def compute_look_at(self, target_x: float, target_y: float, target_z: float) -> dict:
        """Solves 3D LookAt kinematics from the node's current odometry pose."""
        return compute_look_at(
            target_x=target_x,
            target_y=target_y,
            target_z=target_z,
            robot_x=self.current_x,
            robot_y=self.current_y,
            robot_z=self.current_z,
            robot_yaw=self.current_yaw_rad,
        )

    def execute_look_at(self, target_x: float, target_y: float, target_z: float) -> dict:
        """Solves 3D LookAt kinematics, enforces joint limits, commands active neck.
        CRITICAL: Never publishes to /cmd_vel and never rotates the base.
        """
        result = self.compute_look_at(target_x, target_y, target_z)

        if result["workspace_exceeded"]:
            self.get_logger().warning(
                f"⚠️ [ACTION] LookAt workspace exceeded for target ({target_x:.2f}, {target_y:.2f}, {target_z:.2f}): "
                f"{result['reason']}. Head and base remain stationary."
            )
            # Emit failure to kernel; DO NOT publish neck commands; DO NOT publish cmd_vel
            self._emit_event("LookAtResult", result)
            return result

        # Target is inside mechanical workspace: command neck
        self.publish_neck_command(result["pan_rad"], result["tilt_rad"])
        self.get_logger().info(
            f"✓ [ACTION] LookAt commanded: pan={result['pan_deg']:+.1f}° ({result['pan_rad']:+.3f} rad), "
            f"tilt={result['tilt_deg']:+.1f}° ({result['tilt_rad']:+.3f} rad). Base stationary."
        )
        self._emit_event("LookAtResult", result)
        return result

    def _rotate_to_yaw(self, target_yaw: float, timeout_sec: float = 6.0):
        """Rotates the robot in place to align with target_yaw."""
        rate_hz = 20.0
        dt = 1.0 / rate_hz
        start_t = time.time()
        self.get_logger().info(f"🔄 [ROTATE] Orienting to yaw: {math.degrees(target_yaw):+.1f}° ({target_yaw:+.2f} rad)...")

        while self.running and rclpy.ok():
            if time.time() - start_t > timeout_sec:
                self.get_logger().warning(f"⚠️ [ROTATE] Orientation timeout after {timeout_sec}s")
                break

            yaw_err = target_yaw - self.current_yaw_rad
            while yaw_err > math.pi: yaw_err -= 2.0 * math.pi
            while yaw_err < -math.pi: yaw_err += 2.0 * math.pi

            if abs(yaw_err) < 0.08:
                self.get_logger().info(f"✓ [ROTATE] Final orientation reached (err: {math.degrees(yaw_err):+.1f}°)")
                break

            angular_w = math.copysign(min(0.70, max(0.25, abs(yaw_err) * 1.2)), yaw_err)
            self._publish_cmd_vel(0.0, angular_w)
            time.sleep(dt)

        self._publish_cmd_vel(0.0, 0.0)

    def _start_navigation_to_room(self, room: str):
        """Resolves topological corridor and doorway waypoints for designated room."""
        low = room.lower().strip()
        waypoints = []
        canonical_room = room
        target_final_yaw = None

        # Step 1: Room exit logic if currently inside a room
        cur_x, cur_y = self.current_x, self.current_y
        if cur_y > 1.2:
            door_x = -5.0 if cur_x < 0 else 5.0
            waypoints.extend([(door_x, 1.2), (door_x, 0.0)])
        elif cur_y < -1.2:
            door_x = -5.0 if cur_x < 0 else 5.0
            waypoints.extend([(door_x, -1.2), (door_x, 0.0)])

        # Step 2: Corridor & Doorway waypoints to target room and observation heading
        if "kitchen" in low or "dining" in low:
            canonical_room = "Kitchen & Dining"
            waypoints.extend([(-5.0, 0.0), (-5.0, -1.3), (-4.5, -2.5)])
            target_final_yaw = -math.pi / 2  # -90 deg: South toward Dining Table, Chairs & Refrigerator
        elif "bed" in low:
            canonical_room = "Master Bedroom"
            waypoints.extend([(-5.0, 0.0), (-5.0, 1.3), (-5.0, 3.0)])
            target_final_yaw = math.pi / 2   # +90 deg: North toward Bed & Wardrobe
        elif "study" in low:
            canonical_room = "Home Study"
            waypoints.extend([(5.0, 0.0), (5.0, 1.3), (4.5, 3.0)])
            target_final_yaw = math.pi / 2   # +90 deg: North toward Desk & Bookshelf
        elif "living" in low:
            canonical_room = "Living Room"
            waypoints.extend([(5.0, 0.0), (5.0, -1.3), (4.0, -2.5)])
            target_final_yaw = -math.pi / 2  # -90 deg: South toward Sofa & Coffee Table
        elif "hall" in low:
            canonical_room = "Central Hallway"
            waypoints.append((0.0, 0.0))
            target_final_yaw = 0.0
        else:
            self.get_logger().warning(f"⚠️ Unrecognized room: '{room}'")
            return

        self._start_waypoint_thread(waypoints, canonical_room, final_yaw=target_final_yaw)

    def _start_navigation_to_coordinates(self, x: float, y: float):
        """Navigates to specific metric coordinates."""
        waypoints = [(x, y)]
        self._start_waypoint_thread(waypoints, f"Pose({x:.2f}, {y:.2f})")

    def _start_waypoint_thread(self, waypoints: list, destination_name: str, final_yaw: float = None):
        self.navigating = False
        if self.nav_thread and self.nav_thread.is_alive():
            self.nav_thread.join(timeout=0.5)

        self.nav_thread = threading.Thread(
            target=self._execute_waypoints,
            args=(waypoints, destination_name, final_yaw),
            daemon=True
        )
        self.nav_thread.start()

    def _execute_waypoints(self, waypoints: list, destination: str, final_yaw: float = None):
        self.navigating = True
        self.get_logger().info(f"🚀 [NAV] Commencing transit to '{destination}' via {len(waypoints)} waypoints")

        rate_hz = 20.0
        dt = 1.0 / rate_hz

        for idx, (tx, ty) in enumerate(waypoints, 1):
            reach_dist = 0.30 if idx < len(waypoints) else 0.35
            self.get_logger().info(f"  -> [WAYPOINT {idx}/{len(waypoints)}] Heading to ({tx:+.2f}, {ty:+.2f})...")

            while self.navigating and self.running and rclpy.ok():
                dx = tx - self.current_x
                dy = ty - self.current_y
                dist = math.hypot(dx, dy)

                if dist <= reach_dist:
                    self.get_logger().info(f"  ✓ [WAYPOINT {idx} REACHED]")
                    break

                target_yaw = math.atan2(dy, dx)
                yaw_err = target_yaw - self.current_yaw_rad
                while yaw_err > math.pi: yaw_err -= 2.0 * math.pi
                while yaw_err < -math.pi: yaw_err += 2.0 * math.pi

                if abs(yaw_err) > 0.45:
                    # In-place rotation
                    linear_v = 0.0
                    angular_w = math.copysign(min(0.75, max(0.30, abs(yaw_err) * 1.3)), yaw_err)
                else:
                    # Translation with steering correction
                    linear_v = min(0.45, max(0.18, 0.65 * dist))
                    angular_w = max(-0.65, min(0.65, 1.2 * yaw_err))

                self._publish_cmd_vel(linear_v, angular_w)
                time.sleep(dt)

            if not self.navigating:
                break

        # Stop robot translation locomotion
        self._publish_cmd_vel(0.0, 0.0)

        # Final observation orientation alignment (if specified)
        if final_yaw is not None and self.running and self.navigating:
            self.get_logger().info(f"🎯 [NAV] Aligning final observation pose to {math.degrees(final_yaw):+.1f}°...")
            self._rotate_to_yaw(final_yaw, timeout_sec=6.0)

        self._publish_cmd_vel(0.0, 0.0)
        self.navigating = False

        if self.running:
            self.get_logger().info(
                f"🎯 [ARRIVED] Destination '{destination}' reached! "
                f"(Final Pose: x={self.current_x:+.2f}, y={self.current_y:+.2f}, yaw={math.degrees(self.current_yaw_rad):+.1f}°)"
            )
            self._emit_event("NavigationArrived", {
                "destination": destination,
                "success": True,
                "x": round(self.current_x, 3),
                "y": round(self.current_y, 3)
            })

    def _handle_kernel_action(self, payload: dict):
        action = payload.get("action")
        params = payload.get("params", {})

        # Canonical: RobotAction::Stop
        if action == "Stop":
            self.navigating = False
            self._publish_cmd_vel(0.0, 0.0)
            self.get_logger().info("🛑 Executed Motor Stop from MNSE Action")

        # Canonical: RobotAction::NavigateToRoom
        elif action in ("NavigateToRoom", "Navigate"):
            room = params.get("room", "").strip()
            self.get_logger().info(f"📍 Navigation Intent Received for: {room.upper()}")
            self._start_navigation_to_room(room)

        # Canonical: RobotAction::NavigateTo { x, y }
        elif action == "NavigateTo":
            x = float(params.get("x", 0.0))
            y = float(params.get("y", 0.0))
            self.get_logger().info(f"📍 Metric Navigation Target Received: x={x:.2f}, y={y:.2f}")
            self._start_navigation_to_coordinates(x, y)

        # Canonical: RobotAction::LookAt { x, y, z }
        elif action == "LookAt":
            target_x = float(params.get("x", 0.0))
            target_y = float(params.get("y", 0.0))
            # Default to neutral neck height (0.645 m) if z is unspecified
            target_z = float(params.get("z", 0.645))
            self.get_logger().info(
                f"👀 [ACTION] LookAt request: target=({target_x:.2f}, {target_y:.2f}, {target_z:.2f})"
            )
            self.execute_look_at(target_x, target_y, target_z)

        elif action == "Express":
            emotion = params.get("emotion", "neutral")
            self.get_logger().info(f"😊 Facial Expression Intent Received: {emotion}")

        elif action == "Speak":
            pass

        elif action == "Move":
            linear_x = float(params.get("linear_x", 0.0))
            angular_z = float(params.get("angular_z", 0.0))
            self._publish_cmd_vel(linear_x, angular_z)

        else:
            self.get_logger().warning(f"⚠️ Unknown or unhandled RobotAction: {action}")


def main(args=None):
    rclpy.init(args=args)
    node = KernelBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.running = False
        node.navigating = False
        node._publish_cmd_vel(0.0, 0.0)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
