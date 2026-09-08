#!/usr/bin/env python3
"""
Sensor-Driven Obstacle Avoidance Demo for Piece 2 (Mobile Base + Elevated LiDAR).
Uses Euclidean Robot Footprint Filtering to reject self-hits while detecting obstacles down to +2.5cm clearance.
"""
import time
import math
import sys
import gz.transport13 as gz_transport
from gz.msgs10.laserscan_pb2 import LaserScan
from gz.msgs10.twist_pb2 import Twist

class ObstacleAvoidanceController:
    def __init__(self):
        self.node = gz_transport.Node()
        self.pub_cmd = self.node.advertise("/cmd_vel", Twist)
        self.node.subscribe(LaserScan, "/scan", self.on_scan)

        # Footprint filter parameters
        self.x_lidar = 0.110    # LiDAR X offset from robot axle
        self.r_self = 0.215     # Outer bumper radius + 1cm margin (205mm + 10mm)

        # Clearance distances (meters)
        self.min_center = 99.0
        self.min_left = 99.0
        self.min_right = 99.0
        self.last_scan_time = 0.0

    def on_scan(self, msg: LaserScan):
        n = len(msg.ranges)
        if n == 0:
            return

        c_dists = []
        l_dists = []
        r_dists = []

        angle_min = msg.angle_min
        angle_step = msg.angle_step

        for i in range(n):
            r = msg.ranges[i]
            if math.isnan(r) or math.isinf(r) or r < 0.05 or r > 10.0:
                continue

            theta = angle_min + i * angle_step

            # Transform ray endpoint into robot base frame
            x_rob = self.x_lidar + r * math.cos(theta)
            y_rob = r * math.sin(theta)
            d_center = math.hypot(x_rob, y_rob)

            # Rejection: strictly inside physical robot bumper
            if d_center <= self.r_self:
                continue

            # Legitimate physical obstacle detected!
            deg = math.degrees(theta)
            if -18.0 <= deg <= 18.0:
                c_dists.append(r)
            elif 18.0 < deg <= 75.0:
                l_dists.append(r)
            elif -75.0 <= deg < -18.0:
                r_dists.append(r)

        self.min_center = min(c_dists) if c_dists else 99.0
        self.min_left   = min(l_dists) if l_dists else 99.0
        self.min_right  = min(r_dists) if r_dists else 99.0
        self.last_scan_time = time.time()

    def run(self, max_duration=25.0):
        print("==================================================================")
        print("  GRaCEmo ViRa — Piece 2 Sensor Obstacle Avoidance Live Controller")
        print("  Algorithm: Euclidean Footprint Filter + Regulated Unicycle Avoidance")
        print("==================================================================")
        print("Waiting for /scan stream...")
        while self.last_scan_time == 0.0:
            time.sleep(0.1)
        print("✓ LiDAR /scan stream active!")

        t_start = time.time()
        last_log = 0.0

        try:
            while time.time() - t_start < max_duration:
                # Controller decisions
                dc = self.min_center
                dl = self.min_left
                dr = self.min_right

                # 1. Wide Clear Ahead -> Cruise forward
                if dc > 1.20:
                    vx = 0.35
                    wz = 0.00
                    state = "CRUISE FORWARD"

                # 2. Approaching Obstacle (0.50m - 1.20m) -> Decelerate & smoothly steer toward open side
                elif dc > 0.48:
                    vx = 0.12 + 0.20 * ((dc - 0.48) / (1.20 - 0.48))
                    # Steer away from closest obstacle
                    steer_dir = 1.0 if dl >= dr else -1.0
                    wz = steer_dir * 0.75
                    state = f"SMOOTH STEER ({'LEFT' if steer_dir > 0 else 'RIGHT'})"

                # 3. Close Proximity Cushion (<= 0.48m) -> Stop forward motion, pivot in place to clear path
                else:
                    vx = 0.00
                    steer_dir = 1.0 if dl >= dr else -1.0
                    wz = steer_dir * 0.90
                    state = f"PROXIMITY PIVOT ({'LEFT' if steer_dir > 0 else 'RIGHT'})"

                # Publish command
                cmd = Twist()
                cmd.linear.x = float(vx)
                cmd.angular.z = float(wz)
                self.pub_cmd.publish(cmd)

                now = time.time()
                if now - last_log >= 0.35:
                    print(f"[{now - t_start:4.1f}s] {state:<22s} | Clear: Center={dc:4.2f}m Left={dl:4.2f}m Right={dr:4.2f}m | Cmd: vx={vx:.2f} wz={wz:+.2f}")
                    last_log = now

                time.sleep(0.05)

        except KeyboardInterrupt:
            pass

        # Stop at the end
        cmd = Twist()
        self.pub_cmd.publish(cmd)
        print("✓ Avoidance demo completed. Robot stopped.")

if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    ctrl = ObstacleAvoidanceController()
    ctrl.run(dur)
