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
        # Scan range is -pi to +pi (360 samples). Center index (180) is straight ahead (0 deg).
        # Only inspect front cone (-25 deg to +25 deg: indices 155 to 205)
        n = len(msg.ranges)
        if n >= 360:
            mid = n // 2
            front_span = int(n * (25.0 / 360.0))
            front_ranges = [msg.ranges[i] for i in range(mid - front_span, mid + front_span + 1)]
        else:
            front_ranges = list(msg.ranges)

        valid = [r for r in front_ranges if not math.isnan(r) and r > 0.1]
        self.min_obstacle_dist = min(valid) if valid else 10.0

    def publish_cmd(self, vx: float, wz: float):
        twist = GzTwist()
        twist.linear.x = float(vx)
        twist.angular.z = float(wz)
        self.cmd_pub.publish(twist)

    def plan_path_to_room(self, target_room: str):
        """
        Generate a collision-free waypoint trajectory through doorways and the central hallway.
        Uses aligned approach and exit waypoints so the robot enters/exits doorways perfectly straight.
        """
        waypoints = []
        cur_x, cur_y = self.cur_x, self.cur_y

        # Step 1: If currently inside a room, first exit through doorway into central hallway
        if cur_y > 1.2:
            # Inside Bedroom (left) or Study (right)
            door_x = -5.0 if cur_x < 0 else 5.0
            waypoints.extend([(door_x, 2.0), (door_x, 0.8), (door_x, 0.0)])
        elif cur_y < -1.2:
            # Inside Kitchen (left) or Living Room (right)
            door_x = -5.0 if cur_x < 0 else 5.0
            waypoints.extend([(door_x, -2.0), (door_x, -0.8), (door_x, 0.0)])

        # Step 2: Route through central hallway to target room doorway and room center
        if target_room == "bedroom":
            waypoints.extend([(-5.0, 0.0), (-5.0, 0.6), (-5.0, 1.8), (-5.0, 3.8)])
        elif target_room == "study":
            waypoints.extend([(5.0, 0.0), (5.0, 0.6), (5.0, 1.8), (5.0, 3.8)])
        elif target_room == "kitchen":
            waypoints.extend([(-5.0, 0.0), (-5.0, -0.6), (-5.0, -1.8), (-4.5, -3.8)])
        elif target_room == "living":
            waypoints.extend([(5.0, 0.0), (5.0, -0.6), (5.0, -1.8), (4.5, -3.8)])
        elif target_room == "hallway":
            waypoints.append((0.0, 0.0))

        # Deduplicate consecutive waypoints within 0.35m
        clean_wps = []
        for wp in waypoints:
            if not clean_wps:
                clean_wps.append(wp)
            elif math.hypot(wp[0] - clean_wps[-1][0], wp[1] - clean_wps[-1][1]) > 0.35:
                clean_wps.append(wp)

        return clean_wps

    def navigate_to_room(self, room_name: str):
        key = room_name.lower().strip()
        matched = None
        for k in ["bedroom", "study", "kitchen", "living", "hallway"]:
            if k in key:
                matched = k
                break

        if matched:
            self.target_room = matched
            self.active_waypoints = self.plan_path_to_room(matched)
            self.wp_idx = 0
            self.navigating = True
            self.surveying = False
            console.print(f"[bold green]🚀 [NAVIGATOR] Generated {len(self.active_waypoints)}-point doorway route to {matched.upper()}...[/bold green]")
            for i, wp in enumerate(self.active_waypoints):
                console.print(f"[dim]    WP {i+1}: ({wp[0]:+.1f}, {wp[1]:+.1f})[/dim]")
            self.speak(f"Navigating to {matched.title()}.")
            return True

        console.print(f"[bold red]❌ Unknown target room: {room_name}[/bold red]")
        return False

    def _control_loop(self):
        log_tick = 0
        while self.running:
            time.sleep(0.05)
            if not self.has_odom or not self.navigating:
                continue

            log_tick += 1

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

            # Waypoint reached tolerance (0.55m for intermediate, 0.40m for final)
            is_final_wp = (self.wp_idx == len(self.active_waypoints) - 1)
            reach_radius = 0.40 if is_final_wp else 0.55

            if dist < reach_radius:
                console.print(f"[green]  ✓ Waypoint {self.wp_idx+1}/{len(self.active_waypoints)} reached ({tx:.1f}, {ty:.1f})[/green]")
                self.wp_idx += 1
                continue

            target_yaw = math.atan2(dy, dx)
            alpha = target_yaw - self.cur_yaw
            while alpha > math.pi:
                alpha -= 2 * math.pi
            while alpha < -math.pi:
                alpha += 2 * math.pi

            # Regulated Pure Pursuit Controller
            # 1. Front Obstacle Safety Recovery
            if self.min_obstacle_dist < 0.28:
                vx = -0.20
                wz = 0.40 if alpha > 0 else -0.40
                phase = "BACKUP"
            # 2. Large Heading Error: Pivot on the spot
            elif abs(alpha) > math.radians(40):
                vx = 0.0
                wz = 0.65 if alpha > 0 else -0.65
                phase = "ALIGN"
            # 3. Aligned: Smooth Curvature Arc Drive
            else:
                lookahead = max(0.45, min(1.2, dist))
                v_max = min(0.35, max(0.12, 0.45 * dist))
                
                # Slow down if approaching obstacles ahead
                if self.min_obstacle_dist < 0.60:
                    v_max = min(v_max, 0.18)
                    
                curvature = 2.0 * math.sin(alpha) / lookahead
                vx = v_max * max(0.2, math.cos(alpha))
                wz = float(np.clip(vx * curvature + 0.3 * alpha, -0.75, 0.75))
                phase = "PURSUIT"

            self.publish_cmd(vx, wz)

            # Print navigation status every 1 second (20 ticks)
            if log_tick % 20 == 0:
                console.print(
                    f"[dim]  NAV [{phase}] wp={self.wp_idx+1}/{len(self.active_waypoints)} "
                    f"pos=({self.cur_x:+.1f},{self.cur_y:+.1f}) → target=({tx:.1f},{ty:.1f}) "
                    f"dist={dist:.1f}m err={math.degrees(alpha):+.0f}° "
                    f"cmd=(vx={vx:.2f}, wz={wz:.2f}) obs={self.min_obstacle_dist:.1f}m[/dim]"
                )


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
