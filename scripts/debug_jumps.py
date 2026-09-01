#!/usr/bin/env python3
"""
Diagnostic 2: Monitor odometry for jumps/teleports while the robot drives.
Prints a warning whenever position jumps more than 0.1m between consecutive readings.
"""
import time, math, sys
import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry

node = gz_transport.Node()
pub = node.advertise("/cmd_vel", GzTwist)

prev = {"x": None, "y": None, "yaw": None, "t": None}
jump_count = 0
total_readings = 0

def on_odom(msg):
    global jump_count, total_readings
    pos = msg.pose.position
    q = msg.pose.orientation
    siny = 2 * (q.w * q.z + q.x * q.y)
    cosy = 1 - 2 * (q.y * q.y + q.z * q.z)
    x, y, yaw = pos.x, pos.y, math.atan2(siny, cosy)
    now = time.time()
    total_readings += 1

    if prev["x"] is not None:
        dx = x - prev["x"]
        dy = y - prev["y"]
        jump = math.hypot(dx, dy)
        dt = now - prev["t"]
        if jump > 0.1 and dt < 0.5:
            jump_count += 1
            print(f"  ⚠️  JUMP #{jump_count} at t={now:.2f}: "
                  f"({prev['x']:+.3f},{prev['y']:+.3f}) → ({x:+.3f},{y:+.3f}) "
                  f"jump={jump:.3f}m in {dt:.3f}s  "
                  f"yaw: {math.degrees(prev['yaw']):+.1f}° → {math.degrees(yaw):+.1f}°")

    prev["x"], prev["y"], prev["yaw"], prev["t"] = x, y, yaw, now

node.subscribe(GzOdometry, "/odom", on_odom)

print("Waiting for first odom...")
time.sleep(1)
if prev["x"] is None:
    print("ERROR: no odom received")
    sys.exit(1)

print(f"Start: ({prev['x']:+.3f}, {prev['y']:+.3f}), yaw={math.degrees(prev['yaw']):+.1f}°")
print(f"\n--- Driving forward slowly (vx=0.2) for 10 seconds ---")
print(f"--- Watching for position jumps > 0.1m ---\n")

t0 = time.time()
while time.time() - t0 < 10.0:
    twist = GzTwist()
    twist.linear.x = 0.2
    twist.angular.z = 0.0
    pub.publish(twist)
    time.sleep(0.05)

# Stop
twist = GzTwist()
pub.publish(twist)
time.sleep(0.5)

print(f"\n--- Results ---")
print(f"Total odom readings: {total_readings}")
print(f"Position jumps detected: {jump_count}")
print(f"End: ({prev['x']:+.3f}, {prev['y']:+.3f}), yaw={math.degrees(prev['yaw']):+.1f}°")

if jump_count > 0:
    print(f"\n🔴 Found {jump_count} teleport jumps! This is the cause of the flashing.")
    print(f"   The robot is being repositioned by something external.")
else:
    print(f"\n🟢 No jumps detected. Odometry is smooth.")
    print(f"   The 'flashing' may be a Gazebo rendering/GPU issue, not physics.")
