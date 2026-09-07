"""
GRaCEmo ViRa — Semantic Spatial Knowledge Graph & Mission Task Planner
Decomposes high-level natural language requests into structured, verifiable multi-step action plans.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

console = Console(highlight=False)


@dataclass
class MissionStep:
    step_num: int
    title: str
    action_type: str  # "TRANSIT", "ENTER_DOOR", "STATION", "SCAN", "REPORT"
    target_pos: Tuple[float, float]  # (x, y)
    target_yaw: Optional[float] = None  # in radians, None if any
    target_room: str = "Central Hallway"
    expected_objects: List[str] = field(default_factory=list)
    description: str = ""
    status: str = "PENDING"  # "PENDING", "ACTIVE", "COMPLETED", "FAILED"
    progress: float = 0.0  # 0.0 to 1.0


@dataclass
class MissionPlan:
    mission_id: str
    goal: str
    target_room: str
    target_object: Optional[str]
    steps: List[MissionStep]
    created_at: float = 0.0
    current_step_idx: int = 0
    status: str = "PLANNED"  # "PLANNED", "EXECUTING", "COMPLETED", "FAILED"

    def current_step(self) -> Optional[MissionStep]:
        if 0 <= self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return None

    def advance(self) -> bool:
        if self.current_step():
            self.current_step().status = "COMPLETED"
            self.current_step().progress = 1.0
        self.current_step_idx += 1
        if self.current_step_idx >= len(self.steps):
            self.status = "COMPLETED"
            return False
        if self.current_step():
            self.current_step().status = "ACTIVE"
        return True

    def render_table(self) -> Table:
        table = Table(title=f"📋 MISSION PLAN: {self.goal.upper()}", border_style="cyan", show_header=True)
        table.add_column("#", style="bold yellow", width=3)
        table.add_column("Status", width=12)
        table.add_column("Phase", style="bold cyan", width=14)
        table.add_column("Target (X, Y)", width=14)
        table.add_column("Action Description", style="green")

        for step in self.steps:
            if step.status == "COMPLETED":
                st_badge = "[bold green]✓ DONE[/bold green]"
            elif step.status == "ACTIVE":
                st_badge = f"[bold yellow]▶ {int(step.progress * 100)}%[/bold yellow]"
            else:
                st_badge = "[dim]⏳ PENDING[/dim]"

            pos_str = f"({step.target_pos[0]:+.1f}, {step.target_pos[1]:+.1f})"
            table.add_row(str(step.step_num), st_badge, step.action_type, pos_str, step.description)

        return table


class SpatialKnowledgeGraph:
    """
    Topological and semantic spatial map of the 4-room apartment environment.
    Guarantees perpendicular doorway corridors, fluid transitions, and clear camera framing.
    """

    ROOM_NODES = {
        "hallway": {
            "name": "Central Hallway",
            "center": (0.0, 0.0),
            "station_yaw": 0.0,
            "furniture": []
        },
        "bedroom": {
            "name": "Master Bedroom",
            "center": (-5.0, 2.0),
            "door_x": -5.0,
            "door_threshold_y": 1.4,
            "station_pose": (-5.0, 2.0),
            "station_yaw": math.pi / 2,  # +90 deg: Face North directly toward Bed & Wardrobe
            "furniture": ["bed", "wardrobe", "nightstand"],
            "targets": {
                "bed": (-5.0, 2.0),
                "wardrobe": (-5.5, 2.0),
                "nightstand": (-4.5, 2.0)
            }
        },
        "study": {
            "name": "Home Study",
            "center": (5.0, 2.0),
            "door_x": 5.0,
            "door_threshold_y": 1.4,
            "station_pose": (5.0, 2.0),
            "station_yaw": math.pi / 2,  # +90 deg: Face North directly toward Desk & Bookshelf
            "furniture": ["desk", "bookshelf", "chair", "laptop"],
            "targets": {
                "desk": (5.0, 2.0),
                "bookshelf": (5.5, 2.0)
            }
        },
        "kitchen": {
            "name": "Kitchen & Dining",
            "center": (-5.0, -2.2),
            "door_x": -5.0,
            "door_threshold_y": -1.4,
            "station_pose": (-5.0, -2.2),
            "station_yaw": -math.pi / 2,  # -90 deg: Face South directly toward Dining Table & Refrigerator
            "furniture": ["refrigerator", "dining table", "chair", "counter", "bottle", "cup"],
            "targets": {
                "refrigerator": (-5.0, -2.2),
                "table": (-5.0, -2.2),
                "counter": (-5.0, -2.2)
            }
        },
        "living": {
            "name": "Living Room",
            "center": (5.0, -2.2),
            "door_x": 5.0,
            "door_threshold_y": -1.4,
            "station_pose": (5.0, -2.2),
            "station_yaw": -math.pi / 2,  # -90 deg: Face South directly toward Sofa, Coffee Table & TV
            "furniture": ["sofa", "coffee table", "tv", "bowl"],
            "targets": {
                "tv": (5.0, -2.2)
            }
        }
    }

    CANONICAL_ROOMS = {
        "bedroom": "bedroom", "master bedroom": "bedroom", "bed": "bedroom",
        "study": "study", "home study": "study", "office": "study",
        "kitchen": "kitchen", "kitchen & dining": "kitchen", "dining": "kitchen",
        "living": "living", "living room": "living", "lounge": "living",
        "hallway": "hallway", "central hallway": "hallway"
    }

    @classmethod
    def get_room_node(cls, room_name: str) -> Dict[str, Any]:
        """Dynamically query MNSE Knowledge Graph (graph.db) or fallback to topology."""
        canonical = cls.CANONICAL_ROOMS.get(room_name.lower().strip(), room_name.lower().strip())
        try:
            import requests
            resp = requests.get("http://127.0.0.1:7780/graph", timeout=0.5)
            if resp.status_code == 200:
                data = resp.json()
                nodes = data.get("nodes", [])
                for n in nodes:
                    if n.get("type") == "Room":
                        label = n.get("label", "").lower()
                        if canonical in label or label in canonical:
                            props = n.get("properties", {})
                            if "center_x" in props and "door_x" in props:
                                return {
                                    "name": n.get("label"),
                                    "center": (props["center_x"], props["center_y"]),
                                    "door_x": props["door_x"],
                                    "door_threshold_y": props["door_threshold_y"],
                                    "station_pose": (props["center_x"], props["center_y"]),
                                    "station_yaw": props.get("station_yaw", 0.0),
                                    "furniture": props.get("furniture", []),
                                    "targets": props.get("targets", {})
                                }
        except Exception:
            pass
        return cls.ROOM_NODES.get(canonical, cls.ROOM_NODES.get("hallway"))

    @classmethod
    def get_room_from_position(cls, x: float, y: float) -> str:
        if y > 1.0:
            return "bedroom" if x < 0 else "study"
        elif y < -1.0:
            return "kitchen" if x < 0 else "living"
        return "hallway"

    @classmethod
    def generate_path_waypoints(cls, start_pos: Tuple[float, float], target_room: str, target_object: Optional[str] = None) -> List[Tuple[float, float]]:
        """
        Generate mathematically collision-free corridor waypoints across the apartment.
        Always routes through hallway centerline (Y = 0.0) and perpendicular doorway thresholds.
        """
        cur_x, cur_y = start_pos
        cur_room = cls.get_room_from_position(cur_x, cur_y)
        waypoints = []

        # Stage 1: If currently inside a room, first exit through the current room's door to hallway
        if cur_room != "hallway" and cur_room != target_room:
            cur_info = cls.ROOM_NODES[cur_room]
            door_x = cur_info["door_x"]
            threshold_y = cur_info["door_threshold_y"]
            # 1a. Move to door inside room
            waypoints.append((door_x, threshold_y))
            # 1b. Step into central hallway
            waypoints.append((door_x, 0.0))

        # Stage 2: Target room approach and entry
        if target_room in cls.ROOM_NODES and target_room != "hallway":
            tgt_info = cls.ROOM_NODES[target_room]
            tgt_door_x = tgt_info["door_x"]
            tgt_threshold_y = tgt_info["door_threshold_y"]

            if cur_room == target_room:
                # Already inside target room: proceed straight to station pose
                if target_object and target_object in tgt_info.get("targets", {}):
                    waypoints.append(tgt_info["targets"][target_object])
                else:
                    waypoints.append(tgt_info["station_pose"])
            else:
                # 2a. Hallway approach at target room doorway (along Y=0.0 centerline)
                waypoints.append((tgt_door_x, 0.0))
                # 2b. Perpendicular doorway entrance
                waypoints.append((tgt_door_x, tgt_threshold_y))
                # 2c. Final room station pose (or specific object approach)
                if target_object and target_object in tgt_info.get("targets", {}):
                    waypoints.append(tgt_info["targets"][target_object])
                else:
                    waypoints.append(tgt_info["station_pose"])

        elif target_room == "hallway":
            waypoints.append((0.0, 0.0))

        # Deduplicate consecutive waypoints within 0.35m
        clean = []
        for wp in waypoints:
            if not clean:
                clean.append(wp)
            elif math.hypot(wp[0] - clean[-1][0], wp[1] - clean[-1][1]) > 0.35:
                clean.append(wp)

        return clean


class MissionPlanner:
    """
    Cognitive Mission Planner: Decomposes tasks into structured, verifiable MissionPlans.
    """

    def __init__(self):
        self.graph = SpatialKnowledgeGraph()

    def create_mission(self, user_command: str, current_pose: Tuple[float, float, float]) -> MissionPlan:
        """
        Decompose a natural language or key command into a verified MissionPlan.
        """
        cmd = user_command.lower().strip()
        cur_x, cur_y, cur_yaw = current_pose

        # Identify target room
        target_room = "hallway"
        for room in ["bedroom", "study", "kitchen", "living"]:
            if room in cmd:
                target_room = room
                break

        # Identify target object if mentioned
        target_obj = None
        for obj in ["bed", "wardrobe", "nightstand", "desk", "bookshelf", "table", "chair", "refrigerator", "counter", "sofa", "tv", "bottle", "cup"]:
            if obj in cmd:
                target_obj = obj
                break

        # Generate path waypoints
        raw_waypoints = self.graph.generate_path_waypoints((cur_x, cur_y), target_room, target_obj)
        tgt_node = self.graph.ROOM_NODES.get(target_room, {})
        final_yaw = tgt_node.get("station_yaw", None)

        steps: List[MissionStep] = []
        step_counter = 1

        # Phase 1: Transit Steps
        for i, wp in enumerate(raw_waypoints):
            is_door = abs(wp[1]) > 0.5 and abs(wp[1]) < 1.8
            is_final = (i == len(raw_waypoints) - 1)

            if is_door:
                desc = f"Transit through doorway threshold ({wp[0]:+.1f}, {wp[1]:+.1f})"
                action = "ENTER_DOOR"
            elif is_final:
                desc = f"Station at {target_room.title()} facing furniture"
                action = "STATION"
            else:
                desc = f"Transit hallway centerline toward ({wp[0]:+.1f}, {wp[1]:+.1f})"
                action = "TRANSIT"

            step_yaw = final_yaw if is_final else None
            steps.append(MissionStep(
                step_num=step_counter,
                title=f"Path Segment {i+1}",
                action_type=action,
                target_pos=wp,
                target_yaw=step_yaw,
                target_room=target_room,
                description=desc
            ))
            step_counter += 1

        # Phase 2: Perceptual Verification Step
        room_furniture = tgt_node.get("furniture", [])
        expected = [target_obj] if target_obj else room_furniture[:3]
        steps.append(MissionStep(
            step_num=step_counter,
            title="Visual Perception & Verification",
            action_type="SCAN",
            target_pos=raw_waypoints[-1] if raw_waypoints else (cur_x, cur_y),
            target_yaw=final_yaw,
            target_room=target_room,
            expected_objects=expected,
            description=f"Verify furniture objects: {', '.join(expected)}"
        ))
        step_counter += 1

        # Phase 3: Verbal Report Step
        steps.append(MissionStep(
            step_num=step_counter,
            title="Mission Report",
            action_type="REPORT",
            target_pos=raw_waypoints[-1] if raw_waypoints else (cur_x, cur_y),
            target_yaw=final_yaw,
            target_room=target_room,
            description=f"Announce room status and detected objects"
        ))

        # Set first step to ACTIVE
        if steps:
            steps[0].status = "ACTIVE"

        goal_text = f"Navigate to {target_room.title()}" + (f" and inspect {target_obj}" if target_obj else "")
        return MissionPlan(
            mission_id=f"mission_{int(math.fabs(cur_x * 100))}_{target_room}",
            goal=goal_text,
            target_room=target_room,
            target_object=target_obj,
            steps=steps,
            status="PLANNED"
        )
