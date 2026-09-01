#!/usr/bin/env python3
"""
GRaCEmo ViRa — Real-Time Visual Perception, Navigation & Mission Control
Direct Gazebo Harmonic Transport (gz.transport13) + YOLO Detection + Dual Control + TTS
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

import gz.transport13 as gz_transport
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan

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


class MissionVisualizer:
    def __init__(self):
        self.node = gz_transport.Node()

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

        # Subscriptions
        self.node.subscribe(GzImage, "/camera/image_raw", self._on_image)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)

        # Publisher
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)

        # TTS voice
        self.voice = None
        if VoiceAdapter:
            try:
                self.voice = VoiceAdapter()
            except Exception:
                pass

        # Background control loop thread (20Hz)
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()

        console.print("[bold green]✓ Connected to Gazebo Harmonic via native gz.transport13[/bold green]")

    def speak(self, text: str):
        console.print(f"\n[bold cyan]🗣️ ViRa:[/bold cyan] [italic yellow]\"{text}\"[/italic yellow]")
        if self.voice:
            threading.Thread(target=self.voice.speak, args=(text,), daemon=True).start()

    def _on_image(self, msg: GzImage):
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            self.latest_frame = frame

            # Run YOLO
            results = self.yolo(frame, verbose=False, conf=0.28)
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

    def _on_odom(self, msg: GzOdometry):
        pos = msg.pose.position
        self.cur_x = pos.x
        self.cur_y = pos.y
        q = msg.pose.orientation
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

    def _on_scan(self, msg: GzLaserScan):
        valid = [r for r in msg.ranges if not math.isnan(r) and r > 0.1]
        self.min_obstacle_dist = min(valid) if valid else 10.0

    def publish_cmd(self, vx: float, wz: float):
        twist = GzTwist()
        twist.linear.x = float(vx)
        twist.angular.z = float(wz)
        self.cmd_pub.publish(twist)

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
        while self.running:
            time.sleep(0.05)
            if not self.has_odom or not self.navigating:
                continue

            # 1. 360-Degree Visual Survey Mode
            if self.surveying:
                self.publish_cmd(0.0, 0.40)  # Gentle 360 spin
                elapsed = time.time() - self.survey_start_time
                if elapsed > 8.0:
                    self.surveying = False
                    self.navigating = False
                    self.publish_cmd(0.0, 0.0)
                    found = ", ".join(self.room_inventory.get(self.current_room_label, ["objects"])) or "various furniture"
                    console.print(f"[bold magenta]✓ [SURVEY COMPLETE] {self.current_room_label}: {found}[/bold magenta]")
                    self.speak(f"Inspection of {self.current_room_label} complete. I found: {found}.")
                continue

            # 2. Check Waypoint Reached
            if self.wp_idx >= len(self.active_waypoints):
                self.surveying = True
                self.survey_start_time = time.time()
                self.publish_cmd(0.0, 0.0)
                console.print(f"[bold magenta]📍 [ARRIVED] Reached {self.target_room.upper()} center. Initiating 360 survey...[/bold magenta]")
                self.speak(f"Arrived at {self.target_room.title()}. Starting visual survey.")
                continue

            # 3. Target Waypoint Vector
            tx, ty = self.active_waypoints[self.wp_idx]
            dx = tx - self.cur_x
            dy = ty - self.cur_y
            dist = math.hypot(dx, dy)

            # Waypoint reached tolerance
            if dist < 0.45:
                self.wp_idx += 1
                continue

            target_yaw = math.atan2(dy, dx)
            angle_err = target_yaw - self.cur_yaw
            while angle_err > math.pi:
                angle_err -= 2 * math.pi
            while angle_err < -math.pi:
                angle_err += 2 * math.pi

            # Two-Phase Stable Motion:
            # Phase 1: Rotate on spot to align with target (heading error > 0.3 rad)
            if abs(angle_err) > 0.30:
                vx = 0.0
                wz = np.clip(1.2 * angle_err, -0.65, 0.65)
            else:
                # Phase 2: Drive straight forward with gentle steering correction
                vx = min(0.38, max(0.12, 0.5 * dist))
                wz = 0.8 * angle_err

            self.publish_cmd(vx, wz)


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
    vis = MissionVisualizer()

    console.print(Panel.fit(
        "[bold cyan]GRaCEmo ViRa — Real-Time Mission Visualizer & Control Online[/bold cyan]\n"
        "[dim]Type a command below or press keys in the OpenCV video window.[/dim]",
        border_style="cyan"
    ))
    print_help()

    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder, "Connecting to Gazebo Harmonic Camera...", (40, 240), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 200, 255), 1)

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

    # Dedicated thread for Terminal Input
    def terminal_input_loop():
        nonlocal auto_tour, patrol_idx
        while vis.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if not cmd:
                    continue

                if cmd in ("q", "quit", "exit"):
                    vis.running = False
                    break
                elif cmd in ("1", "bedroom"):
                    auto_tour = False
                    vis.navigate_to_room("bedroom")
                elif cmd in ("2", "study"):
                    auto_tour = False
                    vis.navigate_to_room("study")
                elif cmd in ("3", "living", "living room"):
                    auto_tour = False
                    vis.navigate_to_room("living")
                elif cmd in ("4", "kitchen"):
                    auto_tour = False
                    vis.navigate_to_room("kitchen")
                elif cmd in ("h", "hallway"):
                    auto_tour = False
                    vis.navigate_to_room("hallway")
                elif cmd in ("a", "auto", "tour"):
                    auto_tour = True
                    patrol_idx = 0
                    vis.navigate_to_room(patrol_order[patrol_idx])
                    vis.speak("Starting full autonomous apartment tour.")
                elif cmd in ("w", "forward"):
                    vis.navigating = False
                    vis.surveying = False
                    vis.publish_cmd(0.35, 0.0)
                elif cmd in ("s", "backward", "back"):
                    vis.navigating = False
                    vis.surveying = False
                    vis.publish_cmd(-0.30, 0.0)
                elif cmd in ("left",):
                    vis.navigating = False
                    vis.surveying = False
                    vis.publish_cmd(0.0, 0.60)
                elif cmd in ("right",):
                    vis.navigating = False
                    vis.surveying = False
                    vis.publish_cmd(0.0, -0.60)
                elif cmd in (" ", "stop", "x"):
                    vis.navigating = False
                    vis.surveying = False
                    vis.publish_cmd(0.0, 0.0)
                    console.print("[bold red]🛑 Emergency Stop applied.[/bold red]")
                elif cmd in ("help", "?"):
                    print_help()
                else:
                    if not vis.navigate_to_room(cmd):
                        console.print(f"[dim]Type 'help' for command list.[/dim]")
            except Exception:
                break

    input_thread = threading.Thread(target=terminal_input_loop, daemon=True)
    input_thread.start()

    try:
        while vis.running:
            # 1. Update Video GUI if available
            if gui_available:
                frame_to_show = vis.annotated_frame if vis.annotated_frame is not None else placeholder
                try:
                    cv2.imshow("GRaCEmo ViRa — Live Vision HUD", frame_to_show)
                    key = cv2.waitKey(30) & 0xFF
                    if key == ord('q') or key == 27:
                        vis.running = False
                        break
                    elif key == ord('1'):
                        auto_tour = False
                        vis.navigate_to_room("bedroom")
                    elif key == ord('2'):
                        auto_tour = False
                        vis.navigate_to_room("study")
                    elif key == ord('3'):
                        auto_tour = False
                        vis.navigate_to_room("living")
                    elif key == ord('4'):
                        auto_tour = False
                        vis.navigate_to_room("kitchen")
                    elif key == ord('h') or key == ord('H'):
                        auto_tour = False
                        vis.navigate_to_room("hallway")
                    elif key == ord('w') or key == ord('W'):
                        vis.navigating = False
                        vis.surveying = False
                        vis.publish_cmd(0.35, 0.0)
                    elif key == ord('s') or key == ord('S'):
                        vis.navigating = False
                        vis.surveying = False
                        vis.publish_cmd(-0.30, 0.0)
                    elif key == ord('d') or key == ord('D'):
                        vis.navigating = False
                        vis.surveying = False
                        vis.publish_cmd(0.0, -0.60)
                    elif key == ord(' '):
                        vis.navigating = False
                        vis.surveying = False
                        vis.publish_cmd(0.0, 0.0)
                    elif key == ord('a') or key == ord('A'):
                        auto_tour = True
                        patrol_idx = 0
                        vis.navigate_to_room(patrol_order[patrol_idx])
                        vis.speak("Starting full autonomous apartment tour.")
                except Exception:
                    gui_available = False
            else:
                time.sleep(0.05)

            # 2. Auto tour progression
            if auto_tour and not vis.navigating and not vis.surveying:
                patrol_idx += 1
                if patrol_idx < len(patrol_order):
                    time.sleep(1.0)
                    vis.navigate_to_room(patrol_order[patrol_idx])
                else:
                    auto_tour = False
                    vis.speak("Full apartment tour complete. All 4 rooms cataloged.")

    finally:
        vis.running = False
        vis.publish_cmd(0.0, 0.0)
        if gui_available:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
