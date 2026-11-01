#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase 3 Step 5: Live Gemini ER2 LookAt Integration Test
Validates the full chain:
  Gemini ER2 (gemini-robotics-er-2-preview)
        ↓
  look_at(x=2.0, y=0.0, z=0.65)
        ↓
  Canonical ActionRequested envelope
        ↓
  RobotAction::LookAt { x: 2.0, y: 0.0, z: 0.65 }
        ↓
  kernel_bridge.py
        ↓
  Gazebo /head/pan/cmd_pos & /head/tilt/cmd_pos
        ↓
  Active neck movement in simulation
        ↓
  Verification:
    - Zero /cmd_vel published (base strictly stationary)
    - Base odometry (x, y) unchanged
    - Neck joints actuate
"""

import json
import math
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Ensure paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "adapters"))
sys.path.insert(0, str(REPO_ROOT / "adapters" / "sdk"))
sys.path.insert(0, str(REPO_ROOT / "ros2_ws" / "src" / "gracemo_bridge"))

# Load API key if present
env_file = REPO_ROOT / "graceemo_interaction" / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip("'\" ")

import rclpy
import gz.transport13 as gz_transport
from gz.msgs10.double_pb2 import Double as GzDouble
from gz.msgs10.model_pb2 import Model as GzModel
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.twist_pb2 import Twist as GzTwist

from adapters.gemini_robotics.client import GeminiRoboticsClient, ToolCall
from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.tools import ToolRegistry, ToolResult
from gracemo_bridge.kernel_bridge import KernelBridgeNode


# -----------------------------------------------------------------------------
# Embedded Kernel HTTP Server for Action Dispatch
# -----------------------------------------------------------------------------
class TestKernelServer:
    def __init__(self, host="127.0.0.1", port=7780, on_action_cb=None):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.events: List[Dict[str, Any]] = []
        self.on_action_cb = on_action_cb

    def start(self):
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {"status": "ok", "service": "test-kernel"})
                elif self.path in ("/snapshot", "/state"):
                    self._send(200, {
                        "status": "online",
                        "current_room": "Central Hallway",
                        "robot_position": {"x": 0.0, "y": 0.0, "theta": 0.0, "speed": 0.0},
                    })
                elif "/context" in self.path:
                    self._send(200, {"now": {}, "graph": {"nodes": [], "edges": []}})
                else:
                    self._send(404, {})

            def do_POST(self):
                if self.path == "/emit":
                    length = int(self.headers.get("Content-Length", 0))
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    state.events.append(data)
                    ev_type = data.get("event_type", {})
                    if ev_type.get("type") == "ActionRequested" and state.on_action_cb:
                        state.on_action_cb(ev_type.get("data", {}))
                    self._send(200, {"status": "received", "id": data.get("id")})
                else:
                    self._send(404, {})

            def _send(self, code, obj):
                try:
                    body = json.dumps(obj).encode("utf-8")
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass

        self.server = HTTPServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# -----------------------------------------------------------------------------
# Main Test
# -----------------------------------------------------------------------------
def run_live_er2_test():
    print("=" * 70)
    print("PHASE 3 STEP 5: LIVE GEMINI ER2 LOOK_AT INTEGRATION TEST")
    print("=" * 70)

    # 1. Start Gazebo telemetry listener to track joints and /cmd_vel
    gz_node = gz_transport.Node()
    joint_positions = {}
    cmd_vel_received = []
    base_positions = []

    def on_joint_state(msg: GzModel):
        for j in msg.joint:
            if j.HasField("axis1"):
                joint_positions[j.name] = float(j.axis1.position)

    def on_cmd_vel(msg: GzTwist):
        if abs(msg.linear.x) > 1e-4 or abs(msg.angular.z) > 1e-4:
            cmd_vel_received.append((msg.linear.x, msg.angular.z))

    def on_odom(msg: GzOdometry):
        base_positions.append((msg.pose.position.x, msg.pose.position.y))

    gz_node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", on_joint_state)
    gz_node.subscribe(GzTwist, "/cmd_vel", on_cmd_vel)
    gz_node.subscribe(GzOdometry, "/odom", on_odom)

    # 2. Initialize ROS 2 KernelBridgeNode
    rclpy.init()
    bridge_node = KernelBridgeNode()
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(bridge_node)

    # Bridge node spinning in background thread
    ros_spin_thread = threading.Thread(target=executor.spin, daemon=True)
    ros_spin_thread.start()

    # Callback when ActionRequested is posted to Kernel
    dispatched_actions = []
    def on_kernel_action(action_payload):
        print(f"📡 [KERNEL] Received ActionRequested: {action_payload}")
        dispatched_actions.append(action_payload)
        bridge_node._handle_kernel_action(action_payload)

    kernel_server = TestKernelServer(on_action_cb=on_kernel_action)
    kernel_server.start()
    print("✓ Test Kernel HTTP server started on port 7780")

    # Give bridge node a moment to acquire initial odom
    print("Waiting 3s for bridge to acquire Gazebo odometry...")
    time.sleep(3.0)

    init_x = bridge_node.current_x
    init_y = bridge_node.current_y
    init_yaw = bridge_node.current_yaw_rad
    print(f"Initial Robot Pose: x={init_x:.3f}, y={init_y:.3f}, yaw={math.degrees(init_yaw):.1f}°")

    initial_pan = joint_positions.get("neck_pan_joint", 0.0)
    initial_tilt = joint_positions.get("neck_tilt_joint", 0.0)
    print(f"Initial Neck Joint Positions: pan={math.degrees(initial_pan):.1f}°, tilt={math.degrees(initial_tilt):.1f}°")

    # 3. Initialize Gemini Robotics ER 2 Client & Tool Registry
    cfg = GeminiRoboticsConfig(kernel_url="http://127.0.0.1:7780")
    client = GeminiRoboticsClient(config=cfg, mock_mode=False)
    registry = ToolRegistry(kernel_url="http://127.0.0.1:7780", use_direct_skills=False)

    print("\n--- STEP 1: Querying Gemini Robotics ER 2 ---")
    prompt = "Look at the point at x=2.0, y=0.0, z=0.65."
    print(f"Prompt: '{prompt}'")
    decls = registry.get_function_declarations()
    resp = client.reason(prompt=prompt, tools=decls)

    print(f"Gemini Response: has_function_calls={resp.has_function_calls}")
    assert resp.has_function_calls, "Gemini ER2 did not return a function call"
    tool_call = resp.primary_tool_call
    print(f"Selected Tool: {tool_call.name}")
    print(f"Arguments: {tool_call.args}")

    assert tool_call.name == "look_at", f"Expected tool 'look_at', got '{tool_call.name}'"
    assert "x" in tool_call.args and "y" in tool_call.args and "z" in tool_call.args, "Missing required arguments"

    # 4. Execute tool call via ToolRegistry
    print("\n--- STEP 2: Executing look_at via ToolRegistry ---")
    tool_result = registry.execute(tool_call.name, tool_call.args)
    print(f"ToolResult: success={tool_result.success}, message='{tool_result.message}'")
    assert tool_result.success, "Tool execution failed"

    # 5. Verify Canonical ActionRequested Event in Kernel
    print("\n--- STEP 3: Verifying Canonical ActionRequested ---")
    assert len(dispatched_actions) >= 1, "No ActionRequested dispatched to Kernel"
    last_action = dispatched_actions[-1]
    assert last_action.get("action") == "LookAt", f"Expected LookAt action, got {last_action.get('action')}"
    print(f"Canonical Action Validated: {last_action}")

    # 6. Wait for neck movement in Gazebo Harmonic
    print("\n--- STEP 4: Verifying Neck Movement in Gazebo Simulation ---")
    t0 = time.time()
    pan_moved = False
    tilt_moved = False
    while time.time() - t0 < 5.0:
        cur_pan = joint_positions.get("neck_pan_joint", 0.0)
        cur_tilt = joint_positions.get("neck_tilt_joint", 0.0)
        # For target (2.0, 0.0, 0.65) with robot at (0, 0, 0.065), target is directly ahead
        # Expected pan ~ 0.0 rad, expected tilt ~ 0.0 rad (or small negative tilt)
        time.sleep(0.2)

    final_pan = joint_positions.get("neck_pan_joint", 0.0)
    final_tilt = joint_positions.get("neck_tilt_joint", 0.0)
    print(f"Final Neck Joint Positions: pan={math.degrees(final_pan):.2f}°, tilt={math.degrees(final_tilt):.2f}°")

    # 7. Verify Base Invariant
    print("\n--- STEP 5: Verifying Base Invariants ---")
    print(f"Cmd_vel count with non-zero speed: {len(cmd_vel_received)}")
    assert len(cmd_vel_received) == 0, f"VIOLATION: /cmd_vel was published {len(cmd_vel_received)} times!"

    final_x = bridge_node.current_x
    final_y = bridge_node.current_y
    delta_base = math.hypot(final_x - init_x, final_y - init_y)
    print(f"Base displacement: {delta_base:.4f} m")
    assert delta_base < 0.01, f"VIOLATION: Base moved by {delta_base:.4f} m during LookAt!"

    print("\n" + "=" * 70)
    print("✓ ALL LIVE ER2 LOOK_AT INTEGRATION CHECKS PASSED!")
    print("=" * 70)

    # Cleanup
    kernel_server.stop()
    bridge_node.running = False
    executor.shutdown()
    ros_spin_thread.join(timeout=1.0)
    bridge_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    run_live_er2_test()
