#!/usr/bin/env python3
import time
import math
import sys
from pathlib import Path

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.twist_pb2 import Twist as GzTwist
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
except ImportError:
    print("Error: gz.transport13 not found")
    sys.exit(1)

cur_yaw = 0.0
has_odom = False

def on_odom(msg):
    global cur_yaw, has_odom
    q = msg.pose.orientation
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    cur_yaw = math.atan2(siny, cosy)
    has_odom = True

node = gz_transport.Node()
node.subscribe(GzOdometry, "/odom", on_odom)
cmd_pub = node.advertise("/cmd_vel", GzTwist)

time.sleep(1.0)
target_yaw = -math.pi / 2  # -1.5708 rad (South)
print(f"Current yaw: {math.degrees(cur_yaw):.1f}° | Target yaw: {math.degrees(target_yaw):.1f}°")

t0 = time.time()
while time.time() - t0 < 8.0:
    yaw_err = target_yaw - cur_yaw
    while yaw_err > math.pi: yaw_err -= 2.0 * math.pi
    while yaw_err < -math.pi: yaw_err += 2.0 * math.pi
    if abs(yaw_err) < 0.08:
        print(f"Target yaw reached: {math.degrees(cur_yaw):.1f}°")
        break
    tw = GzTwist()
    tw.angular.z = math.copysign(min(0.7, max(0.25, abs(yaw_err) * 1.2)), yaw_err)
    cmd_pub.publish(tw)
    time.sleep(0.05)

# Stop
tw = GzTwist()
cmd_pub.publish(tw)
time.sleep(0.5)
print(f"Final settled yaw: {math.degrees(cur_yaw):.1f}°")
