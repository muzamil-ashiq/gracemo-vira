#!/usr/bin/env python3
"""
Continuous Obstacle Avoidance Navigator for Piece 2 (Mobile Base + Elevated LiDAR).
Runs indefinitely, exploring the multi-obstacle arena and weaving through obstacles smoothly.
"""
import time
import math
import sys
import argparse
import gz.transport13 as gz_transport
from gz.msgs10.laserscan_pb2 import LaserScan
from gz.msgs10.twist_pb2 import Twist

class ContinuousNavigator:
    def __init__(self):
        self.node = gz_transport.Node()
        self.pub_cmd = self.node.advertise("/cmd_vel", Twist)
        self.node.subscribe(LaserScan, "/scan", self.on_scan)

        self.x_lidar = 0.110
        self.r_self = 0.215

        self.min_center = 99.0
        self.min_left = 99.0
        self.min_right = 99.0
        self.last_scan_time = 0.0

        # State tracking
        self.preferred_steer = 1.0
        self.last_pivot_time = 0.0

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
            if math.isnan(r) or math.isinf(r) or r < 0.05 or r > 12.0:
                continue

            theta = angle_min + i * angle_step

            # Euclidean footprint transformation
            x_rob = self.x_lidar + r * math.cos(theta)
            y_rob = r * math.sin(theta)
            d_center = math.hypot(x_rob, y_rob)

            if d_center <= self.r_self:
                continue

            deg = math.degrees(theta)
            if -20.0 <= deg <= 20.0:
                c_dists.append(r)
            elif 20.0 < deg <= 80.0:
                l_dists.append(r)
            elif -80.0 <= deg < -20.0:
                r_dists.append(r)

        self.min_center = min(c_dists) if c_dists else 99.0
        self.min_left   = min(l_dists) if l_dists else 99.0
        self.min_right  = min(r_dists) if r_dists else 99.0
        self.last_scan_time = time.time()

    def run(self, max_duration=None):
        mode_str = f"Continuous ({max_duration}s limit)" if max_duration else "Continuous (Indefinite — press Ctrl+C to stop)"
        print("==================================================================")
        print("  GRaCEmo ViRa — Continuous Obstacle Navigation Controller")
        print(f"  Mode: {mode_str}")
        print("  Footprint Filter: Euclidean (R_self = 0.215m)")
        print("==================================================================")
        print("Waiting for /scan stream...")
        while self.last_scan_time == 0.0:
            time.sleep(0.1)
        print("✓ Sensor stream active! Navigating arena...\n")

        t_start = time.time()
        last_log = 0.0
        is_pivoting = False

        try:
            while True:
                now = time.time()
                if max_duration and (now - t_start >= max_duration):
                    break

                dc = self.min_center
                dl = self.min_left
                dr = self.min_right

                # 1. Trapped in a tight corner / pocket (all close) -> Reverse back
                if dc < 0.35 and dl < 0.40 and dr < 0.40:
                    vx = -0.18
                    wz = 0.60 * self.preferred_steer
                    state = "POCKET REVERSE ESCAPE"

                # 2. Obstacle ahead within close cushion (<= 0.52m) or currently pivoting
                elif dc <= 0.52 or is_pivoting:
                    is_pivoting = True
                    vx = 0.00
                    # Pick clearer side and lock it for smooth turning
                    if now - self.last_pivot_time > 1.2:
                        self.preferred_steer = 1.0 if dl >= dr else -1.0
                        self.last_pivot_time = now

                    wz = self.preferred_steer * 0.95
                    state = f"PIVOT CLEARANCE ({'LEFT' if self.preferred_steer > 0 else 'RIGHT'})"

                    # Exit pivot when ahead has opened up to a wide corridor
                    if dc > 0.95 and min(dl, dr) > 0.45:
                        is_pivoting = False

                # 3. Approaching Obstacle (0.52m - 1.20m) -> Decelerate & weave
                elif dc <= 1.20:
                    is_pivoting = False
                    vx = 0.14 + 0.20 * ((dc - 0.52) / (1.20 - 0.52))
                    steer_dir = 1.0 if dl >= dr else -1.0
                    wz = steer_dir * 0.70
                    state = f"WEAVE AVOID ({'LEFT' if steer_dir > 0 else 'RIGHT'})"

                # 4. Wide Open Space (> 1.20m) -> Full cruise speed
                else:
                    is_pivoting = False
                    vx = 0.35
                    # Gentle centering bias away from whichever wall is closer
                    if dl < 0.75:
                        wz = -0.25
                        state = "CRUISE (BIAS RIGHT)"
                    elif dr < 0.75:
                        wz = +0.25
                        state = "CRUISE (BIAS LEFT)"
                    else:
                        wz = 0.00
                        state = "FULL CRUISE FORWARD"

                # Publish command
                cmd = Twist()
                cmd.linear.x = float(vx)
                cmd.angular.z = float(wz)
                self.pub_cmd.publish(cmd)

                if now - last_log >= 0.40:
                    print(f"[{now - t_start:5.1f}s] {state:<24s} | Dist: C={dc:4.2f}m L={dl:4.2f}m R={dr:4.2f}m | cmd: vx={vx:.2f} wz={wz:+.2f}")
                    last_log = now

                time.sleep(0.04)

        except KeyboardInterrupt:
            print("\nOperator requested stop.")

        # Stop at the end
        cmd = Twist()
        self.pub_cmd.publish(cmd)
        print("✓ Navigator stopped cleanly.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=None, help="Run duration in seconds (default: continuous)")
    args = parser.parse_args()

    ctrl = ContinuousNavigator()
    ctrl.run(args.duration)
