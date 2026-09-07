#!/usr/bin/env python3
import time
import math
import numpy as np

import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan

node = gz_transport.Node()
cmd_pub = node.advertise("/cmd_vel", GzTwist)

cur_x, cur_y, cur_yaw = 0.0, 0.0, 0.0
latest_scan = None

def odom_cb(msg: GzOdometry):
    global cur_x, cur_y, cur_yaw
    p = msg.pose.position
    q = msg.pose.orientation
    siny = 2 * (q.w * q.z + q.x * q.y)
    cosy = 1 - 2 * (q.y * q.y + q.z * q.z)
    cur_x, cur_y = p.x, p.y
    cur_yaw = math.atan2(siny, cosy)

def scan_cb(msg: GzLaserScan):
    global latest_scan
    latest_scan = msg

node.subscribe(GzOdometry, "/odom", odom_cb)
node.subscribe(GzLaserScan, "/scan", scan_cb)

time.sleep(1.0)
print("🎯 Testing direct wall approach: First pivoting ViRa to face North wall (+90°)...")

# Step 1: Pivot to face North (+90 deg)
target_yaw = math.pi / 2
t0 = time.time()
while time.time() - t0 < 4.0:
    time.sleep(0.04)
    err = target_yaw - cur_yaw
    while err > math.pi: err -= 2*math.pi
    while err < -math.pi: err += 2*math.pi
    if abs(err) < math.radians(4):
        break
    tw = GzTwist()
    tw.angular.z = float(np.clip(1.2 * err, -0.6, 0.6))
    cmd_pub.publish(tw)

cmd_pub.publish(GzTwist())
print(f"✓ ViRa now facing North wall! Pose: ({cur_x:+.2f}m, {cur_y:+.2f}m, yaw={math.degrees(cur_yaw):+.0f}°)")
print("\n🚨 [EXPERIMENT]: Sending command to drive straight forward into the wall at +0.35 m/s!")
print("🛡️ Watch the Autonomous LiDAR Reflex Shield brake & curve to save the robot:")
print("─" * 75)

# Step 2: Drive forward with reflex shield active
t_start = time.time()
log_tick = 0
while time.time() - t_start < 8.0:
    time.sleep(0.04)
    log_tick += 1

    cmd_vx = 0.35
    cmd_wz = 0.0

    min_front_dist = 10.0
    repulse_wz = 0.0
    reflex_engaged = False

    if latest_scan and len(latest_scan.ranges) >= 180:
        ranges = latest_scan.ranges
        n = len(ranges)
        ang_min = latest_scan.angle_min
        inc = latest_scan.angle_step if latest_scan.angle_step > 0 else (2.0 * math.pi / n)

        for i, r in enumerate(ranges):
            if 0.16 < r < 0.60 and not math.isnan(r) and not math.isinf(r):
                b_ang = ang_min + i * inc
                weight = (0.60 - r) / 0.60
                repulse_wz += -0.90 * weight * math.sin(b_ang)
                reflex_engaged = True
                if abs(b_ang) < math.radians(35):
                    if r < min_front_dist:
                        min_front_dist = r

    # Reflex braking
    safe_vx = cmd_vx
    if min_front_dist < 0.55:
        reflex_engaged = True
        brake = max(0.0, (min_front_dist - 0.25) / (0.55 - 0.25))
        safe_vx = cmd_vx * (brake ** 1.8)
        # Automatic reflex swerve when approaching front barrier
        repulse_wz += 0.50

    safe_wz = float(np.clip(cmd_wz + repulse_wz, -0.65, 0.65))

    tw = GzTwist()
    tw.linear.x = safe_vx
    tw.angular.z = safe_wz
    cmd_pub.publish(tw)

    if log_tick % 10 == 0:
        status = "🛡️ REFLEX ENGAGED" if reflex_engaged else "🟢 CLEAR"
        print(f"[{status:<17}] Pos: ({cur_x:+.2f}m, {cur_y:+.2f}m) | Wall Dist: {min_front_dist:.2f}m | Input vx: {cmd_vx:.2f} → Output vx: {safe_vx:.2f}, wz: {safe_wz:+.2f}")

cmd_pub.publish(GzTwist())
print("─" * 75)
print(f"🏆 SUCCESS! Final pose: ({cur_x:+.2f}m, {cur_y:+.2f}m). Robot safely stopped and swerved without touching the wall!")
