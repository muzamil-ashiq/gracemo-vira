#!/usr/bin/env python3
import sys
import time
import math
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

class DestinationTester(Node):
    def __init__(self, target_dest):
        super().__init__("destination_tester")
        self.target_dest = target_dest
        
        self.current_x = 0.0
        self.current_y = 0.0
        self.map_x = 0.0
        self.map_y = 0.0
        self.has_map_pose = False
        self.last_cmd_vel = Twist()
        self.feedbacks = []
        self.spoken = []
        
        best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        transient = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)

        self.odom_sub = self.create_subscription(Odometry, "/odom", self.on_odom, best_effort)
        self.amcl_sub = self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self.on_amcl, transient)
        self.cmd_sub = self.create_subscription(Twist, "/cmd_vel", self.on_cmd, reliable)
        self.fb_sub = self.create_subscription(String, "/coordinator/feedback", self.on_fb, reliable)
        self.spoken_sub = self.create_subscription(String, "/interaction/spoken_feedback", self.on_spoken, reliable)
        self.input_pub = self.create_publisher(String, "/interaction/user_input", 10)

    def on_odom(self, msg):
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y

    def on_amcl(self, msg):
        self.map_x = msg.pose.pose.position.x
        self.map_y = msg.pose.pose.position.y
        self.has_map_pose = True

    def on_cmd(self, msg):
        self.last_cmd_vel = msg

    def on_fb(self, msg):
        try:
            data = json.loads(msg.data)
            self.feedbacks.append(data)
            print(f"[{time.strftime('%H:%M:%S')}] FB: {data.get('state')} | speech='{data.get('speech')}' | details={data.get('details')}")
        except Exception:
            pass

    def on_spoken(self, msg):
        try:
            data = json.loads(msg.data)
            self.spoken.append(data)
            print(f"[{time.strftime('%H:%M:%S')}] SPOKEN: '{data.get('text')}'")
        except Exception:
            pass

def run_test(dest_name, timeout_sec=90.0):
    rclpy.init()
    tester = DestinationTester(dest_name)
    
    print(f"=== TESTING AUTONOMOUS NAVIGATION TO: {dest_name} ===")
    
    # 1. Wait for publishers/subscribers and initial pose
    t0 = time.time()
    while time.time() - t0 < 5.0 and tester.input_pub.get_subscription_count() == 0:
        rclpy.spin_once(tester, timeout_sec=0.1)
    
    # Spin a bit to get current pose
    for _ in range(10):
        rclpy.spin_once(tester, timeout_sec=0.1)
        
    start_x = tester.current_x
    start_y = tester.current_y
    start_map_x = tester.map_x if tester.has_map_pose else start_x
    start_map_y = tester.map_y if tester.has_map_pose else start_y
    
    print(f"Initial Pose: odom=({start_x:.3f}, {start_y:.3f}), map=({start_map_x:.3f}, {start_map_y:.3f})")
    print(f"Subscribers to user_input: {tester.input_pub.get_subscription_count()}")
    
    # 2. Publish goal command
    cmd = String()
    cmd.data = f"navigate to {dest_name}"
    tester.input_pub.publish(cmd)
    print(f"Published command: '{cmd.data}'")
    
    # 3. Monitor execution
    start_time = time.time()
    last_print = 0
    success = False
    failed = False
    
    while time.time() - start_time < timeout_sec:
        rclpy.spin_once(tester, timeout_sec=0.1)
        
        # Check feedback status
        for fb in tester.feedbacks:
            state = fb.get("state")
            if state == "SUCCEEDED":
                success = True
                break
            elif state == "FAILED":
                failed = True
                break
                
        if success or failed:
            break
            
        now = time.time()
        if now - last_print >= 3.0:
            last_print = now
            odom_disp = math.hypot(tester.current_x - start_x, tester.current_y - start_y)
            print(f"[{now - start_time:.1f}s] Pos: odom=({tester.current_x:.3f}, {tester.current_y:.3f}), disp={odom_disp:.3f}m | cmd_vel: lin={tester.last_cmd_vel.linear.x:.2f}, ang={tester.last_cmd_vel.angular.z:.2f}")

    # Spin 2 more seconds to catch trailing feedback
    for _ in range(20):
        rclpy.spin_once(tester, timeout_sec=0.1)

    final_odom_disp = math.hypot(tester.current_x - start_x, tester.current_y - start_y)
    final_map_disp = math.hypot(tester.map_x - start_map_x, tester.map_y - start_map_y)
    elapsed = time.time() - start_time
    
    print("\n--- TEST SUMMARY ---")
    print(f"Target Destination: {dest_name}")
    print(f"Final Odom Pose:    ({tester.current_x:.3f}, {tester.current_y:.3f})")
    print(f"Final Map Pose:     ({tester.map_x:.3f}, {tester.map_y:.3f})")
    print(f"Total Displacement: odom={final_odom_disp:.3f}m, map={final_map_disp:.3f}m")
    print(f"Elapsed Time:       {elapsed:.1f} seconds")
    print(f"Final Outcome:      {'SUCCESS' if success else ('FAILED' if failed else 'TIMEOUT')}")
    print(f"Final Velocity:     lin={tester.last_cmd_vel.linear.x:.3f}, ang={tester.last_cmd_vel.angular.z:.3f}")
    
    tester.destroy_node()
    rclpy.shutdown()
    return success

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "living_room"
    ok = run_test(dest)
    sys.exit(0 if ok else 1)
