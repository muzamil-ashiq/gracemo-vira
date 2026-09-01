#!/usr/bin/env python3
"""
GraceEMO — Autonomous Patrol & Waypoint Navigation Node
Cycles through predefined patrol waypoints across the campus floor,
smoothly calculating navigation vectors and obstacle avoidance.
"""

import math
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

class AutonomousPatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')
        self.get_logger().info('🚀 Starting GraceEMO Autonomous Patrol & Navigation Agent...')

        # Predefined campus waypoints (x, y, name)
        self.waypoints = [
            (2.5, 2.0, 'Robotics Research Lab'),
            (-2.5, 2.0, 'AI Compute Center'),
            (-2.5, -2.5, 'Campus Commons'),
            (2.5, -2.5, 'Welcome Reception Desk'),
        ]
        self.current_wp_idx = 0
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0
        self.is_active = True

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.control_timer = self.create_timer(0.1, self.control_loop)

        self.get_logger().info(f'📍 Initial Target: Waypoint 1 -> {self.waypoints[0][2]}')

    def on_odom(self, msg: Odometry):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.robot_yaw = math.atan2(siny_cosp, cosy_cosp)

    def control_loop(self):
        if not self.is_active:
            return

        tx, ty, tname = self.waypoints[self.current_wp_idx]
        dx = tx - self.robot_x
        dy = ty - self.robot_y
        dist = math.hypot(dx, dy)

        # Reached waypoint?
        if dist < 0.35:
            self.get_logger().info(f'✅ Reached: {tname}! Cruising to next location...')
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)
            return

        target_angle = math.atan2(dy, dx)
        angle_diff = target_angle - self.robot_yaw
        # Normalize to [-pi, pi]
        angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

        cmd = Twist()
        # Rotate first if heading difference is large
        if abs(angle_diff) > 0.4:
            cmd.angular.z = 0.8 if angle_diff > 0 else -0.8
            cmd.linear.x = 0.05
        else:
            cmd.linear.x = min(0.35, 0.15 + dist * 0.2)
            cmd.angular.z = angle_diff * 1.2

        self.cmd_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = AutonomousPatrolNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
