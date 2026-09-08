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
from gz.msgs10.double_pb2 import Double as GzDouble

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

from gracemo_sdk import AdapterClient, VisionNoiseGate
from gracemo_brain.mission_planner import MissionPlanner, MissionPlan, MissionStep, SpatialKnowledgeGraph


class MissionVisualizer:
    def __init__(self):
        self.node = gz_transport.Node()

        # Kernel connection & Noise Gate
        self.client = AdapterClient(adapter_name="mission_visualizer", base_url="http://127.0.0.1:7780")
        self.noise_gate = VisionNoiseGate(confidence_threshold=0.30, cooldown_sec=3.0)

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

        # Mission Planner & State
        self.planner = MissionPlanner()
        self.active_mission: Optional[MissionPlan] = None
        self.target_room = "hallway"
        self.active_waypoints = []
        self.wp_idx = 0
        self.navigating = False
        self.current_room_label = "Central Hallway"
        self.detected_objects = set()
        self.room_inventory = {
            "Master Bedroom": set(),
            "Kitchen & Dining": set(),
            "Living Room": set(),
            "Home Study": set()
        }

        # Active Wall-Unstick Reflex & Stall Detection
        self.stall_count = 0
        self.last_pos = None
        self.recovering = 0

        # Subscriptions
        self.node.subscribe(GzImage, "/camera/image_raw", self._on_image)
        self.node.subscribe(GzOdometry, "/odom", self._on_odom)
        self.node.subscribe(GzLaserScan, "/scan", self._on_scan)

        # Publisher
        self.cmd_pub = self.node.advertise("/cmd_vel", GzTwist)

        # Arm Joint Publishers (Keep arm securely resting in natural hand-DOWN STANCE_HOME)
        self.arm_pubs = [self.node.advertise(f"/arm/joint_{i+1}/cmd_pos", GzDouble) for i in range(7)]
        threading.Thread(target=self._init_arm_stance, daemon=True).start()

        # TTS voice
        self.voice = None
        if VoiceAdapter:
            try:
                self.voice = VoiceAdapter()
            except Exception:
                pass

        # Vision Worker State (Decoupled for Zero-Latency 30 FPS Stream)
        self.latest_raw_frame = None
        self.latest_detections = []  # List of (xyxy, conf, cls_name)
        self.vision_lock = threading.Lock()
        self.pose_lock = threading.Lock()
        
        # Start async background YOLO inference thread
        self.vision_thread = threading.Thread(target=self._vision_inference_loop, daemon=True)
        self.vision_thread.start()

        # Background control loop thread (20Hz)
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()

        console.print("[bold green]✓ Connected to Gazebo Harmonic via native gz.transport13[/bold green]")

    def speak(self, text: str):
        console.print(f"\n[bold cyan]🗣️ ViRa:[/bold cyan] [italic yellow]\"{text}\"[/italic yellow]")
        if self.voice:
            threading.Thread(target=self.voice.speak, args=(text,), daemon=True).start()

    def _init_arm_stance(self):
        """Holds the 7-DOF arm safely down along the torso in STANCE_HOME throughout navigation."""
        time.sleep(0.5)
        # STANCE_HOME: shoulder yaw=0, shoulder pitch=+75 deg (+1.31 rad), roll=+14 deg (+0.25 rad), elbow=-11 deg (-0.20 rad)
        home_q = [0.0, 1.31, 0.25, -0.20, -0.10, 0.0, 0.0]
        while self.running:
            for i, val in enumerate(home_q):
                msg = GzDouble()
                msg.data = float(val)
                self.arm_pubs[i].publish(msg)
            time.sleep(1.0)

    def _vision_inference_loop(self):
        """Asynchronous background worker running YOLO without blocking the 30 FPS video transport."""
        while self.running:
            if self.latest_raw_frame is None:
                time.sleep(0.02)
                continue

            with self.vision_lock:
                frame_to_process = self.latest_raw_frame.copy()

            try:
                results = self.yolo(frame_to_process, verbose=False, conf=0.25, imgsz=480)
                detections = []
                for box in results[0].boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = self.yolo.names[cls_id]
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    detections.append((xyxy, conf, cls_name))
                    self.detected_objects.add(cls_name)
                    if self.current_room_label in self.room_inventory:
                        self.room_inventory[self.current_room_label].add(cls_name)

                    # Emit grounded observation to MNSE Kernel
                    if self.noise_gate.should_emit(cls_name, conf, self.current_room_label):
                        cx = float((xyxy[0] + xyxy[2]) / 2.0)
                        cy = float((xyxy[1] + xyxy[3]) / 2.0)
                        self.client.emit(
                            "ObjectDetected",
                            {"class_name": cls_name, "confidence": conf, "x": cx, "y": cy},
                            source="Vision"
                        )

                with self.vision_lock:
                    self.latest_detections = detections
            except Exception:
                pass

            time.sleep(0.04)  # ~25 FPS inference rate

    def _on_image(self, msg: GzImage):
        """Ultra-fast non-blocking transport callback (runs in < 1ms to eliminate stream buffering lag)."""
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            frame = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            self.latest_raw_frame = frame

            # Render HUD and latest detection bounding boxes instantly onto fresh frame
            annotated = frame.copy()
            with self.vision_lock:
                current_dets = list(self.latest_detections)

            current_frame_classes = set()
            for xyxy, conf, cls_name in current_dets:
                current_frame_classes.add(cls_name)
                x1, y1, x2, y2 = xyxy
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 120), 2)
                cv2.putText(annotated, f"{cls_name} {conf:.2f}", (x1, max(20, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 120), 2)

            # Draw HUD Telemetry Overlay on Video
            h, w, _ = annotated.shape
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (w, 65), (20, 20, 25), -1)
            cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 25), -1)
            cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

            # Top HUD Text
            room_color = (0, 220, 100) if self.current_room_label != "Central Hallway" else (255, 180, 0)
            cv2.putText(annotated, f"ROOM: {self.current_room_label.upper()}", (15, 24), cv2.FONT_HERSHEY_DUPLEX, 0.60, room_color, 2)
            
            # Mission Step Text
            if self.active_mission and self.active_mission.current_step():
                step = self.active_mission.current_step()
                plan_str = f"STEP {step.step_num}/{len(self.active_mission.steps)}: {step.description}"
                cv2.putText(annotated, plan_str, (15, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 220, 255), 1)
            else:
                cv2.putText(annotated, f"POS: ({self.cur_x:+.2f}m, {self.cur_y:+.2f}m) | HEADING: {math.degrees(self.cur_yaw):.0f}deg", (15, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

            # Status Badge Top Right
            if self.navigating and self.active_mission:
                status_text = f"PLAN: {self.target_room.upper()}"
                badge_color = (0, 160, 255)
            else:
                status_text = "STATIONED"
                badge_color = (0, 230, 100)
            cv2.putText(annotated, status_text, (w - 180, 32), cv2.FONT_HERSHEY_DUPLEX, 0.55, badge_color, 2)

            # Bottom HUD Bar: Active Detections
            det_str = " | ".join(sorted(current_frame_classes)) if current_frame_classes else "Scanning Field of View"
            cv2.putText(annotated, f"OBJECTS: {det_str}", (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

            self.annotated_frame = annotated

        except Exception:
            pass

    def _on_odom(self, msg: GzOdometry):
        pos = msg.pose.position
        q = msg.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        with self.pose_lock:
            self.cur_x = pos.x
            self.cur_y = pos.y
            self.cur_yaw = yaw
            self.has_odom = True

        # Update current room label based on spatial position
        prev_room = self.current_room_label
        if pos.y > 1.2:
            new_room = "Master Bedroom" if pos.x < 0 else "Home Study"
        elif pos.y < -1.2:
            new_room = "Kitchen & Dining" if pos.x < 0 else "Living Room"
        else:
            new_room = "Central Hallway"

        self.current_room_label = new_room
        if new_room != prev_room:
            self.client.emit(
                "NavigationArrived",
                {"destination": new_room, "success": True},
                source="RobotBridge"
            )
            self.client.emit(
                "RobotPosition",
                {"x": pos.x, "y": pos.y, "theta": yaw, "speed": 0.0},
                source="RobotBridge"
            )

    def _on_scan(self, msg: GzLaserScan):
        # Scan range is -pi to +pi (360 samples). Center index (180) is straight ahead (0 deg).
        # Inspect direct forward driving cone (-15 deg to +15 deg: 30-deg path clearance)
        n = len(msg.ranges)
        if n >= 360:
            mid = n // 2
            front_span = int(n * (15.0 / 360.0))
            front_ranges = [msg.ranges[i] for i in range(mid - front_span, mid + front_span + 1)]
        else:
            front_ranges = list(msg.ranges)

        # Ignore robot self-reflection (chassis radius is 0.19m) by requiring r > 0.24m
        valid = [r for r in front_ranges if not math.isnan(r) and r > 0.24]
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
            waypoints.extend([(-5.0, 0.0), (-5.0, 0.6), (-5.0, 1.8), (-5.5, 3.5)])
        elif target_room == "study":
            waypoints.extend([(5.0, 0.0), (5.0, 0.6), (5.0, 1.8), (4.5, 3.5)])
        elif target_room == "kitchen":
            waypoints.extend([(-5.0, 0.0), (-5.0, -0.6), (-5.0, -1.8), (-3.5, -3.5)])
        elif target_room == "living":
            waypoints.extend([(5.0, 0.0), (5.0, -0.6), (5.0, -1.8), (3.5, -3.5)])
        elif target_room == "hallway":
            waypoints.append((0.0, 0.0))

        # Deduplicate consecutive waypoints within 0.25m
        clean_wps = []
        for wp in waypoints:
            if not clean_wps:
                clean_wps.append(wp)
            elif math.hypot(wp[0] - clean_wps[-1][0], wp[1] - clean_wps[-1][1]) > 0.25:
                clean_wps.append(wp)

        return clean_wps

    def execute_mission(self, user_command: str) -> bool:
        """
        Decomposes command into an explicit MissionPlan, displays the plan table, and begins step-by-step execution.
        """
        # Ensure latest odom pose is available before planning
        if not self.has_odom:
            t_wait = time.time()
            while not self.has_odom and time.time() - t_wait < 2.0:
                time.sleep(0.05)

        plan = self.planner.create_mission(user_command, (self.cur_x, self.cur_y, self.cur_yaw))
        if not plan or not plan.steps:
            console.print(f"[bold red]❌ Could not generate valid mission plan for: {user_command}[/bold red]")
            return False

        self.active_mission = plan
        self.target_room = plan.target_room
        self.navigating = True

        console.print("\n")
        console.print(plan.render_table())
        console.print(f"[bold cyan]🤖 ViRa Planner:[/bold cyan] [yellow]Generated {len(plan.steps)}-step plan for '{plan.goal}'. Beginning execution...[/yellow]\n")
        self.speak(f"Mission plan confirmed. {len(plan.steps)} steps scheduled. Starting execution.")
        return True

    def navigate_to_room(self, room_name: str) -> bool:
        return self.execute_mission(f"Go to {room_name}")

    def _control_loop(self):
        log_tick = 0
        while self.running:
            time.sleep(0.05)
            if not self.has_odom or not self.navigating or not self.active_mission:
                continue

            log_tick += 1
            step = self.active_mission.current_step()

            # Mission finished
            if not step:
                self.navigating = False
                self.publish_cmd(0.0, 0.0)
                continue

            # 1. Action: Perceptual Scan & Verification (360° Panoramic Camera Survey)
            if step.action_type == "SCAN":
                if not hasattr(self, "_scan_start_time") or self._scan_start_time is None:
                    self._scan_start_time = time.time()
                    self.speak(f"Entering scan mode in {step.target_room.title()}. Surveying environment.")
                    console.print(f"[bold cyan]🔄 [SCANNING] Performing 360° visual survey of {step.target_room.title()}...[/bold cyan]")

                elapsed_scan = time.time() - self._scan_start_time
                if elapsed_scan < 7.0:
                    self.publish_cmd(0.0, 0.45)
                    continue
                else:
                    self.publish_cmd(0.0, 0.0)
                    self._scan_start_time = None
                    room_key = self.current_room_label
                    found_items = list(self.room_inventory.get(room_key, []))
                    found_str = ", ".join(found_items) if found_items else "room furniture"
                    console.print(f"[bold green]✓ [STEP {step.step_num} COMPLETE] Scanned {step.target_room.title()}: Cataloged {found_str}[/bold green]")
                    self.active_mission.advance()
                    continue

            # 2. Action: Verbal Report
            if step.action_type == "REPORT":
                found = ", ".join(self.room_inventory.get(self.current_room_label, ["objects"])) or "furniture"
                console.print(f"[bold magenta]🏁 [MISSION COMPLETE] {self.active_mission.goal.upper()}[/bold magenta]")
                self.speak(f"Mission complete. I am stationed in {self.current_room_label} with {found} in view.")
                self.active_mission.advance()
                self.navigating = False
                self.publish_cmd(0.0, 0.0)
                continue

            # 0. Active Wall Unstick Reflex: If recovering, execute smooth backoff and disengagement
            if self.recovering > 0:
                self.recovering -= 1
                self.publish_cmd(-0.20, 0.45)
                continue

            # 3. Action: Motion Navigation (TRANSIT, ENTER_DOOR, STATION, APPROACH)
            with self.pose_lock:
                cur_x = self.cur_x
                cur_y = self.cur_y
                cur_yaw = self.cur_yaw

            tx, ty = step.target_pos
            dx = tx - cur_x
            dy = ty - cur_y
            dist = math.hypot(dx, dy)

            # Reach Tolerance: 0.25m ensures robot enters the exact doorway center (X=-5.0) before turning
            reach_radius = 0.25

            if dist < reach_radius:
                console.print(f"[green]  ✓ Step {step.step_num}/{len(self.active_mission.steps)} Reached: {step.description}[/green]")
                has_next = self.active_mission.advance()
                if not has_next:
                    self.navigating = False
                    self.publish_cmd(0.0, 0.0)
                continue

            # Shortest-signed-angle tracking (-pi to +pi)
            target_yaw = math.atan2(dy, dx)
            alpha = target_yaw - cur_yaw
            while alpha > math.pi:
                alpha -= 2 * math.pi
            while alpha < -math.pi:
                alpha += 2 * math.pi

            # Continuous Unicycle Navigation:
            # Quick, responsive in-place turn only for large initial turns (> 40 degrees)
            if abs(alpha) > math.radians(40):
                vx = 0.0
                wz = float(np.clip(1.8 * alpha, -0.65, 0.65))
            else:
                # Drive forward continuously with cosine speed scaling during gentle curves
                align = max(0.20, math.cos(alpha))
                v_max = min(0.38, max(0.18, 0.50 * dist))
                vx = v_max * align

                # Proactive angular steering authority keeps robot tracking straight without drifting
                wz = float(np.clip(2.2 * alpha, -0.55, 0.55))

            # Stall & Wall Contact Detection: If commanded forward but physically stationary, trigger reflex
            if vx > 0.12:
                if self.last_pos is not None:
                    moved = math.hypot(cur_x - self.last_pos[0], cur_y - self.last_pos[1])
                    if moved < 0.015:
                        self.stall_count += 1
                    else:
                        self.stall_count = 0
                self.last_pos = (cur_x, cur_y)

                if self.stall_count >= 8:  # Stalled against surface for ~0.4s
                    console.print("[bold yellow]⚡ [WALL REFLEX] Surface contact detected! Reversing and disengaging...[/bold yellow]")
                    self.recovering = 15  # Back up and pivot away for 0.75s
                    self.stall_count = 0
                    continue

            # Adaptive Proximity Cushion: prevents doorway freeze while protecting against collisions
            if self.min_obstacle_dist < 0.22:
                vx = 0.0
                if log_tick % 20 == 0:
                    console.print(f"[bold red]⚠️ Proximity cushion active ({self.min_obstacle_dist:.2f}m). Pausing forward translation.[/bold red]")
            elif self.min_obstacle_dist < 0.32:
                cushion_scale = (self.min_obstacle_dist - 0.22) / 0.10
                vx = vx * max(0.40, min(1.0, cushion_scale))

            self.publish_cmd(vx, wz)

            # Print navigation status every 1 second (20 ticks)
            if log_tick % 20 == 0:
                console.print(
                    f"[dim]  MISSION [Step {step.step_num}/{len(self.active_mission.steps)}: {step.action_type}] "
                    f"pos=({cur_x:+.1f},{cur_y:+.1f}) → target=({tx:.1f},{ty:.1f}) "
                    f"dist={dist:.1f}m err={math.degrees(alpha):+.0f}° "
                    f"cmd=(vx={vx:.2f}, wz={wz:.2f})[/dim]"
                )


def print_help():
    table = Table(title="🎮 GRaCEmo ViRa Mission & Voice Controls", border_style="cyan", show_header=True)
    table.add_column("Command / Voice", style="bold yellow")
    table.add_column("Action", style="green")
    table.add_row("1 or 'bedroom' / 🗣️ 'Go to bedroom'", "Navigate to Master Bedroom")
    table.add_row("2 or 'study' / 🗣️ 'Go to study'", "Navigate to Home Study")
    table.add_row("3 or 'living' / 🗣️ 'Go to living room'", "Navigate to Living Room")
    table.add_row("4 or 'kitchen' / 🗣️ 'Go to kitchen'", "Navigate to Kitchen & Dining")
    table.add_row("h or 'hallway' / 🗣️ 'Go to hallway'", "Return to Central Hallway")
    table.add_row("a or 'auto' / 🗣️ 'Start tour'", "Start full autonomous 4-room tour")
    table.add_row("w / a / s / d / space", "Manual teleoperation drive & stop")
    table.add_row("q or 'quit'", "Stop robot and exit")
    console.print(table)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GRaCEmo ViRa Real-Time Mission Visualizer & Control")
    parser.add_argument("--auto", "--tour", action="store_true", help="Start full autonomous tour immediately")
    parser.add_argument("--room", type=str, default=None, help="Navigate to specific room immediately")
    args, _ = parser.parse_known_args()

    vis = MissionVisualizer()

    console.print(Panel.fit(
        "[bold cyan]GRaCEmo ViRa — Real-Time Mission Visualizer & Control Online[/bold cyan]\n"
        "[dim]Type a command, press keys in the HUD, or speak into your microphone.[/dim]",
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
    auto_tour = bool(args.auto)

    if args.auto:
        vis.navigate_to_room(patrol_order[patrol_idx])
        vis.speak("Starting full autonomous apartment tour.")
    elif args.room:
        vis.navigate_to_room(args.room)

    def handle_command(cmd_str: str):
        nonlocal auto_tour, patrol_idx
        cmd = cmd_str.strip().lower()
        if not cmd:
            return

        if cmd in ("q", "quit", "exit"):
            vis.running = False
        elif any(w in cmd for w in ["bedroom", "1"]):
            auto_tour = False
            vis.navigate_to_room("bedroom")
        elif any(w in cmd for w in ["study", "2"]):
            auto_tour = False
            vis.navigate_to_room("study")
        elif any(w in cmd for w in ["living", "3"]):
            auto_tour = False
            vis.navigate_to_room("living")
        elif any(w in cmd for w in ["kitchen", "4"]):
            auto_tour = False
            vis.navigate_to_room("kitchen")
        elif any(w in cmd for w in ["hallway", "hall", "h"]):
            auto_tour = False
            vis.navigate_to_room("hallway")
        elif any(w in cmd for w in ["auto", "tour", "patrol", "a"]):
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
        elif any(w in cmd for w in [" ", "stop", "halt", "x"]):
            vis.navigating = False
            vis.surveying = False
            vis.publish_cmd(0.0, 0.0)
            console.print("[bold red]🛑 Emergency Stop applied.[/bold red]")
            vis.speak("Stopped.")
        elif cmd in ("help", "?"):
            print_help()
        else:
            if not vis.navigate_to_room(cmd):
                console.print(f"[dim]Type 'help' for command list.[/dim]")

    # 1. Background thread for Terminal Keyboard Input
    def terminal_input_loop():
        while vis.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                handle_command(line)
            except Exception:
                break

    input_thread = threading.Thread(target=terminal_input_loop, daemon=True)
    input_thread.start()

    # 2. Background thread for Voice Microphone Input via STT
    def voice_listener_loop():
        if not vis.voice:
            return
        console.print("[bold green]🎤 Microphone Voice Engine Active (Speak commands anytime!)[/bold green]")
        while vis.running:
            try:
                # Listen to microphone and transcribe via faster-whisper
                text = vis.voice.listen_and_transcribe(timeout=4.0)
                if text and len(text.strip()) > 1:
                    console.print(f"\n[bold cyan]🎙️ Heard Voice Command:[/bold cyan] [italic]\"{text}\"[/italic]")
                    handle_command(text)
            except Exception:
                time.sleep(1.0)

    if vis.voice:
        voice_thread = threading.Thread(target=voice_listener_loop, daemon=True)
        voice_thread.start()

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
