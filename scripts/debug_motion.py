#!/usr/bin/env python3
"""
Diagnostic: Drive robot forward for 3 seconds, log odometry every 100ms.
This tells us if the robot actually moves or is stuck/jittering.
"""
import time, math, sys
import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry

node = gz_transport.Node()
pub = node.advertise("/cmd_vel", GzTwist)

odom_log = []
cur = {"x": 0, "y": 0, "yaw": 0, "got": False}

def on_odom(msg):
    pos = msg.pose.position
    q = msg.pose.orientation
    siny = 2 * (q.w * q.z + q.x * q.y)
    cosy = 1 - 2 * (q.y * q.y + q.z * q.z)
    cur["x"] = pos.x
    cur["y"] = pos.y
    cur["yaw"] = math.atan2(siny, cosy)
    cur["got"] = True

node.subscribe(GzOdometry, "/odom", on_odom)

print("Waiting for odometry...")
for _ in range(50):
    if cur["got"]:
        break
    time.sleep(0.1)

if not cur["got"]:
    print("ERROR: No odometry received! The /odom topic is not publishing.")
    print("This means the DiffDrive plugin is not running or the topic name is wrong.")
    sys.exit(1)

start_x, start_y = cur["x"], cur["y"]
print(f"Start position: ({start_x:.4f}, {start_y:.4f}), yaw={math.degrees(cur['yaw']):.1f}°")

# Phase 1: Send forward velocity for 3 seconds
print("\n--- DRIVING FORWARD at vx=0.3 for 3 seconds ---")
t0 = time.time()
while time.time() - t0 < 3.0:
    twist = GzTwist()
    twist.linear.x = 0.3
    twist.angular.z = 0.0
    pub.publish(twist)
    odom_log.append((time.time() - t0, cur["x"], cur["y"], math.degrees(cur["yaw"])))
    time.sleep(0.1)

# Stop
twist = GzTwist()
twist.linear.x = 0.0
twist.angular.z = 0.0
pub.publish(twist)

end_x, end_y = cur["x"], cur["y"]
dist = math.hypot(end_x - start_x, end_y - start_y)

print(f"End position:   ({end_x:.4f}, {end_y:.4f}), yaw={math.degrees(cur['yaw']):.1f}°")
print(f"Distance moved: {dist:.4f} m")

if dist < 0.05:
    print("\n⚠️  ROBOT DID NOT MOVE! Possible causes:")
    print("  1. Wheels are trapped inside chassis collision geometry")
    print("  2. Robot is spawned inside floor/wall geometry")
    print("  3. DiffDrive plugin wheel_separation or wheel_radius is wrong")
    print("  4. Wheel joints are not connected to the correct links")
elif dist < 0.3:
    print("\n⚠️  ROBOT MOVED VERY LITTLE (expected ~0.9m at 0.3m/s for 3s)")
    print("  Possible wheel slip or ground contact issue")
else:
    print(f"\n✅ Robot moved {dist:.2f}m — physics seems OK!")

print("\n--- Odometry Log (time, x, y, yaw_deg) ---")
for t, x, y, yaw in odom_log[::3]:  # Print every 3rd entry
    print(f"  t={t:.2f}s  x={x:+.4f}  y={y:+.4f}  yaw={yaw:+.1f}°")

# Phase 2: Turn in place for 2 seconds
print("\n--- TURNING LEFT at wz=0.5 for 2 seconds ---")
yaw_start = cur["yaw"]
t0 = time.time()
while time.time() - t0 < 2.0:
    twist = GzTwist()
    twist.linear.x = 0.0
    twist.angular.z = 0.5
    pub.publish(twist)
    time.sleep(0.1)

twist = GzTwist()
pub.publish(twist)

yaw_end = cur["yaw"]
yaw_diff = math.degrees(yaw_end - yaw_start)
print(f"Yaw changed: {yaw_diff:+.1f}° (expected ~+57°)")

if abs(yaw_diff) < 5:
    print("\n⚠️  ROBOT DID NOT TURN! Joints may be locked or wheels stuck.")
else:
    print(f"\n✅ Robot turned {yaw_diff:.1f}° — rotation works!")
