"""
GRaCEmo ViRa — ROS 2 to Kernel Bridge Node
Bridges ROS 2 sensory streams (/camera/image_raw, /odom, /scan) and motor commands (/cmd_vel)
with the GRaCEmo Kernel event bus.
"""

import sys
import time
import json
import threading
import requests
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Image


class KernelBridgeNode(Node):
    def __init__(self):
        super().__init__("gracemo_kernel_bridge")

        self.declare_parameter("kernel_url", "http://127.0.0.1:7780")
        self.kernel_url = self.get_parameter("kernel_url").get_parameter_value().string_value

        self.get_logger().info(f"Starting GRaCEmo ROS 2 Bridge connected to: {self.kernel_url}")

        # 1. Motor Command Publisher (/cmd_vel)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # 2. Odometry Subscriber (/odom)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._on_odom, 10)

        # 3. LiDAR Scan Subscriber (/scan)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        self.last_emit_time = 0.0
        self.running = True

        # 4. Start Kernel Action Listener thread (ActionRequested -> /cmd_vel)
        threading.Thread(target=self._listen_kernel_actions, daemon=True).start()

    def _on_odom(self, msg: Odometry):
        now = time.time()
        if now - self.last_emit_time > 0.5:
            pos = msg.pose.pose.position
            vel = msg.twist.twist.linear
            self._emit_event("RobotStateUpdated", {
                "position": {"x": round(pos.x, 2), "y": round(pos.y, 2), "z": round(pos.z, 2)},
                "linear_velocity": round(vel.x, 2)
            })
            self.last_emit_time = now

    def _on_scan(self, msg: LaserScan):
        # Check minimum range for obstacle warning
        if msg.ranges:
            valid_ranges = [r for r in msg.ranges if msg.range_min < r < msg.range_max]
            if valid_ranges and min(valid_ranges) < 0.35:
                self._emit_event("ObstacleWarning", {
                    "min_distance": round(min(valid_ranges), 2)
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
            self.cmd_vel_pub.publish(twist)
            self.get_logger().info(f"Executing Move: linear_x={linear_x}, angular_z={angular_z}")

        elif action == "Stop":
            self.cmd_vel_pub.publish(Twist())
            self.get_logger().info("Executing Emergency Stop")


def main(args=None):
    rclpy.init(args=args)
    node = KernelBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.running = False
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
