#!/usr/bin/env python3
"""
GRaCEmo ViRa — Real-Time Visual Perception, Navigation & Mission Control
Dual Terminal + Video HUD Control | YOLO Vision | Room Cataloging | Voice Output
"""

import os
import sys
import time
import math
import select
import threading
from pathlib import Path
import numpy as np
import cv2

# Silence driver warnings
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["ORT_LOGGING_LEVEL"] = "3"

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, LaserScan
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from ultralytics import YOLO
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(highlight=False)

ROOT = Path(__file__).resolve().parent.parent
for adapter_sub in ["sdk", "vision", "voice", "brain"]:
    p = str(ROOT / "adapters" / adapter_sub)
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from gracemo_voice.audio_engine import VoiceAdapter
except Exception:
    VoiceAdapter = None

# 4-Room Apartment Waypoints (Doorways at X=±5.0, Hallway Y=±1.0)
ROOM_WAYPOINTS = {
    "bedroom":  [(-5.0, 0.0), (-5.0, 1.8), (-5.0, 4.0)],
    "study":    [(5.0, 0.0),  (5.0, 1.8),  (5.0, 4.0)],
    "kitchen":  [(-5.0, 0.0), (-5.0, -1.8), (-5.0, -4.0)],
    "living":   [(5.0, 0.0),  (5.0, -1.8),  (5.0, -4.0)],
    "hallway":  [(0.0, 0.0)]
}

ROOM_SIGNATURES = {
    "Master Bedroom": {"bed", "wardrobe", "pillow"},
    "Kitchen & Dining": {"refrigerator", "dining_table", "table", "chair", "bottle", "cup"},
    "Living Room": {"sofa", "couch", "tv", "bowl"},
    "Home Study": {"bookshelf", "desk", "laptop", "book", "cardboard_box", "coke_can"}
}


class MissionVisualizerNode(Node):
    def __init__(self):
        super().__init__("mission_visualizer_node")

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.image_sub = self.create_subscription(Image, "/camera/image_raw", self._on_image, 10)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.scan_sub = self.create_subscription(LaserScan, "/scan", self._on_scan, 10)

        # Load YOLO model
        model_path = str(ROOT / "yolo11n.pt") if (ROOT / "yolo11n.pt").exists() else "yolo11n.pt"
        self.yolo = YOLO(model_path)

        self.latest_frame = None
        self.annotated_frame = None
        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_yaw = 0.0
        self.has_odom = False
        self.min_obstacle_dist = 10.0

        # State
        self.target_room = "hallway"
        self.active_waypoints = []
        self.wp_idx = 0
        self.navigating = False
        self.surveying = False
        self.survey_start_yaw = 0.0
        self.survey_start_time = 0.0
        self.current_room_label = "Central Hallway"
        self.detected_objects = set()
        self.room_inventory = {
            "Master Bedroom": set(),
            "Kitchen & Dining": set(),
            "Living Room": set(),
            "Home Study": set()
        }

        # TTS voice
        self.voice = None
        if VoiceAdapter:
            try:
                self.voice = VoiceAdapter()
            except Exception:
                pass

        # Timer for control loop (20Hz)
        self.timer = self.create_timer(0.05, self._control_loop)
        self.get_logger().info("🚀 Mission Visualizer & Perception Node Online.")

    def speak(self, text: str):
        console.print(f"\n[bold cyan]🗣️ ViRa:[/bold cyan] [italic yellow]\"{text}\"[/italic yellow]")
        if self.voice:
            threading.Thread(target=self.voice.speak, args=(text,), daemon=True).start()

    def _on_image(self, msg: Image):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, -1))
            if msg.encoding in ("rgb8", "RGB8"):
                frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            else:
                frame = arr.copy()
            self.latest_frame = frame

            # Run YOLO
            results = self.yolo(frame, verbose=False, conf=0.30)
            annotated = results[0].plot()

            # Extract detected classes
            current_frame_classes = set()
            for box in results[0].boxes:
                cls_id = int(box.cls[0].item())
                cls_name = self.yolo.names[cls_id]
                current_frame_classes.add(cls_name)
                self.detected_objects.add(cls_name)

                # Assign to current room inventory
                if self.current_room_label in self.room_inventory:
                    self.room_inventory[self.current_room_label].add(cls_name)

            # Draw HUD Telemetry Overlay on Video
            h, w, _ = annotated.shape
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (w, 65), (20, 20, 25), -1)
            cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 25), -1)
            cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

            # Top HUD Text
            room_color = (0, 220, 100) if self.current_room_label != "Central Hallway" else (255, 180, 0)
            cv2.putText(annotated, f"ROOM: {self.current_room_label.upper()}", (15, 26), cv2.FONT_HERSHEY_DUPLEX, 0.65, room_color, 2)
            cv2.putText(annotated, f"POS: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m) | HEADING: {math.degrees(self.cur_yaw):.0f}deg", (15, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

            # Status Badge Top Right
            status_text = "SURVEYING" if self.surveying else ("NAVIGATING" if self.navigating else "IDLE")
            badge_color = (0, 140, 255) if self.navigating else ((180, 0, 255) if self.surveying else (100, 200, 100))
            cv2.putText(annotated, status_text, (w - 140, 36), cv2.FONT_HERSHEY_DUPLEX, 0.6, badge_color, 2)

            # Bottom HUD Bar: Active Detections
            det_str = " | ".join(sorted(current_frame_classes)) if current_frame_classes else "Scanning apartment environment..."
            cv2.putText(annotated, f"DETECTED: {det_str}", (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

            self.annotated_frame = annotated

        except Exception:
            pass

    def _on_odom(self, msg: Odometry):
        self.cur_x = msg.pose.pose.position.x
        self.cur_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.cur_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.has_odom = True

        # Update current room label based on spatial position
        if self.cur_y > 1.2:
            self.current_room_label = "Master Bedroom" if self.cur_x < 0 else "Home Study"
        elif self.cur_y < -1.2:
            self.current_room_label = "Kitchen & Dining" if self.cur_x < 0 else "Living Room"
        else:
            self.current_room_label = "Central Hallway"

    def _on_scan(self, msg: LaserScan):
        valid = [r for r in msg.ranges if not math.isnan(r) and r > 0.1]
        self.min_obstacle_dist = min(valid) if valid else 10.0

    def navigate_to_room(self, room_name: str):
        key = room_name.lower().strip()
        for k in ROOM_WAYPOINTS:
            if k in key:
                self.target_room = k
                self.active_waypoints = list(ROOM_WAYPOINTS[k])
                self.wp_idx = 0
                self.navigating = True
                self.surveying = False
                console.print(f"[bold green]🚀 [NAVIGATOR] Heading to {k.upper()} via doorway waypoint...[/bold green]")
                self.speak(f"Navigating to {k.title()}.")
                return True
        console.print(f"[bold red]❌ Unknown target room: {room_name}[/bold red]")
        return False

    def _control_loop(self):
        if not self.has_odom or not self.navigating:
            return

        # 1. Check if surveying room
        if self.surveying:
            twist = Twist()
            twist.angular.z = 0.6  # Spin 360 deg
            self.cmd_pub.publish(twist)

            # Check if full rotation completed (or 8s elapsed)
            elapsed = time.time() - self.survey_start_time
            if elapsed > 7.0:
                self.surveying = False
                self.navigating = False
                twist.angular.z = 0.0
                self.cmd_pub.publish(twist)
                found = ", ".join(self.room_inventory.get(self.current_room_label, ["objects"])) or "various furniture"
                console.print(f"[bold magenta]✓ [SURVEY COMPLETE] {self.current_room_label}: {found}[/bold magenta]")
                self.speak(f"Inspection of {self.current_room_label} complete. I found: {found}.")
            return

        # 2. Reached all waypoints?
        if self.wp_idx >= len(self.active_waypoints):
            self.surveying = True
            self.survey_start_yaw = self.cur_yaw
            self.survey_start_time = time.time()
            console.print(f"[bold magenta]📍 [ARRIVED] Reached {self.target_room.upper()} center. Initiating 360 survey...[/bold magenta]")
            self.speak(f"Arrived at {self.target_room.title()}. Starting visual survey.")
            return

        # 3. Drive towards current waypoint
        tx, ty = self.active_waypoints[self.wp_idx]
        dx = tx - self.cur_x
        dy = ty - self.cur_y
        dist = math.hypot(dx, dy)

        if dist < 0.40:
            self.wp_idx += 1
            return

        target_yaw = math.atan2(dy, dx)
        angle_err = target_yaw - self.cur_yaw
        while angle_err > math.pi:
            angle_err -= 2 * math.pi
        while angle_err < -math.pi:
            angle_err += 2 * math.pi

        twist = Twist()
        if abs(angle_err) > 0.4:
            twist.angular.z = max(-1.2, min(1.2, 2.5 * angle_err))
            twist.linear.x = 0.08
        else:
            twist.linear.x = min(0.50, 0.7 * dist)
            twist.angular.z = 1.4 * angle_err

        self.cmd_pub.publish(twist)


def print_help():
    table = Table(title="🎮 GRaCEmo ViRa Mission Controls", border_style="cyan", show_header=True)
    table.add_column("Key / Command", style="bold yellow")
    table.add_column("Action", style="green")
    table.add_row("1 or 'bedroom'", "Navigate to Master Bedroom")
    table.add_row("2 or 'study'", "Navigate to Home Study")
    table.add_row("3 or 'living'", "Navigate to Living Room")
    table.add_row("4 or 'kitchen'", "Navigate to Kitchen & Dining")
    table.add_row("h or 'hallway'", "Return to Central Hallway")
    table.add_row("a or 'auto'", "Start full autonomous 4-room cataloging tour")
    table.add_row("q or 'quit'", "Stop robot and exit")
    console.print(table)


def main():
    rclpy.init()
    node = MissionVisualizerNode()

    # Spin ROS 2 in background thread
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    console.print(Panel.fit(
        "[bold cyan]GRaCEmo ViRa — Real-Time Mission Visualizer & Control Online[/bold cyan]\n"
        "[dim]Type a command below or press keys in the OpenCV video window.[/dim]",
        border_style="cyan"
    ))
    print_help()

    # Create dummy black frame if camera not yet arrived
    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder, "Connecting to /camera/image_raw...", (60, 240), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 200, 255), 1)

    gui_available = True
    try:
        cv2.namedWindow("GRaCEmo ViRa — Live Vision HUD", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("GRaCEmo ViRa — Live Vision HUD", 800, 600)
    except Exception:
        gui_available = False
        console.print("[yellow]Notice: GUI display not available, running in full Terminal Control mode.[/yellow]")

    patrol_order = ["bedroom", "study", "living", "kitchen", "hallway"]
    patrol_idx = 0
    auto_tour = False

    running = True

    # Dedicated thread for Terminal Input
    def terminal_input_loop():
        nonlocal auto_tour, patrol_idx, running
        while running and rclpy.ok():
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if not cmd:
                    continue

                if cmd in ("q", "quit", "exit"):
                    running = False
                    break
                elif cmd in ("1", "bedroom"):
                    auto_tour = False
                    node.navigate_to_room("bedroom")
                elif cmd in ("2", "study"):
                    auto_tour = False
                    node.navigate_to_room("study")
                elif cmd in ("3", "living", "living room"):
                    auto_tour = False
                    node.navigate_to_room("living")
                elif cmd in ("4", "kitchen"):
                    auto_tour = False
                    node.navigate_to_room("kitchen")
                elif cmd in ("h", "hallway"):
                    auto_tour = False
                    node.navigate_to_room("hallway")
                elif cmd in ("a", "auto", "tour"):
                    auto_tour = True
                    patrol_idx = 0
                    node.navigate_to_room(patrol_order[patrol_idx])
                    node.speak("Starting full autonomous apartment tour.")
                elif cmd in ("help", "?"):
                    print_help()
                else:
                    # Generic room match
                    if not node.navigate_to_room(cmd):
                        console.print(f"[dim]Type 'help' for command list.[/dim]")
            except Exception:
                break

    input_thread = threading.Thread(target=terminal_input_loop, daemon=True)
    input_thread.start()

    try:
        while running and rclpy.ok():
            # 1. Update Video GUI if available
            if gui_available:
                frame_to_show = node.annotated_frame if node.annotated_frame is not None else placeholder
                try:
                    cv2.imshow("GRaCEmo ViRa — Live Vision HUD", frame_to_show)
                    key = cv2.waitKey(30) & 0xFF
                    if key == ord('q') or key == 27:
                        running = False
                        break
                    elif key == ord('1'):
                        auto_tour = False
                        node.navigate_to_room("bedroom")
                    elif key == ord('2'):
                        auto_tour = False
                        node.navigate_to_room("study")
                    elif key == ord('3'):
                        auto_tour = False
                        node.navigate_to_room("living")
                    elif key == ord('4'):
                        auto_tour = False
                        node.navigate_to_room("kitchen")
                    elif key == ord('h') or key == ord('H'):
                        auto_tour = False
                        node.navigate_to_room("hallway")
                    elif key == ord('a') or key == ord('A'):
                        auto_tour = True
                        patrol_idx = 0
                        node.navigate_to_room(patrol_order[patrol_idx])
                        node.speak("Starting full autonomous apartment tour.")
                except Exception:
                    gui_available = False
            else:
                time.sleep(0.05)

            # 2. Auto tour progression
            if auto_tour and not node.navigating and not node.surveying:
                patrol_idx += 1
                if patrol_idx < len(patrol_order):
                    time.sleep(1.0)
                    node.navigate_to_room(patrol_order[patrol_idx])
                else:
                    auto_tour = False
                    node.speak("Full apartment tour complete. All 4 rooms cataloged.")

    finally:
        if gui_available:
            cv2.destroyAllWindows()
        node.cmd_pub.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
