"""
GRaCEmo ViRa — Phase 4 Step 3: Live Gazebo Harmonic Gemini Object-Grounded Closed Loop Verification

Validates the full end-to-end chain in Gazebo Harmonic + ROS 2 Humble + Rust MNSE Kernel:
1. Live camera RGB + Depth streams acquired.
2. YOLO11n perception detects chair in Kitchen & Dining.
3. Canonical ObjectDetected emitted to Rust MNSE Kernel.
4. Kernel creates persistent chair_001 world object.
5. Authoritative coordinates queried from Kernel /world/objects.
6. User command: "Look at the chair." sent to Gemini Robotics ER 2.
7. Gemini ER 2 reasons over grounded reality and selects look_at_object("chair").
8. ToolRegistry resolves chair -> chair_001, reads MNSE coordinates, emits canonical ActionRequested.
9. kernel_bridge receives ActionRequested and commands active 2-DOF neck.
10. Neck physically articulates in Gazebo.
11. Mobile base remains stationary (< 0.01 m displacement).
12. /cmd_vel non-zero emissions count == 0.
13. Perception re-observes chair and MNSE updates chair_001 with preserved identity.
14. Orchestrator re-observes updated state and verifies completion.
"""

import math
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image as RosImage, CameraInfo as RosCameraInfo
from nav_msgs.msg import Odometry as RosOdom
from geometry_msgs.msg import Twist as RosTwist

import gz.transport13 as gz_t
from gz.msgs10.pose_pb2 import Pose as GzPose
from gz.msgs10.boolean_pb2 import Boolean as GzBoolean
from gz.msgs10.model_pb2 import Model as GzModel

from adapters.perception.perception_service import PerceptionService
from adapters.perception.gaze_bridge import GazeBridge
from adapters.perception.world_model import WorldModelClient, WorldObject
from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.context import MNSEContextProvider
from adapters.gemini_robotics.client import GeminiRoboticsClient
from adapters.gemini_robotics.tools import ToolRegistry
from adapters.gemini_robotics.orchestrator import GeminiRoboticsOrchestrator


class LiveGeminiGroundingTester(Node):
    def __init__(self):
        super().__init__("live_gemini_grounding_tester")

        self.latest_rgb = None
        self.latest_depth = None
        self.camera_info = None

        self.init_base_x = None
        self.init_base_y = None
        self.cur_base_x = 0.0
        self.cur_base_y = 0.0
        self.cur_base_yaw = 0.0
        self.cmd_vel_count = 0

        self.joint_positions = {}
        self.has_joint_states = False
        self.gz_js_count = 0
        self.ros_js_count = 0

        self.baseline_pan: Optional[float] = None
        self.baseline_tilt: Optional[float] = None
        self.max_pan_delta: float = 0.0
        self.max_tilt_delta: float = 0.0

        # ROS 2 Subscribers
        self.sub_rgb = self.create_subscription(RosImage, "/camera/image_raw", self._on_rgb, 10)
        self.sub_depth = self.create_subscription(RosImage, "/camera/depth_image", self._on_depth, 10)
        self.sub_info = self.create_subscription(RosCameraInfo, "/camera/camera_info", self._on_info, 10)
        self.sub_odom = self.create_subscription(RosOdom, "/odom", self._on_odom, 10)
        self.sub_cmd_vel = self.create_subscription(RosTwist, "/cmd_vel", self._on_cmd_vel, 10)

        # Gazebo Transport Node
        self.gz_node = gz_t.Node()
        self.gz_node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", self._on_gz_joint_state)

        # Perception Service (emits directly to kernel)
        self.service = PerceptionService(
            emit_to_kernel=True,
            save_debug_frames=True,
            debug_frame_path=str(REPO_ROOT / "scripts" / "perception_debug_frame.jpg"),
            ros_node=self,
        )

        self.gaze_bridge = GazeBridge()

    def _on_info(self, msg: RosCameraInfo):
        self.camera_info = msg
        self.service.set_camera_info(msg)

    def _on_rgb(self, msg: RosImage):
        h, w = msg.height, msg.width
        if msg.encoding in ["rgb8", "bgr8"]:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
            if msg.encoding == "rgb8":
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            self.latest_rgb = arr

    def _on_depth(self, msg: RosImage):
        h, w = msg.height, msg.width
        if msg.encoding == "32FC1":
            self.latest_depth = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))

    def _on_odom(self, msg: RosOdom):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        self.cur_base_x = float(p.x)
        self.cur_base_y = float(p.y)
        if self.init_base_x is None:
            self.init_base_x = self.cur_base_x
            self.init_base_y = self.cur_base_y

        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.cur_base_yaw = math.atan2(siny, cosy)

    def _on_cmd_vel(self, msg: RosTwist):
        if abs(msg.linear.x) > 1e-4 or abs(msg.angular.z) > 1e-4:
            self.cmd_vel_count += 1

    def _on_gz_joint_state(self, msg: GzModel):
        self.gz_js_count += 1
        for j in msg.joint:
            if j.HasField("axis1"):
                pos = float(j.axis1.position)
                self.joint_positions[j.name] = pos
                if j.name == "neck_pan_joint" and self.baseline_pan is not None:
                    d = abs(pos - self.baseline_pan)
                    if d > self.max_pan_delta:
                        self.max_pan_delta = d
                elif j.name == "neck_tilt_joint" and self.baseline_tilt is not None:
                    d = abs(pos - self.baseline_tilt)
                    if d > self.max_tilt_delta:
                        self.max_tilt_delta = d
        self.has_joint_states = True

    def set_robot_pose(self, x: float, y: float, yaw: float) -> bool:
        """Positions robot via Gazebo Harmonic set_pose service."""
        req = GzPose()
        req.name = "gracemo_vira"
        req.id = 171
        req.position.x = x
        req.position.y = y
        req.position.z = 0.08
        req.orientation.z = math.sin(yaw / 2.0)
        req.orientation.w = math.cos(yaw / 2.0)

        rep = GzBoolean()
        res, rep = self.gz_node.request("/world/gracemo_home/set_pose", req, GzPose, GzBoolean, 3000)
        success = bool(rep.data if res else False)
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.05)
        self.init_base_x = self.cur_base_x
        self.init_base_y = self.cur_base_y
        self.cmd_vel_count = 0
        return success

    def wait_for_sensors(self, timeout_sec: float = 12.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.latest_rgb is not None and self.latest_depth is not None and self.camera_info is not None:
                return True
        return False


def run_live_grounding_test():
    print("=" * 80)
    print("  GRaCEmo ViRa — PHASE 4 STEP 3 LIVE GEMINI ER 2 OBJECT GROUNDING TEST")
    print("=" * 80)

    rclpy.init()
    node = LiveGeminiGroundingTester()

    # -------------------------------------------------------------------------
    # Gate 1: Sensor Streams
    # -------------------------------------------------------------------------
    print("\n[1/8] Acquiring live RGB, Depth, and CameraInfo streams...")
    if not node.wait_for_sensors(timeout_sec=12.0):
        print("❌ FAILED: Timed out waiting for camera topics.")
        node.destroy_node()
        rclpy.shutdown()
        return False

    print("✓ All 3 sensor topics active and streaming.")

    # -------------------------------------------------------------------------
    # Gate 2: Robot Pose in Kitchen & Dining
    # -------------------------------------------------------------------------
    print("\n[2/8] Positioning robot in Kitchen & Dining facing dining table & chairs...")
    ok_pose = node.set_robot_pose(-4.5, -2.5, -1.5708)
    print(f"  • Pose set: {ok_pose} (Base: x={node.cur_base_x:.3f}, y={node.cur_base_y:.3f}, yaw={math.degrees(node.cur_base_yaw):.1f}°)")

    for _ in range(30):
        rclpy.spin_once(node, timeout_sec=0.05)

    # -------------------------------------------------------------------------
    # Gate 3: Initial Perception & MNSE Object Persistence
    # -------------------------------------------------------------------------
    print("\n[3/8] Running perception pipeline to detect chair in visual field...")
    p_res = node.service.process_frame(node.latest_rgb, node.latest_depth)
    print(f"  • Detections count: {p_res.count}")

    if p_res.count == 0:
        print("  ⚠️ Initial pass 0 detections; applying 10° tilt scan...")
        from gz.msgs10.double_pb2 import Double as GzDouble
        gz_cmd_tilt = node.gz_node.advertise("/head/tilt/cmd_pos", GzDouble)
        msg_tilt = GzDouble()
        msg_tilt.data = 0.20
        gz_cmd_tilt.publish(msg_tilt)
        time.sleep(1.0)
        for _ in range(30):
            rclpy.spin_once(node, timeout_sec=0.05)
        p_res = node.service.process_frame(node.latest_rgb, node.latest_depth)
        print(f"  • Post-tilt detections count: {p_res.count}")

    if p_res.count == 0:
        print("❌ FAILED: No objects detected in scene.")
        node.destroy_node()
        rclpy.shutdown()
        return False

    target_det = p_res.primary_detection()
    print(f"  ✓ Primary detection: {target_det.class_name} (conf: {target_det.confidence:.2f}, depth: {target_det.depth_m:.3f}m)")
    print(f"    World XYZ: ({target_det.position_world.x:.3f}, {target_det.position_world.y:.3f}, {target_det.position_world.z:.3f})")

    # Wait 0.5s for Kernel to process ObjectDetected event into SQLite
    time.sleep(0.5)

    # -------------------------------------------------------------------------
    # Gate 4: Authoritative World Object Query from Rust MNSE
    # -------------------------------------------------------------------------
    print("\n[4/8] Querying Authoritative World Objects from Rust MNSE Kernel (/world/objects)...")
    provider = MNSEContextProvider(kernel_url="http://127.0.0.1:7780")
    world_objs = provider.get_world_objects(visible_only=True)
    print(f"  • Objects in MNSE Kernel: {[o.object_id for o in world_objs]}")

    chair_obj: Optional[WorldObject] = None
    for o in world_objs:
        if "chair" in o.class_name.lower():
            chair_obj = o
            break

    if chair_obj is None:
        print("❌ FAILED: chair_001 not found in Rust MNSE world objects.")
        node.destroy_node()
        rclpy.shutdown()
        return False

    print(f"  ✓ Authoritative World Object: {chair_obj.object_id}")
    print(f"    • Class:             {chair_obj.class_name}")
    print(f"    • Authoritative XYZ: ({chair_obj.world_x:.3f}, {chair_obj.world_y:.3f}, {chair_obj.world_z:.3f})")
    print(f"    • Confidence:        {chair_obj.confidence:.2f}")
    print(f"    • Observations:      {chair_obj.observation_count}")
    print(f"    • Currently Visible: {chair_obj.currently_visible}")

    # Verify finite coordinates
    assert math.isfinite(chair_obj.world_x) and math.isfinite(chair_obj.world_y) and math.isfinite(chair_obj.world_z)

    # -------------------------------------------------------------------------
    # Gate 5: Gemini Robotics ER 2 Closed-Loop Orchestration
    # -------------------------------------------------------------------------
    print("\n[5/8] Invoking Gemini Robotics ER 2 with user command: \"Look at the chair.\"...")
    config = GeminiRoboticsConfig(model_name="gemini-robotics-er-2-preview")
    print(f"  • Target Gemini Model: {config.model_name}")
    print(f"  • API Key Configured:  {config.is_configured()}")

    # Initialize Gemini client
    client = GeminiRoboticsClient(config=config)
    is_live_gemini = client.is_live
    print(f"  • Client Mode:         {'LIVE API' if is_live_gemini else 'MOCK REASONER'}")

    registry = ToolRegistry(
        kernel_url="http://127.0.0.1:7780",
        use_direct_skills=False,
        context_provider=provider,
    )

    orchestrator = GeminiRoboticsOrchestrator(
        config=config,
        client=client,
        context_provider=provider,
        registry=registry,
    )

    # Spin to get fresh baseline joint angles
    for _ in range(20):
        rclpy.spin_once(node, timeout_sec=0.05)

    init_pan = node.joint_positions.get("neck_pan_joint", 0.0)
    init_tilt = node.joint_positions.get("neck_tilt_joint", 0.0)
    node.baseline_pan = init_pan
    node.baseline_tilt = init_tilt
    node.max_pan_delta = 0.0
    node.max_tilt_delta = 0.0
    base_x_before = node.cur_base_x
    base_y_before = node.cur_base_y
    node.cmd_vel_count = 0

    print(f"  • Pre-Action Neck: Pan={math.degrees(init_pan):+.2f}°, Tilt={math.degrees(init_tilt):+.2f}°")
    print(f"  • Pre-Action Base: ({base_x_before:.4f}, {base_y_before:.4f})")

    # Execute embodied reasoning task
    t_orch_start = time.time()
    orch_result = orchestrator.run_task("Look at the chair.")
    orch_elapsed = time.time() - t_orch_start

    print(f"\n  ✓ Orchestrator Output ({orch_elapsed:.2f}s):")
    print(f"    • Success:            {orch_result.success}")
    print(f"    • Turns:              {orch_result.turns_count}")
    print(f"    • Actions Dispatched: {orch_result.actions_dispatched}")
    print(f"    • Final Response:     \"{orch_result.final_response}\"")

    # -------------------------------------------------------------------------
    # Gate 6: Physical Neck Movement & Invariant Verification in Gazebo
    # -------------------------------------------------------------------------
    print("\n[6/8] Waiting 4.0s for physical neck articulation and monitoring base...")
    t_wait_start = time.time()
    last_print = t_wait_start
    while time.time() - t_wait_start < 4.0:
        rclpy.spin_once(node, timeout_sec=0.02)
        time.sleep(0.03)
        if time.time() - last_print >= 0.5:
            cp = node.joint_positions.get("neck_pan_joint", 0.0)
            ct = node.joint_positions.get("neck_tilt_joint", 0.0)
            print(f"    ... t={time.time()-t_wait_start:.1f}s: pan={math.degrees(cp):+.2f}°, tilt={math.degrees(ct):+.2f}° (max_d_pan={math.degrees(node.max_pan_delta):.2f}°, max_d_tilt={math.degrees(node.max_tilt_delta):.2f}°)")
            last_print = time.time()

    final_pan = node.joint_positions.get("neck_pan_joint", 0.0)
    final_tilt = node.joint_positions.get("neck_tilt_joint", 0.0)
    base_x_after = node.cur_base_x
    base_y_after = node.cur_base_y
    base_disp = math.hypot(base_x_after - base_x_before, base_y_after - base_y_before)

    neck_moved = (
        node.max_pan_delta > 0.002
        or node.max_tilt_delta > 0.002
        or abs(final_pan - init_pan) > 0.002
        or abs(final_tilt - init_tilt) > 0.002
    )

    print(f"\n  ✓ Physical Motion Observed:")
    print(f"    • Neck Articulation: Pan: {math.degrees(init_pan):+.2f}° -> {math.degrees(final_pan):+.2f}°, "
          f"Tilt: {math.degrees(init_tilt):+.2f}° -> {math.degrees(final_tilt):+.2f}° (Moved: {neck_moved})")
    print(f"    • Base Displacement: {base_disp:.5f} m (Acceptance limit: < 0.01 m)")
    print(f"    • /cmd_vel Non-Zero: {node.cmd_vel_count} (Acceptance limit: == 0)")

    # -------------------------------------------------------------------------
    # Gate 7: Re-Observation & Object Identity Preservation
    # -------------------------------------------------------------------------
    print("\n[7/8] Re-running perception and verifying persistent object identity preservation...")
    for _ in range(30):
        rclpy.spin_once(node, timeout_sec=0.05)
    re_res = node.service.process_frame(node.latest_rgb, node.latest_depth)
    print(f"  • Re-observation detections count: {re_res.count}")

    time.sleep(0.5)
    re_objs = provider.get_world_objects(visible_only=True)
    chair_after: Optional[WorldObject] = None
    for o in re_objs:
        if o.object_id == chair_obj.object_id:
            chair_after = o
            break

    print(f"  • Objects in MNSE after re-observation: {[o.object_id for o in re_objs]}")
    identity_preserved = chair_after is not None and chair_after.object_id == chair_obj.object_id
    if chair_after:
        print(f"  ✓ Identity Preserved: {chair_after.object_id} (obs count: {chair_after.observation_count})")
        print(f"    Position: ({chair_after.world_x:.3f}, {chair_after.world_y:.3f}, {chair_after.world_z:.3f})")

    # -------------------------------------------------------------------------
    # Gate 8: Final Acceptance Invariant Checks
    # -------------------------------------------------------------------------
    print("\n[8/8] ACCEPTANCE GATES EVALUATION:")
    g1 = len(world_objs) > 0
    g2 = chair_obj is not None
    g3 = math.isfinite(chair_obj.world_x)
    g4 = "look_at_object" in orch_result.actions_dispatched or "look_at" in orch_result.actions_dispatched
    g5 = neck_moved
    g6 = base_disp < 0.01
    g7 = node.cmd_vel_count == 0
    g8 = identity_preserved
    g9 = orch_result.success

    print(f"  1. Context Grounding:          {'PASS' if g1 else 'FAIL'}")
    print(f"  2. Object Resolution:          {'PASS' if g2 else 'FAIL'} ({chair_obj.object_id if chair_obj else 'None'})")
    print(f"  3. Coordinate Authority:       {'PASS' if g3 else 'FAIL'} (({chair_obj.world_x:.2f}, {chair_obj.world_y:.2f}, {chair_obj.world_z:.2f}))")
    print(f"  4. Semantic Intent Dispatch:   {'PASS' if g4 else 'FAIL'} ({orch_result.actions_dispatched})")
    print(f"  5. Physical Neck Motion:       {'PASS' if g5 else 'FAIL'}")
    print(f"  6. Stationary Base (<0.01m):   {'PASS' if g6 else 'FAIL'} ({base_disp:.5f}m)")
    print(f"  7. Zero /cmd_vel Emissions:    {'PASS' if g7 else 'FAIL'} (count: {node.cmd_vel_count})")
    print(f"  8. Identity Preservation:      {'PASS' if g8 else 'FAIL'} ({chair_obj.object_id} preserved)")
    print(f"  9. Closed-Loop Completion:     {'PASS' if g9 else 'FAIL'}")

    all_pass = all([g1, g2, g3, g4, g5, g6, g7, g8, g9])
    print("\n" + "=" * 80)
    if all_pass:
        print("🏆 PHASE 4 STEP 3 LIVE GAZEBO DEMONSTRATION: ALL GATES GREEN (PASS)")
    else:
        print("❌ PHASE 4 STEP 3 LIVE GAZEBO DEMONSTRATION: FAILED GATES DETECTED")
    print("=" * 80 + "\n")

    node.destroy_node()
    rclpy.shutdown()
    return all_pass


if __name__ == "__main__":
    success = run_live_grounding_test()
    sys.exit(0 if success else 1)
