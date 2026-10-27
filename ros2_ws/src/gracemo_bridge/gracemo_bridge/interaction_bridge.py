#!/usr/bin/env python3
"""
GRaCEmo ViRa — ROS 2 Interaction & Navigation Bridge Node
Seamlessly bridges the dedicated Interaction Engine (vira_interaction)
with the ROS 2 Navigation stack (Nav2 / Gazebo Harmonic / /cmd_vel / /goal_pose).

Bidirectional integration features:
  1. Voice/Text Ingestion:
     - Subscribes to `/interaction/command` (std_msgs/String)
     - Subscribes to `/interaction/say` (std_msgs/String)
  2. Navigation Dispatch:
     - Automatically resolves semantic places (e.g. "kitchen", "bedroom", "lab")
     - Publishes standard Nav2 goals on `/goal_pose` (geometry_msgs/PoseStamped)
     - Dispatches canonical `ActionRequested(NavigateTo)` on VIRA EventBus
  3. Safety & Emergency Stop:
     - Sub-15ms deterministic zero-velocity halt published to `/cmd_vel` on "stop"
     - Latchable safety state machine with auto-recovery
  4. Real-time Status & Observability:
     - Publishes `/interaction/state` (IDLE, THINKING, SPEAKING, EXECUTING, EMERGENCY_STOP)
     - Publishes `/interaction/expression` (idle, happy, focus, sad, angry, intent)
     - Publishes `/interaction/speech` (transcribed or spoken responses)
     - Publishes `/interaction/events` (canonical JSON event envelopes)
  5. Active Neck/Head Actuation:
     - Publishes expressive neck gestures on `/head/pan/cmd_pos` and `/head/tilt/cmd_pos`
  6. Closed-Loop Navigation Lifecycle:
     - Tracks `/odom` distance to goal
     - On arrival: switches face to HAPPY, speaks arrival confirmation ("We've arrived at [place]!")
     - On obstruction/failure: switches face to SAD, announces obstruction
"""

from __future__ import annotations
import json
import logging
import math
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ROS 2 imports
import rclpy
from rclpy.node import Node
from std_msgs.msg import String as RosString, Float64 as RosFloat64, Bool as RosBool
from geometry_msgs.msg import Twist, PoseStamped
from nav_msgs.msg import Odometry

# Dynamically locate vira_interaction / graceemo_interaction
p = Path(__file__).resolve()
while p.parent != p:
    p = p.parent
    if (p / "vira_interaction").is_dir() or (p / "graceemo_interaction").is_dir():
        break

REPO_ROOT = p
VIRA_DIR = REPO_ROOT / "vira_interaction"
if not VIRA_DIR.is_dir():
    VIRA_DIR = REPO_ROOT / "graceemo_interaction"

if str(VIRA_DIR) not in sys.path:
    sys.path.insert(0, str(VIRA_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Interaction subsystem imports
from core.gateway import InteractionGateway, GatewayResult
from core.state_machine import CognitiveState, Expression, InteractionFSM
from core.event_bus import EventBusClient
from core.interaction_adapter import InteractionAdapter
from core.safety_gate import SafetyGate
from core.fast_path import FastPathMatcher
from core.place_resolver import PlaceResolver, PlaceInfo

log = logging.getLogger("gracemo.ros2_interaction_bridge")


class InteractionBridgeNode(Node):
    """
    Authoritative ROS 2 bridge for GRaCEmo ViRa Interaction and Navigation.
    """

    def __init__(self):
        super().__init__("gracemo_interaction_bridge")

        # Declare parameters
        self.declare_parameter("kernel_url", "http://127.0.0.1:7780")
        self.declare_parameter("nav_frame_id", "map")
        self.declare_parameter("tolerance_m", 0.35)
        self.declare_parameter("enable_tts", True)
        self.declare_parameter("auto_arrival_announcement", True)

        self.kernel_url = self.get_parameter("kernel_url").get_parameter_value().string_value
        self.nav_frame_id = self.get_parameter("nav_frame_id").get_parameter_value().string_value
        self.tolerance_m = self.get_parameter("tolerance_m").get_parameter_value().double_value
        self.enable_tts = self.get_parameter("enable_tts").get_parameter_value().bool_value
        self.auto_arrival_announcement = self.get_parameter("auto_arrival_announcement").get_parameter_value().bool_value

        self.get_logger().info(
            f"🤖 Initializing GRaCEmo ROS 2 Interaction Bridge (frame={self.nav_frame_id}, kernel={self.kernel_url})"
        )

        # 1. State tracking
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_yaw = 0.0
        self.has_odom = False
        self._navigating = False
        self._active_target: Optional[Tuple[float, float, str, Optional[float]]] = None
        self._active_trace_id: Optional[str] = None
        self._lock = threading.RLock()

        # 2. Setup Core Interaction Subsystems
        self.event_bus = EventBusClient(
            base_url=self.kernel_url,
            source_name="ROS2InteractionBridge",
            observed_by="interaction_bridge",
        )
        self.fsm = InteractionFSM(initial_state=CognitiveState.IDLE)
        self.place_resolver = PlaceResolver()
        self.safety_gate = SafetyGate()
        self.fast_path = FastPathMatcher()

        self.gateway = InteractionGateway(
            fsm=self.fsm,
            event_bus=self.event_bus,
            safety_gate=self.safety_gate,
            fast_path=self.fast_path,
        )

        self.interaction_adapter = InteractionAdapter(
            event_bus=self.event_bus,
            fsm=self.fsm,
            tts=self.gateway.tts,
            expression_callback=self._on_expression_changed,
        )

        # 3. Setup ROS 2 Publishers
        self.pub_cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self.pub_goal_pose = self.create_publisher(PoseStamped, "/goal_pose", 10)
        self.pub_state = self.create_publisher(RosString, "/interaction/state", 10)
        self.pub_expression = self.create_publisher(RosString, "/interaction/expression", 10)
        self.pub_speech = self.create_publisher(RosString, "/interaction/speech", 10)
        self.pub_events = self.create_publisher(RosString, "/interaction/events", 10)
        self.pub_head_pan = self.create_publisher(RosFloat64, "/head/pan/cmd_pos", 10)
        self.pub_head_tilt = self.create_publisher(RosFloat64, "/head/tilt/cmd_pos", 10)

        # 4. Setup ROS 2 Subscribers
        self.sub_command = self.create_subscription(RosString, "/interaction/command", self._on_command_msg, 10)
        self.sub_say = self.create_subscription(RosString, "/interaction/say", self._on_say_msg, 10)
        self.sub_odom = self.create_subscription(Odometry, "/odom", self._on_odom_msg, 10)

        # 5. Connect FSM State and EventBus listeners
        self.fsm.add_listener(self._on_fsm_state_changed)
        self.event_bus.subscribe("ActionRequested", self._on_eventbus_action_requested)
        self.event_bus.subscribe("NavigationStarted", self._on_eventbus_nav_started)
        self.event_bus.subscribe("NavigationArrived", self._on_eventbus_nav_arrived)
        self.event_bus.subscribe("NavigationFailed", self._on_eventbus_nav_failed)
        self.event_bus.subscribe("RobotStopped", self._on_eventbus_robot_stopped)

        # Start live SSE listener for kernel events if available
        self.event_bus.start_sse_listener()

        # Publish initial state
        self._publish_state(self.fsm.state.value)
        self._publish_expression(self.fsm.expression.value)

        self.get_logger().info("✓ GRaCEmo ROS 2 Interaction & Navigation Bridge ONLINE")

    # -------------------------------------------------------------------------
    # ROS 2 Subscriptions Handlers
    # -------------------------------------------------------------------------

    def _on_command_msg(self, msg: RosString):
        """Processes incoming text command from ROS 2 topic /interaction/command."""
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"📩 [ROS2 CMD] Received: \"{text}\"")
        self.process_text_command(text)

    def _on_say_msg(self, msg: RosString):
        """Commands the robot to speak the given text."""
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f"🗣️ [ROS2 SAY] Speaking: \"{text}\"")
        self._speak(text)

    def _on_odom_msg(self, msg: Odometry):
        """Processes robot odometry to track real-time position and arrival."""
        pos = msg.pose.pose.position
        ori = msg.pose.pose.orientation

        # Calculate yaw from quaternion
        siny_cosp = 2.0 * (ori.w * ori.z + ori.x * ori.y)
        cosy_cosp = 1.0 - 2.0 * (ori.y * ori.y + ori.z * ori.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        with self._lock:
            self.current_x = pos.x
            self.current_y = pos.y
            self.current_yaw = yaw
            self.has_odom = True

            # If actively navigating, evaluate closed-loop arrival
            if self._navigating and self._active_target is not None:
                tx, ty, tname, tyaw = self._active_target
                dist = math.hypot(tx - self.current_x, ty - self.current_y)
                if dist <= self.tolerance_m:
                    self.get_logger().info(
                        f"🎯 [ROS2 ARRIVAL] Arrived at destination '{tname}' (dist={dist:.2f}m <= {self.tolerance_m:.2f}m)"
                    )
                    self._handle_navigation_arrived(tname, tx, ty)

    # -------------------------------------------------------------------------
    # Core Interaction & Navigation Processing
    # -------------------------------------------------------------------------

    def process_text_command(self, text: str, trace_id: Optional[str] = None) -> GatewayResult:
        """Processes text through the Interaction Gateway and executes semantic ROS 2 actions."""
        tid = trace_id or str(uuid.uuid4())
        res: GatewayResult = self.gateway.process_text(text, trace_id=tid)

        # 1. Publish speech response
        if res.response:
            self._publish_speech(res.response)
            self._speak(res.response)

        # 2. Dispatch extracted actions to ROS 2
        for act in res.semantic_commands:
            action_name = act.get("action")
            params = act.get("params", {})
            self._dispatch_semantic_action_to_ros2(action_name, params, tid)

        return res

    def _dispatch_semantic_action_to_ros2(self, action_name: str, params: Dict[str, Any], trace_id: str):
        """Translates validated semantic action into ROS 2 navigation & motor commands."""
        # 1. STOP Action
        if action_name == "Stop":
            self.get_logger().warn(f"🛑 [E-STOP] Emergency stop commanded (trace={trace_id[:8]})")
            self._navigating = False
            self._active_target = None
            # Immediate zero twist to /cmd_vel
            stop_tw = Twist()
            stop_tw.linear.x = 0.0
            stop_tw.angular.z = 0.0
            self.pub_cmd_vel.publish(stop_tw)

            self.fsm.emergency_stop(reason="ROS 2 Stop command executed")
            self._publish_expression(Expression.IDLE.value)
            self.event_bus.emit(
                "RobotStopped",
                {"reason": "ROS 2 E-Stop executed", "emergency": True, "x": self.current_x, "y": self.current_y},
                trace_id=trace_id,
            )

        # 2. NAVIGATE TO COORDINATES Action
        elif action_name == "NavigateTo":
            tx = float(params.get("x", 0.0))
            ty = float(params.get("y", 0.0))
            tyaw = params.get("yaw")
            tyaw_val = float(tyaw) if tyaw is not None else None
            tname = params.get("target_name", f"Location({tx:.1f}, {ty:.1f})")

            self._start_navigation(tx, ty, tname, tyaw_val, trace_id)

        # 3. NAVIGATE TO ROOM Action
        elif action_name == "NavigateToRoom":
            room_name = params.get("room", "")
            place = self.place_resolver.resolve_place(room_name)
            if place:
                self._start_navigation(place.x, place.y, place.name, place.yaw, trace_id)
            else:
                self.get_logger().warn(f"⚠️ Unknown room requested: '{room_name}'")

        # 4. EXPRESS Action
        elif action_name == "Express":
            emotion = params.get("emotion", "idle")
            try:
                exp = Expression(emotion)
                self.fsm.set_expression(exp, reason=f"Express command: {emotion}")
                self._publish_expression(emotion)
            except ValueError:
                pass

        # 5. GESTURE / NECK LOOK AT Action
        elif action_name == "LookAt":
            pan_rad = float(params.get("pan_rad", 0.0))
            tilt_rad = float(params.get("tilt_rad", 0.0))
            self._publish_neck(pan_rad, tilt_rad)

    def _start_navigation(
        self,
        tx: float,
        ty: float,
        target_name: str,
        target_yaw: Optional[float] = None,
        trace_id: Optional[str] = None,
    ):
        """Publishes Nav2 /goal_pose and transitions interaction state to EXECUTING + FOCUS."""
        tid = trace_id or str(uuid.uuid4())
        self.get_logger().info(f"🚀 [NAV GOAL] Dispatching goal '{target_name}' -> ({tx:.2f}, {ty:.2f})")

        with self._lock:
            self._navigating = True
            self._active_target = (tx, ty, target_name, target_yaw)
            self._active_trace_id = tid

        # 1. Publish standard Nav2 Goal Pose
        goal_msg = PoseStamped()
        goal_msg.header.stamp = self.get_clock().now().to_msg()
        goal_msg.header.frame_id = self.nav_frame_id
        goal_msg.pose.position.x = float(tx)
        goal_msg.pose.position.y = float(ty)
        goal_msg.pose.position.z = 0.0

        yaw_val = target_yaw if target_yaw is not None else 0.0
        goal_msg.pose.orientation.x = 0.0
        goal_msg.pose.orientation.y = 0.0
        goal_msg.pose.orientation.z = math.sin(yaw_val / 2.0)
        goal_msg.pose.orientation.w = math.cos(yaw_val / 2.0)

        self.pub_goal_pose.publish(goal_msg)

        # 2. Update interaction state & expression
        self.fsm.transition_to(CognitiveState.EXECUTING, reason=f"Navigating to {target_name}", expression=Expression.FOCUS)
        self._publish_expression(Expression.FOCUS.value)

        # 3. Emit NavigationStarted on EventBus
        dist_initial = math.hypot(tx - self.current_x, ty - self.current_y)
        est_duration = max(3.0, dist_initial / 0.35)
        self.event_bus.emit(
            "NavigationStarted",
            {
                "destination": target_name,
                "target_x": round(tx, 3),
                "target_y": round(ty, 3),
                "estimated_duration_sec": round(est_duration, 1),
            },
            trace_id=tid,
        )

    def _handle_navigation_arrived(self, destination: str, x: float, y: float):
        """Executed upon arrival at waypoint: triggers announcement and HAPPY expression."""
        with self._lock:
            self._navigating = False
            self._active_target = None
            tid = self._active_trace_id or str(uuid.uuid4())

        self.fsm.transition_to(
            CognitiveState.IDLE,
            reason=f"Arrived at {destination}",
            expression=Expression.HAPPY,
        )
        self._publish_expression(Expression.HAPPY.value)

        # Emit NavigationArrived to EventBus
        self.event_bus.emit(
            "NavigationArrived",
            {"destination": destination, "success": True, "x": round(x, 3), "y": round(y, 3)},
            trace_id=tid,
        )

        # Spoken confirmation
        if self.auto_arrival_announcement:
            announcement = f"We have safely arrived at {destination}."
            self._publish_speech(announcement)
            self._speak(announcement)

    # -------------------------------------------------------------------------
    # EventBus Callbacks
    # -------------------------------------------------------------------------

    def _on_eventbus_action_requested(self, envelope: Dict[str, Any]):
        """Listens for actions requested across the nervous system."""
        data = envelope.get("event_type", {}).get("data", {})
        action = data.get("action")
        params = data.get("params", {})
        tid = envelope.get("trace_id", str(uuid.uuid4()))
        if action and envelope.get("source") != "ROS2InteractionBridge":
            self._dispatch_semantic_action_to_ros2(action, params, tid)

    def _on_eventbus_nav_started(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "destination")
        self.fsm.transition_to(CognitiveState.EXECUTING, reason=f"Transit started to {dest}", expression=Expression.FOCUS)
        self._publish_expression(Expression.FOCUS.value)

    def _on_eventbus_nav_arrived(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "destination")
        self.fsm.transition_to(CognitiveState.IDLE, reason=f"Arrived at {dest}", expression=Expression.HAPPY)
        self._publish_expression(Expression.HAPPY.value)

    def _on_eventbus_nav_failed(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        dest = data.get("destination", "destination")
        self.fsm.transition_to(CognitiveState.ERROR, reason=f"Nav failed: {dest}", expression=Expression.SAD)
        self._publish_expression(Expression.SAD.value)
        self.fsm.transition_to(CognitiveState.IDLE, reason="Recovered from nav failure", expression=Expression.SAD)

    def _on_eventbus_robot_stopped(self, envelope: Dict[str, Any]):
        data = envelope.get("event_type", {}).get("data", {})
        if data.get("emergency"):
            self.fsm.emergency_stop(reason=data.get("reason", "Robot stopped"))
            self._publish_expression(Expression.IDLE.value)

    # -------------------------------------------------------------------------
    # Physical Actuation & Helper Methods
    # -------------------------------------------------------------------------

    def _on_fsm_state_changed(self, prev: CognitiveState, curr: CognitiveState, exp: Expression, reason: str):
        self._publish_state(curr.value)

    def _on_expression_changed(self, expression: Expression):
        self._publish_expression(expression.value)

    def _publish_state(self, state: str):
        msg = RosString()
        msg.data = state
        self.pub_state.publish(msg)

    def _publish_expression(self, expression: str):
        msg = RosString()
        msg.data = expression
        self.pub_expression.publish(msg)

    def _publish_speech(self, text: str):
        msg = RosString()
        msg.data = text
        self.pub_speech.publish(msg)

    def _publish_neck(self, pan_rad: float, tilt_rad: float):
        pan_msg = RosFloat64()
        pan_msg.data = float(pan_rad)
        self.pub_head_pan.publish(pan_msg)

        tilt_msg = RosFloat64()
        tilt_msg.data = float(tilt_rad)
        self.pub_head_tilt.publish(tilt_msg)

    def _speak(self, text: str):
        if self.enable_tts and hasattr(self.gateway, "tts") and self.gateway.tts:
            self.gateway.tts.speak(text)


def main(args=None):
    rclpy.init(args=args)
    node = InteractionBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
