#!/usr/bin/env python3
"""
LIVING ROOM & BEDROOM AUTONOMOUS NAVIGATION ACCEPTANCE TEST
==========================================================
Validates:
1. Living Room navigation from initial origin/hallway.
2. Bedroom navigation as a long-range regression check across apartment.
3. Accurate pose arrival within tolerance (<= 0.65m).
4. Safe stop verification (velocity <= 0.05 m/s).
5. Safety status and single-owner command pipeline.
"""

import sys
import time
import math
import json
import rclpy
import tf2_ros
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

class NavigationAcceptanceTester(Node):
    def __init__(self):
        super().__init__("nav_acceptance_tester")
        self.map_x = 0.0
        self.map_y = 0.0
        self.map_yaw = 0.0
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

    def on_amcl(self, msg: PoseWithCovarianceStamped):
        self.map_x = msg.pose.pose.position.x
        self.map_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.map_yaw = math.atan2(siny, cosy)
        self.has_map_pose = True

    def on_cmd(self, msg: Twist):
        self.last_cmd = msg

    def on_fb(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.feedback_history.append(data)
            sp = data.get("speech", data.get("state", ""))
            print(f"      [FEEDBACK] state={data.get('state')}: {sp[:70]}", flush=True)
        except Exception:
            pass

    def on_spoken(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.spoken_texts.append(data.get("text", ""))
        except Exception:
            pass

    def get_current_pose(self):
        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
            q = t.transform.rotation
            siny = 2.0 * (q.w * q.z + q.x * q.y)
            cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw = math.atan2(siny, cosy)
            return t.transform.translation.x, t.transform.translation.y, yaw
        except Exception:
            return self.map_x, self.map_y, self.map_yaw

def execute_navigation_test(tester: NavigationAcceptanceTester, target_name: str, target_coords: tuple, timeout_sec: float = 120.0):
    tx, ty, tyaw, tol = target_coords
    print(f"\n================================================================================")
    print(f"  🏁 EXECUTING MISSION: NAVIGATE TO {target_name.upper()}")
    print(f"================================================================================")

    # Ensure match on user_input_pub
    t_match = time.time()
    while tester.user_input_pub.get_subscription_count() == 0 and time.time() - t_match < 5.0:
        rclpy.spin_once(tester, timeout_sec=0.1)

    start_x, start_y, start_yaw = tester.get_current_pose()
    print(f"  Initial Pose:         X={start_x:.3f}, Y={start_y:.3f}, Yaw={math.degrees(start_yaw):.1f}°")
    print(f"  Target Goal:          X={tx:.3f}, Y={ty:.3f}, Yaw={math.degrees(tyaw):.1f}° (Frame: map)")
    print(f"  Tolerance Allowed:    {tol:.2f} m")

    tester.feedback_history.clear()
    tester.spoken_texts.clear()

    # Dispatch text navigation command
    cmd_msg = String()
    cmd_msg.data = f"navigate to {target_name}"
    print(f"  Dispatching command:  '{cmd_msg.data}'")
    tester.user_input_pub.publish(cmd_msg)

    start_time = time.time()
    last_telemetry = 0.0
    action_succeeded = False
    action_failed = False
    failure_details = None

    while time.time() - start_time < timeout_sec:
        rclpy.spin_once(tester, timeout_sec=0.1)
        now = time.time() - start_time

        # Periodic telemetry
        if now - last_telemetry >= 3.0:
            last_telemetry = now
            cx, cy, cyaw = tester.get_current_pose()
            d_remain = math.hypot(cx - tx, cy - ty)
            lin_v = tester.last_cmd.linear.x
            ang_v = tester.last_cmd.angular.z
            print(f"    T+{now:5.1f}s | Map=({cx:5.2f}, {cy:5.2f}) | DistToGoal={d_remain:4.2f}m | CmdVel=(lin:{lin_v:4.2f}, ang:{ang_v:4.2f})", flush=True)

        for fb in tester.feedback_history:
            if fb.get("state") == "SUCCEEDED":
                action_succeeded = True
                break
            elif fb.get("state") == "FAILED":
                action_failed = True
                failure_details = fb
                break

        if action_succeeded or action_failed:
            break

    # Wait 2.0s to ensure complete safe halt and flush final messages
    t_end = time.time()
    while time.time() - t_end < 2.0:
        rclpy.spin_once(tester, timeout_sec=0.1)

    duration = time.time() - start_time
    final_x, final_y, final_yaw = tester.get_current_pose()
    pos_error = math.hypot(final_x - tx, final_y - ty)
    total_displacement = math.hypot(final_x - start_x, final_y - start_y)
    final_lin_v = abs(tester.last_cmd.linear.x)
    final_ang_v = abs(tester.last_cmd.angular.z)

    print(f"\n  --- MISSION EXECUTION RESULTS ---")
    print(f"  Action Result:        {'SUCCEEDED' if action_succeeded else 'FAILED'}")
    print(f"  Duration:             {duration:.1f} s")
    print(f"  Final Robot Pose:     X={final_x:.3f}, Y={final_y:.3f}, Yaw={math.degrees(final_yaw):.1f}°")
    print(f"  Position Error:       {pos_error:.3f} m (Tolerance: {tol:.2f} m)")
    print(f"  Total Displacement:   {total_displacement:.3f} m")
    print(f"  Final Velocity:       Linear={final_lin_v:.3f} m/s, Angular={final_ang_v:.3f} rad/s")
    print(f"  Safe Stop Confirmed:  {final_lin_v <= 0.05 and final_ang_v <= 0.05}")
    print(f"  Spoken Output:        {tester.spoken_texts}")

    assert action_succeeded, f"Navigation to {target_name} did not succeed! Details: {failure_details}"
    assert pos_error <= tol, f"Arrival error {pos_error:.3f}m exceeds tolerance {tol:.2f}m!"
    assert final_lin_v <= 0.05 and final_ang_v <= 0.05, f"Robot failed to halt safely! Vel=({final_lin_v}, {final_ang_v})"

    print(f"  ✅ VERIFICATION PASSED: Successfully navigated to {target_name} safely and accurately.\n")
    return {
        "destination": target_name,
        "target": (tx, ty),
        "final_pose": (round(final_x, 3), round(final_y, 3), round(final_yaw, 3)),
        "error_m": round(pos_error, 3),
        "duration_s": round(duration, 1),
        "velocity": (round(final_lin_v, 3), round(final_ang_v, 3)),
        "status": "PASS"
    }

def main():
    rclpy.init()
    tester = NavigationAcceptanceTester()

    # Wait for initial AMCL pose
    print("Waiting for initial AMCL localization pose...")
    t0 = time.time()
    while time.time() - t0 < 5.0 and not tester.has_map_pose:
        rclpy.spin_once(tester, timeout_sec=0.1)

    cur_x, cur_y, cur_yaw = tester.get_current_pose()
    print(f"Initial Robot Pose: X={cur_x:.3f}, Y={cur_y:.3f}, Yaw={math.degrees(cur_yaw):.1f}°\n")

    results = []

    # 1. Living Room Test (Target: 4.0, -2.5, yaw=0.0, tol=0.65m)
    # If already in living room (from previous motion test), first transition to hallway then living room
    if cur_x > 2.0 and cur_y < -1.0:
        print("Robot is currently in Living Room. Executing initial transit to Hallway first...")
        execute_navigation_test(tester, "hallway", (0.0, 0.0, 0.0, 0.65), timeout_sec=60.0)

    # TEST: Living Room
    res_lr = execute_navigation_test(tester, "living room", (4.0, -2.5, 0.0, 0.65), timeout_sec=90.0)
    results.append(res_lr)

    # 2. Regression Check: Bedroom Test (Target: -5.0, 2.2, yaw=0.0, tol=0.65m)
    res_br = execute_navigation_test(tester, "bedroom", (-5.0, 2.2, 0.0, 0.65), timeout_sec=140.0)
    results.append(res_br)

    tester.destroy_node()
    rclpy.shutdown()

    print("================================================================================")
    print("  🏆 FINAL VERIFICATION ACCEPTANCE SUMMARY")
    print("================================================================================")
    for res in results:
        print(f"  - {res['destination'].upper():15s} : {res['status']} | Final Pose: {res['final_pose'][:2]} | Error: {res['error_m']}m | Duration: {res['duration_s']}s | Safe Stop: {res['velocity']}")
    print("================================================================================\n")

if __name__ == "__main__":
    main()
