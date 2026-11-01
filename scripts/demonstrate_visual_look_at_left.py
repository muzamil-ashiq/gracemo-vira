#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 3 Visual Verification: Angle Articulation Demo
Commands a 45° left gaze (x=1.414, y=1.414, z=0.65) to verify physical joint movement in Gazebo.
"""

import json
import math
import os
import sys
import time
from pathlib import Path
import numpy as np
import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "adapters"))
sys.path.insert(0, str(REPO_ROOT / "adapters" / "sdk"))

env_file = REPO_ROOT / "graceemo_interaction" / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip("'\" ")

import gz.transport13 as gz_transport
from gz.msgs10.model_pb2 import Model as GzModel
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.image_pb2 import Image as GzImage

from adapters.gemini_robotics.client import GeminiRoboticsClient
from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.tools import ToolRegistry


def main():
    print("=" * 75)
    print("GRaCEmo ViRa — LOOK_AT PHYSICAL ARTICULATION DEMO (+45° LEFT)")
    print("=" * 75)

    gz_node = gz_transport.Node()
    telemetry = {
        "joint_positions": {},
        "base_x": 0.0,
        "base_y": 0.0,
        "base_yaw": 0.0,
        "cmd_vel_count": 0,
        "latest_frame": None,
    }

    def on_joint_state(msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                telemetry["joint_positions"][j.name] = float(j.axis1.position)

    def on_odom(msg: GzOdometry):
        p = msg.pose.position
        q = msg.pose.orientation
        telemetry["base_x"] = float(p.x)
        telemetry["base_y"] = float(p.y)
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        telemetry["base_yaw"] = math.atan2(siny, cosy)

    def on_cmd_vel(msg: GzTwist):
        if abs(msg.linear.x) > 1e-4 or abs(msg.angular.z) > 1e-4:
            telemetry["cmd_vel_count"] += 1

    def on_image(msg: GzImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            telemetry["latest_frame"] = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception:
            pass

    gz_node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", on_joint_state)
    gz_node.subscribe(GzOdometry, "/odom", on_odom)
    gz_node.subscribe(GzTwist, "/cmd_vel", on_cmd_vel)
    gz_node.subscribe(GzImage, "/camera/image_raw", on_image)

    # Wait for telemetry
    time.sleep(1.0)

    init_pan = telemetry["joint_positions"].get("neck_pan_joint", 0.0)
    init_tilt = telemetry["joint_positions"].get("neck_tilt_joint", 0.0)
    init_x = telemetry["base_x"]
    init_y = telemetry["base_y"]

    print(f"Initial Neck Joint Pose: pan={math.degrees(init_pan):+.2f}°, tilt={math.degrees(init_tilt):+.2f}°")
    print(f"Initial Base Position:   x={init_x:+.4f}m, y={init_y:+.4f}m")

    # Command via Gemini ER 2
    cfg = GeminiRoboticsConfig(kernel_url="http://127.0.0.1:7780")
    client = GeminiRoboticsClient(config=cfg, mock_mode=False)
    registry = ToolRegistry(kernel_url="http://127.0.0.1:7780", use_direct_skills=False)

    prompt = "Look at the point at x=1.414, y=1.414, z=0.65."
    print(f"\nSending Gemini Prompt: \"{prompt}\"...")
    decls = registry.get_function_declarations()
    resp = client.reason(prompt=prompt, tools=decls)

    assert resp.has_function_calls, "Expected function call"
    tool_call = resp.primary_tool_call
    print(f"Gemini Selected Tool: {tool_call.name}({tool_call.args})")

    # Dispatch tool
    telemetry["cmd_vel_count"] = 0
    res = registry.execute(tool_call.name, tool_call.args)
    print(f"Tool Execution: {res.message}")

    # Wait for physical neck movement in Gazebo
    print("Awaiting physical neck articulation in Gazebo Harmonic...")
    time.sleep(3.0)

    final_pan = telemetry["joint_positions"].get("neck_pan_joint", 0.0)
    final_tilt = telemetry["joint_positions"].get("neck_tilt_joint", 0.0)
    final_x = telemetry["base_x"]
    final_y = telemetry["base_y"]
    base_disp = math.hypot(final_x - init_x, final_y - init_y)

    print("\nObservations:")
    print(f"  • Neck Pan Before/After:  {math.degrees(init_pan):+6.2f}° -> {math.degrees(final_pan):+6.2f}° (Target ~+45°)")
    print(f"  • Neck Tilt Before/After: {math.degrees(init_tilt):+6.2f}° -> {math.degrees(final_tilt):+6.2f}°")
    print(f"  • Base Displacement:      {base_disp:.4f} m")
    print(f"  • /cmd_vel count:         {telemetry['cmd_vel_count']}")

    if telemetry["latest_frame"] is not None:
        p_left = REPO_ROOT / "scripts" / "camera_view_look_at_left.jpg"
        cv2.imwrite(str(p_left), telemetry["latest_frame"])
        print(f"  • Snapshot saved: {p_left.name}")

    # Verify physical movement
    pan_delta = abs(final_pan - init_pan)
    print(f"  • Pan Joint Delta:        {math.degrees(pan_delta):.1f}° (Confirmed Articulation)")
    assert pan_delta > 0.3, f"Expected neck to turn left, got delta {pan_delta}"
    assert telemetry["cmd_vel_count"] == 0, "Base velocity detected"
    assert base_disp < 0.01, "Base moved"

    print("\n✓ PHYSICAL NECK ARTICULATION DEMO PASSED!")
    os._exit(0)


if __name__ == "__main__":
    main()
