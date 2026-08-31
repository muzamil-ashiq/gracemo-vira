"""
GRaCEmo ViRa — ROS 2 to Kernel Bridge Node
Bridges ROS 2 sensory streams (/camera/image_raw, /odom, /scan) and motor commands (/cmd_vel)
with the GRaCEmo Kernel event bus.
Includes autonomous waypoint navigation for high-level room dispatch (k goto <room>).
"""

import sys
import time
import json
import math
import threading
import requests
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Image


ROOM_WAYPOINTS = {
    "kitchen":  [(3.6, 0.0), (3.6, 2.0), (4.2, 3.6)],
    "bedroom":  [(-2.3, 0.0), (-2.3, 2.0), (-4.5, 4.0)],
    "living":   [(4.0, 0.0), (4.0, -2.0), (4.2, -4.0)],
    "study":    [(-1.3, 0.0), (-1.3, -2.0), (-4.5, -4.0)],
    "hallway":  [(0.0, 0.0)]
}


class KernelBridgeNode(Node):
    def __init__(self):
        super().__init__("gracemo_kernel_bridge")

        self.declare_parameter("kernel_url", "http://127.0.0.1:7780")
        self.kernel_url = self.get_parameter("kernel_url").get_parameter_value().string_value

        self.get_logger().info(f"Starting GRaCEmo ROS 2 Bridge connected to: {self.kernel_url}")

        # 1. Motor Command Publisher (/cmd_vel)
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # 2. Odometry Subscriber (/odom)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._on_odom, 10)

        # 3. LiDAR Scan Subscriber (/scan)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw_rad = 0.0
        self.last_emit_time = 0.0
        self.running = True
        self.nav_thread = None

        # 4. Start Kernel Action Listener thread
        threading.Thread(target=self._listen_kernel_actions, daemon=True).start()

    def _on_odom(self, msg: Odometry):
        pos = msg.pose.pose.position
        self.current_x = pos.x
        self.current_y = pos.y

        # Calculate yaw
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.current_yaw_rad = math.atan2(siny_cosp, cosy_cosp)

        now = time.time()
        if now - self.last_emit_time > 0.5:
            vel = msg.twist.twist.linear
            self._emit_event("RobotStateUpdated", {
                "position": {"x": round(self.current_x, 2), "y": round(self.current_y, 2)},
                "linear_velocity": round(vel.x, 2)
            })
            self.last_emit_time = now

    def _on_scan(self, msg: LaserScan):
        if msg.ranges:
            valid = [r for r in msg.ranges if 0.15 < r < 12.0 and not math.isnan(r) and not math.isinf(r)]
            if valid and min(valid) < 0.35:
                self._emit_event("ObstacleWarning", {
                    "min_distance": round(min(valid), 2)
                })

    def _emit_event(self, event_type: str, payload: dict):
        try:
            requests.post(
                f"{self.kernel_url}/emit",
                json={"event_type": event_type, "payload": payload, "source": "ROS2Bridge"},
                timeout=0.2
            )
        except Exception:
            pass

    def _listen_kernel_actions(self):
        """Listen to SSE live event stream from Kernel."""
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
                            if event.get("event_type") == "ActionRequested":
                                self._handle_kernel_action(event.get("payload", {}))
            except Exception:
                time.sleep(1.0)

    def _handle_kernel_action(self, payload: dict):
        action = payload.get("action")
        params = payload.get("params", {})

        if action == "Move":
            linear_x = float(params.get("linear_x", 0.0))
            angular_z = float(params.get("angular_z", 0.0))
            twist = Twist()
            twist.linear.x = linear_x
            twist.angular.z = angular_z
            self.cmd_pub.publish(twist)

        elif action == "Stop":
            self.cmd_pub.publish(Twist())
            self.get_logger().info("Executing Stop")

        elif action == "Navigate":
            room = params.get("room", "").lower()
            if room in ROOM_WAYPOINTS:
                self.get_logger().info(f"🚀 Navigating to {room.upper()} via Doorway Waypoints...")
                waypoints = ROOM_WAYPOINTS[room]
                threading.Thread(target=self._execute_waypoints, args=(waypoints, room), daemon=True).start()

    def _execute_waypoints(self, waypoints: list, room_name: str):
        """Drive through doorway waypoints smoothly into target room."""
        for wx, wy in waypoints:
            while rclpy.ok() and self.running:
                dx = wx - self.current_x
                dy = wy - self.current_y
                dist = math.hypot(dx, dy)

                if dist < 0.40:
                    break

                target_heading = math.atan2(dy, dx)
                angle_diff = (target_heading - self.current_yaw_rad + math.pi) % (2 * math.pi) - math.pi

                twist = Twist()
                if abs(angle_diff) > 0.45:
                    twist.angular.z = 1.2 if angle_diff > 0 else -1.2
                    twist.linear.x = 0.05
                else:
                    twist.linear.x = 0.60
                    twist.angular.z = 0.9 * angle_diff

                self.cmd_pub.publish(twist)
                time.sleep(0.05)

        # Arrived at final waypoint
        self.cmd_pub.publish(Twist())
        self.get_logger().info(f"✅ Arrived in {room_name.upper()}!")
        self._emit_event("RobotArrived", {"room": room_name})


def main(args=None):
    rclpy.init(args=args)
    node = KernelBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.running = False
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
