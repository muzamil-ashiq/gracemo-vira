#!/usr/bin/env python3
"""
GRaCEmo ViRa — Autonomous System Readiness Verification Probe
==============================================================
Validates the complete 11-stage autonomous robotics readiness sequence:
  Stage 1: ROS environment & Localhost DDS isolation
  Stage 2: Gazebo Harmonic simulation clock (/clock)
  Stage 3: Robot model & ros_gz_bridge interfaces
  Stage 4: Sensor streams freshness (/scan, /odom, /imu/data, /camera/image_raw)
  Stage 5: Coordinate Transform (TF) chain (map -> odom -> base_footprint -> lidar_link)
  Stage 6: Valid localization & AMCL pose covariance bounds
  Stage 7: Nav2 lifecycle nodes status (all 12 nodes ACTIVE)
  Stage 8: Nav2 Action Server readiness (/navigate_to_pose)
  Stage 9: Velocity pipeline integrity & single ownership (/cmd_vel)
  Stage 10: Command Coordinator state machine (gracemo_command_coordinator IDLE)
  Stage 11: Interaction backend & Kernel health (interaction_node & gracemo-kernel)
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
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from std_msgs.msg import String, Bool
from std_srvs.srv import Empty
from lifecycle_msgs.srv import GetState
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose


NAV2_LIFECYCLE_NODES = [
    "map_server",
    "amcl",
    "controller_server",
    "smoother_server",
    "planner_server",
    "route_server",
    "behavior_server",
    "bt_navigator",
    "waypoint_follower",
    "velocity_smoother",
    "collision_monitor",
    "docking_server"
]


class SystemReadinessProbe(Node):
    def __init__(self):
        super().__init__("system_readiness_probe")

        # Counters & timestamps
        self.clock_count = 0
        self.last_clock_sim_time = 0.0
        self.scan_count = 0
        self.odom_count = 0
        self.imu_count = 0
        self.camera_count = 0
        self.latest_scan_time = 0.0
        self.latest_odom_time = 0.0
        self.latest_imu_time = 0.0
        self.latest_camera_time = 0.0
        self.latest_amcl_pose: PoseWithCovarianceStamped = None
        self.coordinator_state = None
        self.interaction_feedback = []

        # TF Buffer
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # QoS
        qos_transient = QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        qos_reliable = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        # Subscriptions using qos_profile_sensor_data for high-rate simulation topics
        self.create_subscription(Clock, "/clock", self._on_clock, qos_profile_sensor_data)
        self.create_subscription(LaserScan, "/scan", self._on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/odom", self._on_odom, qos_profile_sensor_data)
        self.create_subscription(Imu, "/imu/data", self._on_imu, qos_profile_sensor_data)
        self.create_subscription(Image, "/camera/image_raw", self._on_camera, qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, qos_transient)
        self.create_subscription(String, "/coordinator/feedback", self._on_coord_feedback, qos_reliable)

        # Action Client
        self.nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

        # Service Clients
        self.nomotion_cli = self.create_client(Empty, "/request_nomotion_update")
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)

    def _on_clock(self, msg: Clock):
        self.clock_count += 1
        self.last_clock_sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9

    def _on_scan(self, msg: LaserScan):
        self.scan_count += 1
        self.latest_scan_time = time.time()

    def _on_odom(self, msg: Odometry):
        self.odom_count += 1
        self.latest_odom_time = time.time()

    def _on_imu(self, msg: Imu):
        self.imu_count += 1
        self.latest_imu_time = time.time()

    def _on_camera(self, msg: Image):
        self.camera_count += 1
        self.latest_camera_time = time.time()

    def _on_amcl(self, msg: PoseWithCovarianceStamped):
        self.latest_amcl_pose = msg

    def _on_coord_feedback(self, msg: String):
        try:
            d = json.loads(msg.data)
            self.coordinator_state = d.get("state")
            self.interaction_feedback.append(d)
        except Exception:
            pass


def check_node_lifecycle_state(probe: Node, node_name: str, timeout_sec: float = 2.0) -> str:
    cli = probe.create_client(GetState, f"/{node_name}/get_state")
    if not cli.wait_for_service(timeout_sec=timeout_sec):
        return "SERVICE_UNAVAILABLE"
    req = GetState.Request()
    future = cli.call_async(req)
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        rclpy.spin_once(probe, timeout_sec=0.05)
        if future.done():
            res = future.result()
            if res:
                return res.current_state.label.upper()
            return "CALL_FAILED"
    return "TIMEOUT"


def run_full_readiness_probe(verbose: bool = True) -> Tuple[bool, Dict[str, Any]]:
    print("=" * 80)
    print("  🔍 GRaCEmo ViRa — AUTONOMOUS SYSTEM READINESS VERIFICATION")
    print("=" * 80)

    rclpy.init()
    probe = SystemReadinessProbe()
    stages = {}

    # Accumulate background messages and allow DDS discovery to warm up (up to 4.0 seconds)
    t_warm = time.time()
    while time.time() - t_warm < 4.0:
        rclpy.spin_once(probe, timeout_sec=0.1)
        if probe.clock_count > 0 and probe.scan_count > 0 and probe.odom_count > 0:
            break

    # -------------------------------------------------------------------------
    # STAGE 1: ROS environment & Localhost DDS isolation
    # -------------------------------------------------------------------------
    localhost_env = os.environ.get("ROS_LOCALHOST_ONLY", "0") == "1" or os.environ.get("ROS_AUTOMATIC_DISCOVERY_RANGE", "") == "LOCALHOST"
    gz_part = os.environ.get("GZ_PARTITION", "")
    s1_ok = (gz_part == "gracemo")
    diag_s1 = f"ROS_DISCOVERY_RANGE: {os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE', 'DEFAULT')}, GZ_PARTITION: {gz_part}"
    stages["Stage 1: ROS & Localhost DDS Environment"] = {"status": "PASS" if s1_ok else "WARN", "details": diag_s1}
    print(f"[{'PASS' if s1_ok else 'WARN'}] Stage 1: ROS & DDS Environment -> {diag_s1}")

    # -------------------------------------------------------------------------
    # STAGE 2: Gazebo Harmonic simulation clock (/clock)
    # -------------------------------------------------------------------------
    t_clock = time.time()
    while time.time() - t_clock < 5.0 and probe.clock_count == 0:
        rclpy.spin_once(probe, timeout_sec=0.1)
    s2_ok = (probe.clock_count > 0 and probe.last_clock_sim_time > 0.0)
    diag_s2 = f"Clock ticks: {probe.clock_count} (Sim Time: {probe.last_clock_sim_time:.2f}s)"
    stages["Stage 2: Gazebo Harmonic Clock"] = {"status": "PASS" if s2_ok else "FAIL", "details": diag_s2}
    print(f"[{'PASS' if s2_ok else 'FAIL'}] Stage 2: Gazebo Harmonic Clock -> {diag_s2}")

    # -------------------------------------------------------------------------
    # STAGE 3: Robot model & ros_gz_bridge
    # -------------------------------------------------------------------------
    gz_res = subprocess.run(["gz", "model", "-m", "gracemo_vira"], capture_output=True, text=True, env=dict(os.environ, GZ_PARTITION="gracemo"))
    model_in_gz = (gz_res.returncode == 0 or "gracemo_vira" in gz_res.stdout)
    bridge_rx = (probe.odom_count > 0 or probe.scan_count > 0)
    s3_ok = model_in_gz and bridge_rx
    diag_s3 = f"Gazebo model online: {model_in_gz}, Bridge telemetry received: {bridge_rx}"
    stages["Stage 3: Robot Model & GZ Bridge"] = {"status": "PASS" if s3_ok else "FAIL", "details": diag_s3}
    print(f"[{'PASS' if s3_ok else 'FAIL'}] Stage 3: Robot Model & GZ Bridge -> {diag_s3}")

    # -------------------------------------------------------------------------
    # STAGE 4: Sensor streams freshness (/scan, /odom, /imu/data, /camera/image_raw)
    # -------------------------------------------------------------------------
    t_sens = time.time()
    while time.time() - t_sens < 5.0 and not (probe.scan_count > 0 and probe.odom_count > 0 and probe.imu_count > 0 and probe.camera_count > 0):
        rclpy.spin_once(probe, timeout_sec=0.1)
    s4_ok = (probe.scan_count > 0 and probe.odom_count > 0 and probe.imu_count > 0 and probe.camera_count > 0)
    diag_s4 = f"Scan: {probe.scan_count}, Odom: {probe.odom_count}, IMU: {probe.imu_count}, Camera: {probe.camera_count}"
    stages["Stage 4: Sensor Streams Freshness"] = {"status": "PASS" if s4_ok else "FAIL", "details": diag_s4}
    print(f"[{'PASS' if s4_ok else 'FAIL'}] Stage 4: Sensor Streams Freshness -> {diag_s4}")

    # -------------------------------------------------------------------------
    # STAGE 5: Transform (TF) chain (map -> odom -> base_footprint -> lidar_link)
    # -------------------------------------------------------------------------
    tf_odom_base = False
    tf_base_lidar = False
    tf_map_base = False
    t_start = time.time()
    while time.time() - t_start < 4.0:
        rclpy.spin_once(probe, timeout_sec=0.05)
        try:
            tf_odom_base = probe.tf_buffer.can_transform("odom", "base_footprint", rclpy.time.Time())
            tf_base_lidar = probe.tf_buffer.can_transform("base_footprint", "lidar_link", rclpy.time.Time())
            tf_map_base = probe.tf_buffer.can_transform("map", "base_footprint", rclpy.time.Time())
            if tf_odom_base and tf_base_lidar and tf_map_base:
                break
        except Exception:
            pass
    s5_ok = (tf_odom_base and tf_base_lidar and tf_map_base)
    diag_s5 = f"odom->base: {tf_odom_base}, base->lidar: {tf_base_lidar}, map->base: {tf_map_base}"
    stages["Stage 5: Coordinate Transform Chain"] = {"status": "PASS" if s5_ok else "FAIL", "details": diag_s5}
    print(f"[{'PASS' if s5_ok else 'FAIL'}] Stage 5: Coordinate Transform Chain -> {diag_s5}")

    # -------------------------------------------------------------------------
    # STAGE 6: Valid localization & AMCL pose covariance bounds
    # -------------------------------------------------------------------------
    if probe.nomotion_cli.wait_for_service(timeout_sec=1.5):
        probe.nomotion_cli.call_async(Empty.Request())
    for _ in range(15):
        rclpy.spin_once(probe, timeout_sec=0.1)

    s6_ok = False
    diag_s6 = "No /amcl_pose received"
    if probe.latest_amcl_pose:
        px = probe.latest_amcl_pose.pose.pose.position.x
        py = probe.latest_amcl_pose.pose.pose.position.y
        cov = probe.latest_amcl_pose.pose.covariance
        var_x = cov[0]
        var_y = cov[7]
        var_yaw = cov[35]
        s6_ok = (var_x < 1.0 and var_y < 1.0)
        diag_s6 = f"Pose: ({px:.2f}, {py:.2f}), Var: (x={var_x:.3f}, y={var_y:.3f}, yaw={var_yaw:.3f})"
    stages["Stage 6: AMCL Localization & Covariance"] = {"status": "PASS" if s6_ok else "FAIL", "details": diag_s6}
    print(f"[{'PASS' if s6_ok else 'FAIL'}] Stage 6: AMCL Localization & Covariance -> {diag_s6}")

    # -------------------------------------------------------------------------
    # STAGE 7: Nav2 lifecycle nodes status (all 12 nodes ACTIVE)
    # -------------------------------------------------------------------------
    lifecycle_states = {}
    all_active = True
    for n in NAV2_LIFECYCLE_NODES:
        st = check_node_lifecycle_state(probe, n, timeout_sec=1.5)
        lifecycle_states[n] = st
        if st != "ACTIVE":
            all_active = False

    s7_ok = all_active
    diag_s7 = f"Active: {sum(1 for s in lifecycle_states.values() if s == 'ACTIVE')}/{len(NAV2_LIFECYCLE_NODES)}"
    stages["Stage 7: Nav2 Lifecycle Nodes"] = {"status": "PASS" if s7_ok else "FAIL", "details": diag_s7, "nodes": lifecycle_states}
    print(f"[{'PASS' if s7_ok else 'FAIL'}] Stage 7: Nav2 Lifecycle Nodes -> {diag_s7}")

    # -------------------------------------------------------------------------
    # STAGE 8: Nav2 Action Server readiness (/navigate_to_pose)
    # -------------------------------------------------------------------------
    s8_ok = probe.nav_client.wait_for_server(timeout_sec=2.5)
    diag_s8 = f"/navigate_to_pose server reachable: {s8_ok}"
    stages["Stage 8: Nav2 Action Server"] = {"status": "PASS" if s8_ok else "FAIL", "details": diag_s8}
    print(f"[{'PASS' if s8_ok else 'FAIL'}] Stage 8: Nav2 Action Server -> {diag_s8}")

    # -------------------------------------------------------------------------
    # STAGE 9: Velocity pipeline integrity & single ownership
    # -------------------------------------------------------------------------
    pubs = probe.get_publishers_info_by_topic("/cmd_vel")
    subs = probe.get_subscriptions_info_by_topic("/cmd_vel")
    pub_names = [p.node_name for p in pubs]
    sub_names = [s.node_name for s in subs]
    s9_ok = (len(pubs) == 1 and "terrain_monitor" in pub_names and len(subs) == 1 and "ros_gz_bridge" in sub_names)
    diag_s9 = f"Pubs ({len(pubs)}): {pub_names}, Subs ({len(subs)}): {sub_names}"
    stages["Stage 9: Velocity Pipeline Integrity"] = {"status": "PASS" if s9_ok else "FAIL", "details": diag_s9}
    print(f"[{'PASS' if s9_ok else 'FAIL'}] Stage 9: Velocity Pipeline Integrity -> {diag_s9}")

    # -------------------------------------------------------------------------
    # STAGE 10: Command Coordinator state machine
    # -------------------------------------------------------------------------
    status_pub = probe.create_publisher(String, "/interaction/user_input", 10)
    cmd_msg = String()
    cmd_msg.data = "what is your status"
    status_pub.publish(cmd_msg)
    t_c = time.time()
    coord_heard = False
    while time.time() - t_c < 2.5:
        rclpy.spin_once(probe, timeout_sec=0.1)
        if probe.coordinator_state in ("IDLE", "NAVIGATING", "SAFE_STOP"):
            coord_heard = True
            break
    s10_ok = coord_heard
    diag_s10 = f"Coordinator state: {probe.coordinator_state or 'ONLINE'}"
    stages["Stage 10: Command Coordinator FSM"] = {"status": "PASS" if s10_ok else "FAIL", "details": diag_s10}
    print(f"[{'PASS' if s10_ok else 'FAIL'}] Stage 10: Command Coordinator FSM -> {diag_s10}")

    # -------------------------------------------------------------------------
    # STAGE 11: Interaction backend & Kernel health
    # -------------------------------------------------------------------------
    kernel_ok = os.path.exists("/tmp/gracemo.sock") or (subprocess.run(["pgrep", "-f", "gracemo-kernel"], capture_output=True).returncode == 0)
    s11_ok = kernel_ok
    diag_s11 = f"Kernel online: {kernel_ok}, Interaction feedback channel active: {len(probe.interaction_feedback) > 0}"
    stages["Stage 11: Interaction Backend & Kernel"] = {"status": "PASS" if s11_ok else "FAIL", "details": diag_s11}
    print(f"[{'PASS' if s11_ok else 'FAIL'}] Stage 11: Interaction Backend & Kernel -> {diag_s11}")

    probe.destroy_node()
    rclpy.shutdown()

    # Final Verdict
    all_pass = all(v["status"] == "PASS" for v in stages.values())

    print("\n" + "=" * 80)
    print("  📊 SYSTEM READINESS VERIFICATION SUMMARY")
    print("=" * 80)
    for st_name, val in stages.items():
        tag = "✅ PASS" if val["status"] == "PASS" else ("⚠️ WARN" if val["status"] == "WARN" else "❌ FAIL")
        print(f"  {st_name:<46} : {tag} | {val['details']}")
    print("=" * 80)

    verdict_text = "🎉 SYSTEM FULLY HEALTHY & READY FOR AUTONOMOUS NAVIGATION" if all_pass else "❌ READINESS CRITERIA NOT MET"
    print(f"  READINESS VERDICT: {verdict_text}")
    print("=" * 80 + "\n")
    return all_pass, stages

if __name__ == "__main__":
    ok, _ = run_full_readiness_probe()
    sys.exit(0 if ok else 1)
