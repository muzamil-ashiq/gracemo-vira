#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase A Physics Validation: In-Place Spin & Axle CoM Test
Tests whether the physical robot rotates in-place without eccentric drift.
Success criterion: Translational drift sqrt(dx^2 + dy^2) < 0.05m during rotation.
"""

import sys
import time
import math
from pathlib import Path

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.twist_pb2 import Twist as GzTwist
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
except ImportError:
    print("ERROR: gz.transport13 or gz.msgs10 not available. Run inside distrobox gracemo-harmonic.")
    sys.exit(1)

class SpinTester:
    def __init__(self):
        self.node = gz_transport.Node()
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        
        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.has_odom = False

    def _on_odom(self, msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        siny = 2 * (q.w * q.z + q.x * q.y)
        cosy = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.cur_x = p.x
        self.cur_y = p.y
        self.cur_yaw = math.atan2(siny, cosy)
        self.has_odom = True

    def stop(self):
        tw = GzTwist()
        tw.linear.x = 0.0
        tw.angular.z = 0.0
        self.cmd_pub.publish(tw)

    def run_test(self, duration_sec: float = 6.0, wz_cmd: float = 0.5) -> bool:
        print("[SpinTester] Waiting for /odom...")
        t0 = time.time()
        while not self.has_odom and time.time() - t0 < 5.0:
            time.sleep(0.05)
        
        if not self.has_odom:
            print("[SpinTester] FAIL: No /odom received within 5 seconds.")
            return False

        x0, y0, yaw0 = self.cur_x, self.cur_y, self.cur_yaw
        print(f"[SpinTester] Initial Pose: x={x0:.4f}, y={y0:.4f}, yaw={math.degrees(yaw0):.1f}°")

        print(f"[SpinTester] Commanding pure rotation wz={wz_cmd} rad/s for {duration_sec}s...")
        t_start = time.time()
        while time.time() - t_start < duration_sec:
            tw = GzTwist()
            tw.linear.x = 0.0
            tw.angular.z = wz_cmd
            self.cmd_pub.publish(tw)
            time.sleep(0.02)

        # Stop and let settle
        self.stop()
        time.sleep(1.0)
        self.stop()

        x1, y1, yaw1 = self.cur_x, self.cur_y, self.cur_yaw
        dx = x1 - x0
        dy = y1 - y0
        drift = math.hypot(dx, dy)
        yaw_diff = math.atan2(math.sin(yaw1 - yaw0), math.cos(yaw1 - yaw0))

        print(f"[SpinTester] Final Pose:   x={x1:.4f}, y={y1:.4f}, yaw={math.degrees(yaw1):.1f}°")
        print(f"[SpinTester] Displacement: dx={dx:.4f}m, dy={dy:.4f}m => Translational Drift = {drift:.4f}m")
        print(f"[SpinTester] Rotation:     Net turn = {math.degrees(yaw_diff):.1f}°")

        threshold = 0.05  # 5 cm max allowable drift
        if drift >= threshold:
            print(f"[SpinTester] FAIL: Excessive translational drift {drift:.4f}m >= {threshold}m.")
            return False
        print(f"[SpinTester] PASS: Robot CoM is well-centered on wheel axle! Drift {drift:.4f}m < {threshold}m.")

        # Test 2: Pure Linear Drive (Forward 1.0m, Backward 1.0m)
        print("\n[LinearTester] Testing forward drive vx=0.3 m/s for 3.0s...")
        t_lin = time.time()
        while time.time() - t_lin < 3.0:
            tw = GzTwist()
            tw.linear.x = 0.3
            tw.angular.z = 0.0
            self.cmd_pub.publish(tw)
            time.sleep(0.02)

        self.stop()
        time.sleep(0.5)

        x2, y2, yaw2 = self.cur_x, self.cur_y, self.cur_yaw
        print(f"[LinearTester] Forward Pose: x={x2:.4f}, y={y2:.4f}, yaw={math.degrees(yaw2):.1f}°")
        
        # Drive back
        print("[LinearTester] Testing reverse drive vx=-0.3 m/s for 3.0s...")
        t_rev = time.time()
        while time.time() - t_rev < 3.0:
            tw = GzTwist()
            tw.linear.x = -0.3
            tw.angular.z = 0.0
            self.cmd_pub.publish(tw)
            time.sleep(0.02)

        self.stop()
        time.sleep(1.0)
        self.stop()

        x3, y3, yaw3 = self.cur_x, self.cur_y, self.cur_yaw
        print(f"[LinearTester] Return Pose:  x={x3:.4f}, y={y3:.4f}, yaw={math.degrees(yaw3):.1f}°")
        return_err = math.hypot(x3 - x1, y3 - y1)
        print(f"[LinearTester] Closed-loop round-trip return error: {return_err:.4f}m")
        if return_err < 0.05:
            print(f"[LinearTester] PASS: High traction and linear tracking validated! Error {return_err:.4f}m < 0.05m.")
            return True
        else:
            print(f"[LinearTester] FAIL: Excessive return error {return_err:.4f}m.")
            return False

if __name__ == "__main__":
    tester = SpinTester()
    success = tester.run_test()
    sys.exit(0 if success else 1)

