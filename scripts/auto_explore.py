#!/usr/bin/env python3
"""
GRaCEmo ViRa — Autonomous Multi-Room LiDAR Explorer Node
Correctly maps 360 LaserScan angles [-pi, +pi] to steer through doorways and avoid obstacles.
"""

import sys
import time
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class AutoExplorer(Node):
    def __init__(self):
        super().__init__("gracemo_auto_explorer")

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        self.timer = self.create_timer(0.05, self._control_loop)  # 20Hz
        self.latest_scan = None
        self.state = "EXPLORING"
        self.turn_direction = 1.0
        self.turn_end_time = 0.0

        self.get_logger().info("🤖 ViRa Autonomous LiDAR Navigator Active! Scanning 360° environment...")

    def _on_scan(self, msg: LaserScan):
        self.latest_scan = msg

    def _control_loop(self):
        if not self.latest_scan or not self.latest_scan.ranges:
            return

        ranges = self.latest_scan.ranges
        angle_min = self.latest_scan.angle_min
        inc = self.latest_scan.angle_increment

        front_dists = []
        left_dists = []
        right_dists = []

        for i, r in enumerate(ranges):
            # Calculate exact angle relative to robot forward heading (0 rad)
            angle = angle_min + (i * inc)

            # Filter valid range: inf or nan means clear space beyond max range (12m)
            if math.isnan(r) or r < 0.10:
                dist = 12.0
            elif math.isinf(r):
                dist = 12.0
            else:
                dist = r

            # Sector classification
            if -0.52 <= angle <= 0.52:         # Front (-30° to +30°)
                front_dists.append(dist)
            elif 0.52 < angle <= 1.83:         # Left (+30° to +105°)
                left_dists.append(dist)
            elif -1.83 <= angle < -0.52:       # Right (-105° to -30°)
                right_dists.append(dist)

        front_min = min(front_dists) if front_dists else 12.0
        left_min = min(left_dists) if left_dists else 12.0
        right_min = min(right_dists) if right_dists else 12.0

        now = time.time()
        twist = Twist()

        if self.state == "BACKING_UP":
            if now < self.turn_end_time:
                twist.linear.x = -0.3
                twist.angular.z = 0.5 * self.turn_direction
            else:
                self.state = "TURNING"
                self.turn_end_time = now + 1.0

        elif self.state == "TURNING":
            if now < self.turn_end_time and front_min < 1.0:
                twist.linear.x = 0.0
                twist.angular.z = 1.2 * self.turn_direction
            else:
                self.state = "EXPLORING"

        elif self.state == "EXPLORING":
            if front_min < 0.40:
                # Emergency close to obstacle: back up
                self.state = "BACKING_UP"
                self.turn_direction = 1.0 if left_min > right_min else -1.0
                self.turn_end_time = now + 0.8
                twist.linear.x = -0.3
                twist.angular.z = 0.5 * self.turn_direction

            elif front_min < 0.90:
                # Wall or door frame ahead: turn toward the more open side
                self.state = "TURNING"
                self.turn_direction = 1.0 if left_min > right_min else -1.0
                self.turn_end_time = now + (1.2 if front_min < 0.6 else 0.8)
                twist.linear.x = 0.05
                twist.angular.z = 1.2 * self.turn_direction

            else:
                # Clear path forward: drive forward and center between walls
                twist.linear.x = 0.50
                # Gentle corridor centering
                diff = left_min - right_min
                twist.angular.z = max(min(0.25 * diff, 0.4), -0.4)

        self.cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = AutoExplorer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        twist = Twist()
        node.cmd_pub.publish(twist)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
