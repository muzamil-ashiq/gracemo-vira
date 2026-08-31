#!/usr/bin/env python3
"""
GRaCEmo ViRa — Closed-Loop Dynamic APF & Odometry Navigator
Pure closed-loop feedback: reads live /odom and /scan at 20Hz.
Uses Artificial Potential Fields (APF) to dynamically steer through doorway centers
and repel from walls, completely eliminating open-loop timer drift.
"""

import sys
import time
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
import requests

KERNEL_URL = "http://127.0.0.1:7780"

ROOM_WAYPOINTS = {
    "kitchen":  [(3.6, 0.0), (3.6, 2.0), (4.2, 3.6)],
    "bedroom":  [(-2.3, 0.0), (-2.3, 2.0), (-4.5, 4.0)],
    "living":   [(4.0, 0.0), (4.0, -2.0), (4.2, -4.0)],
    "study":    [(-1.3, 0.0), (-1.3, -2.0), (-4.5, -4.0)],
    "hallway":  [(0.0, 0.0)]
}


class ClosedLoopNavigator(Node):
    def __init__(self, target_room: str):
        super().__init__("closed_loop_navigator")

        self.target_room = target_room.lower()
        if self.target_room not in ROOM_WAYPOINTS:
            self.get_logger().error(f"Unknown room: {target_room}")
            sys.exit(1)

        self.waypoints = ROOM_WAYPOINTS[self.target_room]
        self.current_wp_idx = 0

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.has_odom = False

        self.latest_scan = None
        self.reached = False

        self.timer = self.create_timer(0.05, self._control_loop)  # 20Hz
        self.get_logger().info(f"🎯 Closed-Loop Navigation Active: Navigating to {self.target_room.upper()}...")

    def _on_odom(self, msg: Odometry):
        pos = msg.pose.pose.position
        self.cur_x = pos.x
        self.cur_y = pos.y

        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.cur_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.has_odom = True

    def _on_scan(self, msg: LaserScan):
        self.latest_scan = msg

    def _control_loop(self):
        if not self.has_odom or self.reached:
            return

        if self.current_wp_idx >= len(self.waypoints):
            self.reached = True
            self.cmd_pub.publish(Twist())
            self.get_logger().info(f"✅ Arrived at {self.target_room.upper()} destination!")
            # Emit arrival to Kernel
            try:
                requests.post(f"{KERNEL_URL}/emit", json={"event_type": "RobotArrived", "payload": {"room": self.target_room}, "source": "ClosedLoopNav"}, timeout=0.5)
            except Exception:
                pass
            rclpy.shutdown()
            return

        target_x, target_y = self.waypoints[self.current_wp_idx]

        dx = target_x - self.cur_x
        dy = target_y - self.cur_y
        dist = math.hypot(dx, dy)

        # Waypoint reached threshold
        if dist < 0.35:
            self.current_wp_idx += 1
            self.get_logger().info(f"✓ Waypoint {self.current_wp_idx}/{len(self.waypoints)} reached. Progressing...")
            return

        target_heading = math.atan2(dy, dx)
        angle_diff = (target_heading - self.cur_yaw + math.pi) % (2 * math.pi) - math.pi

        # 1. Attractive force
        twist = Twist()

        # 2. LiDAR Wall Repulsion (Safety Bubble)
        repulse_angular = 0.0
        if self.latest_scan and self.latest_scan.ranges:
            ranges = self.latest_scan.ranges
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_increment
            for i, r in enumerate(ranges):
                if 0.15 < r < 0.55:  # Wall is close
                    beam_angle = ang_min + i * inc
                    # If obstacle on left (+angle), push right (-angular); if right (-angle), push left (+angular)
                    weight = (0.55 - r) / 0.55
                    repulse_angular += -1.5 * weight * math.sin(beam_angle)

        # 3. Closed-loop PID Heading & Speed
        if abs(angle_diff) > 0.50:
            # Turn in place toward target
            twist.linear.x = 0.05
            twist.angular.z = (1.2 if angle_diff > 0 else -1.2) + repulse_angular
        else:
            # Drive forward with proportional steering
            speed = min(0.65, max(0.20, 0.8 * dist))
            twist.linear.x = speed
            twist.angular.z = 1.4 * angle_diff + repulse_angular

        self.cmd_pub.publish(twist)


def main():
    if len(sys.argv) < 2:
        print("Usage: closed_loop_nav.py <room>")
        sys.exit(1)

    target_room = sys.argv[1]
    rclpy.init()
    node = ClosedLoopNavigator(target_room)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.cmd_pub.publish(Twist())
        node.destroy_node()


if __name__ == "__main__":
    main()
