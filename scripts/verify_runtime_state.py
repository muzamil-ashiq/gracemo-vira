#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 3 Visual / Runtime Simulation State Verifier
Inspects live Gazebo Harmonic physics, ROS 2 topics, and Kernel state.
"""

import json
import math
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import gz.transport13 as gz_transport
from gz.msgs10.model_pb2 import Model as GzModel
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan
from gz.msgs10.imu_pb2 import IMU as GzIMU

def main():
    print("=" * 70)
    print("GRaCEmo ViRa — RUNTIME SIMULATION STATE AUDIT")
    print("=" * 70)

    # 1. Kernel Health
    print("\n1. KERNEL NERVOUS SYSTEM (HTTP :7780)")
    try:
        with urllib.request.urlopen("http://127.0.0.1:7780/health", timeout=1.0) as resp:
            data = json.loads(resp.read().decode())
            print(f"   Status:  {data.get('status')}")
            print(f"   Service: {data.get('service')} (v{data.get('version')})")
    except Exception as e:
        print(f"   ERROR: Kernel unreachable: {e}")
        return False

    # 2. Gazebo Harmonic Node & Subscriptions
    print("\n2. GAZEBO HARMONIC 8 RUNTIME TELEMETRY")
    gz_node = gz_transport.Node()

    state = {
        "joint_positions": {},
        "cur_pos": None,
        "cur_rpy": None,
        "got_camera": False,
        "camera_dims": None,
        "got_lidar": False,
        "lidar_ranges": None,
        "got_imu": False,
    }

    def on_joint_state(msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                state["joint_positions"][j.name] = float(j.axis1.position)

    def on_odom(msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        state["cur_pos"] = (p.x, p.y, p.z)
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny, cosy)
        pitch = math.asin(max(-1.0, min(1.0, 2.0 * (q.w * q.y - q.z * q.x))))
        roll = math.atan2(2.0 * (q.w * q.x + q.y * q.z), 1.0 - 2.0 * (q.x * q.x + q.y * q.y))
        state["cur_rpy"] = (roll, pitch, yaw)

    def on_camera(msg: GzImage):
        state["got_camera"] = True
        state["camera_dims"] = (msg.width, msg.height)

    def on_lidar(msg: GzLaserScan):
        state["got_lidar"] = True
        state["lidar_ranges"] = len(msg.ranges)

    def on_imu(msg: GzIMU):
        state["got_imu"] = True

    gz_node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", on_joint_state)
    gz_node.subscribe(GzOdometry, "/odom", on_odom)
    gz_node.subscribe(GzImage, "/camera/image_raw", on_camera)
    gz_node.subscribe(GzLaserScan, "/scan", on_lidar)
    gz_node.subscribe(GzIMU, "/imu/data", on_imu)

    # Wait for telemetry
    t0 = time.time()
    while time.time() - t0 < 4.0:
        if state["cur_pos"] and len(state["joint_positions"]) >= 13 and state["got_camera"]:
            break
        time.sleep(0.1)

    # Check Robot Pose
    if state["cur_pos"]:
        x, y, z = state["cur_pos"]
        r, p, yaw = state["cur_rpy"]
        print(f"   Robot Position:  x={x:+.3f}m, y={y:+.3f}m, z={z:+.3f}m")
        print(f"   Robot Attitude:  roll={math.degrees(r):+.1f}°, pitch={math.degrees(p):+.1f}°, yaw={math.degrees(yaw):+.1f}°")
        # Base is on floor if z is ~0.065m and roll/pitch near zero
        is_upright = abs(r) < 0.1 and abs(p) < 0.1
        is_on_ground = 0.05 <= z <= 0.12
        print(f"   Ground Contact:  {'✓ UPRIGHT ON GROUND' if (is_upright and is_on_ground) else '⚠️ ABNORMAL POSE'}")
    else:
        print("   ERROR: No odometry received from Gazebo!")
        return False

    # Check Joints
    print("\n3. ARTICULATED STRUCTURE & JOINTS")
    print(f"   Total Active Joints: {len(state['joint_positions'])}/13")
    joints = sorted(state["joint_positions"].keys())
    print("   Raw Joint Keys:", joints)
    
    expected_categories = {
        "Neck (Phase 3)": ["neck_pan_joint", "neck_tilt_joint"],
        "Mobility Base": ["left_wheel_joint", "right_wheel_joint"],
        "7-DOF Arm": [
            "right_shoulder_yaw_joint",
            "right_shoulder_pitch_joint",
            "right_shoulder_roll_joint",
            "right_elbow_pitch_joint",
            "right_wrist_yaw_joint",
            "right_wrist_pitch_joint",
            "right_wrist_roll_joint",
        ],
        "Gripper": ["finger_left_joint", "finger_right_joint"],
    }

    all_found = True
    for cat, expected in expected_categories.items():
        print(f"   • {cat}:")
        for j in expected:
            if j in state["joint_positions"]:
                val = state["joint_positions"][j]
                print(f"       - {j:26s}: {math.degrees(val):+7.2f}° ({val:+6.3f} rad)")
            else:
                print(f"       - {j:26s}: ❌ MISSING")
                all_found = False

    # Check Sensors
    print("\n4. PHYSICAL SENSORS ACTIVE")
    print(f"   • Head RGB Camera:   {'✓ ACTIVE (' + str(state['camera_dims'][0]) + 'x' + str(state['camera_dims'][1]) + ')' if state['got_camera'] else '❌ INACTIVE'}")
    print(f"   • 2D LiDAR Scanner:  {'✓ ACTIVE (' + str(state['lidar_ranges']) + ' beams)' if state['got_lidar'] else '❌ INACTIVE'}")
    print(f"   • IMU Sensor:        {'✓ ACTIVE' if state['got_imu'] else '❌ INACTIVE'}")

    print("\n" + "=" * 70)
    if all_found and state["got_camera"] and state["got_lidar"]:
        print("✓ SIMULATION VISUAL / RUNTIME AUDIT: ALL SYSTEMS NOMINAL")
    else:
        print("⚠️ SOME SYSTEMS INCOMPLETE")
    print("=" * 70)
    import os
    os._exit(0 if all_found else 1)

if __name__ == "__main__":
    main()
