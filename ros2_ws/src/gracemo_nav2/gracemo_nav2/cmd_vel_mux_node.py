#!/usr/bin/env python3
"""
GRaCEmo ViRa — Command Velocity Multiplexer (Command MUX / Arbiter)
Package: gracemo_nav2
Executable: cmd_vel_mux_node.py

Arbitrates between autonomous navigation (/cmd_vel_nav) and teleoperation/exploration (/cmd_vel_teleop).
Outputs a unified velocity stream to /cmd_vel_mux.

Safety Rules:
1. Strict Priority: Teleoperation preempts autonomous navigation when actively publishing.
2. Timeout Enforcement: If teleoperation stops publishing for > teleop_timeout_sec,
   the arbiter deterministically falls back to autonomous navigation (if active) or halts.
3. Safe Zero Command: When no inputs are active or inputs time out, publishes a safe zero Twist
   to ensure the downstream velocity smoother and collision monitor bring the robot to a complete stop.
4. Diagnostics: Publishes current arbiter state, source ages, and active owner to /cmd_vel_mux/status.
"""

import json
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String as RosString


class CommandVelocityMuxNode(Node):
    """
    ROS 2 Command Velocity Multiplexer node.
    """

    def __init__(self, node_name: str = "cmd_vel_mux"):
        super().__init__(node_name)

        # Declare parameters
        self.declare_parameter("teleop_topic", "/cmd_vel_teleop")
        self.declare_parameter("nav_topic", "/cmd_vel_nav")
        self.declare_parameter("mux_topic", "/cmd_vel_mux")
        self.declare_parameter("status_topic", "/cmd_vel_mux/status")
        self.declare_parameter("teleop_timeout_sec", 0.5)
        self.declare_parameter("nav_timeout_sec", 0.5)
        self.declare_parameter("publish_rate_hz", 20.0)

        # Retrieve parameters
        self.teleop_topic = str(self.get_parameter("teleop_topic").value)
        self.nav_topic = str(self.get_parameter("nav_topic").value)
        self.mux_topic = str(self.get_parameter("mux_topic").value)
        self.status_topic = str(self.get_parameter("status_topic").value)
        self.teleop_timeout_sec = float(self.get_parameter("teleop_timeout_sec").value)
        self.nav_timeout_sec = float(self.get_parameter("nav_timeout_sec").value)
        self.publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        # Internal state tracking
        self._last_teleop_msg: Optional[Twist] = None
        self._last_teleop_time: float = 0.0

        self._last_nav_msg: Optional[Twist] = None
        self._last_nav_time: float = 0.0

        self._active_source: str = "NONE"
        self._zero_latched: bool = True
        self._last_published_twist: Twist = Twist()

        # Subscribers
        self.sub_teleop = self.create_subscription(
            Twist, self.teleop_topic, self._on_teleop_cmd, 10
        )
        self.sub_nav = self.create_subscription(
            Twist, self.nav_topic, self._on_nav_cmd, 10
        )

        # Publishers
        self.pub_mux = self.create_publisher(Twist, self.mux_topic, 10)
        self.pub_status = self.create_publisher(RosString, self.status_topic, 10)

        # Timers
        loop_interval = 1.0 / max(1.0, self.publish_rate_hz)
        self.timer_loop = self.create_timer(loop_interval, self._on_arbitration_cycle)
        self.timer_status = self.create_timer(0.2, self._on_status_cycle)  # 5 Hz status

        self.get_logger().info(
            f"🔀 Command Velocity MUX online. Teleop: '{self.teleop_topic}' (timeout={self.teleop_timeout_sec}s) | "
            f"Nav: '{self.nav_topic}' (timeout={self.nav_timeout_sec}s) -> Output: '{self.mux_topic}'"
        )

    def _on_teleop_cmd(self, msg: Twist):
        """Callback for teleoperation commands (High Priority)."""
        self._last_teleop_msg = msg
        self._last_teleop_time = self._get_time_sec()

    def _on_nav_cmd(self, msg: Twist):
        """Callback for autonomous Nav2 navigation commands (Low Priority)."""
        self._last_nav_msg = msg
        self._last_nav_time = self._get_time_sec()

    def _get_time_sec(self) -> float:
        """Returns current clock time in float seconds."""
        return self.get_clock().now().nanoseconds / 1e9

    def evaluate_arbitration(self, now: float) -> tuple[str, Twist, bool]:
        """
        Pure arbitration evaluation logic.
        Returns: (active_source, twist_to_publish, should_publish)
        """
        teleop_active = (
            self._last_teleop_msg is not None
            and (now - self._last_teleop_time) <= self.teleop_timeout_sec
        )
        nav_active = (
            self._last_nav_msg is not None
            and (now - self._last_nav_time) <= self.nav_timeout_sec
        )

        if teleop_active:
            return "TELEOP", self._last_teleop_msg, True
        elif nav_active:
            return "NAV", self._last_nav_msg, True
        else:
            return "NONE", Twist(), not self._zero_latched

    def _on_arbitration_cycle(self):
        """Periodic arbitration cycle executing at publish_rate_hz."""
        now = self._get_time_sec()
        source, cmd, should_publish = self.evaluate_arbitration(now)
        self._active_source = source

        if should_publish:
            self.pub_mux.publish(cmd)
            self._last_published_twist = cmd
            if source == "NONE":
                self._zero_latched = True
            else:
                self._zero_latched = False

    def _on_status_cycle(self):
        """Publishes diagnostic telemetry for the command multiplexer."""
        now = self._get_time_sec()
        teleop_age = round(now - self._last_teleop_time, 3) if self._last_teleop_time > 0 else None
        nav_age = round(now - self._last_nav_time, 3) if self._last_nav_time > 0 else None

        payload = {
            "active_source": self._active_source,
            "teleop_active": bool(teleop_age is not None and teleop_age <= self.teleop_timeout_sec),
            "nav_active": bool(nav_age is not None and nav_age <= self.nav_timeout_sec),
            "teleop_age_sec": teleop_age,
            "nav_age_sec": nav_age,
            "zero_command_held": self._zero_latched,
            "current_linear_x": round(self._last_published_twist.linear.x, 3),
            "current_angular_z": round(self._last_published_twist.angular.z, 3),
        }
        status_msg = RosString()
        status_msg.data = json.dumps(payload)
        self.pub_status.publish(status_msg)


def main(args=None):
    rclpy.init(args=args)
    node = CommandVelocityMuxNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
