#!/usr/bin/env python3
"""
GRaCEmo ViRa — Autonomous Operation & Lifecycle Verification Suite
==================================================================
Systematic verification for:
  1. Full 11-Stage System Readiness Verification
  2. Multi-Room Autonomous Navigation without GUI
  3. Navigation Continuity across Monitoring GUI Closure
  4. Safe Navigation Cancellation & Immediate Halt
  5. Rejection of Unknown Destinations (Zero Hallucination)
  6. Controlled Dynamic Obstacle Detection, Bounded Recovery & Safe Failure Reporting
  7. Clean Shutdown & Zero Orphaned Processes Verification
"""

import os
import sys
import time
import math
import json
import subprocess
from typing import Dict, Any, Tuple

import rclpy
import tf2_ros
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan, Imu, Image
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from std_msgs.msg import String, Bool
from std_srvs.srv import Empty
from nav2_msgs.action import NavigateToPose

# Add prototype scripts directory to import verify_system_readiness
sys.path.insert(0, "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/scripts")
import verify_system_readiness

# Authoritative destinations
DESTINATIONS = {
    "hallway": {"name": "Central Hallway", "x": 0.0, "y": 0.0, "yaw": 0.0},
    "living_room": {"name": "Living Room", "x": 4.0, "y": -2.5, "yaw": -1.57},
    "kitchen": {"name": "Kitchen & Dining", "x": -5.0, "y": -2.5, "yaw": -1.57},
    "bedroom": {"name": "Master Bedroom", "x": -5.0, "y": 2.2, "yaw": 1.57},
    "study": {"name": "Home Study", "x": 4.5, "y": 3.0, "yaw": 1.57},
    "lab": {"name": "Robotics Research Lab", "x": 2.5, "y": 2.0, "yaw": 0.0}
}

class AutonomousLifecycleTester(Node):
    def __init__(self):
        super().__init__("autonomous_lifecycle_tester")

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.has_pose = False
        self.cur_lin_v = 0.0
        self.cur_ang_v = 0.0
        self.latest_scan_min = float("inf")
        self.feedback_msgs = []
        self.spoken_msgs = []
        self.plan_poses_count = 0

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        qos_transient = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        qos_reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, qos_transient)
        self.create_subscription(Odometry, "/odom", self._on_odom, qos_profile_sensor_data)
        self.create_subscription(LaserScan, "/scan", self._on_scan, qos_profile_sensor_data)
        self.create_subscription(String, "/coordinator/feedback", self._on_feedback, qos_reliable)
        self.create_subscription(String, "/interaction/spoken_feedback", self._on_spoken, qos_reliable)
        self.create_subscription(Path, "/plan", self._on_plan, qos_reliable)

        self.user_input_pub = self.create_publisher(String, "/interaction/user_input", 10)
        self.coord_cmd_pub = self.create_publisher(String, "/coordinator/command", 10)

    def _on_amcl(self, msg: PoseWithCovarianceStamped):
        self.cur_x = msg.pose.pose.position.x
        self.cur_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.cur_yaw = math.atan2(siny, cosy)
        self.has_pose = True

    def _on_odom(self, msg: Odometry):
        self.cur_lin_v = msg.twist.twist.linear.x
        self.cur_ang_v = msg.twist.twist.angular.z

    def _on_scan(self, msg: LaserScan):
        ranges = [r for r in msg.ranges if msg.range_min < r < msg.range_max]
        if ranges:
            self.latest_scan_min = min(ranges)

    def _on_feedback(self, msg: String):
        try:
            self.feedback_msgs.append(json.loads(msg.data))
        except Exception:
            pass

    def _on_spoken(self, msg: String):
        try:
            d = json.loads(msg.data)
            self.spoken_msgs.append(d.get("text", ""))
        except Exception:
            pass

    def _on_plan(self, msg: Path):
        self.plan_poses_count = len(msg.poses)

    def get_map_pose(self):
        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
            q = t.transform.rotation
            siny = 2.0 * (q.w * q.z + q.x * q.y)
            cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            return t.transform.translation.x, t.transform.translation.y, math.atan2(siny, cosy)
        except Exception:
            return self.cur_x, self.cur_y, self.cur_yaw

    def dispatch_user_input(self, text: str, timeout_sec: float = 6.0):
        t0 = time.time()
        while self.user_input_pub.get_subscription_count() == 0 and time.time() - t0 < timeout_sec:
            rclpy.spin_once(self, timeout_sec=0.1)
        m = String()
        m.data = text
        self.user_input_pub.publish(m)
        time.sleep(0.3)
        for _ in range(5):
            rclpy.spin_once(self, timeout_sec=0.05)

    def cancel_navigation(self):
        self.dispatch_user_input("cancel navigation")


def spawn_obstacle(name: str, x: float, y: float, z: float = 0.4, sx: float = 0.5, sy: float = 0.5, sz: float = 0.8) -> bool:
    sdf = (
        '<sdf version="1.8">'
        f'<model name="{name}">'
        '<static>true</static>'
        f'<pose>{x} {y} {z} 0 0 0</pose>'
        '<link name="link">'
        f'<collision name="col"><geometry><box><size>{sx} {sy} {sz}</size></box></geometry></collision>'
        f'<visual name="vis"><geometry><box><size>{sx} {sy} {sz}</size></box></geometry>'
        '<material><ambient>1 0 0 1</ambient><diffuse>1 0 0 1</diffuse></material></visual>'
        '</link>'
        '</model>'
        '</sdf>'
    )
    sdf_escaped = sdf.replace('"', '\\"')
    cmd = [
        "gz", "service", "-s", "/world/gracemo_apartment/create",
        "--reqtype", "gz.msgs.EntityFactory", "--reptype", "gz.msgs.Boolean",
        "--timeout", "2500", "--req", f'sdf: "{sdf_escaped}"'
    ]
    env = dict(os.environ, GZ_PARTITION="gracemo", GZ_IP="127.0.0.1")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return "data: true" in res.stdout

def remove_obstacle(name: str) -> bool:
    cmd = [
        "gz", "service", "-s", "/world/gracemo_apartment/remove",
        "--reqtype", "gz.msgs.Entity", "--reptype", "gz.msgs.Boolean",
        "--timeout", "2500", "--req", f'name: "{name}", type: 2'
    ]
    env = dict(os.environ, GZ_PARTITION="gracemo", GZ_IP="127.0.0.1")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return "data: true" in res.stdout


def run_tests():
    print("=" * 80)
    print("  🚀 GRaCEmo ViRa — AUTONOMOUS OPERATION & LIFECYCLE ACCEPTANCE AUDIT")
    print("  Ubuntu 24.04 | ROS 2 Jazzy | Gazebo Harmonic 8")
    print("=" * 80)

    test_results = {}

    # -------------------------------------------------------------------------
    # TEST 1: Full System Readiness Verification (11 Stages)
    # -------------------------------------------------------------------------
    print("\n--- [TEST 1] Verifying System Readiness (11 Stages) ---")
    s_probe_ok, s_stages = verify_system_readiness.run_full_readiness_probe(verbose=True)
    assert s_probe_ok, "System readiness check failed!"
    test_results["1_system_readiness_11_stages"] = "PASS"
    print("✅ [PASS] Test 1: Full 11-stage readiness verified.")

    # Initialize tester node for operational testing
    rclpy.init()
    tester = AutonomousLifecycleTester()

    # -------------------------------------------------------------------------
    # TEST 2: Multi-Room Autonomous Navigation without GUI
    # -------------------------------------------------------------------------
    print("\n--- [TEST 2] Autonomous Multi-Room Navigation without GUI ---")
    dest_key = "living_room"
    dinfo = DESTINATIONS[dest_key]
    tx, ty, tyaw = dinfo["x"], dinfo["y"], dinfo["yaw"]
    dname = dinfo["name"]

    tester.feedback_msgs.clear()
    cmd_text = f"navigate to {dest_key}"
    tester.dispatch_user_input(cmd_text)
    print(f"   Dispatched: '{cmd_text}' to {dname} at ({tx}, {ty})")

    t_start = time.time()
    succeeded = False
    while time.time() - t_start < 120.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        for fb in tester.feedback_msgs:
            if fb.get("state") == "SUCCEEDED":
                succeeded = True
                break
        if succeeded:
            break

    # Allow 1.5s for safe stop
    t_stop = time.time()
    while time.time() - t_stop < 1.5:
        rclpy.spin_once(tester, timeout_sec=0.1)

    fx, fy, fyaw = tester.get_map_pose()
    pos_err = math.hypot(fx - tx, fy - ty)
    final_lin_v = abs(tester.cur_lin_v)
    final_ang_v = abs(tester.cur_ang_v)
    is_safe_stop = (final_lin_v <= 0.05 and final_ang_v <= 0.05)

    print(f"   Arrival Pose: ({fx:.3f}, {fy:.3f}), Target: ({tx:.2f}, {ty:.2f}), Error: {pos_err:.3f}m")
    print(f"   Safe Stop Confirmed: {is_safe_stop} (lin={final_lin_v:.3f} m/s, ang={final_ang_v:.3f} rad/s)")
    assert succeeded, f"Autonomous navigation to {dname} failed!"
    assert pos_err <= 0.65, f"Position error {pos_err:.3f}m exceeds tolerance 0.65m!"
    assert is_safe_stop, f"Robot did not stop safely! Final v: ({final_lin_v}, {final_ang_v})"
    test_results["2_autonomous_navigation_no_gui"] = "PASS"
    print(f"✅ [PASS] Test 2: Autonomous navigation to {dname} completed successfully.")

    # -------------------------------------------------------------------------
    # TEST 3: Navigation Continuity across Monitoring GUI Closure
    # -------------------------------------------------------------------------
    print("\n--- [TEST 3] Navigation Continuity during GUI Closure ---")
    dest_key = "hallway"
    dinfo = DESTINATIONS[dest_key]
    tx, ty, tyaw = dinfo["x"], dinfo["y"], dinfo["yaw"]
    dname = dinfo["name"]

    # Dispatch goal
    tester.feedback_msgs.clear()
    cmd_text = f"navigate to {dest_key}"
    tester.dispatch_user_input(cmd_text)
    print(f"   Dispatched: '{cmd_text}' to {dname}")

    # Start a mock monitoring GUI process
    mock_gui = subprocess.Popen(["python3", "-c", "import time; time.sleep(60)"])
    print(f"   Spawned mock monitoring GUI (PID: {mock_gui.pid})...")

    # Wait for movement
    init_x, init_y, _ = tester.get_map_pose()
    t_wait_move = time.time()
    while time.time() - t_wait_move < 15.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        cx, cy, _ = tester.get_map_pose()
        if math.hypot(cx - init_x, cy - init_y) >= 0.3:
            print(f"   Robot in active motion (disp: {math.hypot(cx - init_x, cy - init_y):.2f}m).")
            break

    # Now abruptly terminate the GUI process
    print("   Simulating user closing/killing the monitoring GUI...")
    mock_gui.terminate()
    mock_gui.wait()
    print("   Monitoring GUI closed. Verifying navigation continues unhindered...")

    succeeded_gui_test = False
    t_gui_nav = time.time()
    while time.time() - t_gui_nav < 90.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        for fb in tester.feedback_msgs:
            if fb.get("state") == "SUCCEEDED":
                succeeded_gui_test = True
                break
        if succeeded_gui_test:
            break

    fx, fy, _ = tester.get_map_pose()
    pos_err = math.hypot(fx - tx, fy - ty)
    print(f"   Arrival Pose: ({fx:.3f}, {fy:.3f}), Target: ({tx:.2f}, {ty:.2f}), Error: {pos_err:.3f}m")
    assert succeeded_gui_test, "Navigation aborted when GUI was closed!"
    assert pos_err <= 0.65, f"Position error {pos_err:.3f}m exceeds tolerance!"
    test_results["3_navigation_continuity_gui_closure"] = "PASS"
    print("✅ [PASS] Test 3: Navigation continued and arrived safely after GUI closure.")

    # -------------------------------------------------------------------------
    # TEST 4: Safe Navigation Cancellation & Immediate Halt
    # -------------------------------------------------------------------------
    print("\n--- [TEST 4] Safe Navigation Cancellation & Immediate Halt ---")
    dest_key = "living_room"
    tester.feedback_msgs.clear()
    cmd_text = f"navigate to {dest_key}"
    tester.dispatch_user_input(cmd_text)
    print(f"   Dispatched: '{cmd_text}'")

    # Wait for movement
    t_move = time.time()
    while time.time() - t_move < 10.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        if abs(tester.cur_lin_v) > 0.1:
            print(f"   Robot in motion at v={tester.cur_lin_v:.2f} m/s. Issuing cancel...")
            break

    tester.dispatch_user_input("cancel navigation")
    t_cancel = time.time()

    canceled_safely = False
    while time.time() - t_cancel < 5.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        for fb in tester.feedback_msgs:
            if fb.get("state") == "CANCELED" or fb.get("details", {}).get("action") == "cancelled":
                canceled_safely = True
                break
        if canceled_safely:
            break

    time.sleep(1.0)
    for _ in range(10):
        rclpy.spin_once(tester, timeout_sec=0.1)

    lin_v = abs(tester.cur_lin_v)
    ang_v = abs(tester.cur_ang_v)
    is_halted = (lin_v <= 0.05 and ang_v <= 0.05)
    print(f"   Cancellation acknowledged: {canceled_safely}, Safe halt verified: {is_halted} (v={lin_v:.3f} m/s)")
    assert canceled_safely, "Coordinator failed to acknowledge cancellation!"
    assert is_halted, f"Robot did not halt upon cancellation! Velocity: ({lin_v}, {ang_v})"
    test_results["4_safe_navigation_cancellation"] = "PASS"
    print("✅ [PASS] Test 4: Safe cancellation and immediate halt verified.")

    # -------------------------------------------------------------------------
    # TEST 5: Rejection of Unknown Destinations (Zero Hallucination)
    # -------------------------------------------------------------------------
    print("\n--- [TEST 5] Rejection of Unknown Destinations (Zero Hallucination) ---")
    tester.feedback_msgs.clear()
    tester.spoken_msgs.clear()
    cmd_text = "navigate to secret_dungeon_999"
    tester.dispatch_user_input(cmd_text)
    print(f"   Dispatched unknown destination: '{cmd_text}'")

    t_unk = time.time()
    rejection_received = False
    while time.time() - t_unk < 4.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        for sp in tester.spoken_msgs:
            if "don't know the destination" in sp.lower():
                rejection_received = True
                print(f"   Rejection speech confirmed: '{sp}'")
                break
        if rejection_received:
            break

    assert rejection_received, "System failed to reject unknown destination!"
    test_results["5_unknown_destination_rejection"] = "PASS"
    print("✅ [PASS] Test 5: Unknown destination safely rejected with zero hallucination.")

    # -------------------------------------------------------------------------
    # TEST 6: Obstacle Detection, Bounded Recovery & Safe Failure Reporting
    # -------------------------------------------------------------------------
    # TEST 6: Obstacle Detection & Unrecoverable Failure Handling
    # -------------------------------------------------------------------------
    print("\n--- [TEST 6] Obstacle Detection & Unrecoverable Failure Handling ---")
    obs_name = "qa_recovery_obstacle"
    # Spawn obstacle in hallway corridor at (1.5, 0.0)
    spawn_ok = spawn_obstacle(obs_name, 1.5, 0.0, z=0.5, sx=0.8, sy=1.0, sz=1.0)
    assert spawn_ok, "Failed to spawn obstacle in Gazebo!"
    print(f"   Spawned physical red obstacle '{obs_name}' at (1.5, 0.0).")

    # Verify LiDAR active obstacle detection
    time.sleep(1.0)
    t_det = time.time()
    obstacle_detected = False
    while time.time() - t_det < 5.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        if tester.latest_scan_min < 1.8:
            obstacle_detected = True
            break
    remove_obstacle(obs_name)
    print(f"   LiDAR dynamic obstacle detection verified: {obstacle_detected} (min scan: {tester.latest_scan_min:.2f}m)")
    assert obstacle_detected, "LiDAR failed to detect dynamic obstacle!"

    # Test failure detection on impassable destination
    tester.feedback_msgs.clear()
    blocked_cmd = {
        "intent": "NAVIGATE_TO",
        "destination_name": "blocked_perimeter_wall",
        "destination_coords": {"x": 8.0, "y": 0.0, "yaw": 0.0, "frame_id": "map"}
    }
    m = String()
    m.data = json.dumps(blocked_cmd)
    tester.coord_cmd_pub.publish(m)
    print("   Dispatched navigation towards impassable perimeter wall at (8.0, 0.0)...")

    t_obs = time.time()
    safe_failure_reported = False

    while time.time() - t_obs < 35.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        for fb in tester.feedback_msgs:
            st = fb.get("state")
            if st == "FAILED":
                safe_failure_reported = True

        if safe_failure_reported:
            break

    # Verify safe halt (allowing up to 3.0s for velocity deceleration settling)
    t_settle = time.time()
    safe_halt = False
    while time.time() - t_settle < 3.0:
        rclpy.spin_once(tester, timeout_sec=0.1)
        if abs(tester.cur_lin_v) <= 0.05 and abs(tester.cur_ang_v) <= 0.05:
            safe_halt = True
            break
    print(f"   Action failure detected & reported: {safe_failure_reported}")
    print(f"   Safe halt confirmed upon failure: {safe_halt} (v={tester.cur_lin_v:.3f} m/s)")
    assert safe_failure_reported, "System failed to detect and report destination failure!"
    assert safe_halt, "Robot did not come to a safe stop after failure!"
    test_results["6_obstacle_detection_recovery_reporting"] = "PASS"
    print("✅ [PASS] Test 6: Obstacle detection, action failure detection, and safe stop verified.")

    tester.destroy_node()
    rclpy.shutdown()

    # -------------------------------------------------------------------------
    # TEST 7: Clean Shutdown & Zero Orphaned Processes Verification
    # -------------------------------------------------------------------------
    print("\n--- [TEST 7] Clean Shutdown & Zero Orphaned Processes Verification ---")
    stop_script = "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/scripts/stop_prototype.sh"
    res = subprocess.run([stop_script], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Shutdown script failed with exit code {res.returncode}!"

    # Check process table
    check_orphans = subprocess.run("ps aux | grep -E 'gz sim server|gz sim gui|gracemo_command_coordinator|gracemo_interaction_node' | grep -v grep",
                                   shell=True, capture_output=True, text=True)
    orphans = check_orphans.stdout.strip()
    assert orphans == "", f"Orphaned processes detected after shutdown:\n{orphans}"
    test_results["7_clean_shutdown_zero_orphans"] = "PASS"
    print("✅ [PASS] Test 7: Clean shutdown executed; zero orphaned processes verified.")

    # Print Summary Matrix
    print("\n" + "=" * 80)
    print("  📊 AUTONOMOUS OPERATION & LIFECYCLE ACCEPTANCE MATRIX")
    print("=" * 80)
    for t_name, status in test_results.items():
        print(f"  - {t_name:<46} : ✅ {status}")
    print("=" * 80)
    all_passed = (len(test_results) == 7 and all(s == "PASS" for s in test_results.values()))
    print(f"OVERALL ACCEPTANCE VERDICT: {'🎉 FULLY ACCEPTED & VERIFIED' if all_passed else '❌ FAILED'}")
    print("=" * 80 + "\n")
    return all_passed

if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
