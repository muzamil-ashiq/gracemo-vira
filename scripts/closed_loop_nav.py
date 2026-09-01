#!/usr/bin/env python3
"""
GRaCEmo ViRa — Closed-Loop Dynamic APF & Odometry Navigator
Pure closed-loop feedback: reads live /odom and /scan at 20Hz.
Uses Artificial Potential Fields (APF) to dynamically steer through doorway centers,
repel from walls, and smoothly park in front of room furniture without circling.
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

# Updated waypoints matching the 4-room apartment layout:
# Doorways at X=±5.0 on hallway walls Y=±1.0
ROOM_WAYPOINTS = {
    "bedroom":  [(-5.0, 0.0), (-5.0, 1.5), (-5.0, 3.5)],
    "study":    [(5.0, 0.0),  (5.0, 1.5),  (5.0, 3.5)],
    "kitchen":  [(-5.0, 0.0), (-5.0, -1.5), (-5.0, -3.5)],
    "living":   [(5.0, 0.0),  (5.0, -1.5),  (5.0, -3.5)],
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
            self._stop_and_finish()
            return

        target_x, target_y = self.waypoints[self.current_wp_idx]
        is_final_wp = (self.current_wp_idx == len(self.waypoints) - 1)

        dx = target_x - self.cur_x
        dy = target_y - self.cur_y
        dist = math.hypot(dx, dy)

        # Check front obstacle clearance
        min_front_obs = 12.0
        if self.latest_scan and self.latest_scan.ranges:
            ranges = self.latest_scan.ranges
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_increment
            front_readings = []
            for i, r in enumerate(ranges):
                if 0.15 < r < 12.0 and not math.isnan(r) and not math.isinf(r):
                    beam_angle = ang_min + i * inc
                    if -0.40 <= beam_angle <= 0.40:
                        front_readings.append(r)
            if front_readings:
                min_front_obs = min(front_readings)

        # Waypoint arrival conditions
        arrival_threshold = 0.55 if is_final_wp else 0.40
        if dist < arrival_threshold or (is_final_wp and dist < 0.85 and min_front_obs < 0.70):
            if is_final_wp:
                self._stop_and_finish()
                return
            else:
                self.current_wp_idx += 1
                self.get_logger().info(f"✓ Doorway cleared! Waypoint {self.current_wp_idx}/{len(self.waypoints)} reached.")
                return

        target_heading = math.atan2(dy, dx)
        angle_diff = (target_heading - self.cur_yaw + math.pi) % (2 * math.pi) - math.pi

        twist = Twist()

        # LiDAR Wall Repulsion (Safety Bubble)
        repulse_angular = 0.0
        if self.latest_scan and self.latest_scan.ranges:
            ranges = self.latest_scan.ranges
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_increment
            for i, r in enumerate(ranges):
                if 0.15 < r < 0.50:  # Wall is close
                    beam_angle = ang_min + i * inc
                    weight = (0.50 - r) / 0.50
                    repulse_angular += -1.2 * weight * math.sin(beam_angle)

        if abs(angle_diff) > 0.45:
            # Heading alignment turn
            twist.linear.x = 0.05
            twist.angular.z = (1.1 if angle_diff > 0 else -1.1) + (0.5 * repulse_angular)
        else:
            # Smooth proportional driving
            speed = min(0.60, max(0.18, 0.75 * dist))
            if is_final_wp and dist < 1.0:
                speed = 0.30  # Slow down smoothly when parking
            twist.linear.x = speed
            twist.angular.z = 1.3 * angle_diff + repulse_angular

        self.cmd_pub.publish(twist)

    def _stop_and_finish(self):
        self.reached = True
        self.cmd_pub.publish(Twist())  # Clean stop
        self.get_logger().info(f"✅ Safely parked in {self.target_room.upper()}!")
        try:
            requests.post(f"{KERNEL_URL}/emit", json={"event_type": "RobotArrived", "payload": {"room": self.target_room}, "source": "ClosedLoopNav"}, timeout=0.5)
        except Exception:
            pass
        rclpy.shutdown()


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
