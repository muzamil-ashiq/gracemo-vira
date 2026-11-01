#!/usr/bin/env python3
"""
Live Gazebo Harmonic Simulation Test for Phase 3 Step 4:
Validates 3D LookAt Kinematics, Active Neck Movement, and Base Invariance:

TARGET 1: Point directly ahead in front of robot.
  Verify: head pans/tilts, camera follows, base does not move.
TARGET 2: Point approximately 45° left.
  Verify: neck pan moves toward +45°, base remains stationary.
TARGET 3: Low target representing floor/table point.
  Verify: neck tilts downward, base remains stationary.
TARGET 4: Target outside ±120°.
  Verify: LookAt rejected, neck receives no command, cmd_vel remains zero, base stationary.
"""

import math
import sys
import time
from pathlib import Path

# Add bridge path
REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = REPO_ROOT / "ros2_ws" / "src" / "gracemo_bridge"
if str(BRIDGE_PATH) not in sys.path:
    sys.path.insert(0, str(BRIDGE_PATH))

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.double_pb2 import Double as GzDouble
    from gz.msgs10.model_pb2 import Model as GzModel
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
    from gz.msgs10.twist_pb2 import Twist as GzTwist
except ImportError:
    print("ERROR: gz.transport13 not available. Must run inside gracemo-harmonic container.")
    sys.exit(1)

from gracemo_bridge.kernel_bridge import compute_look_at, KernelBridgeNode
import rclpy


class LiveLookAtTester:
    def __init__(self):
        self.gz_node = gz_transport.Node()

        self.joint_positions = {}
        self.has_joint_state = False

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_z = 0.0
        self.cur_yaw = 0.0
        self.has_odom = False

        self.cmd_vel_count = 0
        self.neck_pan_cmd_count = 0
        self.neck_tilt_cmd_count = 0

        # Subscribe to Gazebo simulation telemetry
        self.gz_node.subscribe(
            GzModel,
            "/world/gracemo_home/model/gracemo_vira/joint_state",
            self._on_joint_state,
        )
        self.gz_node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.gz_node.subscribe(GzTwist, "/cmd_vel", self._on_cmd_vel)
        self.gz_node.subscribe(GzDouble, "/head/pan/cmd_pos", self._on_pan_cmd)
        self.gz_node.subscribe(GzDouble, "/head/tilt/cmd_pos", self._on_tilt_cmd)

    def _on_joint_state(self, msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                self.joint_positions[j.name] = float(j.axis1.position)
        self.has_joint_state = True

    def _on_odom(self, msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        self.cur_x = float(p.x)
        self.cur_y = float(p.y)
        self.cur_z = float(p.z)
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.cur_yaw = math.atan2(siny, cosy)
        self.has_odom = True

    def _on_cmd_vel(self, msg: GzTwist):
        if abs(msg.linear.x) > 1e-4 or abs(msg.angular.z) > 1e-4:
            self.cmd_vel_count += 1

    def _on_pan_cmd(self, msg: GzDouble):
        self.neck_pan_cmd_count += 1

    def _on_tilt_cmd(self, msg: GzDouble):
        self.neck_tilt_cmd_count += 1

    def wait_for_telemetry(self, timeout_sec: float = 10.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if self.has_joint_state and self.has_odom:
                if "neck_pan_joint" in self.joint_positions and "neck_tilt_joint" in self.joint_positions:
                    return True
            time.sleep(0.05)
        return False


def run_live_test():
    print("=" * 70)
    print("  GRaCEmo ViRa — PHASE 3 STEP 4 LIVE 3D LOOKAT SIMULATION TEST")
    print("=" * 70)

    if not rclpy.ok():
        rclpy.init()

    tester = LiveLookAtTester()
    print("\n[1/5] Connecting to live Gazebo Harmonic simulation...")
    if not tester.wait_for_telemetry(timeout_sec=10.0):
        print("❌ FAILED: Did not receive Gazebo telemetry within 10s.")
        return False

    print("✓ Successfully connected to live Gazebo Harmonic!")
    print(f"  Initial Robot Pose: x={tester.cur_x:+.3f}m, y={tester.cur_y:+.3f}m, z={tester.cur_z:+.3f}m, yaw={math.degrees(tester.cur_yaw):+.1f}°")
    print(f"  Initial Neck State: pan={tester.joint_positions['neck_pan_joint']:+.3f} rad, tilt={tester.joint_positions['neck_tilt_joint']:+.3f} rad")

    # Instantiate KernelBridgeNode
    bridge = KernelBridgeNode()
    bridge.current_x = tester.cur_x
    bridge.current_y = tester.cur_y
    bridge.current_z = tester.cur_z
    bridge.current_yaw_rad = tester.cur_yaw

    initial_x = tester.cur_x
    initial_y = tester.cur_y
    tester.cmd_vel_count = 0

    all_passed = True

    # -------------------------------------------------------------------------
    # TARGET 1: A point directly in front of the robot
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[2/5] TARGET 1: Point directly ahead in front of robot")
    t1_x = tester.cur_x + 2.0 * math.cos(tester.cur_yaw)
    t1_y = tester.cur_y + 2.0 * math.sin(tester.cur_yaw)
    t1_z = tester.cur_z + 0.645

    print(f"  Target: ({t1_x:.2f}, {t1_y:.2f}, {t1_z:.2f})")
    bridge.current_x = tester.cur_x
    bridge.current_y = tester.cur_y
    bridge.current_z = tester.cur_z
    bridge.current_yaw_rad = tester.cur_yaw

    res1 = bridge.execute_look_at(t1_x, t1_y, t1_z)
    print(f"  Computed: pan={res1.get('pan_deg', 0):+.1f}°, tilt={res1.get('tilt_deg', 0):+.1f}°")

    time.sleep(2.5)

    pan1 = tester.joint_positions["neck_pan_joint"]
    tilt1 = tester.joint_positions["neck_tilt_joint"]
    base_dist1 = math.hypot(tester.cur_x - initial_x, tester.cur_y - initial_y)

    print(f"  Physical Neck: pan={pan1:+.3f} rad ({math.degrees(pan1):+.1f}°), tilt={tilt1:+.3f} rad ({math.degrees(tilt1):+.1f}°)")
    print(f"  Base displacement: {base_dist1:.4f}m, non-zero cmd_vel count: {tester.cmd_vel_count}")

    t1_ok = (
        res1["success"]
        and abs(pan1) < 0.08
        and abs(tilt1) < 0.08
        and base_dist1 < 0.02
        and tester.cmd_vel_count == 0
    )
    if t1_ok:
        print("✓ TARGET 1 PASSED: Head aligned straight, camera follows, base stationary.")
    else:
        print(f"❌ TARGET 1 FAILED: pan={pan1:.3f}, tilt={tilt1:.3f}, base_dist={base_dist1:.4f}")
        all_passed = False

    # -------------------------------------------------------------------------
    # TARGET 2: A point approximately 45° left
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[3/5] TARGET 2: Point approximately +45° left")
    t2_heading = tester.cur_yaw + math.radians(45.0)
    t2_x = tester.cur_x + 2.0 * math.cos(t2_heading)
    t2_y = tester.cur_y + 2.0 * math.sin(t2_heading)
    t2_z = tester.cur_z + 0.645

    print(f"  Target: ({t2_x:.2f}, {t2_y:.2f}, {t2_z:.2f})")
    bridge.current_x = tester.cur_x
    bridge.current_y = tester.cur_y
    bridge.current_z = tester.cur_z
    bridge.current_yaw_rad = tester.cur_yaw

    res2 = bridge.execute_look_at(t2_x, t2_y, t2_z)
    print(f"  Computed: pan={res2.get('pan_deg', 0):+.1f}°, tilt={res2.get('tilt_deg', 0):+.1f}°")

    time.sleep(3.5)

    pan2 = tester.joint_positions["neck_pan_joint"]
    tilt2 = tester.joint_positions["neck_tilt_joint"]
    base_dist2 = math.hypot(tester.cur_x - initial_x, tester.cur_y - initial_y)

    print(f"  Physical Neck: pan={pan2:+.3f} rad ({math.degrees(pan2):+.1f}°), tilt={tilt2:+.3f} rad ({math.degrees(tilt2):+.1f}°)")
    print(f"  Base displacement: {base_dist2:.4f}m, non-zero cmd_vel count: {tester.cmd_vel_count}")

    # Verify neck pan moves toward +45° (> +0.40 rad / +23°) while tilt stays ~0 and base stays still
    t2_ok = (
        res2["success"]
        and pan2 > 0.40  # Clearly moved toward +45°
        and abs(tilt2) < 0.08
        and base_dist2 < 0.02
        and tester.cmd_vel_count == 0
    )
    if t2_ok:
        print("✓ TARGET 2 PASSED: Neck pan moved toward +45°, base stationary.")
    else:
        print(f"❌ TARGET 2 FAILED: Expected pan > 0.40 rad, got pan={pan2:.3f}, tilt={tilt2:.3f}")
        all_passed = False

    # -------------------------------------------------------------------------
    # TARGET 3: Low target representing a floor/table point
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[4/5] TARGET 3: Low target representing floor/table point (downward tilt)")
    t3_x = tester.cur_x + 1.2 * math.cos(tester.cur_yaw)
    t3_y = tester.cur_y + 1.2 * math.sin(tester.cur_yaw)
    t3_z = tester.cur_z + 0.10

    print(f"  Target: ({t3_x:.2f}, {t3_y:.2f}, {t3_z:.2f})")
    bridge.current_x = tester.cur_x
    bridge.current_y = tester.cur_y
    bridge.current_z = tester.cur_z
    bridge.current_yaw_rad = tester.cur_yaw

    res3 = bridge.execute_look_at(t3_x, t3_y, t3_z)
    print(f"  Computed: pan={res3.get('pan_deg', 0):+.1f}°, tilt={res3.get('tilt_deg', 0):+.1f}°")

    time.sleep(3.5)

    pan3 = tester.joint_positions["neck_pan_joint"]
    tilt3 = tester.joint_positions["neck_tilt_joint"]
    base_dist3 = math.hypot(tester.cur_x - initial_x, tester.cur_y - initial_y)

    print(f"  Physical Neck: pan={pan3:+.3f} rad ({math.degrees(pan3):+.1f}°), tilt={tilt3:+.3f} rad ({math.degrees(tilt3):+.1f}°)")
    print(f"  Base displacement: {base_dist3:.4f}m, non-zero cmd_vel count: {tester.cmd_vel_count}")

    # Verify neck tilts downward (tilt > 0.08 rad / > 4.5°) and base stays stationary
    t3_ok = (
        res3["success"]
        and tilt3 > 0.08  # Clearly downward tilt
        and base_dist3 < 0.02
        and tester.cmd_vel_count == 0
    )
    if t3_ok:
        print("✓ TARGET 3 PASSED: Neck tilted downward toward low point, base stationary.")
    else:
        print(f"❌ TARGET 3 FAILED: Expected downward tilt (tilt > 0.08), got tilt={tilt3:.3f}")
        all_passed = False

    # -------------------------------------------------------------------------
    # TARGET 4: Target outside ±120°
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("[5/5] TARGET 4: Target outside ±120° (rejection & stationary invariance)")
    # Target directly behind robot: 180°
    t4_heading = tester.cur_yaw + math.pi
    t4_x = tester.cur_x + 2.0 * math.cos(t4_heading)
    t4_y = tester.cur_y + 2.0 * math.sin(t4_heading)
    t4_z = tester.cur_z + 0.645

    pan_cmds_before = tester.neck_pan_cmd_count
    tilt_cmds_before = tester.neck_tilt_cmd_count

    print(f"  Target: ({t4_x:.2f}, {t4_y:.2f}, {t4_z:.2f})")
    bridge.current_x = tester.cur_x
    bridge.current_y = tester.cur_y
    bridge.current_z = tester.cur_z
    bridge.current_yaw_rad = tester.cur_yaw

    res4 = bridge.execute_look_at(t4_x, t4_y, t4_z)
    print(f"  Result: success={res4['success']}, workspace_exceeded={res4['workspace_exceeded']}")
    print(f"  Reason: {res4.get('reason')}")

    time.sleep(1.0)

    pan_cmds_after = tester.neck_pan_cmd_count
    tilt_cmds_after = tester.neck_tilt_cmd_count
    base_dist4 = math.hypot(tester.cur_x - initial_x, tester.cur_y - initial_y)

    print(f"  Neck command count changes: pan Δ={pan_cmds_after - pan_cmds_before}, tilt Δ={tilt_cmds_after - tilt_cmds_before}")
    print(f"  Base displacement: {base_dist4:.4f}m, non-zero cmd_vel count: {tester.cmd_vel_count}")

    t4_ok = (
        not res4["success"]
        and res4["workspace_exceeded"]
        and (pan_cmds_after == pan_cmds_before)  # No neck command issued
        and (tilt_cmds_after == tilt_cmds_before)
        and tester.cmd_vel_count == 0  # No cmd_vel issued
        and base_dist4 < 0.02  # Base stayed still
    )
    if t4_ok:
        print("✓ TARGET 4 PASSED: Out-of-workspace target rejected, neck not commanded, base stationary.")
    else:
        print("❌ TARGET 4 FAILED: Expected rejection with zero command emissions.")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("🎯 ALL 4 LIVE SIMULATION LOOKAT TARGET TESTS PASSED PERFECTLY!")
    else:
        print("❌ SOME LIVE SIMULATION TESTS FAILED.")
    print("=" * 70)

    # Clean shutdown
    bridge.running = False
    bridge.destroy_node()
    rclpy.shutdown()
    return all_passed


if __name__ == "__main__":
    success = run_live_test()
    sys.exit(0 if success else 1)
