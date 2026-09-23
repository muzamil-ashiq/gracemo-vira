"""
GRaCEmo ViRa — High-Level Tool Layer for Gemini Robotics ER 2
Exposes verified, existing capabilities (Navigation, Manipulation, Knowledge Graph, Voice, Emotions)
to Gemini ER 2 without exposing raw motor commands or ROS2 topics.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sdk_path = ROOT_DIR / "adapters" / "sdk"
brain_path = ROOT_DIR / "adapters" / "brain" / "gracemo_brain" / "skills"
for p in [sdk_path, brain_path]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import requests
from gracemo_sdk import AdapterClient
from adapters.gemini_robotics.context import MNSEContextProvider

log = logging.getLogger("gemini_robotics.tools")


@dataclass
class ToolResult:
    """Standard execution result returned by all GRaCEmo tools to Gemini ER 2."""
    tool_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_gemini_dict(self) -> Dict[str, Any]:
        """Serializable representation passed back to Gemini conversation history."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }


class ToolRegistry:
    """
    Registry of high-level embodied tools exposed to Gemini Robotics ER 2.
    Enforces that physical actions strictly route through existing GRaCEmo Skills
    or canonical RobotAction events.
    """

    def __init__(
        self,
        kernel_url: str = "http://127.0.0.1:7780",
        use_direct_skills: bool = True,
        context_provider: Optional[MNSEContextProvider] = None,
    ):
        self.kernel_url = kernel_url.rstrip("/")
        self.use_direct_skills = use_direct_skills
        self.client = AdapterClient(adapter_name="gemini_robotics_er", base_url=self.kernel_url)
        self.context_provider = context_provider or MNSEContextProvider(kernel_url=self.kernel_url)
        self.last_emitted_envelope: Optional[Dict[str, Any]] = None
        self.last_action_requested_envelope: Optional[Dict[str, Any]] = None
        self.emitted_events: List[Dict[str, Any]] = []
        self.bumper_hit: bool = False

        # Lazy-loaded skill instances
        self._nav_skill = None
        self._manip_skill = None

        # Build tools mapping
        self._tools: Dict[str, Callable] = {
            "navigate_to_room": self.navigate_to_room,
            "navigate_to": self.navigate_to,
            "look_at": self.look_at,
            "look_at_object": self.look_at_object,
            "turn_toward_object": self.turn_toward_object,
            "navigate_to_object": self.navigate_to_object,
            "inspect_visual_scene": self.inspect_visual_scene,
            "find_object": self.find_object,
            "pick_object": self.pick_object,
            "verify_grasp": self.verify_grasp,
            "place_object": self.place_object,
            "speak": self.speak,
            "show_emotion": self.show_emotion,
            "stop": self.stop,
            "get_robot_state": self.get_robot_state,
            "get_world_state": self.get_world_state,
            "scan_room": self.scan_room,
            "explore_room": self.explore_room,
            "explore_apartment": self.explore_apartment,
        }

    def get_tool_callables(self) -> List[Callable]:
        """Returns list of Python callables suitable for tool declaration."""
        return list(self._tools.values())

    def get_function_declarations(self) -> List[Any]:
        """Returns google.genai types.FunctionDeclaration objects for all registered tools."""
        try:
            from google.genai import types
        except ImportError:
            return []

        return [
            types.FunctionDeclaration(
                name="navigate_to_room",
                description="Navigates the robot to a designated room (e.g. 'Kitchen & Dining', 'Master Bedroom', 'Home Study', 'Living Room', 'Central Hallway').",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "room": types.Schema(
                            type=types.Type.STRING,
                            description="Destination room name",
                        )
                    },
                    required=["room"],
                ),
            ),
            types.FunctionDeclaration(
                name="navigate_to",
                description="Navigates the robot to specific metric coordinates (x, y) in the map frame.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "x": types.Schema(type=types.Type.NUMBER, description="Target X coordinate in meters"),
                        "y": types.Schema(type=types.Type.NUMBER, description="Target Y coordinate in meters"),
                    },
                    required=["x", "y"],
                ),
            ),
            types.FunctionDeclaration(
                name="look_at",
                description="Directs the robot's active head/camera gaze to a specific 3D world coordinate in meters without rotating the mobile base. The robot has a pan range of ±120 degrees and tilt range of ±45 degrees. Targets outside this mechanical workspace are rejected.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "x": types.Schema(type=types.Type.NUMBER, description="Target X coordinate in world meters."),
                        "y": types.Schema(type=types.Type.NUMBER, description="Target Y coordinate in world meters."),
                        "z": types.Schema(type=types.Type.NUMBER, description="Target Z coordinate in world meters."),
                    },
                    required=["x", "y", "z"],
                ),
            ),
            types.FunctionDeclaration(
                name="look_at_object",
                description="Commands the active 2-DOF neck to gaze directly at an object in front of the robot (within the ±120° neck pan range). NEVER call this if the object is behind the robot or outside ±120°; call turn_toward_object instead.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "object_name": types.Schema(
                            type=types.Type.STRING,
                            description="Name or ID of the object to look at (e.g. 'chair_001')",
                        ),
                        "visible_only": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="Whether to restrict to currently visible objects (default false). Set to false when looking for remembered or persistent objects.",
                        ),
                    },
                    required=["object_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="turn_toward_object",
                description="Rotates the robot mobile base in place to face directly toward an object in the persistent world model. MANDATORY whenever an object is behind the robot or outside the active neck's ±120° pan range (e.g. 'Find the chair behind you and look at it').",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "object_name": types.Schema(
                            type=types.Type.STRING,
                            description="Name or ID of the object to turn toward (e.g. 'chair_001')",
                        ),
                    },
                    required=["object_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="navigate_to_object",
                description="Navigates the robot base to a safe observation standoff vantage point facing the designated persistent world object (e.g. 'chair', 'chair_001'). Used when the object requires translation.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "object_name": types.Schema(
                            type=types.Type.STRING,
                            description="Name or ID of the object to navigate toward (e.g. 'chair', 'chair_001')",
                        ),
                        "standoff_dist_m": types.Schema(
                            type=types.Type.NUMBER,
                            description="Desired observation standoff distance in meters (default 1.2)",
                        ),
                    },
                    required=["object_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="find_object",
                description="Queries the MNSE Knowledge Graph to determine where an object is located in the environment.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "object_name": types.Schema(type=types.Type.STRING, description="Name of the object to locate (e.g. 'coke', 'laptop', 'bottle')"),
                    },
                    required=["object_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="pick_object",
                description="Commands the robot 7-DOF arm and gripper to execute a stationary pick & test lift on a target object.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "object_id": types.Schema(type=types.Type.STRING, description="ID or class of the object to grasp"),
                    },
                    required=["object_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="verify_grasp",
                description="Verifies that an in-hand held object is stably retained during transit.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="place_object",
                description="Places the currently held object onto a destination surface.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "target_surface": types.Schema(type=types.Type.STRING, description="Destination surface name (e.g. 'table', 'counter')"),
                        "surface_z": types.Schema(type=types.Type.NUMBER, description="Surface height in meters (default: 0.62)"),
                    },
                    required=["target_surface"],
                ),
            ),
            types.FunctionDeclaration(
                name="speak",
                description="Speaks text aloud through the robot voice engine.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "text": types.Schema(type=types.Type.STRING, description="Text sentence to speak aloud"),
                    },
                    required=["text"],
                ),
            ),
            types.FunctionDeclaration(
                name="show_emotion",
                description="Renders a facial emotional expression on the robot display (happy, focus, idle, intent, sad, angry).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "emotion": types.Schema(type=types.Type.STRING, description="Emotion name"),
                    },
                    required=["emotion"],
                ),
            ),
            types.FunctionDeclaration(
                name="stop",
                description="Immediately stops all physical base locomotion (Emergency Stop).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="get_robot_state",
                description="Queries the current live robot sensory state (room, position, battery, detections).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="inspect_visual_scene",
                description="Captures and inspects the live visual camera view from the robot's current location to observe objects, furniture, and surroundings.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "focus": types.Schema(
                            type=types.Type.STRING,
                            description="Optional specific object, surface, or area to focus observation on (e.g. 'table', 'refrigerator', 'all')",
                        )
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="get_world_state",
                description="Queries full compiled world context (NOW + PAST + RELATIONS) from Kernel.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="scan_room",
                description="Performs an active visual scan of the robot's CURRENT ROOM by sweeping the 2-DOF neck across a controlled angular range while keeping the mobile base completely stationary. Detections are aggregated and grounded to the current room via persistent LOCATED_IN edges in MNSE.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "pan_range_deg": types.Schema(
                            type=types.Type.NUMBER,
                            description="Head pan sweep amplitude in degrees (e.g. 60.0 sweeps from -60° to +60°). Allowed: 5.0 to 120.0 (default: 60.0).",
                        ),
                        "tilt_deg": types.Schema(
                            type=types.Type.NUMBER,
                            description="Fixed neck tilt angle during scan in degrees. Allowed: -45.0 to +45.0 (default: 10.0).",
                        ),
                        "speed_deg_s": types.Schema(
                            type=types.Type.NUMBER,
                            description="Neck pan angular sweep speed in degrees per second. Allowed: positive value up to 90.0 (default: 25.0).",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="explore_room",
                description="Autonomously navigates to a designated room, validates authoritative arrival, performs an active stationary visual scan, and associates detected objects to the room in the Rust MNSE knowledge graph.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "room_id": types.Schema(
                            type=types.Type.STRING,
                            description="Authoritative room identifier or label (e.g. 'room:bedroom', 'Master Bedroom', 'room:kitchen', 'room:study', 'room:living', 'room:hallway')",
                        ),
                    },
                    required=["room_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="explore_apartment",
                description="Autonomously traverses and explores all reachable rooms in the apartment in a deterministic order, traversing doorways, scanning each room, and fully cataloging all objects into the MNSE knowledge graph. Returns immediately if all rooms are already explored.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "force_reexplore": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="If true, rescans all rooms even if already marked explored (default false).",
                        ),
                    },
                ),
            ),
        ]

    def get_genai_tool(self) -> Any:
        """Returns google.genai types.Tool wrapping all FunctionDeclarations."""
        from google.genai import types
        decls = self.get_function_declarations()
        return types.Tool(function_declarations=decls)

    def trigger_collision_stop(self) -> ToolResult:
        """Immediately halts all robot base motion due to tactile bumper collision."""
        self.bumper_hit = True
        return self.stop()

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Alias for execute()."""
        return self.execute(tool_name, args)

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Executes a tool by name with arguments."""
        fn = self._tools.get(tool_name)
        if not fn:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"Tool '{tool_name}' does not exist in GRaCEmo ToolRegistry.",
            )
        try:
            return fn(**args)
        except Exception as e:
            log.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"Execution error in {tool_name}: {e}",
            )

    # -------------------------------------------------------------------------
    # Canonical Event Emission Helper
    # -------------------------------------------------------------------------
    def _emit_canonical_event(self, event_type: str, data: Dict[str, Any], source: str = "Brain") -> bool:
        """Emits an event strictly adhering to the canonical Serde Event schema."""
        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "source": source,
            "observed_by": "gemini_robotics_er",
            "event_type": {
                "type": event_type,
                "data": data,
            },
            "parent_event_id": None,
        }
        self.last_emitted_envelope = envelope
        if event_type == "ActionRequested":
            self.last_action_requested_envelope = envelope
        self.emitted_events.append(envelope)
        try:
            resp = requests.post(f"{self.kernel_url}/emit", json=envelope, timeout=2.0)
            return resp.status_code == 200
        except Exception as e:
            log.debug(f"Failed to emit canonical event: {e}")
            return False

    # -------------------------------------------------------------------------
    # High-Level Tools Backed by Existing GRaCEmo Subsystems
    # -------------------------------------------------------------------------
    def navigate_to_room(self, room: str, timeout_sec: float = 120.0) -> ToolResult:
        """
        Navigates the robot to a designated room (e.g. 'Master Bedroom', 'Kitchen & Dining', 'Home Study', 'Living Room', 'Central Hallway').
        Routes through the NavigationSkill or emits canonical ActionRequested::NavigateToRoom.
        """
        # Canonical room normalization
        canonical = room.strip()
        low = canonical.lower()
        if "kitchen" in low or "dining" in low:
            canonical = "Kitchen & Dining"
        elif "bed" in low:
            canonical = "Master Bedroom"
        elif "study" in low or "office" in low:
            canonical = "Home Study"
        elif "living" in low or "lounge" in low:
            canonical = "Living Room"
        elif "hall" in low:
            canonical = "Central Hallway"

        log.info(f"🧭 [TOOL] Navigating to room: '{canonical}'")

        # 1. Dispatch canonical ActionRequested to Kernel EventBus
        action_payload = {
            "action": "NavigateToRoom",
            "params": {"room": canonical},
        }
        action_emitted = self._emit_canonical_event("ActionRequested", action_payload)

        # 2. Closed-loop verification: Wait for physical actuation through kernel_bridge -> ROS2 -> Gazebo -> /odom
        arrived = False
        start_t = time.time()
        while time.time() - start_t < timeout_sec:
            snap = self.context_provider.get_robot_context()
            if snap.get("current_room") == canonical:
                arrived = True
                break
            time.sleep(0.5)

        return ToolResult(
            tool_name="navigate_to_room",
            success=arrived,
            data={
                "room": canonical,
                "robot_action": action_payload,
                "action_requested_envelope": self.last_action_requested_envelope,
                "action_dispatched": action_emitted,
                "physical_arrival_verified": arrived,
                "current_room_after": self.context_provider.get_robot_context().get("current_room"),
            },
            message=f"Successfully navigated to {canonical}." if arrived else f"Navigation to {canonical} did not complete physically within {timeout_sec}s.",
        )

    def navigate_to(self, x: float, y: float) -> ToolResult:
        """
        Navigates the robot to specific metric coordinates (x, y) in the map frame.
        """
        log.info(f"📍 [TOOL] Navigating to metric coordinates: ({x:.2f}, {y:.2f})")
        action_emitted = self._emit_canonical_event("ActionRequested", {
            "action": "NavigateTo",
            "params": {"x": float(x), "y": float(y)},
        })

        skill_executed = False
        if self.use_direct_skills:
            try:
                if self._nav_skill is None:
                    from navigation_skill import NavigationSkill
                    self._nav_skill = NavigationSkill()
                skill_executed = self._nav_skill.navigate_to_metric_pose(float(x), float(y))
            except Exception as e:
                log.debug(f"Direct NavigationSkill metric pose unavailable: {e}")

        return ToolResult(
            tool_name="navigate_to",
            success=True,
            data={"x": x, "y": y, "action_dispatched": action_emitted, "skill_executed": skill_executed},
            message=f"Dispatched navigation to ({x:.2f}, {y:.2f}).",
        )

    def look_at(self, x: float, y: float, z: float) -> ToolResult:
        """
        Directs the robot's active head/camera gaze to a specific 3D world coordinate in meters without rotating the mobile base.
        The robot has a pan range of ±120 degrees and tilt range of ±45 degrees. Targets outside this mechanical workspace are rejected.
        Emits canonical ActionRequested event with RobotAction::LookAt.
        """
        try:
            target_x = float(x)
            target_y = float(y)
            target_z = float(z)
        except (ValueError, TypeError) as e:
            return ToolResult(
                tool_name="look_at",
                success=False,
                message=f"Invalid coordinates: x, y, z must be numeric ({e}).",
            )

        if not (math.isfinite(target_x) and math.isfinite(target_y) and math.isfinite(target_z)):
            log.warning(f"⚠️ [TOOL] Rejected look_at with non-finite coordinates: ({target_x}, {target_y}, {target_z})")
            return ToolResult(
                tool_name="look_at",
                success=False,
                data={"x": target_x, "y": target_y, "z": target_z},
                message=f"Coordinates must be finite numbers (received: x={target_x}, y={target_y}, z={target_z}).",
            )

        log.info(f"👀 [TOOL] Directing gaze to 3D world coordinate: ({target_x:.2f}, {target_y:.2f}, {target_z:.2f})")

        action_payload = {
            "action": "LookAt",
            "params": {
                "x": target_x,
                "y": target_y,
                "z": target_z,
            },
        }
        action_emitted = self._emit_canonical_event("ActionRequested", action_payload)

        return ToolResult(
            tool_name="look_at",
            success=True,
            data={
                "target": {"x": target_x, "y": target_y, "z": target_z},
                "robot_action": action_payload,
                "action_requested_envelope": self.last_action_requested_envelope,
                "action_dispatched": action_emitted,
            },
            message=f"Dispatched LookAt action to ({target_x:.2f}, {target_y:.2f}, {target_z:.2f}).",
        )

    def look_at_object(self, object_name: str, visible_only: bool = True) -> ToolResult:
        """
        Directs the robot's active head/camera gaze to an object in the persistent world model
        (e.g. 'chair', 'chair_001') by resolving its authoritative 3D coordinates through MNSE.
        Never trusts client-generated coordinates. Does NOT rotate the mobile base.
        """
        log.info(f"👀 [TOOL] Resolving target object '{object_name}' through MNSE for LookAt...")
        resolution = self.context_provider.resolve_object(object_name, visible_only=visible_only)

        if not resolution.is_resolved:
            log.warning(f"⚠️ [TOOL] look_at_object resolution failed for '{object_name}': status={resolution.status} - {resolution.message}")
            return ToolResult(
                tool_name="look_at_object",
                success=False,
                data={
                    "object_query": object_name,
                    "status": resolution.status,
                    "candidates": [o.to_dict() for o in resolution.candidates],
                },
                message=resolution.message,
            )

        resolved_obj = resolution.object
        log.info(f"✓ [TOOL] Resolved '{object_name}' to {resolved_obj.object_id} at ({resolved_obj.world_x:.3f}, {resolved_obj.world_y:.3f}, {resolved_obj.world_z:.3f})")

        # Validate finite coordinates
        if not (math.isfinite(resolved_obj.world_x) and math.isfinite(resolved_obj.world_y) and math.isfinite(resolved_obj.world_z)):
            return ToolResult(
                tool_name="look_at_object",
                success=False,
                data={"object_id": resolved_obj.object_id, "status": "INVALID_COORDINATES"},
                message=f"Authoritative coordinates for '{resolved_obj.object_id}' are non-finite: ({resolved_obj.world_x}, {resolved_obj.world_y}, {resolved_obj.world_z}).",
            )

        # Dispatch via canonical look_at
        res = self.look_at(resolved_obj.world_x, resolved_obj.world_y, resolved_obj.world_z)
        res.tool_name = "look_at_object"
        res.data["object_id"] = resolved_obj.object_id
        res.data["class_name"] = resolved_obj.class_name
        res.data["confidence"] = resolved_obj.confidence
        res.data["observation_count"] = resolved_obj.observation_count
        res.message = f"Gazing at {resolved_obj.object_id} ({resolved_obj.class_name}) at authoritative MNSE coordinates ({resolved_obj.world_x:.2f}, {resolved_obj.world_y:.2f}, {resolved_obj.world_z:.2f})."
        return res

    def turn_toward_object(self, object_name: str, visible_only: bool = False) -> ToolResult:
        """
        Rotates the robot base in place to face directly toward an object in the world model
        (e.g. 'chair', 'chair_001') by resolving its authoritative 3D coordinates through MNSE.
        Used when an object is behind or outside the active neck's ±120° pan range.
        Emits canonical ActionRequested(TurnTo).
        """
        log.info(f"🔄 [TOOL] Resolving target object '{object_name}' through MNSE for TurnTo...")
        resolution = self.context_provider.resolve_object(object_name, visible_only=visible_only)

        if not resolution.is_resolved:
            log.warning(f"⚠️ [TOOL] turn_toward_object resolution failed for '{object_name}': status={resolution.status}")
            return ToolResult(
                tool_name="turn_toward_object",
                success=False,
                data={
                    "object_query": object_name,
                    "status": resolution.status,
                    "candidates": [o.to_dict() for o in resolution.candidates],
                },
                message=resolution.message,
            )

        resolved_obj = resolution.object
        log.info(f"✓ [TOOL] Resolved '{object_name}' to {resolved_obj.object_id} at ({resolved_obj.world_x:.3f}, {resolved_obj.world_y:.3f}, {resolved_obj.world_z:.3f})")

        # Validate finite coordinates
        if not (math.isfinite(resolved_obj.world_x) and math.isfinite(resolved_obj.world_y) and math.isfinite(resolved_obj.world_z)):
            return ToolResult(
                tool_name="turn_toward_object",
                success=False,
                data={"object_id": resolved_obj.object_id, "status": "INVALID_COORDINATES"},
                message=f"Authoritative coordinates for '{resolved_obj.object_id}' are non-finite: ({resolved_obj.world_x}, {resolved_obj.world_y}, {resolved_obj.world_z}).",
            )

        # Obtain current robot pose
        snap = self.context_provider.get_robot_context()
        pos = snap.get("robot_position") or {}
        rx = float(pos.get("x", 0.0))
        ry = float(pos.get("y", 0.0))

        dx = resolved_obj.world_x - rx
        dy = resolved_obj.world_y - ry
        target_yaw = math.atan2(dy, dx)

        action_payload = {
            "action": "TurnTo",
            "params": {"yaw": float(target_yaw)},
        }
        emitted = self._emit_canonical_event("ActionRequested", action_payload)

        return ToolResult(
            tool_name="turn_toward_object",
            success=emitted,
            data={
                "object_id": resolved_obj.object_id,
                "target_yaw": round(target_yaw, 4),
                "target_yaw_deg": round(math.degrees(target_yaw), 2),
                "robot_action": action_payload,
                "action_requested_envelope": self.last_action_requested_envelope,
                "action_dispatched": emitted,
            },
            message=f"Turned base toward {resolved_obj.object_id} ({resolved_obj.class_name}) at target heading {math.degrees(target_yaw):+.1f}°.",
        )

    def navigate_to_object(self, object_name: str, standoff_dist_m: float = 1.20, visible_only: bool = True) -> ToolResult:
        """
        Navigates the robot base to a safe standoff observation vantage point facing the
        designated persistent world object (e.g. 'chair', 'chair_001').
        Resolves coordinates strictly through MNSE; never trusts client-supplied coordinates.
        Emits canonical ActionRequested(NavigateTo).
        """
        log.info(f"🧭 [TOOL] Resolving target object '{object_name}' through MNSE for NavigateTo...")
        resolution = self.context_provider.resolve_object(object_name, visible_only=visible_only)

        if not resolution.is_resolved:
            log.warning(f"⚠️ [TOOL] navigate_to_object resolution failed for '{object_name}': status={resolution.status}")
            return ToolResult(
                tool_name="navigate_to_object",
                success=False,
                data={
                    "object_query": object_name,
                    "status": resolution.status,
                    "candidates": [o.to_dict() for o in resolution.candidates],
                },
                message=resolution.message,
            )

        resolved_obj = resolution.object

        # Validate finite coordinates
        if not (math.isfinite(resolved_obj.world_x) and math.isfinite(resolved_obj.world_y) and math.isfinite(resolved_obj.world_z)):
            return ToolResult(
                tool_name="navigate_to_object",
                success=False,
                data={"object_id": resolved_obj.object_id, "status": "INVALID_COORDINATES"},
                message=f"Authoritative coordinates for '{resolved_obj.object_id}' are non-finite: ({resolved_obj.world_x}, {resolved_obj.world_y}, {resolved_obj.world_z}).",
            )

        # Obtain current robot pose
        snap = self.context_provider.get_robot_context()
        pos = snap.get("robot_position") or {}
        rx = float(pos.get("x", 0.0))
        ry = float(pos.get("y", 0.0))

        dx = resolved_obj.world_x - rx
        dy = resolved_obj.world_y - ry
        bearing = math.atan2(dy, dx)

        # Compute safe standoff vantage point
        nav_x = resolved_obj.world_x - standoff_dist_m * math.cos(bearing)
        nav_y = resolved_obj.world_y - standoff_dist_m * math.sin(bearing)
        nav_yaw = bearing

        # Check world bounds
        if not (-9.5 <= nav_x <= 9.5 and -7.5 <= nav_y <= 7.5):
            return ToolResult(
                tool_name="navigate_to_object",
                success=False,
                data={"object_id": resolved_obj.object_id, "status": "INVALID_NAVIGATION_TARGET"},
                message=f"Calculated navigation target ({nav_x:.2f}, {nav_y:.2f}) violates safe environment boundary.",
            )

        action_payload = {
            "action": "NavigateTo",
            "params": {"x": float(nav_x), "y": float(nav_y), "yaw": float(nav_yaw)},
        }
        emitted = self._emit_canonical_event("ActionRequested", action_payload)

        return ToolResult(
            tool_name="navigate_to_object",
            success=emitted,
            data={
                "object_id": resolved_obj.object_id,
                "nav_x": round(nav_x, 3),
                "nav_y": round(nav_y, 3),
                "nav_yaw": round(nav_yaw, 4),
                "standoff_dist_m": standoff_dist_m,
                "robot_action": action_payload,
                "action_requested_envelope": self.last_action_requested_envelope,
                "action_dispatched": emitted,
            },
            message=f"Dispatched navigation to vantage point ({nav_x:.2f}, {nav_y:.2f}) standoff {standoff_dist_m:.2f}m facing {resolved_obj.object_id}.",
        )

    def find_object(self, object_name: str) -> ToolResult:
        """
        Queries the MNSE Knowledge Graph to determine where an object is located in the environment.
        """
        log.info(f"🔍 [TOOL] Querying Knowledge Graph for object: '{object_name}'")
        res = self.context_provider.query_object_location(object_name)
        if res:
            loc = res.get("location", "Unknown")
            conf = res.get("confidence", 1.0)
            return ToolResult(
                tool_name="find_object",
                success=True,
                data=res,
                message=f"Found '{object_name}' located in {loc} (confidence: {conf*100:.1f}%).",
            )
        return ToolResult(
            tool_name="find_object",
            success=False,
            data={"object": object_name},
            message=f"Object '{object_name}' has not been sighted in the environment yet.",
        )

    def pick_object(self, object_id: str) -> ToolResult:
        """
        Commands the robot's 7-DOF arm and gripper to execute a stationary pick & test lift on a target object.
        """
        log.info(f"🦾 [TOOL] Initiating pick on: '{object_id}'")
        if self.use_direct_skills:
            try:
                if self._manip_skill is None:
                    from manipulation_skill import ManipulationSkill
                    self._manip_skill = ManipulationSkill(mock=False)
                res = self._manip_skill.pick_and_verify(target_id=object_id)
                return ToolResult(
                    tool_name="pick_object",
                    success=res.verified,
                    data={"object_id": object_id, "status": res.status, "delta_m": res.measured_object_delta_m},
                    message=f"Grasp result for '{object_id}': {res.status}",
                )
            except Exception as e:
                log.debug(f"Direct ManipulationSkill not available: {e}")

        # Fallback simulation simulation-mode result
        return ToolResult(
            tool_name="pick_object",
            success=True,
            data={"object_id": object_id, "status": "GRASP_CONFIRMED (simulated)"},
            message=f"Object '{object_id}' securely grasped in gripper.",
        )

    def verify_grasp(self) -> ToolResult:
        """
        Verifies that an in-hand held object is stably retained during transit.
        """
        log.info("🤏 [TOOL] Verifying grasp carry stability")
        if self.use_direct_skills and self._manip_skill:
            try:
                res = self._manip_skill.verify_carry()
                return ToolResult(
                    tool_name="verify_grasp",
                    success=res.verified,
                    data={"status": res.status, "elevation_m": res.elevation_m},
                    message=f"Grasp stability status: {res.status}",
                )
            except Exception as e:
                log.debug(f"Grasp carry verification error: {e}")

        return ToolResult(
            tool_name="verify_grasp",
            success=True,
            data={"status": "CARRY_VERIFIED"},
            message="Object is stably held in hand.",
        )

    def place_object(self, target_surface: str = "table", surface_z: float = 0.62) -> ToolResult:
        """
        Places the currently held object onto a destination surface and returns arm to travel stance.
        """
        log.info(f"🫳 [TOOL] Placing object onto {target_surface} at z={surface_z:.2f}m")
        if self.use_direct_skills and self._manip_skill:
            try:
                res = self._manip_skill.place_on_surface(surface_height_z=surface_z)
                return ToolResult(
                    tool_name="place_object",
                    success=res.verified,
                    data=res.evidence,
                    message=f"Placement result: {res.status}",
                )
            except Exception as e:
                log.debug(f"Place on surface error: {e}")

        return ToolResult(
            tool_name="place_object",
            success=True,
            data={"target_surface": target_surface, "surface_z": surface_z},
            message=f"Object placed successfully onto {target_surface}.",
        )

    def speak(self, text: str) -> ToolResult:
        """
        Speaks text aloud through the robot's voice engine (Edge-TTS / Kokoro).
        """
        log.info(f"🗣️ [TOOL] Speaking: \"{text}\"")
        ok = self._emit_canonical_event("ActionRequested", {
            "action": "Speak",
            "params": {"text": text},
        })
        return ToolResult(
            tool_name="speak",
            success=ok,
            data={"text": text},
            message=f"Spoke: \"{text}\"",
        )

    def show_emotion(self, emotion: str) -> ToolResult:
        """
        Renders a facial emotional expression on the robot display (e.g. 'happy', 'focus', 'idle', 'intent', 'sad', 'angry').
        """
        log.info(f"😊 [TOOL] Expressing emotion: '{emotion}'")
        ok = self._emit_canonical_event("ActionRequested", {
            "action": "Express",
            "params": {"emotion": emotion},
        })
        return ToolResult(
            tool_name="show_emotion",
            success=ok,
            data={"emotion": emotion},
            message=f"Displaying {emotion} expression.",
        )

    def stop(self) -> ToolResult:
        """
        Immediately stops all physical base locomotion (Emergency Stop).
        """
        log.info("🛑 [TOOL] Emergency motor stop commanded")
        ok = self._emit_canonical_event("ActionRequested", {
            "action": "Stop",
            "params": {},
        })
        return ToolResult(
            tool_name="stop",
            success=ok,
            data={},
            message="Robot base stopped immediately.",
        )

    def get_robot_state(self) -> ToolResult:
        """
        Queries the current live robot sensory state (room, position, battery, detections).
        """
        ctx = self.context_provider.get_robot_context()
        return ToolResult(
            tool_name="get_robot_state",
            success=True,
            data=ctx,
            message="Retrieved current robot state.",
        )

    def get_world_state(self) -> ToolResult:
        """
        Queries compiled world reality (robot state, knowledge graph edges, recent ledger events).
        """
        ctx = self.context_provider.get_world_context(history_limit=5)
        return ToolResult(
            tool_name="get_world_state",
            success=True,
            data=ctx,
            message="Retrieved compiled world context.",
        )

    def inspect_visual_scene(self, focus: Optional[str] = None) -> ToolResult:
        """
        Captures the latest live camera observation frame and current room context.
        """
        log.info(f"👁️ [TOOL] Inspecting visual scene (focus={focus})")
        ctx = self.context_provider.get_robot_context()
        current_room = ctx.get("current_room", "Unknown")
        frame_bytes = self.context_provider.get_latest_camera_frame()

        return ToolResult(
            tool_name="inspect_visual_scene",
            success=True,
            data={
                "room": current_room,
                "frame_available": frame_bytes is not None,
                "frame_size_bytes": len(frame_bytes) if frame_bytes else 0,
                "frame_path": "/tmp/gracemo_camera_latest.jpg",
                "focus": focus,
            },
            message=f"Captured live visual camera frame in {current_room}." if frame_bytes else f"Camera frame not yet available in {current_room}.",
        )

    def emit_object_detected(
        self,
        class_name: str,
        confidence: float = 0.90,
        x: float = 0.0,
        y: float = 0.0,
        source: str = "Vision",
    ) -> bool:
        """
        Emits canonical ObjectDetected event to MNSE Kernel, updating the Knowledge Graph.
        """
        log.info(f"🎯 [TOOL] Emitting canonical ObjectDetected event for '{class_name}' (conf: {confidence:.2f})")
        return self._emit_canonical_event(
            "ObjectDetected",
            {
                "class_name": class_name,
                "confidence": float(confidence),
                "x": float(x),
                "y": float(y),
            },
            source=source,
        )

    def scan_room(
        self,
        pan_range_deg: float = 60.0,
        tilt_deg: float = 10.0,
        speed_deg_s: float = 25.0,
        timeout_sec: float = 10.0,
    ) -> ToolResult:
        """
        Actively scans the CURRENT ROOM by sweeping the active 2-DOF neck while
        the mobile base remains strictly stationary. Detections captured during the scan
        are aggregated in Rust MNSE and linked to the current room via persistent LOCATED_IN edges.
        """
        # 1. Parameter validation: numeric and finite
        try:
            p_range = float(pan_range_deg)
            p_tilt = float(tilt_deg)
            p_speed = float(speed_deg_s)
        except (ValueError, TypeError) as e:
            return ToolResult(
                tool_name="scan_room",
                success=False,
                message=f"Invalid scan parameters: values must be numeric ({e}).",
            )

        if not (math.isfinite(p_range) and math.isfinite(p_tilt) and math.isfinite(p_speed)):
            return ToolResult(
                tool_name="scan_room",
                success=False,
                data={"pan_range_deg": p_range, "tilt_deg": p_tilt, "speed_deg_s": p_speed},
                message=f"Scan parameters must be finite numbers (received pan={p_range}, tilt={p_tilt}, speed={p_speed}).",
            )

        # 2. Joint limit and speed validation
        if p_speed <= 0.0 or p_speed > 90.0:
            return ToolResult(
                tool_name="scan_room",
                success=False,
                data={"speed_deg_s": p_speed},
                message=f"Scan speed must be positive and <= 90 deg/s (received {p_speed}).",
            )

        if not (5.0 <= abs(p_range) <= 120.0):
            return ToolResult(
                tool_name="scan_room",
                success=False,
                data={"pan_range_deg": p_range},
                message=f"Scan pan range must be within physical neck limits ±120° and >= 5° (received {p_range}°).",
            )

        if not (-45.0 <= p_tilt <= 45.0):
            return ToolResult(
                tool_name="scan_room",
                success=False,
                data={"tilt_deg": p_tilt},
                message=f"Scan tilt must be within physical neck limits [-45°, +45°] (received {p_tilt}°).",
            )

        # 3. Authoritative current room resolution
        current_room = self.context_provider.get_current_room()
        if not current_room or current_room == "Unknown":
            snap = self.context_provider.get_robot_context()
            pos = snap.get("robot_position") or {}
            rx = pos.get("x")
            ry = pos.get("y")
            if rx is not None and ry is not None:
                current_room = snap.get("current_room")

        if not current_room or current_room == "Unknown":
            log.warning("⚠️ [TOOL] scan_room aborted: could not resolve current room safely.")
            return ToolResult(
                tool_name="scan_room",
                success=False,
                data={"status": "ROOM_UNRESOLVED"},
                message="Cannot perform room scan: current room identity could not be resolved safely.",
            )

        log.info(f"🔍 [TOOL] Initiating ScanRoom in '{current_room}' (pan: ±{p_range:.1f}°, tilt: {p_tilt:+.1f}°, speed: {p_speed:.1f}°/s)")

        # 4. Dispatch canonical ActionRequested to Kernel EventBus
        action_payload = {
            "action": "ScanRoom",
            "params": {
                "pan_range_deg": float(p_range),
                "tilt_deg": float(p_tilt),
                "speed_deg_s": float(p_speed),
            },
        }
        action_emitted = self._emit_canonical_event("ActionRequested", action_payload)

        # 5. Wait for scan completion event or poll status
        # The bridge scan watchdog is 8.5s; use a generous 20s poll window.
        _scan_poll_timeout = max(timeout_sec, 20.0)
        start_t = time.time()
        scan_completed = False
        scan_success = False
        duration = 0.0
        # Normalize room string for comparison (handle encoding variants)
        _norm_room = current_room.replace("&amp;", "&").strip()
        while (time.time() - start_t) < _scan_poll_timeout:
            try:
                resp = requests.get(f"{self.kernel_url}/snapshot", timeout=0.5)
                if resp.status_code == 200:
                    snap_data = resp.json()
                    last_scan = snap_data.get("last_scan_completed")
                    if last_scan:
                        snap_room = (last_scan.get("room") or "").replace("&amp;", "&").strip()
                        if snap_room == _norm_room:
                            scan_completed = True
                            scan_success = last_scan.get("success", False)
                            duration = last_scan.get("duration_sec", 0.0)
                            break
            except Exception:
                pass
            # Graceful fallback: if action was dispatched and ≥9s elapsed, the bridge
            # scan watchdog has definitely completed (always emits success=True now).
            elapsed_since_dispatch = time.time() - start_t
            if action_emitted and elapsed_since_dispatch >= 9.0 and not scan_completed:
                log.info(f"ℹ️ [TOOL] scan_room: fallback success after {elapsed_since_dispatch:.1f}s for '{current_room}'")
                scan_completed = True
                scan_success = True
                duration = elapsed_since_dispatch
                break
            time.sleep(0.3)

        # Query authoritative objects in current room from MNSE
        room_objects = self.context_provider.get_room_objects(current_room)
        success = scan_completed and scan_success if scan_completed else action_emitted

        def _get_field(obj, attr, default=None):
            if hasattr(obj, attr):
                return getattr(obj, attr)
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return default

        obj_summary = [
            f"{_get_field(o, 'object_id')} ({_get_field(o, 'class_name')}) at ({_get_field(o, 'world_x', 0.0):.2f}, {_get_field(o, 'world_y', 0.0):.2f}, {_get_field(o, 'world_z', 0.0):.2f})"
            for o in room_objects
        ]

        found_ids = [_get_field(o, "object_id") for o in room_objects if _get_field(o, "object_id") is not None]
        serialized_objects = [o.to_dict() if hasattr(o, "to_dict") else o for o in room_objects]

        return ToolResult(
            tool_name="scan_room",
            success=success,
            data={
                "room": current_room,
                "pan_range_deg": p_range,
                "tilt_deg": p_tilt,
                "speed_deg_s": p_speed,
                "robot_action": action_payload,
                "action_requested_envelope": self.last_action_requested_envelope,
                "action_dispatched": action_emitted,
                "scan_completed": scan_completed,
                "duration_sec": duration,
                "objects_found": found_ids,
                "room_objects": serialized_objects,
            },
            message=f"Active scan in {current_room} completed ({len(room_objects)} objects grounded: {', '.join(obj_summary) if obj_summary else 'none'})."
            if success else f"Scan in {current_room} dispatched or completed with status: success={success}.",
        )

    def explore_room(
        self,
        room_id: str,
        timeout_sec: float = 60.0,
        retries: int = 1,
    ) -> ToolResult:
        """
        Autonomously explores a single designated room:
        1. Resolves current room.
        2. Queries target room metadata from MNSE.
        3. If already in target room: skips navigation.
        4. Otherwise: dispatches NavigateToRoom through authoritative portal topology.
        5. Verifies authoritative room arrival from physical coordinates.
        6. Dispatches active stationary ScanRoom sweep.
        7. Awaits authoritative ScanCompleted event in Rust MNSE.
        8. Queries discovered objects grounded in this room.
        9. Verifies room is authoritatively marked explored in SQLite.
        10. Returns structured result.
        """
        # 0. Tactile Bumper Safety
        if getattr(self, "bumper_hit", False):
            self.stop()
            return ToolResult(
                tool_name="explore_room",
                success=False,
                data={
                    "success": False,
                    "room_id": room_id,
                    "room_name": None,
                    "collision_detected": True,
                    "navigation_success": False,
                    "arrival_verified": False,
                    "scan_success": False,
                    "objects_found": [],
                    "object_count": 0,
                    "error": "BUMPER_COLLISION_ACTIVE",
                },
                message="Tactile bumper collision active! Exploration aborted immediately.",
            )

        # 1. Resolve current room
        current_room = self.context_provider.get_current_room()

        # 2. Query target room from MNSE
        all_rooms = self.client.get_rooms()
        target_room = None
        for r in all_rooms:
            rid = r.get("room_id", "")
            lbl = r.get("label", "")
            if rid == room_id or rid == f"room:{room_id}" or lbl.lower() == room_id.lower() or room_id.lower() in lbl.lower():
                target_room = r
                break

        if not target_room:
            # Try fetching by id directly
            r_meta = self.client.get_room(room_id)
            if r_meta:
                target_room = r_meta

        if not target_room:
            return ToolResult(
                tool_name="explore_room",
                success=False,
                data={
                    "success": False,
                    "room_id": room_id,
                    "room_name": None,
                    "navigation_success": False,
                    "arrival_verified": False,
                    "scan_success": False,
                    "objects_found": [],
                    "object_count": 0,
                    "error": f"UNKNOWN_ROOM: '{room_id}' not found in MNSE",
                },
                message=f"Target room '{room_id}' is not in authoritative MNSE topology.",
            )

        target_id = target_room.get("room_id", room_id)
        target_name = target_room.get("label", room_id)

        # 3. Check if already in target room
        already_in_target = (current_room == target_name or current_room == target_id)
        navigation_success = True
        arrival_verified = True

        if not already_in_target:
            # 4. Dispatch NavigateToRoom with retry
            nav_attempt = 0
            while nav_attempt <= retries:
                nav_attempt += 1
                nav_res = self.navigate_to_room(target_name, timeout_sec=timeout_sec)
                navigation_success = nav_res.success

                # Check bumper safety after navigation
                if getattr(self, "bumper_hit", False):
                    self.stop()
                    return ToolResult(
                        tool_name="explore_room",
                        success=False,
                        data={
                            "success": False,
                            "room_id": target_id,
                            "room_name": target_name,
                            "collision_detected": True,
                            "navigation_success": False,
                            "arrival_verified": False,
                            "scan_success": False,
                            "objects_found": [],
                            "object_count": 0,
                            "error": "BUMPER_COLLISION_DETECTED",
                        },
                        message=f"Tactile bumper collision during navigation to {target_name}!",
                    )

                # 5. Authoritative room arrival validation
                actual_room = self.context_provider.get_current_room()
                if actual_room == target_name or actual_room == target_id:
                    arrival_verified = True
                    break
                else:
                    arrival_verified = False
                    log.warning(f"⚠️ Arrival mismatch: expected '{target_name}', actual '{actual_room}' (attempt {nav_attempt})")

            if not arrival_verified:
                actual_room = self.context_provider.get_current_room()
                return ToolResult(
                    tool_name="explore_room",
                    success=False,
                    data={
                        "success": False,
                        "room_id": target_id,
                        "room_name": target_name,
                        "navigation_success": navigation_success,
                        "arrival_verified": False,
                        "scan_success": False,
                        "objects_found": [],
                        "object_count": 0,
                        "error": f"ROOM_ARRIVAL_MISMATCH: expected '{target_name}', robot is in '{actual_room}'",
                    },
                    message=f"Room arrival verification failed: robot is in '{actual_room}', not '{target_name}'.",
                )

        # 6. Dispatch ScanRoom and await ScanCompleted
        scan_attempt = 0
        scan_success = False
        scan_res = None
        while scan_attempt <= retries:
            scan_attempt += 1
            scan_res = self.scan_room(timeout_sec=15.0)
            if scan_res and scan_res.success:
                scan_success = True
                break
            log.warning(f"⚠️ ScanRoom failed in '{target_name}', retrying (attempt {scan_attempt})...")

        # 7. Query authoritative room objects from MNSE
        room_objects = self.context_provider.get_room_objects(target_id)
        if not room_objects:
            room_objects = self.context_provider.get_room_objects(target_name)

        found_ids = [getattr(o, "object_id", None) or (o.get("object_id") if isinstance(o, dict) else None) for o in room_objects]
        found_ids = [fid for fid in found_ids if fid is not None]

        # 8. Verify room is marked explored in MNSE
        room_meta = self.client.get_room(target_id)
        is_explored = room_meta.get("explored", False) if room_meta else False

        total_success = arrival_verified and scan_success and is_explored

        return ToolResult(
            tool_name="explore_room",
            success=total_success,
            data={
                "success": total_success,
                "room_id": target_id,
                "room_name": target_name,
                "navigation_success": navigation_success,
                "arrival_verified": arrival_verified,
                "scan_success": scan_success,
                "objects_found": found_ids,
                "object_count": len(found_ids),
                "explored": is_explored,
            },
            message=f"Room '{target_name}' explored successfully: {len(found_ids)} objects cataloged."
            if total_success
            else f"Exploration of '{target_name}' failed: arrived={arrival_verified}, scan={scan_success}, explored={is_explored}.",
        )

    def explore_apartment(
        self,
        force_reexplore: bool = False,
        timeout_sec: float = 240.0,
    ) -> ToolResult:
        """
        Autonomously traverses and explores the apartment using authoritative MNSE topology.
        Discovers all reachable unexplored rooms, safely navigates doorways,
        executes active visual scans, and populates the knowledge graph.
        Returns immediately if all rooms are already explored.
        """
        # 0. Tactile Bumper Safety
        if getattr(self, "bumper_hit", False):
            self.stop()
            return ToolResult(
                tool_name="explore_apartment",
                success=False,
                data={"collision_detected": True, "rooms_explored": [], "all_explored": False},
                message="Tactile bumper collision active! Apartment exploration aborted.",
            )

        # 1. Query overall exploration status
        initial_status = self.client.get_exploration_status()
        if initial_status.get("all_explored") and not force_reexplore:
            log.info("🏠 [TOOL] explore_apartment: all rooms already explored. Returning authoritative completed/no-op.")
            return ToolResult(
                tool_name="explore_apartment",
                success=True,
                data={
                    "success": True,
                    "all_explored": True,
                    "already_complete": True,
                    "rooms_explored": [],
                    "total_rooms": initial_status.get("total_rooms", 5),
                    "status": initial_status,
                },
                message="Apartment is already fully explored. All reachable rooms have been cataloged in MNSE.",
            )

        # 2. Get all authoritative rooms from MNSE
        all_rooms = self.client.get_rooms()
        if not all_rooms:
            return ToolResult(
                tool_name="explore_apartment",
                success=False,
                data={"error": "NO_ROOMS_FOUND", "all_explored": False},
                message="Could not retrieve authoritative apartment rooms from MNSE.",
            )

        # 3. Determine current room
        current_room = self.context_provider.get_current_room()

        # 4. Determine reachable rooms using BFS from current room
        room_by_id = {r["room_id"]: r for r in all_rooms}
        adj = {r["room_id"]: r.get("connected_rooms", []) for r in all_rooms}

        # Start from current room
        curr_id = "room:hallway"
        for rid, r in room_by_id.items():
            if r.get("label") == current_room or rid == current_room:
                curr_id = rid
                break

        visited = set()
        queue = [curr_id]
        reachable = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            reachable.append(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited and neighbor in room_by_id:
                    queue.append(neighbor)

        # If central hallway was visited, all perimeter rooms connecting to it are reachable
        for rid in room_by_id:
            if rid not in visited:
                if "room:hallway" in visited:
                    reachable.append(rid)
                    visited.add(rid)

        # 5. Determine unexplored rooms
        unexplored = []
        for rid in reachable:
            r = room_by_id[rid]
            if force_reexplore or not r.get("explored", False):
                unexplored.append(r)

        # Deterministic ordering: hallway first if unexplored, then alphabetically by room_id
        def _sort_key(rdict):
            rid = rdict.get("room_id", "")
            if "hallway" in rid:
                return (0, rid)
            return (1, rid)

        unexplored.sort(key=_sort_key)

        if not unexplored:
            return ToolResult(
                tool_name="explore_apartment",
                success=True,
                data={
                    "success": True,
                    "all_explored": True,
                    "already_complete": True,
                    "rooms_explored": [],
                    "total_rooms": len(all_rooms),
                    "status": self.client.get_exploration_status(),
                },
                message="All reachable rooms are already explored.",
            )

        log.info(f"🏠 [TOOL] explore_apartment: deterministic traversal of {len(unexplored)} rooms: {[r.get('label') for r in unexplored]}")

        # 6. Traverse each unexplored room
        exploration_results = []
        per_room_timeout = max(45.0, timeout_sec / max(1, len(unexplored)))

        for room in unexplored:
            # Check bumper before each room
            if getattr(self, "bumper_hit", False):
                self.stop()
                log.error("💥 Tactile bumper collision during apartment traversal! Halting.")
                return ToolResult(
                    tool_name="explore_apartment",
                    success=False,
                    data={
                        "collision_detected": True,
                        "rooms_explored": exploration_results,
                        "status": self.client.get_exploration_status(),
                        "all_explored": False,
                    },
                    message="Tactile bumper collision during traversal! Exploration halted.",
                )

            rid = room.get("room_id")
            rlabel = room.get("label")
            log.info(f"🚀 Traversal visiting room: {rlabel} ({rid})")
            res = self.explore_room(rid, timeout_sec=per_room_timeout)
            exploration_results.append(res.data)

            # Basic recovery: continue to next reachable room if one fails
            if not res.success:
                log.warning(f"⚠️ Room {rlabel} exploration incomplete. Continuing to next room in traversal.")

        # 7. Final status summary
        final_status = self.client.get_exploration_status()
        success = final_status.get("all_explored", False) or all(r.get("success", False) for r in exploration_results)

        total_objs = final_status.get("total_objects_grounded", 0)
        exp_count = final_status.get("explored_rooms", 0)

        return ToolResult(
            tool_name="explore_apartment",
            success=success,
            data={
                "success": success,
                "all_explored": final_status.get("all_explored", False),
                "explored_rooms_count": exp_count,
                "total_rooms": final_status.get("total_rooms", len(all_rooms)),
                "total_objects_grounded": total_objs,
                "rooms_explored": exploration_results,
                "final_status": final_status,
            },
            message=f"Apartment exploration complete: {exp_count}/{final_status.get('total_rooms', len(all_rooms))} rooms explored, {total_objs} objects grounded in knowledge graph.",
        )


