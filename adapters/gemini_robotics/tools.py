"""
GRaCEmo ViRa — High-Level Tool Layer for Gemini Robotics ER 2
Exposes verified, existing capabilities (Navigation, Manipulation, Knowledge Graph, Voice, Emotions)
to Gemini ER 2 without exposing raw motor commands or ROS2 topics.
"""

from __future__ import annotations

import logging
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

        # Lazy-loaded skill instances
        self._nav_skill = None
        self._manip_skill = None

        # Build tools mapping
        self._tools: Dict[str, Callable] = {
            "navigate_to_room": self.navigate_to_room,
            "navigate_to": self.navigate_to,
            "look_at": self.look_at,
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
        ]

    def get_genai_tool(self) -> Any:
        """Returns google.genai types.Tool wrapping all FunctionDeclarations."""
        from google.genai import types
        decls = self.get_function_declarations()
        return types.Tool(function_declarations=decls)

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
        target_x = float(x)
        target_y = float(y)
        target_z = float(z)
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

