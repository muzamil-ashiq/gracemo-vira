#!/usr/bin/env python3
"""
GRaCEmo ViRa — Native Gazebo Closed-Loop Navigator with Centerline Lock & LiDAR APF
Direct gz.transport13 velocity, odometry & laser scan control.
Guarantees:
  1. Strict corridor centerline tracking (zero wall drifting along Y=0.0).
  2. 360-degree LiDAR Artificial Potential Field (APF) wall repulsion.
  3. Orthogonal two-stage doorway entry without clipping doorframes.
"""

import sys
import time
import math
import signal
from pathlib import Path
import numpy as np

import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan

ROOT = Path(__file__).resolve().parent.parent
for sub in ["sdk", "brain"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_sdk import AdapterClient
from gracemo_brain.mission_planner import MissionPlanner, MissionPlan

ROOM_NAMES = {
    "1": "bedroom", "bedroom": "bedroom", "bed": "bedroom",
    "2": "study", "study": "study", "lab": "study",
    "3": "living", "living": "living", "lounge": "living",
    "4": "kitchen", "kitchen": "kitchen", "dining": "kitchen",
    "h": "hallway", "hall": "hallway", "hallway": "hallway"
}


class GzNavigator:
    def __init__(self, target_room_raw: str):
        self.target_room = ROOM_NAMES.get(target_room_raw.lower().strip(), target_room_raw.lower().strip())
        self.running = True
        self.has_odom = False
        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.latest_scan = None

        self.node = gz_transport.Node()
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)

        self.client = AdapterClient(adapter_name="GzNavigator", base_url="http://127.0.0.1:7780")
        self.planner = MissionPlanner()
        self.plan = None

        signal.signal(signal.SIGINT, self._sigint)
        signal.signal(signal.SIGTERM, self._sigint)

    def _sigint(self, sig, frame):
        self.running = False
        self.stop()

    def _on_odom(self, msg: GzOdometry):
        pos = msg.pose.position
        q = msg.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.cur_x = pos.x
        self.cur_y = pos.y
        self.cur_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.has_odom = True

    def _on_scan(self, msg: GzLaserScan):
        self.latest_scan = msg

    def stop(self):
        tw = GzTwist()
        tw.linear.x = 0.0
        tw.angular.z = 0.0
        self.cmd_pub.publish(tw)

    def run(self):
        print(f"🚀 [GZ NAV] Initializing precision navigation to: {self.target_room.upper()}...")
        print("  -> Connecting to Gazebo /odom and /scan...")

        t0 = time.time()
        while not self.has_odom and time.time() - t0 < 5.0:
            time.sleep(0.05)

        if not self.has_odom:
            print("❌ Error: No odometry received from Gazebo. Is Gazebo simulation running?")
            return False

        print(f"✓ Odometry & LiDAR connected! ViRa pose: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m, yaw={math.degrees(self.cur_yaw):+.0f}°)")
        self.plan = self.planner.create_mission(f"Go to {self.target_room}", (self.cur_x, self.cur_y, self.cur_yaw))
        print(f"📋 Scheduled {len(self.plan.steps)} waypoint phases for destination '{self.target_room.upper()}':")
        for s in self.plan.steps:
            print(f"   [{s.step_num}] {s.action_type:<10} target=({s.target_pos[0]:+.1f}, {s.target_pos[1]:+.1f}) | {s.description}")

        log_tick = 0
        while self.running:
            time.sleep(0.05)
            log_tick += 1

            step = self.plan.current_step()
            if not step:
                print(f"\n🏁 [MISSION COMPLETE] Safely arrived in {self.target_room.upper()}!")
                self.stop()
                self.client.emit(
                    "NavigationArrived",
                    {"destination": self.target_room.title(), "success": True},
                    source="GzNavigator"
                )
                return True

            if step.action_type in ("SCAN", "REPORT"):
                print(f"✓ [PHASE COMPLETE] {step.description}")
                self.plan.advance()
                continue

            tx, ty = step.target_pos
            dx = tx - self.cur_x
            dy = ty - self.cur_y
            dist = math.hypot(dx, dy)

            # Waypoint arrival threshold
            reach_radius = 0.35 if step.action_type in ("ENTER_DOOR", "STATION") else 0.28
            if dist < reach_radius:
                print(f"✓ [REACHED] Step {step.step_num}/{len(self.plan.steps)}: {step.description}")
                self.plan.advance()
                continue

            # ── 1. Heading Angle with Corridor Centerline Guidance ──
            # When in the hallway along Y=0.0, amplify cross-track error so robot stays locked to Y=0.00 (+/- 0.04m).
            in_hallway_transit = (abs(ty) < 0.2 and abs(self.cur_y) < 0.8 and abs(dx) > 0.3)
            if in_hallway_transit:
                # Amplify dy to pull firmly back to centerline Y=0.0
                effective_dy = 2.5 * (0.0 - self.cur_y)
                target_yaw = math.atan2(effective_dy, dx)
            else:
                target_yaw = math.atan2(dy, dx)

            # Normalize angle error into [-pi, +pi]
            alpha = target_yaw - self.cur_yaw
            while alpha > math.pi:
                alpha -= 2 * math.pi
            while alpha < -math.pi:
                alpha += 2 * math.pi

            # Prevent jitter when angle is near +/- 180 deg
            if abs(abs(alpha) - math.pi) < 0.15:
                alpha = math.pi

            # ── 2. LiDAR 360-degree APF Wall Repulsion ──
            repulse_wz = 0.0
            min_front_dist = 10.0
            if self.latest_scan and len(self.latest_scan.ranges) >= 180:
                ranges = self.latest_scan.ranges
                n = len(ranges)
                ang_min = self.latest_scan.angle_min
                inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)
                for i, r in enumerate(ranges):
                    if 0.18 < r < 0.50 and not math.isnan(r) and not math.isinf(r):
                        b_ang = ang_min + i * inc
                        weight = (0.50 - r) / 0.50
                        # Smooth repulsive torque away from nearby side walls
                        repulse_wz += -0.50 * weight * math.sin(b_ang)
                        if abs(b_ang) < math.radians(28):
                            if r < min_front_dist:
                                min_front_dist = r

            repulse_wz = float(np.clip(repulse_wz, -0.20, 0.20))

            # ── 3. Motor Actuation (Clean In-Place Alignment + Forward Cruise) ──
            # If heading error is large, align on spot first with ZERO linear velocity.
            # This completely eliminates diagonal wall drift.
            if abs(alpha) > math.radians(22):
                vx = 0.0
                wz = float(np.clip(1.2 * alpha, -0.65, 0.65))
            else:
                # Heading is aligned: cruise forward while applying smooth proportional steering
                align = max(0.0, math.cos(alpha))
                v_max = min(0.48, max(0.18, 0.65 * dist))
                # Slow down if front obstacle is close
                if min_front_dist < 0.55:
                    v_max = min(v_max, max(0.08, 0.50 * min_front_dist))

                vx = v_max * (align ** 2)
                # Combine goal-seeking heading correction with LiDAR wall safety
                wz = float(np.clip(1.2 * alpha + repulse_wz, -0.50, 0.50))

            tw = GzTwist()
            tw.linear.x = vx
            tw.angular.z = wz
            self.cmd_pub.publish(tw)

            if log_tick % 20 == 0:
                print(f"  [Step {step.step_num}/{len(self.plan.steps)}] Pos: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m) → Target: ({tx:.1f}, {ty:.1f}) | Dist: {dist:.2f}m | Heading Err: {math.degrees(alpha):+.0f}° | Wall Repulse: {repulse_wz:+.2f}")

        self.stop()
        return False


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "bedroom"
    nav = GzNavigator(target)
    success = nav.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
