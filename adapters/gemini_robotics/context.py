"""
GRaCEmo ViRa — MNSE Context Provider for Gemini Robotics ER 2
Retrieves authoritative, real-time world awareness (NOW + PAST + RELATIONS) from the MNSE Kernel.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add SDK and perception paths if not present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sdk_path = ROOT_DIR / "adapters" / "sdk"
adapters_path = ROOT_DIR / "adapters"
for p in [sdk_path, adapters_path, ROOT_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import requests
from gracemo_sdk import AdapterClient
from adapters.perception.world_model import WorldObject, VISIBILITY_TIMEOUT_SEC

log = logging.getLogger("gemini_robotics.context")


@dataclass
class ObjectResolutionResult:
    """Structured result of resolving a natural language reference to an MNSE world object."""
    status: str  # "RESOLVED", "NOT_FOUND", "AMBIGUOUS", "STALE", "INVALID_COORDINATES"
    object: Optional[WorldObject] = None
    candidates: List[WorldObject] = field(default_factory=list)
    message: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.status == "RESOLVED" and self.object is not None


class MNSEContextProvider:
    """
    Authoritative Context Bridge between MNSE Kernel and Gemini Robotics ER 2.
    Ensures Gemini remains an embodied reasoner grounded in physical reality
    rather than guessing robot or world state.
    """

    def __init__(self, kernel_url: str = "http://127.0.0.1:7780", timeout_sec: float = 2.0):
        self.kernel_url = kernel_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.client = AdapterClient(adapter_name="gemini_robotics_er", base_url=self.kernel_url)
        self._standalone_tracker: Optional[Any] = None

    def is_kernel_available(self) -> bool:
        """Pings Kernel /health to check availability."""
        try:
            resp = requests.get(f"{self.kernel_url}/health", timeout=self.timeout_sec)
            return resp.status_code == 200
        except Exception:
            return False

    def get_robot_context(self) -> Dict[str, Any]:
        """
        Retrieves the authoritative 'NOW' InspectorState snapshot:
        - Current room
        - Real-time robot coordinates (x, y, theta, speed)
        - Battery level & charging state
        - Last vision detection
        - Last voice command
        """
        snapshot = self.client.get_snapshot()
        if snapshot:
            return snapshot
        return {
            "status": "offline",
            "current_room": "Unknown",
            "robot_position": None,
            "battery": None,
            "last_vision_detection": None,
            "last_voice_command": None,
        }

    def get_world_context(self, history_limit: int = 10) -> Dict[str, Any]:
        """
        Retrieves compiled contextual truth (NOW + PAST + RELATIONS)
        from the Kernel Context Compiler.
        """
        context = self.client.get_context(history_limit=history_limit)
        if context:
            return context
        return {
            "now": self.get_robot_context(),
            "recent_history": [],
            "graph": {"nodes": [], "edges": []},
            "world_objects": [o.to_dict() for o in self.get_world_objects()],
        }

    def get_world_objects(self, visible_only: bool = False, class_name: Optional[str] = None) -> List[WorldObject]:
        """
        Retrieves authoritative persistent 3D world objects from the Rust MNSE Kernel (/world/objects).
        Provides a strictly read-only client representation of the Rust state.
        """
        if self._standalone_tracker is not None:
            return self._standalone_tracker.get_objects(visible_only=visible_only, class_name=class_name)

        params: Dict[str, Any] = {}
        if visible_only:
            params["visible_only"] = "true"
        if class_name:
            params["class"] = class_name

        try:
            resp = requests.get(f"{self.kernel_url}/world/objects", params=params, timeout=self.timeout_sec)
            if resp.status_code == 200:
                data = resp.json()
                objs = data.get("objects", [])
                return [WorldObject.from_dict(o) for o in objs]
        except Exception as e:
            log.debug(f"Failed to fetch world objects from kernel: {e}")
        return []

    def get_world_object_by_id(self, object_id: str) -> Optional[WorldObject]:
        """
        Queries a specific world object by its deterministic identifier from Rust MNSE.
        """
        if self._standalone_tracker is not None:
            return self._standalone_tracker.get_object_by_id(object_id)

        try:
            resp = requests.get(
                f"{self.kernel_url}/world/objects",
                params={"id": object_id},
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found") and "object" in data:
                    return WorldObject.from_dict(data["object"])
        except Exception as e:
            log.debug(f"Failed to query object by id '{object_id}': {e}")
        return None

    def resolve_object(
        self,
        query: str,
        visible_only: bool = True,
        reference_time: Optional[float] = None,
    ) -> ObjectResolutionResult:
        """
        Authoritatively grounds a natural-language reference (e.g. 'chair', 'chair_001')
        against persistent world objects in Rust MNSE.

        Possible statuses:
        - RESOLVED: Exactly one valid matching object found.
        - NOT_FOUND: No matching object exists in world context.
        - AMBIGUOUS: Multiple matching candidates exist; clarification required.
        - STALE: Object exists historically but is no longer currently visible.
        - INVALID_COORDINATES: Coordinates are NaN, Inf, or non-finite.
        """
        raw_query = query.strip()
        if not raw_query:
            return ObjectResolutionResult(
                status="NOT_FOUND",
                message="Empty query provided for object resolution.",
            )

        # Normalize query: strip common leading articles
        low_query = raw_query.lower()
        for article in ["the ", "a ", "an "]:
            if low_query.startswith(article):
                low_query = low_query[len(article):].strip()

        # 1. Check for exact object ID match (e.g. 'chair_001')
        all_objects = self.get_world_objects(visible_only=False)
        exact_match: Optional[WorldObject] = None
        for obj in all_objects:
            if obj.object_id.lower() == low_query or obj.object_id.lower() == raw_query.lower():
                exact_match = obj
                break

        if exact_match is not None:
            # Validate finite coordinates
            if not (math.isfinite(exact_match.world_x) and math.isfinite(exact_match.world_y) and math.isfinite(exact_match.world_z)):
                return ObjectResolutionResult(
                    status="INVALID_COORDINATES",
                    object=exact_match,
                    message=f"Object '{exact_match.object_id}' has non-finite coordinates: ({exact_match.world_x}, {exact_match.world_y}, {exact_match.world_z}).",
                )

            # Validate visibility
            is_vis = exact_match.currently_visible
            if reference_time is not None:
                is_vis = exact_match.is_visible_at(reference_time, timeout_sec=VISIBILITY_TIMEOUT_SEC)

            if visible_only and not is_vis:
                return ObjectResolutionResult(
                    status="STALE",
                    object=exact_match,
                    candidates=[exact_match],
                    message=f"Object '{exact_match.object_id}' exists historically but is no longer currently visible.",
                )

            return ObjectResolutionResult(
                status="RESOLVED",
                object=exact_match,
                candidates=[exact_match],
                message=f"Resolved exact object '{exact_match.object_id}'.",
            )

        # 2. Match by class name (e.g. 'chair')
        same_class_all = [
            obj for obj in all_objects
            if obj.class_name.lower() == low_query or low_query in obj.class_name.lower()
        ]

        if not same_class_all:
            return ObjectResolutionResult(
                status="NOT_FOUND",
                message=f"Object '{query}' has not been sighted in the environment.",
            )

        # Filter by visibility policy
        visible_candidates: List[WorldObject] = []
        stale_candidates: List[WorldObject] = []
        for obj in same_class_all:
            is_vis = obj.currently_visible
            if reference_time is not None:
                is_vis = obj.is_visible_at(reference_time, timeout_sec=VISIBILITY_TIMEOUT_SEC)
            if is_vis:
                visible_candidates.append(obj)
            else:
                stale_candidates.append(obj)

        target_pool = visible_candidates if visible_only else same_class_all

        if not target_pool:
            if stale_candidates:
                return ObjectResolutionResult(
                    status="STALE",
                    candidates=stale_candidates,
                    message=f"Object matching '{query}' ({', '.join(o.object_id for o in stale_candidates)}) is no longer currently visible.",
                )
            return ObjectResolutionResult(
                status="NOT_FOUND",
                message=f"No currently visible object matching '{query}' found.",
            )

        if len(target_pool) > 1:
            # Ambiguity check: do NOT arbitrarily select
            cand_ids = [o.object_id for o in target_pool]
            return ObjectResolutionResult(
                status="AMBIGUOUS",
                candidates=target_pool,
                message=f"Multiple objects matching '{query}' found: [{', '.join(cand_ids)}]. Clarification required.",
            )

        # Exactly 1 candidate
        candidate = target_pool[0]

        # Validate finite coordinates
        if not (math.isfinite(candidate.world_x) and math.isfinite(candidate.world_y) and math.isfinite(candidate.world_z)):
            return ObjectResolutionResult(
                status="INVALID_COORDINATES",
                object=candidate,
                candidates=[candidate],
                message=f"Object '{candidate.object_id}' has non-finite coordinates: ({candidate.world_x}, {candidate.world_y}, {candidate.world_z}).",
            )

        return ObjectResolutionResult(
            status="RESOLVED",
            object=candidate,
            candidates=[candidate],
            message=f"Authoritatively resolved '{query}' to '{candidate.object_id}'.",
        )

    def format_world_objects_context(self, visible_only: bool = False) -> str:
        """
        Formats authoritative persistent world objects into structured context for Gemini prompt.
        """
        objs = self.get_world_objects(visible_only=visible_only)
        if not objs:
            return "WORLD OBJECTS:\n(None currently recorded in persistent world model)"

        now = self.get_robot_context()
        pos = now.get("robot_position") or {}
        rx = float(pos.get("x", 0.0))
        ry = float(pos.get("y", 0.0))
        ryaw = float(pos.get("theta", pos.get("yaw", 0.0)))

        lines = ["WORLD OBJECTS:"]
        for o in objs:
            vis_str = "true" if o.currently_visible else "false"
            lines.append(f"- {o.object_id}")
            lines.append(f"  class: {o.class_name}")
            lines.append(f"  position: ({o.world_x:.3f}, {o.world_y:.3f}, {o.world_z:.3f})")

            # Calculate relative direction and reachability
            dx = o.world_x - rx
            dy = o.world_y - ry
            dist = math.hypot(dx, dy)
            bearing = math.atan2(dy, dx)
            rel_bearing = bearing - ryaw
            while rel_bearing > math.pi: rel_bearing -= 2.0 * math.pi
            while rel_bearing < -math.pi: rel_bearing += 2.0 * math.pi
            rel_deg = math.degrees(rel_bearing)

            if abs(rel_deg) <= 120.0:
                dir_str = f"front / within neck gaze range ({rel_deg:+.0f}°)"
            else:
                dir_str = f"BEHIND ROBOT / outside neck gaze range ({rel_deg:+.0f}°)"

            lines.append(f"  relative_location: {dir_str}, distance: {dist:.2f}m")
            lines.append(f"  confidence: {o.confidence:.2f}")
            lines.append(f"  visible: {vis_str}")
            lines.append(f"  observations: {o.observation_count}")
        return "\n".join(lines)

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves recent chronological events from the SQLite WAL Event Ledger (PAST).
        """
        try:
            resp = requests.get(f"{self.kernel_url}/history?limit={limit}", timeout=self.timeout_sec)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log.debug(f"Failed to fetch ledger history: {e}")
        return []

    def get_graph_context(self) -> Dict[str, Any]:
        """
        Retrieves the relational Knowledge Graph (RELATIONS):
        - Spatial topology (rooms, doorway portals)
        - Grounded object locations (LOCATED_IN edges)
        """
        graph = self.client.get_graph()
        if graph:
            return graph
        return {"nodes": [], "edges": []}

    def query_object_location(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        Directly queries the MNSE Knowledge Graph for an object's location.
        """
        try:
            resp = requests.get(
                f"{self.kernel_url}/graph",
                params={"object": object_name},
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found"):
                    return data.get("result")
        except Exception as e:
            log.debug(f"Graph query failed for '{object_name}': {e}")
        return None

    def get_compiled_context(self, fmt: str = "toon", limit: int = 10) -> str:
        """
        Retrieves context formatted specifically for LLM prompt ingestion.
        Supports 'toon' (Token-Optimized Object Notation) which reduces token usage by 70-80%.
        """
        try:
            resp = requests.get(
                f"{self.kernel_url}/context",
                params={"format": fmt, "limit": limit},
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            log.debug(f"Failed to fetch compiled context ({fmt}): {e}")

        # Fallback to local TOON-like synthesis if kernel format endpoint is unreachable
        now = self.get_robot_context()
        room = now.get("current_room", "Unknown")
        pos = now.get("robot_position") or {}
        x = pos.get("x", 0.0)
        y = pos.get("y", 0.0)
        theta = pos.get("theta", 0.0)
        return f"@NOW:Room[{room}]|Pose[x:{x:.2f},y:{y:.2f},yaw:{math.degrees(theta):.0f}°]"

    def get_current_room(self) -> str:
        """Resolves the current room from authoritative MNSE live state."""
        ctx = self.get_robot_context()
        room = ctx.get("current_room")
        if room and room != "Unknown":
            return room
        # Fallback from position coordinates
        pos = ctx.get("robot_position") or {}
        x = pos.get("x", 0.0)
        y = pos.get("y", 0.0)
        if y > 1.0:
            return "Master Bedroom" if x < 0.0 else "Home Study"
        elif y < -1.0:
            return "Kitchen & Dining" if x < 0.0 else "Living Room"
        else:
            return "Central Hallway"

    def get_all_rooms(self) -> List[Dict[str, Any]]:
        """Queries all apartment rooms from MNSE."""
        return self.client.get_rooms()

    def get_room(self, room: str) -> Optional[Dict[str, Any]]:
        """Queries authoritative room details, exploration status, and object counts."""
        return self.client.get_room(room)

    def get_exploration_status(self) -> Dict[str, Any]:
        """Queries overall apartment exploration status from MNSE."""
        return self.client.get_exploration_status()

    def get_room_objects(self, room: str) -> List[WorldObject]:
        """Queries all persistent world objects located in a designated room."""
        raw_objs = self.client.get_room_objects(room)
        return [WorldObject.from_dict(o) for o in raw_objs]

    def build_grounded_prompt(self, user_command: str) -> str:
        """
        Wraps user command in authoritative MNSE sensory context and persistent world objects.
        Ensures Gemini ER 2 reasons from verified facts.
        """
        toon = self.get_compiled_context(fmt="toon")
        # Strip #OBJECTS from toon to prevent duplicate representation with WORLD OBJECTS
        toon_lines = [line for line in toon.splitlines() if not line.startswith("#OBJECTS:")]
        clean_toon = "\n".join(toon_lines)

        world_objects_str = self.format_world_objects_context(visible_only=False)
        return (
            f"=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            f"{clean_toon}\n\n"
            f"{world_objects_str}\n"
            f"===========================================\n\n"
            f"User Command: \"{user_command}\"\n\n"
            f"MANDATORY PHYSICAL RULES & TOOL SELECTION:\n"
            f"1. Active 2-DOF neck pan limit is ±120°. The neck CANNOT gaze at or reach objects behind the robot.\n"
            f"2. IF AN OBJECT IS BEHIND THE ROBOT (relative_location indicates 'BEHIND ROBOT / outside neck gaze range') "
            f"OR IF THE USER ASKS TO FIND/LOOK AT AN OBJECT BEHIND YOU (e.g. 'Find the chair behind you and look at it'):\n"
            f"   -> YOU MUST CALL turn_toward_object(object_name=...) FIRST to rotate the mobile base to face the object.\n"
            f"   -> DO NOT call find_object when the object is already recorded in WORLD OBJECTS. Call turn_toward_object directly!\n"
            f"   -> DO NOT call look_at_object directly for objects behind you. The neck cannot reach behind.\n"
            f"3. IF AN OBJECT IS IN FRONT (within neck gaze range ±120°):\n"
            f"   -> Call look_at_object(object_name=...).\n"
            f"4. IF AN OBJECT REQUIRES DISTANT NAVIGATION/APPROACH (> 5m):\n"
            f"   -> Call navigate_to_object(object_name=...).\n"
            f"5. Always pass the authoritative object identifier (e.g. 'chair_001') from the WORLD OBJECTS list.\n"
            f"6. Never invent or hallucinate coordinates. 3D coordinates originate strictly from MNSE.\n"
            f"7. Never issue low-level velocity or direct motor commands. Physical motion is handled by the robot substrate.\n"
            f"8. FOR MULTI-ROOM EXPLORATION:\n"
            f"   -> Call explore_room(room_id=...) to autonomously navigate to a specific room, verify arrival, and perform an active visual scan.\n"
            f"   -> Call explore_apartment() to autonomously traverse all reachable unexplored rooms in the apartment and catalog objects into the knowledge graph.\n"
            f"Select the appropriate high-level robot tool to address the user's command."
        )

    def get_latest_camera_frame(self, frame_path: str = "/tmp/gracemo_camera_latest.jpg") -> Optional[bytes]:
        """
        Retrieves the latest live camera observation frame captured by the robot bridge.
        """
        p = Path(frame_path)
        if p.exists():
            try:
                return p.read_bytes()
            except Exception as e:
                log.debug(f"Could not read latest camera frame from {frame_path}: {e}")
        return None

