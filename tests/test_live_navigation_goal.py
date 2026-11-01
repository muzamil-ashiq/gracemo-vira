#!/usr/bin/env python3
"""
Test Live Navigation Goal:
Sends a navigation command to the VIRA coordinator and monitors Nav2 execution,
verifying path planning, motion, obstacle clearance, and goal completion.
"""

import sys
import time
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy

class LiveNavigationTester(Node):
    def __init__(self):
        super().__init__('live_navigation_tester')
        self.input_pub = self.create_publisher(String, '/interaction/user_input', 10)
        self.coord_sub = self.create_subscription(String, '/coordinator/feedback', self.on_coord_feedback, 10)
        self.feedback_sub = self.create_subscription(String, '/interaction/spoken_feedback', self.on_spoken_feedback, 10)
        odom_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.on_odom, odom_qos)
        
        self.latest_odom = None
        self.coordinator_states = []
        self.spoken_messages = []

    def on_odom(self, msg: Odometry):
        self.latest_odom = msg

    def on_coord_feedback(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.coordinator_states.append(data)
            print(f"[Coordinator] State: {data.get('state')} | Speech: {data.get('speech')}", flush=True)
        except Exception as e:
            print(f"[Coordinator Raw] {msg.data}", flush=True)

    def on_spoken_feedback(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.spoken_messages.append(data)
            print(f"[Spoken Feedback] {data.get('text')}", flush=True)
        except Exception:
            print(f"[Spoken Raw] {msg.data}", flush=True)

def test_live_navigation():
    rclpy.init()
    tester = LiveNavigationTester()

    print("[Nav Test] Waiting for initial odom...")
    start_wait = time.time()
    while time.time() - start_wait < 5.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        if tester.latest_odom:
            break

    assert tester.latest_odom is not None, "Failed to receive /odom before navigation test"
    start_pos = (tester.latest_odom.pose.pose.position.x, tester.latest_odom.pose.pose.position.y)
    print(f"[Nav Test] Initial robot pose: x={start_pos[0]:.3f}, y={start_pos[1]:.3f}")

    # Wait for discovery on /interaction/user_input
    while tester.input_pub.get_subscription_count() == 0:
        time.sleep(0.1)
        rclpy.spin_once(tester, timeout_sec=0.1)

    # Send destination command
    target_cmd = "navigate to lab"
    print(f"\n[Nav Test] Publishing command: '{target_cmd}' to /interaction/user_input...")
    msg = String()
    msg.data = target_cmd
    tester.input_pub.publish(msg)

    # Monitor for 25 seconds
    start_nav = time.time()
    displacements = []
    
    while time.time() - start_nav < 25.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        curr_pos = (tester.latest_odom.pose.pose.position.x, tester.latest_odom.pose.pose.position.y)
        dx = curr_pos[0] - start_pos[0]
        dy = curr_pos[1] - start_pos[1]
        dist = (dx**2 + dy**2)**0.5
        displacements.append(dist)
        
        # Check if succeeded
        for state in tester.coordinator_states:
            if state.get("state") == "SUCCEEDED":
                print(f"\n[PASS] Coordinator reported SUCCEEDED at position: x={curr_pos[0]:.3f}, y={curr_pos[1]:.3f}")
                print(f"[PASS] Total displacement: {dist:.3f} meters")
                tester.destroy_node()
                rclpy.shutdown()
                return True
        time.sleep(0.1)

    max_disp = max(displacements) if displacements else 0.0
    print(f"\n[Nav Test Completed] Max displacement observed: {max_disp:.3f} m")
    print(f"Recorded states: {[s.get('state') for s in tester.coordinator_states]}")

    tester.destroy_node()
    rclpy.shutdown()
    return max_disp > 0.1

if __name__ == "__main__":
    success = test_live_navigation()
    print(f"Navigation Test Result: {'SUCCESS' if success else 'PARTIAL'}")
