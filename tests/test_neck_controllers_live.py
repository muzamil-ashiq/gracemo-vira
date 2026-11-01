#!/usr/bin/env python3
"""
Live Gazebo Harmonic Neck Controller & Physics Verification Test:
1. Connects to Gazebo Harmonic via gz-transport.
2. Monitors /world/gracemo_home/model/gracemo_vira/joint_state and /odom.
3. Confirms initial neck_pan_joint and neck_tilt_joint positions are ~0.0 rad.
4. Commands pan = +0.30 rad and tilt = +0.20 rad.
5. Verifies physical movement of neck joints to targets.
6. Verifies mobile base does NOT move during head articulation.
"""

import math
import sys
import time

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.double_pb2 import Double as GzDouble
    from gz.msgs10.model_pb2 import Model as GzModel
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
except ImportError:
    try:
        import gz.transport as gz_transport
        from gz.msgs.double_pb2 import Double as GzDouble
        from gz.msgs.model_pb2 import Model as GzModel
        from gz.msgs.odometry_pb2 import Odometry as GzOdometry
    except ImportError:
        print("ERROR: gz.transport or protobuf messages not available. Run in distrobox gracemo-harmonic.")
        sys.exit(1)


class NeckControllerTester:
    def __init__(self):
        self.node = gz_transport.Node()
        self.pan_pub = self.node.advertise("/head/pan/cmd_pos", GzDouble)
        self.tilt_pub = self.node.advertise("/head/tilt/cmd_pos", GzDouble)

        self.joint_positions = {}
        self.has_joint_state = False

        self.cur_x = 0.0
        self.cur_y = 0.0
        self.has_odom = False

        self.node.subscribe(
            GzModel,
            "/world/gracemo_home/model/gracemo_vira/joint_state",
            self._on_joint_state,
        )
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)

    def _on_joint_state(self, msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                self.joint_positions[j.name] = float(j.axis1.position)
        self.has_joint_state = True

    def _on_odom(self, msg: GzOdometry):
        self.cur_x = msg.pose.position.x
        self.cur_y = msg.pose.position.y
        self.has_odom = True

    def wait_for_telemetry(self, timeout_sec=10.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            if self.has_joint_state and self.has_odom:
                if "neck_pan_joint" in self.joint_positions and "neck_tilt_joint" in self.joint_positions:
                    return True
            time.sleep(0.05)
        return False

    def command_neck(self, pan_rad: float, tilt_rad: float):
        msg_pan = GzDouble()
        msg_pan.data = float(pan_rad)
        self.pan_pub.publish(msg_pan)

        msg_tilt = GzDouble()
        msg_tilt.data = float(tilt_rad)
        self.tilt_pub.publish(msg_tilt)


def run_test():
    print("=" * 65)
    print("  GRaCEmo ViRa — PHASE 3 STEP 2 LIVE NECK CONTROLLER TEST")
    print("=" * 65)

    tester = NeckControllerTester()
    print("\n[1] Waiting for live Gazebo joint state and odometry telemetry...")
    if not tester.wait_for_telemetry(timeout_sec=8.0):
        print("❌ FAILED: Did not receive neck joint telemetry from Gazebo.")
        print(f"Available joints: {list(tester.joint_positions.keys())}")
        return False

    print("✓ Connected to live Gazebo simulation!")

    # 1. Check initial positions
    initial_pan = tester.joint_positions.get("neck_pan_joint", None)
    initial_tilt = tester.joint_positions.get("neck_tilt_joint", None)
    initial_x = tester.cur_x
    initial_y = tester.cur_y

    print(f"\n[2] Initial Joint States:")
    print(f"    neck_pan_joint:  {initial_pan:+.4f} rad ({math.degrees(initial_pan):+.2f}°)")
    print(f"    neck_tilt_joint: {initial_tilt:+.4f} rad ({math.degrees(initial_tilt):+.2f}°)")
    print(f"    Initial Pose:    x={initial_x:.3f}m, y={initial_y:.3f}m")

    assert abs(initial_pan) < 0.05, f"Initial pan should be ~0.0, got {initial_pan}"
    assert abs(initial_tilt) < 0.05, f"Initial tilt should be ~0.0, got {initial_tilt}"
    print("✓ Initial positions verified at nominal 0.0 rad!")

    # 2. Command safe test pulse: pan = +0.3 rad, tilt = +0.2 rad
    target_pan = 0.30
    target_tilt = 0.20
    print(f"\n[3] Commanding neck pulse: pan={target_pan:+.2f} rad (+17.2°), tilt={target_tilt:+.2f} rad (+11.5°)...")

    t_start = time.time()
    pan_reached = False
    tilt_reached = False
    last_log = t_start

    while time.time() - t_start < 8.0:
        tester.command_neck(target_pan, target_tilt)
        time.sleep(0.05)

        cur_pan = tester.joint_positions.get("neck_pan_joint", 0.0)
        cur_tilt = tester.joint_positions.get("neck_tilt_joint", 0.0)

        if time.time() - last_log >= 1.0:
            print(f"    ... t={time.time()-t_start:.1f}s: pan={cur_pan:+.4f} rad, tilt={cur_tilt:+.4f} rad")
            last_log = time.time()

        if abs(cur_pan - target_pan) < 0.04:
            pan_reached = True
        if abs(cur_tilt - target_tilt) < 0.04:
            tilt_reached = True

        if pan_reached and tilt_reached:
            break

    final_pan = tester.joint_positions.get("neck_pan_joint", 0.0)
    final_tilt = tester.joint_positions.get("neck_tilt_joint", 0.0)
    dt_elapsed = time.time() - t_start
    print(f"    Achieved after {dt_elapsed:.1f}s: pan={final_pan:+.4f} rad (target: {target_pan:+.2f}), tilt={final_tilt:+.4f} rad (target: {target_tilt:+.2f})")

    assert abs(final_pan - target_pan) < 0.05, f"Neck pan did not reach target: got {final_pan}"
    assert abs(final_tilt - target_tilt) < 0.05, f"Neck tilt did not reach target: got {final_tilt}"
    print("✓ Neck joints physically moved and achieved commanded targets under PID control!")

    # 3. Check mobile base immobility
    disp = math.hypot(tester.cur_x - initial_x, tester.cur_y - initial_y)
    print(f"\n[4] Mobile Base Immobility Check:")
    print(f"    Base displacement during neck articulation: {disp * 1000:.2f} mm")
    assert disp < 0.01, f"Mobile base moved during neck motion! Displacement: {disp:.4f}m"
    print("✓ Mobile base remained completely stationary (displacement < 10mm)!")

    # 4. Return to zero
    print("\n[5] Returning neck to zero (nominal center)...")
    t0 = time.time()
    while time.time() - t0 < 2.0:
        tester.command_neck(0.0, 0.0)
        time.sleep(0.05)
    print(f"    Reset settled: pan={tester.joint_positions.get('neck_pan_joint', 0.0):+.4f} rad, tilt={tester.joint_positions.get('neck_tilt_joint', 0.0):+.4f} rad")

    print("\n" + "=" * 65)
    print("🎉 PHASE 3 STEP 2 GAZEBO NECK CONTROLLER VERIFICATION PASSED!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)
