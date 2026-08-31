#!/usr/bin/env python3
"""
GRaCEmo ViRa — Smart Multi-Room Frontier & Doorway Exploration Node
Actively detects doorways, hunts open rooms, and eliminates back-and-forth corridor ping-pong.
"""

import sys
import time
import math
import random
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class SmartMultiRoomExplorer(Node):
    def __init__(self):
        super().__init__("smart_multi_room_explorer")

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        self.timer = self.create_timer(0.05, self._control_loop)  # 20Hz
        self.latest_scan = None

        # State machine
        self.state = "HUNTING_OPENING"
        self.target_heading_angle = 0.0
        self.state_end_time = 0.0
        self.last_turn_dir = 1.0
        self.stuck_detect_time = time.time()
        self.room_drive_timeout = 0.0

        self.get_logger().info("🏠 Smart Multi-Room Explorer Online: Hunting doorways and exploring all 4 rooms...")

    def _on_scan(self, msg: LaserScan):
        self.latest_scan = msg

    def _get_sector_distances(self):
        ranges = self.latest_scan.ranges
        angle_min = self.latest_scan.angle_min
        inc = self.latest_scan.angle_increment

        sectors = {
            "front": [],
            "front_left": [],
            "front_right": [],
            "left_90": [],
            "right_90": [],
            "rear": []
        }

        # Store (angle, distance) pairs
        all_readings = []

        for i, r in enumerate(ranges):
            angle = angle_min + (i * inc)
            if math.isnan(r) or r < 0.10:
                dist = 12.0
            elif math.isinf(r):
                dist = 12.0
            else:
                dist = r

            all_readings.append((angle, dist))

            if -0.35 <= angle <= 0.35:          # Front (-20° to +20°)
                sectors["front"].append(dist)
            elif 0.35 < angle <= 1.05:          # Front-Left (+20° to +60°)
                sectors["front_left"].append(dist)
            elif -1.05 <= angle < -0.35:        # Front-Right (-60° to -20°)
                sectors["front_right"].append(dist)
            elif 1.05 < angle <= 2.09:          # Left (+60° to +120°)
                sectors["left_90"].append(dist)
            elif -2.09 <= angle < -1.05:        # Right (-120° to -60°)
                sectors["right_90"].append(dist)
            else:
                sectors["rear"].append(dist)

        def safe_min(lst):
            return min(lst) if lst else 12.0

        def safe_max(lst):
            return max(lst) if lst else 0.0

        return {
            "front_min": safe_min(sectors["front"]),
            "front_left_min": safe_min(sectors["front_left"]),
            "front_right_min": safe_min(sectors["front_right"]),
            "left_max": safe_max(sectors["left_90"]),
            "right_max": safe_max(sectors["right_90"]),
            "left_min": safe_min(sectors["left_90"]),
            "right_min": safe_min(sectors["right_90"]),
            "all": all_readings
        }

    def _find_deepest_opening(self, readings):
        """Find the angle with the longest line of sight (doorway or deep room)."""
        # Look in forward and side arcs [-135° to +135°]
        valid = [(ang, dist) for ang, dist in readings if -2.35 <= ang <= 2.35]
        if not valid:
            return 0.0, 5.0
        # Return angle of max distance
        best = max(valid, key=lambda item: item[1])
        return best[0], best[1]

    def _control_loop(self):
        if not self.latest_scan:
            return

        d = self._get_sector_distances()
        now = time.time()
        twist = Twist()

        front = d["front_min"]

        # Emergency obstacle avoidance
        if front < 0.45 and self.state != "REVERSING":
            self.state = "REVERSING"
            self.state_end_time = now + 0.9
            self.last_turn_dir = 1.0 if d["left_min"] > d["right_min"] else -1.0

        # State 1: Reversing away from wall
        if self.state == "REVERSING":
            if now < self.state_end_time:
                twist.linear.x = -0.35
                twist.angular.z = 0.6 * self.last_turn_dir
            else:
                # Find deepest doorway/room opening and turn toward it
                best_angle, best_dist = self._find_deepest_opening(d["all"])
                self.state = "TURNING_TO_OPENING"
                self.target_heading_angle = best_angle
                turn_time = max(abs(best_angle) / 1.4, 0.6)
                self.state_end_time = now + turn_time
                self.last_turn_dir = 1.0 if best_angle > 0 else -1.0

        # State 2: Turning toward the detected doorway or open room
        elif self.state == "TURNING_TO_OPENING":
            if now < self.state_end_time and front < 1.2:
                twist.linear.x = 0.05
                twist.angular.z = 1.3 * self.last_turn_dir
            else:
                # Doorway aligned! Enter room and commit forward
                self.state = "PENETRATING_ROOM"
                self.state_end_time = now + 4.0  # Drive 4 seconds deep into room

        # State 3: Driving deep into a room through the doorway
        elif self.state == "PENETRATING_ROOM":
            if front < 0.65 or now > self.state_end_time:
                # Room reached or wall approached: resume hunting openings
                self.state = "HUNTING_OPENING"
            else:
                twist.linear.x = 0.55
                # Slight obstacle steering
                if d["front_left_min"] < 0.6:
                    twist.angular.z = -0.4
                elif d["front_right_min"] < 0.6:
                    twist.angular.z = 0.4

        # State 4: Default hunting & hallway navigation
        elif self.state == "HUNTING_OPENING":
            # Check if there's an open doorway on the left or right side (> 3.5m deep)
            if d["left_max"] > 4.0 and d["front_left_min"] > 1.2:
                self.state = "TURNING_TO_OPENING"
                self.last_turn_dir = 1.0
                self.state_end_time = now + 1.1
            elif d["right_max"] > 4.0 and d["front_right_min"] > 1.2:
                self.state = "TURNING_TO_OPENING"
                self.last_turn_dir = -1.0
                self.state_end_time = now + 1.1
            elif front < 0.9:
                best_angle, best_dist = self._find_deepest_opening(d["all"])
                self.state = "TURNING_TO_OPENING"
                self.last_turn_dir = 1.0 if best_angle > 0 else -1.0
                self.state_end_time = now + max(abs(best_angle) / 1.4, 0.7)
            else:
                twist.linear.x = 0.50
                # Corridor centering
                side_diff = d["left_min"] - d["right_min"]
                twist.angular.z = max(min(0.3 * side_diff, 0.35), -0.35)

        self.cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = SmartMultiRoomExplorer()
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
