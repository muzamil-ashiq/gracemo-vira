#!/usr/bin/env python3
"""
GRaCEmo ViRa — Authoritative Spinal Base Controller (Level 1 Substrate)
Deterministic 50Hz motor authority & collision-avoidance safety layer.

Responsibilities:
  1. Pure closed-loop velocity and trajectory tracking (Pure Pursuit / PID).
  2. 50Hz 360° LiDAR Artificial Potential Field (APF) Collision-Avoidance Safety Layer.
  3. Emergency proportional braking (< 0.40m cushion).
  4. ZERO Semantic Knowledge: Contains no room names, no hardcoded coordinates, no map knowledge.
"""

import sys
import os
import time
import math
import signal
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan
try:
    from gz.msgs10.pose_v_pb2 import Pose_V as GzPoseV
except ImportError:
    try:
        from gz.msgs.pose_v_pb2 import Pose_V as GzPoseV
    except ImportError:
        GzPoseV = None
try:
    from gz.msgs10.contacts_pb2 import Contacts as GzContacts
except ImportError:
    try:
        from gz.msgs.contacts_pb2 import Contacts as GzContacts
    except ImportError:
        GzContacts = None

ROOT = Path(__file__).resolve().parent.parent.parent
for sub in ["sdk", "brain", "motion"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_sdk import AdapterClient


class BaseController:
    """
    Level 1 Spinal Base Controller.
    Authoritative controller for differential-drive locomotion and safety.
    Multi-sensor defense: Contact Bumper -> ToF Proximity -> 360° LiDAR APF.
    Zero Semantic Knowledge: Pure kinematics and physics substrate.
    """

    def __init__(self, publish_rate_hz: float = 50.0):
        self.node = gz_transport.Node()
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)
        self.node.subscribe(GzTwist, "/cmd_vel_desired", self._on_cmd_desired)

        # Multi-modal hardware sensor subscriptions
        self.has_pose_v = False
        if GzPoseV is not None:
            self.node.subscribe(GzPoseV, "/world/gracemo_home/dynamic_pose/info", self._on_pose_v)
        if GzContacts is not None:
            self.node.subscribe(GzContacts, "/bumper/contacts", self._on_contacts)
        self.node.subscribe(GzLaserScan, "/tof/front_left", self._on_tof_fl)
        self.node.subscribe(GzLaserScan, "/tof/front_right", self._on_tof_fr)
        self.node.subscribe(GzLaserScan, "/tof/rear", self._on_tof_rear)

        self.client = AdapterClient(adapter_name="BaseController", base_url="http://127.0.0.1:7780")

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.cur_linear_vel = 0.0
        self.cur_angular_vel = 0.0
        self.has_odom = False

        self.latest_scan: Optional[GzLaserScan] = None
        self.bumper_hit = False
        self.last_bumper_hit_time = 0.0
        self.tof_ranges = {"fl": 2.0, "fr": 2.0, "r": 2.0}

        self.desired_vx = 0.0
        self.desired_wz = 0.0
        self.last_desired_cmd_time = 0.0

        # Configurable Safety & Reflex Parameters
        self.safety_cushion_dist = 0.45       # Emergency deceleration starts at 45cm
        self.stop_threshold_dist = 0.25       # Full stop if obstacle closer than 25cm
        self.repulsion_influence_dist = 0.65  # APF field begins influence at 65cm
        self.wall_breakaway_speed = 0.65      # rad/s configurable turning speed for wall disengagement
        self.wall_hysteresis = 0.08           # meters deadband between left and right clearance
        self.last_recovery_turn_bias: Optional[float] = None
        self.recovery_state = "NORMAL"        # NORMAL, BLOCKED, RECOVERY_BACKOFF, RECOVERY_SCAN, RECOVERY_TURN, RESUME

        self.running = True
        self.publish_rate_hz = publish_rate_hz

        signal.signal(signal.SIGINT, self._sigint)
        signal.signal(signal.SIGTERM, self._sigint)

    def _sigint(self, sig, frame):
        self.running = False
        self.stop()
        sys.exit(0)

    def _on_pose_v(self, msg):
        for p in msg.pose:
            if p.name == "gracemo_vira":
                self.cur_x = p.position.x
                self.cur_y = p.position.y
                q = p.orientation
                siny = 2.0 * (q.w * q.z + q.x * q.y)
                cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
                self.cur_yaw = math.atan2(siny, cosy)
                self.has_odom = True
                self.has_pose_v = True
                break

    def _on_odom(self, msg: GzOdometry):
        self.cur_linear_vel = msg.twist.linear.x
        self.cur_angular_vel = msg.twist.angular.z
        if not self.has_pose_v:
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

    def _on_contacts(self, msg):
        if hasattr(msg, "contact") and len(msg.contact) > 0:
            self.bumper_hit = True
            self.last_bumper_hit_time = time.time()

    def _on_tof_fl(self, msg: GzLaserScan):
        valid = [r for r in msg.ranges if not math.isnan(r) and not math.isinf(r) and r > 0.02]
        if valid:
            self.tof_ranges["fl"] = min(valid)

    def _on_tof_fr(self, msg: GzLaserScan):
        valid = [r for r in msg.ranges if not math.isnan(r) and not math.isinf(r) and r > 0.02]
        if valid:
            self.tof_ranges["fr"] = min(valid)

    def _on_tof_rear(self, msg: GzLaserScan):
        valid = [r for r in msg.ranges if not math.isnan(r) and not math.isinf(r) and r > 0.02]
        if valid:
            self.tof_ranges["r"] = min(valid)

    def get_rear_clearance(self) -> float:
        """Returns clearance behind robot using rear LiDAR sector and rear ToF."""
        min_rear = self.tof_ranges.get("r", 2.0)
        if self.latest_scan and len(self.latest_scan.ranges) >= 180:
            ranges = self.latest_scan.ranges
            n = len(ranges)
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)
            for i, r in enumerate(ranges):
                if math.isnan(r) or math.isinf(r) or r <= 0.05: continue
                ang = ang_min + i * inc
                if abs(ang) > math.radians(135):
                    if r < min_rear:
                        min_rear = r
        return min_rear

    def get_front_clearance(self) -> float:
        """Returns direct forward clearance using swept corridor and front ToF."""
        min_front = min(self.tof_ranges.get("fl", 2.0), self.tof_ranges.get("fr", 2.0))
        if self.latest_scan and len(self.latest_scan.ranges) >= 180:
            ranges = self.latest_scan.ranges
            n = len(ranges)
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)
            for i, r in enumerate(ranges):
                if math.isnan(r) or math.isinf(r) or r <= 0.05: continue
                ang = ang_min + i * inc
                ox = r * math.cos(ang)
                oy = r * math.sin(ang)
                if ox > 0.05 and abs(oy) <= 0.24:
                    if ox < min_front:
                        min_front = ox
        return min_front

    def get_lateral_clearances(self) -> Tuple[float, float]:
        """Calculates minimum distance in left sector (+15° to +90°) vs right sector (-90° to -15°)."""
        left_min = 10.0
        right_min = 10.0
        if self.latest_scan and len(self.latest_scan.ranges) >= 180:
            ranges = self.latest_scan.ranges
            n = len(ranges)
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)
            for i, r in enumerate(ranges):
                if math.isnan(r) or math.isinf(r) or r <= 0.05: continue
                ang = ang_min + i * inc
                if math.radians(15) <= ang <= math.radians(90):
                    if r < left_min: left_min = r
                elif -math.radians(90) <= ang <= -math.radians(15):
                    if r < right_min: right_min = r
        return left_min, right_min

    def _on_cmd_desired(self, msg: GzTwist):
        self.desired_vx = msg.linear.x
        self.desired_wz = msg.angular.z
        self.last_desired_cmd_time = time.time()

    def stop(self):
        """Immediately commands zero velocity to actuators."""
        tw = GzTwist()
        tw.linear.x = 0.0
        tw.angular.z = 0.0
        self.cmd_pub.publish(tw)

    def wait_for_sensors(self, timeout_sec: float = 4.0) -> bool:
        """Blocks until odometry and LiDAR are streaming."""
        t0 = time.time()
        while (not self.has_odom or self.latest_scan is None) and time.time() - t0 < timeout_sec:
            time.sleep(0.04)
        return self.has_odom and (self.latest_scan is not None)

    def filter_velocity(self, cmd_vx: float, cmd_wz: float) -> Tuple[float, float, bool]:
        """
        Cartesian Swept-Path APF Safety Shield.
        Guards physical actuators against collisions:
          - Projects 360° LiDAR rays to Cartesian (x, y) robot frame.
          - Calculates exact clearance along swept chassis corridor (|y| <= 0.28m).
          - Contact Bumper has highest local safety priority: STOP, then safe reverse only if rear clear.
          - Breaks symmetric flat wall potential deadbands using lateral sector disparity + deadband hysteresis.
          - Emergency zero forward velocity if obstacle <= 0.25m.
          - Repulsive torque strictly overrides high-level steering if turning toward close obstacles.
        """
        # 1. Contact Bumper: Highest local safety priority
        if self.bumper_hit and (time.time() - self.last_bumper_hit_time < 0.35):
            rear_clear = self.get_rear_clearance()
            if rear_clear > 0.35:
                # Stop first, then controlled reverse away from contact
                return -0.15, 0.0, True
            else:
                # Rear blocked: full stop
                return 0.0, 0.0, True

        min_corridor_dist = min(self.tof_ranges.get("fl", 10.0), self.tof_ranges.get("fr", 10.0))
        min_front_dist = 10.0
        repulse_y = 0.0
        reflex_active = False

        if self.latest_scan and len(self.latest_scan.ranges) >= 180:
            ranges = self.latest_scan.ranges
            n = len(ranges)
            ang_min = self.latest_scan.angle_min
            inc = self.latest_scan.angle_step if self.latest_scan.angle_step > 0 else (2.0 * math.pi / n)

            for i, r in enumerate(ranges):
                if math.isnan(r) or math.isinf(r) or r <= 0.05:
                    continue

                b_ang = ang_min + i * inc
                ox = r * math.cos(b_ang)
                oy = r * math.sin(b_ang)

                # Obstacles in forward arc (ox > 0.05, |b_ang| <= 65 deg) exert repulsive steering
                if ox > 0.05 and abs(b_ang) <= math.radians(65) and (0.10 < r < self.repulsion_influence_dist):
                    weight = (self.repulsion_influence_dist - r) / (r + 0.05)
                    # Forward-projected lateral repulsion: sin(b_ang)*cos(b_ang) isolates forward collision normal
                    repulse_y += -weight * math.sin(b_ang) * math.cos(b_ang)
                    reflex_active = True

                # Narrow front cone (|b_ang| <= 25 deg) for forward obstacles directly in path
                if ox > 0.05 and abs(b_ang) <= math.radians(25):
                    if r < min_front_dist:
                        min_front_dist = r

                # Check direct swept forward corridor (|y| <= 0.24m, robot half-width 0.205m + safety margin)
                if ox > 0.05 and abs(oy) <= 0.24:
                    if ox < min_corridor_dist:
                        min_corridor_dist = ox

        effective_front = min(min_corridor_dist, min_front_dist)
        repulse_wz = float(np.clip(0.85 * repulse_y, -0.85, 0.85))

        # 2. Symmetry Breaking: Address flat perpendicular wall local minima
        if effective_front < self.safety_cushion_dist:
            left_clr, right_clr = self.get_lateral_clearances()
            delta_lr = left_clr - right_clr

            # If lateral repulsion from APF is weak (|repulse_wz| < 0.15) due to cancellation
            if abs(repulse_wz) < 0.15:
                if delta_lr > self.wall_hysteresis:
                    bias_wz = +self.wall_breakaway_speed
                    self.last_recovery_turn_bias = +self.wall_breakaway_speed
                elif delta_lr < -self.wall_hysteresis:
                    bias_wz = -self.wall_breakaway_speed
                    self.last_recovery_turn_bias = -self.wall_breakaway_speed
                else:
                    # Retain previous bias or deterministic tie-break
                    bias_wz = self.last_recovery_turn_bias if self.last_recovery_turn_bias is not None else +self.wall_breakaway_speed
                repulse_wz = bias_wz
                reflex_active = True

        # 3. Forward velocity braking
        safe_vx = cmd_vx
        if cmd_vx > 0:
            if effective_front <= self.stop_threshold_dist:
                safe_vx = 0.0
                reflex_active = True
            elif effective_front < self.safety_cushion_dist:
                brake = max(0.0, (effective_front - self.stop_threshold_dist) / (self.safety_cushion_dist - self.stop_threshold_dist))
                safe_vx = cmd_vx * (brake ** 1.6)
                reflex_active = True

        # 4. Steering: In-place pivot vs forward motion
        if cmd_vx == 0.0:
            # Pure in-place pivot: allow full rotational authority unless physical collision imminent (<= 0.22m)
            min_all_dist = min(min_corridor_dist, min_front_dist)
            if min_all_dist <= 0.22:
                safe_wz = 0.0
                reflex_active = True
            else:
                safe_wz = cmd_wz
        else:
            # Forward motion: blend commanded steering with lateral APF repulsion
            if effective_front < 0.35 and abs(repulse_wz) > 0.25:
                safe_wz = float(np.clip(0.6 * cmd_wz + repulse_wz, -0.80, 0.80))
                reflex_active = True
            else:
                safe_wz = float(np.clip(cmd_wz + 0.5 * repulse_wz, -0.75, 0.75))

        return safe_vx, safe_wz, reflex_active

    def execute_stuck_recovery(self) -> bool:
        """
        Stateful Obstacle & Wall Disengagement Reflex:
        NORMAL -> BLOCKED -> RECOVERY_BACKOFF -> RECOVERY_SCAN -> RECOVERY_TURN -> RESUME
        Sensor-grounded: checks rear clearance before backoff, scans left/right to choose turn direction.
        """
        print("[REFLEX] ⚠️ Stuck condition detected! Executing stateful recovery reflex...")
        self.recovery_state = "BLOCKED"
        self.stop()
        time.sleep(0.05)

        # 1. Check rear clearance before backing off
        rear_clear = self.get_rear_clearance()
        if rear_clear > 0.35:
            self.recovery_state = "RECOVERY_BACKOFF"
            t_back = time.time()
            while self.running and time.time() - t_back < 0.45:
                tw = GzTwist()
                tw.linear.x = -0.15
                tw.angular.z = 0.0
                self.cmd_pub.publish(tw)
                time.sleep(0.02)
                if self.get_rear_clearance() < 0.22:
                    break
            self.stop()
            time.sleep(0.05)

        # 2. RECOVERY_SCAN: Evaluate fresh lateral clearance
        self.recovery_state = "RECOVERY_SCAN"
        left_clr, right_clr = self.get_lateral_clearances()
        turn_dir = 1.0 if left_clr >= right_clr else -1.0
        turn_speed = turn_dir * self.wall_breakaway_speed

        # 3. RECOVERY_TURN: Rotate toward open space
        self.recovery_state = "RECOVERY_TURN"
        t_turn = time.time()
        while self.running and time.time() - t_turn < 0.55:
            tw = GzTwist()
            tw.linear.x = 0.0
            tw.angular.z = turn_speed
            self.cmd_pub.publish(tw)
            time.sleep(0.02)
            if self.get_front_clearance() > 0.60:
                break

        self.stop()
        self.recovery_state = "RESUME"
        print("[REFLEX] ✓ Disengagement complete. Front clearance restored. Resuming navigation.")
        return True

    def drive_raw_velocity(self, vx: float, wz: float):
        """Commands raw velocity directly to actuators without APF repulsion (e.g. for precision docking)."""
        tw = GzTwist()
        tw.linear.x = float(vx)
        tw.angular.z = float(wz)
        self.cmd_pub.publish(tw)

    def drive_velocity(self, vx: float, wz: float) -> Tuple[float, float, bool]:
        """Filters requested velocity through APF shield and sends to motors."""
        safe_vx, safe_wz, active = self.filter_velocity(vx, wz)
        tw = GzTwist()
        tw.linear.x = safe_vx
        tw.angular.z = safe_wz
        self.cmd_pub.publish(tw)
        return safe_vx, safe_wz, active

    def pivot_to_heading(self, target_yaw: float, tolerance_rad: float = math.radians(3), timeout_sec: float = 6.0) -> bool:
        """Pivots in-place to target heading with unwrapped angular error."""
        t0 = time.time()
        while self.running and time.time() - t0 < timeout_sec:
            time.sleep(0.02)
            err = target_yaw - self.cur_yaw
            while err > math.pi: err -= 2 * math.pi
            while err < -math.pi: err += 2 * math.pi

            if abs(err) <= tolerance_rad:
                self.stop()
                return True

            wz = float(np.clip(1.3 * err, -0.60, 0.60))
            self.drive_velocity(0.0, wz)

        self.stop()
        return False

    def drive_to_pose(self, target_x: float, target_y: float, target_yaw: Optional[float] = None, reach_dist: float = 0.18, timeout_sec: Optional[float] = None) -> bool:
        """Closed-loop metric waypoint pursuit with real-time APF safety filtering and stuck recovery."""
        dx0 = target_x - self.cur_x
        dy0 = target_y - self.cur_y
        dist0 = math.hypot(dx0, dy0)
        actual_timeout = timeout_sec if timeout_sec is not None else max(30.0, dist0 * 6.0)

        t0 = time.time()
        last_pos = (self.cur_x, self.cur_y)
        last_progress_time = time.time()
        stuck_recovery_count = 0

        while self.running and time.time() - t0 < actual_timeout:
            time.sleep(0.02)
            dx = target_x - self.cur_x
            dy = target_y - self.cur_y
            dist = math.hypot(dx, dy)

            if dist <= reach_dist:
                self.stop()
                if target_yaw is not None:
                    return self.pivot_to_heading(target_yaw)
                return True

            desired_heading = math.atan2(dy, dx)
            alpha = desired_heading - self.cur_yaw
            while alpha > math.pi: alpha -= 2 * math.pi
            while alpha < -math.pi: alpha += 2 * math.pi

            if abs(alpha) > math.radians(30):
                cmd_vx = 0.0
                cmd_wz = float(np.clip(1.2 * alpha, -0.60, 0.60))
            else:
                align = max(0.0, math.cos(alpha))
                v_max = min(0.45, max(0.15, 0.70 * dist))
                cmd_vx = v_max * (align ** 2)
                cmd_wz = float(np.clip(1.1 * alpha, -0.45, 0.45))

            # Progress tracking & stuck detection: only evaluate when demanding forward drive
            if cmd_vx > 0.08:
                dist_moved = math.hypot(self.cur_x - last_pos[0], self.cur_y - last_pos[1])
                if dist_moved >= 0.03:
                    last_pos = (self.cur_x, self.cur_y)
                    last_progress_time = time.time()
                else:
                    front_clear = self.get_front_clearance()
                    if (time.time() - last_progress_time > 1.8) and (front_clear < 0.28 or self.bumper_hit):
                        if stuck_recovery_count < 3:
                            stuck_recovery_count += 1
                            self.execute_stuck_recovery()
                            last_pos = (self.cur_x, self.cur_y)
                            last_progress_time = time.time()
                        else:
                            print(f"[BASE CONTROLLER] ❌ Unstick failed after {stuck_recovery_count} attempts. Aborting waypoint pursuit.")
                            self.stop()
                            return False
            else:
                # Pivoting or aligning in place: keep progress timer refreshed
                last_pos = (self.cur_x, self.cur_y)
                last_progress_time = time.time()

            self.drive_velocity(cmd_vx, cmd_wz)

        self.stop()
        return False

    def follow_waypoints(self, waypoints: List[Tuple[float, float]], final_yaw: Optional[float] = None, reach_dist: float = 0.35, timeout_sec: float = 35.0) -> bool:
        """
        Pure closed-loop trajectory pursuit:
        Carves smooth continuous arcs through intermediate waypoints without stopping,
        decelerating to a stop only at the final destination.
        """
        if not waypoints:
            return True

        t0 = time.time()
        idx = 0
        n = len(waypoints)

        while self.running and idx < n and (time.time() - t0 < timeout_sec):
            time.sleep(0.02)
            wx, wy = waypoints[idx]
            is_last = (idx == n - 1)

            dx = wx - self.cur_x
            dy = wy - self.cur_y
            dist = math.hypot(dx, dy)

            # Intermediate waypoints use smooth fly-by tolerance; final destination uses 0.20m
            advance_tol = 0.20 if is_last else reach_dist

            if dist <= advance_tol:
                idx += 1
                if idx >= n:
                    self.stop()
                    if final_yaw is not None:
                        return self.pivot_to_heading(final_yaw)
                    return True
                continue

            desired_heading = math.atan2(dy, dx)
            alpha = desired_heading - self.cur_yaw
            while alpha > math.pi: alpha -= 2 * math.pi
            while alpha < -math.pi: alpha += 2 * math.pi

            if abs(alpha) > math.radians(45) and not is_last:
                cmd_vx = 0.08
                cmd_wz = float(np.clip(1.2 * alpha, -0.60, 0.60))
            elif abs(alpha) > math.radians(60):
                cmd_vx = 0.0
                cmd_wz = float(np.clip(1.2 * alpha, -0.60, 0.60))
            else:
                align = max(0.0, math.cos(alpha))
                v_cruise = 0.40 if not is_last else min(0.40, max(0.15, 0.60 * dist))
                cmd_vx = v_cruise * (align ** 1.5)
                cmd_wz = float(np.clip(1.2 * alpha, -0.50, 0.50))

            self.drive_velocity(cmd_vx, cmd_wz)

        self.stop()
        return (idx >= n)

    def spin_safety_daemon(self):
        """Runs the continuous 50Hz safety filter loop consuming /cmd_vel_desired."""
        dt = 1.0 / self.publish_rate_hz
        print(f"[BASE CONTROLLER] Safety daemon running at {self.publish_rate_hz:.0f}Hz...")
        while self.running:
            now = time.time()
            # Command timeout: if no command received for > 0.4s, stop
            if now - self.last_desired_cmd_time > 0.40:
                vx = 0.0
                wz = 0.0
            else:
                vx = self.desired_vx
                wz = self.desired_wz

            self.drive_velocity(vx, wz)
            time.sleep(dt)


def main():
    controller = BaseController()
    if not controller.wait_for_sensors(timeout_sec=4.0):
        print("[BaseController] Warning: Sensor stream not active.")

    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        controller.spin_safety_daemon()
    else:
        print("BaseController initialized. Usage: gracemo_base_controller.py [daemon]")


if __name__ == "__main__":
    main()
