#!/usr/bin/env python3
"""
GRaCEmo ViRa — Mission Control & Live Autonomous Navigation Dashboard
Displays real-time robot location, current room, sensor telemetry, and allows 1-key mission dispatch.
"""

import os
import sys
import time
import math
import threading
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry, OccupancyGrid
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist, PoseStamped
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text


ROOMS = {
    "BEDROOM": {"name": "Master Bedroom", "bounds": (-8.0, -0.5, 1.3, 6.0), "goal": (-4.0, 3.8)},
    "KITCHEN": {"name": "Kitchen & Dining", "bounds": (-0.5, 8.0, 1.3, 6.0), "goal": (3.8, 3.6)},
    "LIVING":  {"name": "Living Room",     "bounds": (-0.5, 8.0, -6.0, -1.3), "goal": (3.8, -3.5)},
    "STUDY":   {"name": "Home Study",      "bounds": (-8.0, -0.5, -6.0, -1.3), "goal": (-4.0, -3.5)},
    "HALLWAY": {"name": "Central Hallway", "bounds": (-8.0, 8.0, -1.3, 1.3), "goal": (0.0, 0.0)}
}


class MissionControlNode(Node):
    def __init__(self):
        super().__init__("gracemo_mission_control")

        self.odom_sub = self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

        self.x = 0.0
        self.y = 0.0
        self.yaw_deg = 0.0
        self.speed = 0.0
        self.min_obstacle_dist = 12.0
        self.current_room = "Central Hallway"
        self.active_mission = "Standby (Waiting for Command)"
        self.visited_rooms = set(["Central Hallway"])
        self.patrol_active = False

    def _on_odom(self, msg: Odometry):
        pos = msg.pose.pose.position
        self.x = pos.x
        self.y = pos.y
        self.speed = msg.twist.twist.linear.x

        # Calculate yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.yaw_deg = math.degrees(math.atan2(siny_cosp, cosy_cosp))

        # Detect Current Room
        self.current_room = "Central Hallway"
        for key, r in ROOMS.items():
            bx_min, bx_max, by_min, by_max = r["bounds"]
            if bx_min <= self.x <= bx_max and by_min <= self.y <= by_max:
                self.current_room = r["name"]
                self.visited_rooms.add(r["name"])
                break

    def _on_scan(self, msg: LaserScan):
        valid = [r for r in msg.ranges if 0.15 < r < 12.0 and not math.isnan(r) and not math.isinf(r)]
        self.min_obstacle_dist = min(valid) if valid else 12.0

    def dispatch_mission(self, room_key: str):
        if room_key not in ROOMS:
            return

        room = ROOMS[room_key]
        gx, gy = room["goal"]
        self.active_mission = f"Navigating to {room['name']} ({gx:.1f}, {gy:.1f})"

        # Send Nav2 Goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(gx)
        goal_msg.pose.pose.position.y = float(gy)
        goal_msg.pose.pose.orientation.w = 1.0

        if self.nav_client.wait_for_server(timeout_sec=0.5):
            self.nav_client.send_goal_async(goal_msg)
        else:
            # Direct heading drive if Nav2 action server is not active
            self._direct_drive_towards(gx, gy)

    def _direct_drive_towards(self, gx, gy):
        def drive_thread():
            rate = 0.05
            while rclpy.ok():
                dx = gx - self.x
                dy = gy - self.y
                dist = math.hypot(dx, dy)
                if dist < 0.4:
                    self.cmd_pub.publish(Twist())
                    self.active_mission = f"Arrived at Destination! ({self.current_room})"
                    break

                target_angle = math.atan2(dy, dx)
                current_angle = math.radians(self.yaw_deg)
                angle_diff = (target_angle - current_angle + math.pi) % (2 * math.pi) - math.pi

                twist = Twist()
                if abs(angle_diff) > 0.35:
                    twist.angular.z = 1.0 if angle_diff > 0 else -1.0
                else:
                    twist.linear.x = 0.50
                    twist.angular.z = 0.8 * angle_diff

                self.cmd_pub.publish(twist)
                time.sleep(rate)

        threading.Thread(target=drive_thread, daemon=True).start()


def render_dashboard(node: MissionControlNode) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", size=15),
        Layout(name="footer", size=5)
    )

    # 1. Header
    header_text = Text.assemble(
        ("GRaCEmo ViRa", "bold cyan"),
        (" — Autonomous Navigation & Mission Control v0.0.1", "white")
    )
    layout["header"].update(Panel(header_text, style="cyan"))

    # 2. Body Grid
    body_layout = Layout()
    body_layout.split_row(
        Layout(name="telemetry", ratio=1),
        Layout(name="map_view", ratio=1)
    )

    # Telemetry Table
    t_table = Table(show_header=False, box=None, padding=(0, 1))
    t_table.add_column("Key", style="bold yellow")
    t_table.add_column("Value", style="white")

    t_table.add_row("📍 Current Room:", f"[bold green]{node.current_room}[/bold green]")
    t_table.add_row("🎯 Active Mission:", f"[bold cyan]{node.active_mission}[/bold cyan]")
    t_table.add_row("📐 Coordinates:", f"X: {node.x:+.2f}m  |  Y: {node.y:+.2f}m")
    t_table.add_row("🧭 Heading & Speed:", f"{node.yaw_deg:+.1f}°  |  {abs(node.speed):.2f} m/s")
    t_table.add_row("🛡️ Closest Obstacle:", f"{node.min_obstacle_dist:.2f} meters")

    rooms_status = ""
    for rname in ["Master Bedroom", "Kitchen & Dining", "Living Room", "Home Study"]:
        check = "✓" if rname in node.visited_rooms else " "
        rooms_status += f"[{check}] {rname}  "
    t_table.add_row("🏠 Explored Rooms:", rooms_status)

    body_layout["telemetry"].update(Panel(t_table, title="[bold]Robot State & Telemetry[/bold]", border_style="blue"))

    # Mini Floorplan ASCII Map
    # Map coordinates [-8..8] to 16 cols, [-6..6] to 8 rows
    ascii_map = [
        "┌───────────────┬───────────────┐",
        "│ BEDROOM       │ KITCHEN       │",
        "│               │               │",
        "├─────── ───────┴─────── ───────┤",
        "│       CENTRAL HALLWAY         │",
        "├─────── ───────┬─────── ───────┤",
        "│ STUDY         │ LIVING ROOM   │",
        "│               │               │",
        "└───────────────┴───────────────┘"
    ]
    # Mark robot location [R]
    r_row = 4
    if node.y > 1.3:
        r_row = 2
    elif node.y < -1.3:
        r_row = 7

    r_col = 16
    if node.x < -0.5:
        r_col = 8
    elif node.x > -0.5:
        r_col = 24

    row_chars = list(ascii_map[r_row])
    if 0 <= r_col < len(row_chars):
        row_chars[r_col] = "🤖"
    ascii_map[r_row] = "".join(row_chars)

    map_text = "\n".join(ascii_map)
    body_layout["map_view"].update(Panel(Text(map_text, style="bold green"), title="[bold]4-Room Apartment Floorplan[/bold]", border_style="green"))

    layout["body"].update(body_layout)

    # 3. Footer / Controls
    controls_text = (
        "🚀 [bold yellow]1-Key Mission Dispatch:[/bold yellow] "
        "[1] Kitchen  |  [2] Bedroom  |  [3] Living Room  |  [4] Study  |  [5] Hallway  |  [Ctrl+C] Exit"
    )
    layout["footer"].update(Panel(controls_text, border_style="yellow"))

    return layout


def input_listener(node: MissionControlNode):
    import tty
    import termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while rclpy.ok():
            ch = sys.stdin.read(1)
            if ch == '1':
                node.dispatch_mission("KITCHEN")
            elif ch == '2':
                node.dispatch_mission("BEDROOM")
            elif ch == '3':
                node.dispatch_mission("LIVING")
            elif ch == '4':
                node.dispatch_mission("STUDY")
            elif ch == '5':
                node.dispatch_mission("HALLWAY")
            elif ch == '\x03':  # Ctrl+C
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    rclpy.init()
    node = MissionControlNode()

    # Spin ROS 2 in background thread
    threading.Thread(target=lambda: rclpy.spin(node), daemon=True).start()
    threading.Thread(target=lambda: input_listener(node), daemon=True).start()

    console = Console()
    with Live(render_dashboard(node), refresh_per_second=8, console=console, screen=False) as live:
        try:
            while rclpy.ok():
                live.update(render_dashboard(node))
                time.sleep(0.12)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
