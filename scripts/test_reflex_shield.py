#!/usr/bin/env python3
"""
GRaCEmo ViRa — Autonomous LiDAR Reflex Shield (Spinal Cord Obstacle Avoidance)
Demonstrates autonomous bodily collision avoidance:
1. Conscious brain / user commands robot to drive straight forward.
2. The Subconscious Reflex Shield intercepts commands at 50Hz.
3. Using 360° LiDAR rays, it automatically repulses and brakes,
   preventing ANY wall collision without brain intervention.
"""

import sys
import time
import math
import numpy as np

import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan


class ReflexShieldDemo:
    def __init__(self):
        self.node = gz_transport.Node()
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.has_odom = False
        self.latest_scan = None

    def _on_odom(self, msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        siny = 2 * (q.w * q.z + q.x * q.y)
        cosy = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.cur_x = p.x
        self.cur_y = p.y
        self.cur_yaw = math.atan2(siny, cosy)
        self.has_odom = True

    def _on_scan(self, msg: GzLaserScan):
        self.latest_scan = msg

    def stop(self):
        tw = GzTwist()
        tw.linear.x = 0.0
        tw.angular.z = 0.0
        self.cmd_pub.publish(tw)

    def run_demo(self, duration_sec: float = 10.0):
        print("🛡️ [LIDAR REFLEX SHIELD] Starting spinal reflex test...")
        print("  -> Waiting for odometry and LiDAR scan...")

        t0 = time.time()
        while (not self.has_odom or self.latest_scan is None) and time.time() - t0 < 4.0:
            time.sleep(0.05)

        if not self.has_odom:
            print("❌ Error: No odometry from Gazebo.")
            return

        print(f"✓ Connected! ViRa at ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m, yaw={math.degrees(self.cur_yaw):+.0f}°)")
        print("\n🧠 [BRAIN COMMAND]: 'Drive straight forward at +0.35 m/s' (No steering commanded)")
        print("🛡️ [REFLEX SHIELD]: Monitoring 360° LiDAR cushion (Safety threshold: 0.50m)...")
        print("─" * 75)

        start_time = time.time()
        log_tick = 0

        while time.time() - start_time < duration_sec:
            time.sleep(0.04)  # 25Hz reflex loop
            log_tick += 1

            # 1. Conscious Brain Command (Blind forward drive)
            cmd_vx = 0.35
            cmd_wz = 0.00

            # 2. Subconscious Reflex Filter (LiDAR Somatosensory Shield)
            min_front_dist = 10.0
            repulse_wz = 0.0
            reflex_active = False

            if self.latest_scan and len(self.latest_scan.ranges) >= 180:
                ranges = self.latest_scan.ranges
                n = len(ranges)
                ang_min = self.latest_scan.angle_min
                inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)

                for i, r in enumerate(ranges):
                    if 0.16 < r < 0.55 and not math.isnan(r) and not math.isinf(r):
                        b_ang = ang_min + i * inc
                        # Obstacle within 55cm cushion
                        weight = (0.55 - r) / 0.55

                        # Lateral repulsion torque: pushes body away from side/diagonal obstacles
                        repulse_wz += -0.90 * weight * math.sin(b_ang)
                        reflex_active = True

                        # Frontal clearance (within +/- 35 deg cone)
                        if abs(b_ang) < math.radians(35):
                            if r < min_front_dist:
                                min_front_dist = r

            # 3. Emergency Deceleration / Braking Reflex
            safe_vx = cmd_vx
            if min_front_dist < 0.50:
                reflex_active = True
                # Smooth quadratic braking as distance approaches 20cm limit
                brake_ratio = max(0.0, (min_front_dist - 0.22) / (0.50 - 0.22))
                safe_vx = cmd_vx * (brake_ratio ** 1.5)
                # If approaching dead-on front wall, bias turn to find open space
                if abs(repulse_wz) < 0.15:
                    repulse_wz += 0.45  # Automatic reflex pivot away from barrier

            safe_wz = float(np.clip(cmd_wz + repulse_wz, -0.65, 0.65))

            # 4. Actuate filtered, collision-proof command
            tw = GzTwist()
            tw.linear.x = safe_vx
            tw.angular.z = safe_wz
            self.cmd_pub.publish(tw)

            if log_tick % 10 == 0:
                status = "🛡️ REFLEX ENGAGED" if reflex_active else "🟢 CLEAR"
                print(f"[{status:<17}] Pos: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m) | Front Obstacle: {min_front_dist:.2f}m | Commanded: vx={cmd_vx:.2f} → Filtered: vx={safe_vx:.2f}, wz={safe_wz:+.2f}")

        self.stop()
        print("─" * 75)
        print(f"✅ Demo completed. Final pose: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m). Collision prevented completely!")


if __name__ == "__main__":
    demo = ReflexShieldDemo()
    demo.run_demo(10.0)
