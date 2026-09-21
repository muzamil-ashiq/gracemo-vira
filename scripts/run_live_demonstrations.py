#!/usr/bin/env python3
"""
GRaCEmo ViRa — Full Live Simulation Demonstration Runner
Executes sequential live demonstrations in running Gazebo Harmonic:
  DEMO 1: Robot Initial State (Embodiment, Joints, Sensors, Camera)
  DEMO 2: Head Pan via Gemini ER 2 (look_at 45° left)
  DEMO 3: Head Return via Gemini ER 2 (look_at forward)
  DEMO 4: Head Tilt via Gemini ER 2 (look_at low floor target)
  DEMO 5: Mobile Navigation via Gemini ER 2 (Hallway -> Corridor -> Kitchen & Dining)
  DEMO 6: Look + Move in Kitchen (Stationary base, gaze at dining table)
  DEMO 7: 7-DOF Arm Motion (Stance transitions to Carry and Travel)
  DEMO 8: Parallel-Jaw Gripper (Open & Close)
  DEMO 9: Sensor Activity Audit (RGB, Depth, LiDAR, IMU, Odometry)
LEAVES SIMULATION RUNNING AT COMPLETION.
"""

import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import cv2

# Set repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "adapters"))
for sub in ["sdk", "motion", "brain/gracemo_brain/skills"]:
    p = str(REPO_ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

# Load GEMINI_API_KEY
env_file = REPO_ROOT / "graceemo_interaction" / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip("'\" ")

import gz.transport13 as gz_transport
from gz.msgs10.model_pb2 import Model as GzModel
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan
from gz.msgs10.imu_pb2 import IMU as GzIMU

from adapters.gemini_robotics.client import GeminiRoboticsClient
from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.tools import ToolRegistry, ToolResult
from arm_controller import ArmController
from hand_controller import HandSubsystem


# -----------------------------------------------------------------------------
# Global Telemetry Monitor
# -----------------------------------------------------------------------------
class SimulationMonitor:
    def __init__(self):
        self.node = gz_transport.Node()
        self.joint_positions: Dict[str, float] = {}
        self.cur_x: float = 0.0
        self.cur_y: float = 0.0
        self.cur_z: float = 0.0
        self.cur_yaw: float = 0.0
        self.speed: float = 0.0
        self.cmd_vel_count: int = 0
        self.latest_rgb: Optional[np.ndarray] = None
        self.latest_depth: Optional[np.ndarray] = None
        self.latest_lidar_ranges: int = 0
        self.has_imu: bool = False
        self.imu_data = None

        # Subscriptions
        self.node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", self._on_joints)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzTwist, "/cmd_vel", self._on_cmd_vel)
        self.node.subscribe(GzImage, "/camera/image_raw", self._on_rgb)
        self.node.subscribe(GzImage, "/camera/depth_image", self._on_depth)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)
        self.node.subscribe(GzIMU, "/imu/data", self._on_imu)

    def _on_joints(self, msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                self.joint_positions[j.name] = float(j.axis1.position)

    def _on_odom(self, msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        self.cur_x = float(p.x)
        self.cur_y = float(p.y)
        self.cur_z = float(p.z)
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.cur_yaw = math.atan2(siny, cosy)
        vx = msg.twist.linear.x
        vy = msg.twist.linear.y
        self.speed = math.hypot(vx, vy)

    def _on_cmd_vel(self, msg: GzTwist):
        if abs(msg.linear.x) > 1e-4 or abs(msg.angular.z) > 1e-4:
            self.cmd_vel_count += 1

    def _on_rgb(self, msg: GzImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            self.latest_rgb = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception:
            pass

    def _on_depth(self, msg: GzImage):
        try:
            # 32FC1 float depth
            arr = np.frombuffer(msg.data, dtype=np.float32).reshape((msg.height, msg.width))
            self.latest_depth = arr
        except Exception:
            pass

    def _on_scan(self, msg: GzLaserScan):
        self.latest_lidar_ranges = len(msg.ranges)

    def _on_imu(self, msg: GzIMU):
        self.has_imu = True
        self.imu_data = msg

    def save_snapshot(self, filename: str, overlay_text: str = ""):
        if self.latest_rgb is not None:
            out_img = self.latest_rgb.copy()
            if overlay_text:
                cv2.putText(
                    out_img, overlay_text, (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                )
            path = REPO_ROOT / "scripts" / filename
            cv2.imwrite(str(path), out_img)
            return str(path)
        return None


# -----------------------------------------------------------------------------
# Main Demonstration Runner
# -----------------------------------------------------------------------------
def run_all_demonstrations():
    print("=" * 80)
    print("  GRaCEmo ViRa — LIVE INTERACTIVE SIMULATION DEMONSTRATION")
    print("=" * 80)
    print("Connecting to live Gazebo Harmonic simulation and Kernel...")

    monitor = SimulationMonitor()
    time.sleep(2.0)

    # Gemini & Tools initialization
    cfg = GeminiRoboticsConfig(kernel_url="http://127.0.0.1:7780")
    client = GeminiRoboticsClient(config=cfg, mock_mode=False)
    registry = ToolRegistry(kernel_url="http://127.0.0.1:7780", use_direct_skills=False)
    tools = registry.get_function_declarations()

    results = {}

    # =========================================================================
    # DEMO 1: ROBOT INITIAL STATE
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 1 — ROBOT INITIAL STATE")
    print("#" * 70)
    print("Visualizing GRaCEmo ViRa standing in Central Hallway...")

    joints_count = len(monitor.joint_positions)
    print(f"• Active Joint Count:    {joints_count}/13")
    print(f"• Robot Position:        x={monitor.cur_x:+.3f}m, y={monitor.cur_y:+.3f}m, z={monitor.cur_z:+.3f}m")
    print(f"• Robot Attitude:        yaw={math.degrees(monitor.cur_yaw):+.1f}°")
    print(f"• RGB Camera Active:     {monitor.latest_rgb is not None}")
    print(f"• Depth Camera Active:   {monitor.latest_depth is not None}")
    print(f"• 2D LiDAR Active:       {monitor.latest_lidar_ranges > 0} ({monitor.latest_lidar_ranges} beams)")
    print(f"• IMU Active:            {monitor.has_imu}")

    # Check that neck, wheels, arm, gripper joints exist
    expected = [
        "left_wheel_joint", "right_wheel_joint",
        "neck_pan_joint", "neck_tilt_joint",
        "right_shoulder_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
        "right_elbow_pitch_joint",
        "right_wrist_yaw_joint", "right_wrist_pitch_joint", "right_wrist_roll_joint",
        "finger_left_joint", "finger_right_joint"
    ]
    missing = [j for j in expected if j not in monitor.joint_positions]
    demo1_pass = (len(missing) == 0 and monitor.latest_rgb is not None and monitor.latest_lidar_ranges > 0)
    results["DEMO 1 — Initial robot"] = "PASS" if demo1_pass else f"FAIL (missing: {missing})"
    
    snap1 = monitor.save_snapshot("demo1_initial_state.jpg", "DEMO 1: Initial State (Central Hallway)")
    print(f"• Snapshot saved:        {snap1}")
    print(f"• Result:                {results['DEMO 1 — Initial robot']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 2: HEAD PAN (+45° LEFT via Gemini ER 2)
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 2 — HEAD PAN")
    print("#" * 70)
    prompt_pan = "Look at the point at x=1.414, y=1.414, z=0.65."
    print(f"• Natural Language Command: \"{prompt_pan}\"")
    
    pan_before = monitor.joint_positions.get("neck_pan_joint", 0.0)
    x_before = monitor.cur_x
    y_before = monitor.cur_y
    monitor.cmd_vel_count = 0

    resp_pan = client.reason(prompt=prompt_pan, tools=tools)
    print(f"• Gemini ER 2 Reasoning:    has_call={resp_pan.has_function_calls}")
    if resp_pan.has_function_calls:
        tc = resp_pan.primary_tool_call
        print(f"• Gemini Selected Tool:     {tc.name}({tc.args})")
        res = registry.execute(tc.name, tc.args)
        print(f"• Tool Execution:           {res.message}")

    print("• Waiting 4.0s for physical neck articulation in Gazebo...")
    time.sleep(4.0)

    pan_after = monitor.joint_positions.get("neck_pan_joint", 0.0)
    disp = math.hypot(monitor.cur_x - x_before, monitor.cur_y - y_before)
    pan_delta = abs(pan_after - pan_before)

    print(f"• Neck Pan Before/After:    {math.degrees(pan_before):+.1f}° -> {math.degrees(pan_after):+.1f}°")
    print(f"• Pan Movement Delta:       {math.degrees(pan_delta):.1f}° (Target: ~+45°)")
    print(f"• Mobile Base Displacement: {disp:.4f} m (Threshold < 0.01 m)")
    print(f"• /cmd_vel Count:           {monitor.cmd_vel_count} messages")

    snap2 = monitor.save_snapshot("demo2_head_pan_left.jpg", f"DEMO 2: Head Pan (+{math.degrees(pan_after):.1f} deg)")
    demo2_pass = (pan_delta > 0.30 and disp < 0.01 and monitor.cmd_vel_count == 0)
    results["DEMO 2 — Head pan"] = "PASS" if demo2_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 2 — Head pan']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 3: HEAD RETURN (Center forward via Gemini ER 2)
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 3 — HEAD RETURN")
    print("#" * 70)
    prompt_return = "Look at the point at x=2.0, y=0.0, z=0.65."
    print(f"• Natural Language Command: \"{prompt_return}\"")
    
    pan_before = monitor.joint_positions.get("neck_pan_joint", 0.0)
    x_before = monitor.cur_x
    y_before = monitor.cur_y
    monitor.cmd_vel_count = 0

    resp_return = client.reason(prompt=prompt_return, tools=tools)
    if resp_return.has_function_calls:
        tc = resp_return.primary_tool_call
        print(f"• Gemini Selected Tool:     {tc.name}({tc.args})")
        res = registry.execute(tc.name, tc.args)
        print(f"• Tool Execution:           {res.message}")

    print("• Waiting 4.0s for neck to return to forward gaze...")
    time.sleep(4.0)

    pan_after = monitor.joint_positions.get("neck_pan_joint", 0.0)
    disp = math.hypot(monitor.cur_x - x_before, monitor.cur_y - y_before)

    print(f"• Neck Pan Before/After:    {math.degrees(pan_before):+.1f}° -> {math.degrees(pan_after):+.1f}°")
    print(f"• Mobile Base Displacement: {disp:.4f} m")
    print(f"• /cmd_vel Count:           {monitor.cmd_vel_count}")

    snap3 = monitor.save_snapshot("demo3_head_return_center.jpg", f"DEMO 3: Head Return ({math.degrees(pan_after):.1f} deg)")
    demo3_pass = (abs(pan_after) < 0.25 and disp < 0.01 and monitor.cmd_vel_count == 0)
    results["DEMO 3 — Head return"] = "PASS" if demo3_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 3 — Head return']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 4: HEAD TILT (Down toward floor via Gemini ER 2)
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 4 — HEAD TILT")
    print("#" * 70)
    prompt_tilt = "Look at the point at x=1.2, y=0.0, z=0.10."
    print(f"• Natural Language Command: \"{prompt_tilt}\" (Inspecting floor in front)")
    
    tilt_before = monitor.joint_positions.get("neck_tilt_joint", 0.0)
    x_before = monitor.cur_x
    y_before = monitor.cur_y
    monitor.cmd_vel_count = 0

    resp_tilt = client.reason(prompt=prompt_tilt, tools=tools)
    if resp_tilt.has_function_calls:
        tc = resp_tilt.primary_tool_call
        print(f"• Gemini Selected Tool:     {tc.name}({tc.args})")
        res = registry.execute(tc.name, tc.args)
        print(f"• Tool Execution:           {res.message}")

    print("• Waiting 4.0s for downward head pitch in Gazebo...")
    time.sleep(4.0)

    tilt_after = monitor.joint_positions.get("neck_tilt_joint", 0.0)
    disp = math.hypot(monitor.cur_x - x_before, monitor.cur_y - y_before)
    tilt_delta = abs(tilt_after - tilt_before)

    print(f"• Neck Tilt Before/After:   {math.degrees(tilt_before):+.1f}° -> {math.degrees(tilt_after):+.1f}°")
    print(f"• Downward Pitch Delta:     {math.degrees(tilt_delta):.1f}° (Target: ~+24° downward)")
    print(f"• Mobile Base Displacement: {disp:.4f} m")
    print(f"• /cmd_vel Count:           {monitor.cmd_vel_count}")

    snap4 = monitor.save_snapshot("demo4_head_tilt_down.jpg", f"DEMO 4: Head Tilt Down (+{math.degrees(tilt_after):.1f} deg)")
    demo4_pass = (tilt_delta > 0.20 and disp < 0.01 and monitor.cmd_vel_count == 0)
    results["DEMO 4 — Head tilt"] = "PASS" if demo4_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 4 — Head tilt']}")
    time.sleep(3.0)

    # Re-align head to neutral before mobile navigation
    registry.execute("look_at", {"x": 2.0, "y": 0.0, "z": 0.65})
    time.sleep(2.0)

    # =========================================================================
    # DEMO 5: MOBILE NAVIGATION (Hallway -> Corridor -> Kitchen & Dining)
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 5 — MOBILE NAVIGATION")
    print("#" * 70)
    prompt_nav = "Navigate to the Kitchen & Dining room."
    print(f"• Natural Language Command: \"{prompt_nav}\"")
    print(f"• Route:                    Hallway (0,0) -> Corridor (-5,0) -> Doorway (-5,-1.3) -> Kitchen (-4.5,-2.5)")

    start_x = monitor.cur_x
    start_y = monitor.cur_y

    resp_nav = client.reason(prompt=prompt_nav, tools=tools)
    if resp_nav.has_function_calls:
        tc = resp_nav.primary_tool_call
        print(f"• Gemini Selected Tool:     {tc.name}({tc.args})")
        # Execute tool (asynchronously drives waypoints via kernel_bridge)
        res = registry.execute(tc.name, tc.args)
        print(f"• Navigation Dispatched:    {res.message}")

    print("• Monitoring live physical transit through apartment...")
    t_start = time.time()
    nav_reached = False
    while time.time() - t_start < 45.0:
        cur_dist = math.hypot(monitor.cur_x - (-4.5), monitor.cur_y - (-2.5))
        total_travelled = math.hypot(monitor.cur_x - start_x, monitor.cur_y - start_y)
        print(f"   [NAV {time.time()-t_start:4.1f}s] Pose: x={monitor.cur_x:+.2f}m, y={monitor.cur_y:+.2f}m | "
              f"Travelled: {total_travelled:.2f}m | Target Dist: {cur_dist:.2f}m | Speed: {monitor.speed:.2f}m/s")
        
        # Save transit frame
        if int(time.time() - t_start) % 8 == 0:
            monitor.save_snapshot("demo5_transit.jpg", f"NAV IN PROGRESS: x={monitor.cur_x:.1f}, y={monitor.cur_y:.1f}")

        # Check arrival in Kitchen & Dining corridor/doorway pocket
        if monitor.cur_y < -1.8 and abs(monitor.cur_x - (-4.5)) < 1.0:
            print("✓ Robot has entered Kitchen & Dining area!")
            nav_reached = True
            break
        time.sleep(1.5)

    # Wait for final observation alignment
    time.sleep(3.0)
    final_nav_disp = math.hypot(monitor.cur_x - start_x, monitor.cur_y - start_y)
    print(f"• Final Pose in Kitchen:    x={monitor.cur_x:+.3f}m, y={monitor.cur_y:+.3f}m, yaw={math.degrees(monitor.cur_yaw):+.1f}°")
    print(f"• Total Metric Distance:    {final_nav_disp:.2f} m")

    snap5 = monitor.save_snapshot("demo5_kitchen_arrival.jpg", f"DEMO 5: Arrived Kitchen (x={monitor.cur_x:.2f}, y={monitor.cur_y:.2f})")
    demo5_pass = (final_nav_disp > 3.0 and monitor.cur_y < -1.5)
    results["DEMO 5 — Navigation"] = "PASS" if demo5_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 5 — Navigation']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 6: LOOK + MOVE (Independent Head Gaze inside Kitchen)
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 6 — LOOK + MOVE (INDEPENDENT HEAD GAZE IN KITCHEN)")
    print("#" * 70)
    # Robot is in kitchen facing south. Dining table & chairs are located around (-4.0, -4.0, 0.65).
    prompt_kitchen_look = "Look at the dining table at x=-4.0, y=-4.0, z=0.65."
    print(f"• Natural Language Command: \"{prompt_kitchen_look}\"")
    print("• Stationary Base Invariant: Base must stay parked while camera inspects dining table.")

    k_x_before = monitor.cur_x
    k_y_before = monitor.cur_y
    pan_before = monitor.joint_positions.get("neck_pan_joint", 0.0)
    monitor.cmd_vel_count = 0

    resp_k_look = client.reason(prompt=prompt_kitchen_look, tools=tools)
    if resp_k_look.has_function_calls:
        tc = resp_k_look.primary_tool_call
        print(f"• Gemini Selected Tool:     {tc.name}({tc.args})")
        res = registry.execute(tc.name, tc.args)
        print(f"• Tool Execution:           {res.message}")

    print("• Waiting 4.0s for head to orient toward dining table...")
    time.sleep(4.0)

    pan_after = monitor.joint_positions.get("neck_pan_joint", 0.0)
    k_disp = math.hypot(monitor.cur_x - k_x_before, monitor.cur_y - k_y_before)
    pan_delta = abs(pan_after - pan_before)

    print(f"• Neck Pan Before/After:    {math.degrees(pan_before):+.1f}° -> {math.degrees(pan_after):+.1f}°")
    print(f"• Base Pose Before/After:   ({k_x_before:.3f}, {k_y_before:.3f}) -> ({monitor.cur_x:.3f}, {monitor.cur_y:.3f})")
    print(f"• Base Movement in LookAt:  {k_disp:.4f} m (Strictly Stationary)")
    print(f"• /cmd_vel in LookAt:       {monitor.cmd_vel_count} messages")

    snap6 = monitor.save_snapshot("demo6_kitchen_table_gaze.jpg", "DEMO 6: Kitchen Dining Table Gaze")
    demo6_pass = (k_disp < 0.01 and monitor.cmd_vel_count == 0)
    results["DEMO 6 — Look + Move"] = "PASS" if demo6_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 6 — Look + Move']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 7: 7-DOF ARM DEMONSTRATION
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 7 — 7-DOF ARM")
    print("#" * 70)
    print("Executing validated 7-DOF arm stance motion (TRAVEL -> CARRY -> TRAVEL)...")
    
    arm = ArmController()
    time.sleep(0.5)

    q_arm_init = arm.get_joint_positions()
    print(f"• Arm Joint Angles (deg):   {[round(math.degrees(v), 1) for v in q_arm_init]}")

    print("• Actuating 7-DOF arm to STANCE_CARRY (shoulder lift, elbow pitch flex, wrist alignment)...")
    arm.move_to_stance("CARRY", duration_sec=2.5)
    time.sleep(3.0)

    q_carry = arm.get_joint_positions()
    print(f"• CARRY Reached (deg):      {[round(math.degrees(v), 1) for v in q_carry]}")
    snap7a = monitor.save_snapshot("demo7_arm_carry.jpg", "DEMO 7: 7-DOF Arm (STANCE_CARRY)")

    print("• Returning 7-DOF arm safely to STANCE_TRAVEL...")
    arm.move_to_stance("TRAVEL", duration_sec=2.0)
    time.sleep(2.5)

    q_travel = arm.get_joint_positions()
    print(f"• TRAVEL Reached (deg):     {[round(math.degrees(v), 1) for v in q_travel]}")
    snap7b = monitor.save_snapshot("demo7_arm_travel.jpg", "DEMO 7: 7-DOF Arm (STANCE_TRAVEL)")

    # Verify arm motion occurred
    arm_moved = any(abs(c - i) > 0.15 for c, i in zip(q_carry, q_arm_init))
    results["DEMO 7 — Arm"] = "PASS" if arm_moved else "FAIL"
    print(f"• Result:                   {results['DEMO 7 — Arm']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 8: PARALLEL-JAW GRIPPER
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 8 — GRIPPER")
    print("#" * 70)
    print("Executing validated parallel-jaw gripper actuation (OPEN -> CLOSE)...")
    
    hand = HandSubsystem()
    time.sleep(0.5)

    l_pos, r_pos = hand.get_joint_positions()
    print(f"• Initial Finger Positions: left={l_pos*1000:.1f}mm, right={r_pos*1000:.1f}mm")

    print("• Commanding Gripper OPEN (width=80mm)...")
    hand.open(width_m=0.08, timeout_sec=2.0)
    time.sleep(2.5)

    l_open, r_open = hand.get_joint_positions()
    print(f"• Fingers OPEN Displacement: left={l_open*1000:.1f}mm, right={r_open*1000:.1f}mm")
    snap8a = monitor.save_snapshot("demo8_gripper_open.jpg", "DEMO 8: Gripper OPEN (80mm)")

    print("• Commanding Gripper CLOSE (gap=18mm)...")
    hand.close(target_width_m=0.018, timeout_sec=2.0)
    time.sleep(2.5)

    l_closed, r_closed = hand.get_joint_positions()
    print(f"• Fingers CLOSED Displace:   left={l_closed*1000:.1f}mm, right={r_closed*1000:.1f}mm")
    snap8b = monitor.save_snapshot("demo8_gripper_closed.jpg", "DEMO 8: Gripper CLOSED (18mm)")

    gripper_moved = (l_open > 0.01 and r_open > 0.01 and l_closed < l_open and r_closed < r_open)
    results["DEMO 8 — Gripper"] = "PASS" if gripper_moved else "FAIL"
    print(f"• Result:                   {results['DEMO 8 — Gripper']}")
    time.sleep(3.0)

    # =========================================================================
    # DEMO 9: SENSOR ACTIVITY AUDIT
    # =========================================================================
    print("\n" + "#" * 70)
    print("DEMO 9 — SENSORS")
    print("#" * 70)
    print("Auditing live sensory substrate...")

    rgb_ok = monitor.latest_rgb is not None
    depth_ok = monitor.latest_depth is not None
    lidar_ok = monitor.latest_lidar_ranges > 0
    imu_ok = monitor.has_imu
    odom_ok = abs(monitor.cur_x) > 0.1 or abs(monitor.cur_y) > 0.1

    print(f"• RGB Camera Stream:     {'PASS' if rgb_ok else 'FAIL'} ({monitor.latest_rgb.shape[1]}x{monitor.latest_rgb.shape[0]} BGR)")
    print(f"• Depth Sensor Stream:   {'PASS' if depth_ok else 'FAIL'} ({monitor.latest_depth.shape[1]}x{monitor.latest_depth.shape[0]} float32)")
    print(f"• 2D LiDAR Scanner:      {'PASS' if lidar_ok else 'FAIL'} ({monitor.latest_lidar_ranges} beams)")
    print(f"• IMU Telemetry:         {'PASS' if imu_ok else 'FAIL'}")
    print(f"• Odometry State:        {'PASS' if odom_ok else 'FAIL'} (x={monitor.cur_x:+.2f}, y={monitor.cur_y:+.2f})")

    # Generate composite HUD visualization
    if rgb_ok and depth_ok:
        # Normalize depth to 8-bit colormap
        depth_vis = np.nan_to_num(monitor.latest_depth, nan=5.0, posinf=5.0, neginf=0.0)
        depth_norm = np.clip((depth_vis / 5.0) * 255.0, 0, 255).astype(np.uint8)
        depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_TURBO)
        
        # Side-by-side composite
        h, w = monitor.latest_rgb.shape[:2]
        depth_resized = cv2.resize(depth_color, (w, h))
        composite = np.hstack([monitor.latest_rgb, depth_resized])
        
        cv2.putText(composite, "LIVE RGB CAMERA", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(composite, "ACTIVE DEPTH SENSOR", (w + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(composite, f"LiDAR: {monitor.latest_lidar_ranges} beams | IMU: ACTIVE | Pose: ({monitor.cur_x:.2f}, {monitor.cur_y:.2f})",
                    (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        comp_path = REPO_ROOT / "scripts" / "demo9_sensor_activity_composite.jpg"
        cv2.imwrite(str(comp_path), composite)
        print(f"• Composite HUD Saved:   {comp_path}")

    demo9_pass = (rgb_ok and depth_ok and lidar_ok and imu_ok and odom_ok)
    results["DEMO 9 — Sensors"] = "PASS" if demo9_pass else "FAIL"
    print(f"• Result:                   {results['DEMO 9 — Sensors']}")

    # =========================================================================
    # SUMMARY REPORT
    # =========================================================================
    print("\n" + "=" * 80)
    print("  LIVE SIMULATION DEMONSTRATION SUMMARY")
    print("=" * 80)
    for demo_name, status in results.items():
        print(f"{demo_name:30s} {status}")
    print("=" * 80)
    print("\nSIMULATION IS RUNNING — READY FOR LIVE OBSERVATION\n")


if __name__ == "__main__":
    run_all_demonstrations()
