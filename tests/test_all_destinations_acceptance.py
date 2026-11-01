import functools
print_flush = functools.partial(print, flush=True)
#!/usr/bin/env python3
"""
COMPREHENSIVE ALL-DESTINATION AUTONOMOUS ACCEPTANCE TEST SUITE
============================================================
Validates autonomous navigation and physical arrival verification
for all 6 canonical apartment destinations:
1. Living Room (4.0, -2.5)
2. Hallway (0.0, 0.0)
3. Kitchen (-5.0, -2.5)
4. Bedroom (-5.0, 2.2)
5. Study (4.5, 3.0)
6. Lab (2.5, 2.0)
"""

import sys
import time
import math
import json
import rclpy
import tf2_ros
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

EXPECTED_DESTINATIONS = {
    "living_room": (4.0, -2.5, 0.65),
    "hallway": (0.0, 0.0, 0.65),
    "kitchen": (-5.0, -2.5, 0.65),
    "bedroom": (-5.0, 2.2, 0.65),
    "study": (4.5, 3.0, 0.65),
    "lab": (2.5, 2.0, 0.65),
}

class MultiDestinationAcceptanceTester(Node):
    def __init__(self):
        super().__init__("multi_destination_tester")
        self.map_x = 0.0
        self.map_y = 0.0
        self.has_map_pose = False
        self.last_cmd = Twist()
        self.feedback_history = []
        self.spoken_texts = []
        
        qos_best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        qos_reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        qos_transient = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)

        self.amcl_sub = self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self.on_amcl, qos_transient)
        self.cmd_sub = self.create_subscription(Twist, "/cmd_vel", self.on_cmd, qos_reliable)
        self.fb_sub = self.create_subscription(String, "/coordinator/feedback", self.on_fb, qos_reliable)
        self.spoken_sub = self.create_subscription(String, "/interaction/spoken_feedback", self.on_spoken, qos_reliable)
        self.user_input_pub = self.create_publisher(String, "/interaction/user_input", 10)
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    def get_robot_pose(self):
        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
            return t.transform.translation.x, t.transform.translation.y
        except Exception:
            return self.map_x, self.map_y

    def on_amcl(self, msg):
        self.map_x = msg.pose.pose.position.x
        self.map_y = msg.pose.pose.position.y
        self.has_map_pose = True

    def on_cmd(self, msg):
        self.last_cmd = msg

    def on_fb(self, msg):
        try:
            data = json.loads(msg.data)
            self.feedback_history.append(data)
            print_flush(f"       [FB] state={data.get('state')}: {data.get('speech', '')[:60]}", flush=True)
        except Exception:
            pass

    def on_spoken(self, msg):
        try:
            data = json.loads(msg.data)
            self.spoken_texts.append(data.get("text", ""))
        except Exception:
            pass

def test_destination(node, dest_key, timeout_sec=150.0):
    tx, ty, tol = EXPECTED_DESTINATIONS[dest_key]
    print_flush(f"\n---> Testing Destination: '{dest_key}' (target: X={tx:.1f}, Y={ty:.1f}, tol<={tol:.2f}m)")
    
    # Wait for subscriber and publisher matches
    while node.user_input_pub.get_subscription_count() == 0 or node.fb_sub.get_publisher_count() == 0:
        rclpy.spin_once(node, timeout_sec=0.1)
        
    for _ in range(5):
        rclpy.spin_once(node, timeout_sec=0.1)
        
    start_map_x, start_map_y = node.get_robot_pose()
    print_flush(f"     Start Map Pose: X={start_map_x:.3f}, Y={start_map_y:.3f}")
    
    node.feedback_history.clear()
    node.spoken_texts.clear()
    
    # Dispatch navigation command
    msg = String()
    msg.data = f"navigate to {dest_key}"
    node.user_input_pub.publish(msg)
    
    start_time = time.time()
    reached = False
    
    while time.time() - start_time < timeout_sec:
        rclpy.spin_once(node, timeout_sec=0.1)
        for fb in node.feedback_history:
            if fb.get("state") == "SUCCEEDED":
                reached = True
                break
            elif fb.get("state") == "FAILED":
                print_flush(f"     [FAIL] Coordinator reported state FAILED: {fb}", flush=True)
                break
        if reached:
            break

    # Spin 2s to flush arrival feedback
    end_spin = time.time()
    while time.time() - end_spin < 2.0:
        rclpy.spin_once(node, timeout_sec=0.1)

    elapsed = time.time() - start_time
    curr_x, curr_y = node.get_robot_pose()
    dist_error = math.hypot(curr_x - tx, curr_y - ty)
    total_disp = math.hypot(curr_x - start_map_x, curr_y - start_map_y)
    
    print_flush(f"     Final Map Pose:   X={curr_x:.3f}, Y={curr_y:.3f}")
    print_flush(f"     Distance to Goal: {dist_error:.3f}m (tolerance: {tol:.2f}m)")
    print_flush(f"     Displacement:     {total_disp:.3f}m")
    print_flush(f"     Elapsed Time:     {elapsed:.1f}s")
    print_flush(f"     CmdVel after:     lin={node.last_cmd.linear.x:.3f}, ang={node.last_cmd.angular.z:.3f}")
    print_flush(f"     Spoken Feedback:  {node.spoken_texts}")
    
    assert reached, f"Navigation to {dest_key} did not confirm SUCCEEDED!"
    assert dist_error <= tol, f"Arrival error ({dist_error:.3f}m) exceeds tolerance ({tol}m)!"
    assert abs(node.last_cmd.linear.x) < 0.05 and abs(node.last_cmd.angular.z) < 0.05, "Robot failed to halt safely!"
    print_flush(f"     ✓ PASS: Arrived and verified at '{dest_key}'")
    return True

def run_all_tests():
    print_flush("=" * 75)
    print_flush("  🚀 FULL MULTI-DESTINATION LIVE ACCEPTANCE TEST: ALL 6 APARTMENT ROOMS")
    print_flush("=" * 75)
    
    rclpy.init()
    node = MultiDestinationAcceptanceTester()
    
    # Wait for AMCL pose
    t0 = time.time()
    while time.time() - t0 < 5.0 and not node.has_map_pose:
        rclpy.spin_once(node, timeout_sec=0.1)
        
    print_flush(f"Initial Robot Location: X={node.map_x:.3f}, Y={node.map_y:.3f}")
    
    # Test sequence covering the full floor plan
    test_sequence = ["hallway", "living_room", "hallway", "bedroom", "kitchen", "study", "lab"]
    results = []
    
    for idx, dest in enumerate(test_sequence, 1):
        leg_name = f"Leg {idx}: {dest}"
        try:
            ok = test_destination(node, dest)
            results.append((leg_name, "PASS", f"Error: {math.hypot(node.map_x - EXPECTED_DESTINATIONS[dest][0], node.map_y - EXPECTED_DESTINATIONS[dest][1]):.3f}m"))
        except AssertionError as e:
            print_flush(f"     ❌ FAIL: {e}")
            results.append((leg_name, f"FAIL: {e}", "Aborted"))
            break
            
    node.destroy_node()
    rclpy.shutdown()
    
    print_flush("\n" + "=" * 75)
    print_flush("  MULTI-DESTINATION TEST RESULTS SUMMARY:")
    for leg, status, detail in results:
        print_flush(f"    - {leg:25s}: {status} ({detail})")
    print_flush("=" * 75 + "\n")
    
    all_passed = all(status == "PASS" for _, status, _ in results) and len(results) == len(test_sequence)
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
