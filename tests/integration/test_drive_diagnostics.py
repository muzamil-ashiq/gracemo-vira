#!/usr/bin/env python3
"""
Comprehensive Drive Diagnostics Integration Test
Compares commanded linear/angular motion against actual simulated displacement,
orientation change (yaw), and wheel angular velocities.
"""

import math
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState


class DriveDiagnosticsTester(Node):
    def __init__(self):
        super().__init__("drive_diagnostics_integration_tester")
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.joint_sub = self.create_subscription(JointState, "/joint_states", self.joint_cb, 10)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self.odom_cb, 10)

        self.latest_joints = {}
        self.latest_odom = None
        self.wheel_radius = 0.115  # meters
        self.track_width = 0.570   # meters
        self.wheelbase = 0.440     # meters

    def joint_cb(self, msg: JointState):
        for name, pos, vel in zip(msg.name, msg.position, msg.velocity):
            self.latest_joints[name] = (pos, vel)

    def odom_cb(self, msg: Odometry):
        self.latest_odom = msg

    @staticmethod
    def get_yaw_from_quat(q):
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def wait_for_data(self, timeout_sec=5.0):
        start = time.time()
        while time.time() - start < timeout_sec:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.latest_odom and len(self.latest_joints) >= 4:
                return True
            time.sleep(0.05)
        return False

    def stop_robot(self, duration_sec=1.0):
        stop_msg = Twist()
        end_time = time.time() + duration_sec
        while time.time() < end_time:
            self.cmd_pub.publish(stop_msg)
            rclpy.spin_once(self, timeout_sec=0.05)
            time.sleep(0.05)

    def execute_maneuver(self, label, linear_x, angular_z, duration_sec):
        print(f"\n[Drive Test] >>> Executing {label}: vx={linear_x} m/s, wz={angular_z} rad/s for {duration_sec}s", flush=True)
        self.stop_robot(duration_sec=0.5)

        # Baseline odom
        for _ in range(5):
            rclpy.spin_once(self, timeout_sec=0.05)
        assert self.latest_odom is not None, "Odometry message not received before maneuver"

        start_x = self.latest_odom.pose.pose.position.x
        start_y = self.latest_odom.pose.pose.position.y
        start_yaw = self.get_yaw_from_quat(self.latest_odom.pose.pose.orientation)

        cmd = Twist()
        cmd.linear.x = float(linear_x)
        cmd.angular.z = float(angular_z)

        expected_wheel_vel_left = (linear_x - angular_z * (self.track_width / 2.0)) / self.wheel_radius
        expected_wheel_vel_right = (linear_x + angular_z * (self.track_width / 2.0)) / self.wheel_radius

        wheel_vel_samples = []
        end_time = time.time() + duration_sec

        while time.time() < end_time:
            self.cmd_pub.publish(cmd)
            rclpy.spin_once(self, timeout_sec=0.05)
            # Record wheel velocities
            fl_v = self.latest_joints.get("front_left_wheel_joint", (0.0, 0.0))[1]
            fr_v = self.latest_joints.get("front_right_wheel_joint", (0.0, 0.0))[1]
            rl_v = self.latest_joints.get("rear_left_wheel_joint", (0.0, 0.0))[1]
            rr_v = self.latest_joints.get("rear_right_wheel_joint", (0.0, 0.0))[1]
            wheel_vel_samples.append((fl_v, fr_v, rl_v, rr_v))
            time.sleep(0.05)

        self.stop_robot(duration_sec=0.8)

        end_x = self.latest_odom.pose.pose.position.x
        end_y = self.latest_odom.pose.pose.position.y
        end_yaw = self.get_yaw_from_quat(self.latest_odom.pose.pose.orientation)

        # Displacement calculations
        dx = end_x - start_x
        dy = end_y - start_y
        dist = math.sqrt(dx * dx + dy * dy)
        dyaw = end_yaw - start_yaw
        # Normalize angle difference
        dyaw = (dyaw + math.pi) % (2.0 * math.pi) - math.pi

        # Average steady-state wheel velocity
        steady_samples = wheel_vel_samples[len(wheel_vel_samples)//3 : -2]
        if steady_samples:
            avg_fl = sum(s[0] for s in steady_samples) / len(steady_samples)
            avg_fr = sum(s[1] for s in steady_samples) / len(steady_samples)
            avg_rl = sum(s[2] for s in steady_samples) / len(steady_samples)
            avg_rr = sum(s[3] for s in steady_samples) / len(steady_samples)
        else:
            avg_fl = avg_fr = avg_rl = avg_rr = 0.0

        print(f"  [Displacement] dist={dist:.4f} m (dx={dx:.4f}, dy={dy:.4f}), dyaw={math.degrees(dyaw):.2f}°")
        print(f"  [Wheel Velocities] FL={avg_fl:+.4f}, RL={avg_rl:+.4f} (exp: {expected_wheel_vel_left:+.4f}) | FR={avg_fr:+.4f}, RR={avg_rr:+.4f} (exp: {expected_wheel_vel_right:+.4f})")

        return {
            "label": label,
            "dist": dist,
            "dx": dx,
            "dy": dy,
            "dyaw": dyaw,
            "expected_wheel_vel_left": expected_wheel_vel_left,
            "expected_wheel_vel_right": expected_wheel_vel_right,
            "avg_fl": avg_fl,
            "avg_fr": avg_fr,
            "avg_rl": avg_rl,
            "avg_rr": avg_rr,
        }


def run_drive_diagnostics_suite():
    rclpy.init()
    tester = DriveDiagnosticsTester()

    print("[Drive Diagnostics] Waiting for simulation odom and joint states...")
    ready = tester.wait_for_data(timeout_sec=8.0)
    if not ready:
        print("[FAIL] Did not receive /odom or /joint_states from Gazebo.")
        tester.destroy_node()
        rclpy.shutdown()
        return False

    results = []

    # 1. Forward test (linear_x = +0.3 m/s for 2.5s -> theoretical dist ~ 0.75m)
    fwd = tester.execute_maneuver("Forward Drive", linear_x=0.3, angular_z=0.0, duration_sec=2.5)
    assert fwd["dist"] > 0.40, f"Forward displacement {fwd['dist']:.3f}m below minimum expected (0.40m)"
    assert abs(fwd["avg_fl"] - 2.6087) < 0.2, f"Left wheel velocity {fwd['avg_fl']} diverged from kinematics"
    assert abs(fwd["avg_fr"] - 2.6087) < 0.2, f"Right wheel velocity {fwd['avg_fr']} diverged from kinematics"
    results.append(("Forward Drive", "PASS"))

    # 2. Reverse test (linear_x = -0.3 m/s for 2.5s -> theoretical dist ~ 0.75m)
    rev = tester.execute_maneuver("Reverse Drive", linear_x=-0.3, angular_z=0.0, duration_sec=2.5)
    assert rev["dist"] > 0.40, f"Reverse displacement {rev['dist']:.3f}m below minimum expected (0.40m)"
    assert abs(rev["avg_fl"] - (-2.6087)) < 0.2, f"Left wheel velocity {rev['avg_fl']} diverged from kinematics"
    assert abs(rev["avg_fr"] - (-2.6087)) < 0.2, f"Right wheel velocity {rev['avg_fr']} diverged from kinematics"
    results.append(("Reverse Drive", "PASS"))

    # 3. In-Place Left Turn (CCW) (angular_z = +0.8 rad/s for 2.5s -> theoretical dyaw ~ 2.0 rad = 114°)
    ccw = tester.execute_maneuver("CCW In-Place Rotation", linear_x=0.0, angular_z=0.8, duration_sec=2.5)
    assert ccw["dyaw"] > 0.8, f"CCW rotation {math.degrees(ccw['dyaw']):.1f}° did not turn left sufficiently"
    assert ccw["avg_fl"] < -1.0, f"Left wheels should rotate backward during CCW turn, got {ccw['avg_fl']}"
    assert ccw["avg_fr"] > 1.0, f"Right wheels should rotate forward during CCW turn, got {ccw['avg_fr']}"
    results.append(("CCW Turn", "PASS"))

    # 4. In-Place Right Turn (CW) (angular_z = -0.8 rad/s for 2.5s)
    cw = tester.execute_maneuver("CW In-Place Rotation", linear_x=0.0, angular_z=-0.8, duration_sec=2.5)
    assert cw["dyaw"] < -0.8, f"CW rotation {math.degrees(cw['dyaw']):.1f}° did not turn right sufficiently"
    assert cw["avg_fl"] > 1.0, f"Left wheels should rotate forward during CW turn, got {cw['avg_fl']}"
    assert cw["avg_fr"] < -1.0, f"Right wheels should rotate backward during CW turn, got {cw['avg_fr']}"
    results.append(("CW Turn", "PASS"))

    # 5. Stop Verification
    print("\n[Drive Test] >>> Verifying Zero Command Stopping...", flush=True)
    tester.stop_robot(duration_sec=1.0)
    for _ in range(5):
        rclpy.spin_once(tester, timeout_sec=0.05)
    stopped_fl = abs(tester.latest_joints.get("front_left_wheel_joint", (0.0, 0.0))[1])
    stopped_fr = abs(tester.latest_joints.get("front_right_wheel_joint", (0.0, 0.0))[1])
    assert stopped_fl < 0.05 and stopped_fr < 0.05, f"Robot did not stop cleanly: FL={stopped_fl}, FR={stopped_fr}"
    results.append(("Zero-Command Stop", "PASS"))

    print("\n" + "=" * 60)
    print("  🏁 DRIVE DIAGNOSTICS SUITE SUMMARY")
    print("=" * 60)
    for name, status in results:
        print(f"  {name:30}: [{status}]")
    print("=" * 60 + "\n")

    tester.destroy_node()
    rclpy.shutdown()
    return True


if __name__ == "__main__":
    success = run_drive_diagnostics_suite()
    if not success:
        exit(1)
