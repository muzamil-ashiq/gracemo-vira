"""
GRaCEmo ViRa — Gemini Robotics ER 2 Client
Provides an isolated, provider-specific client for Google Gemini Robotics ER 2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Sequence

from adapters.gemini_robotics.config import GeminiRoboticsConfig

log = logging.getLogger("gemini_robotics.client")


@dataclass
class ToolCall:
    """Represents a high-level tool/function call selected by Gemini ER 2."""
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeminiResponse:
    """Encapsulates Gemini Robotics ER 2 reasoning response and tool calls."""
    text: Optional[str] = None
    function_calls: List[ToolCall] = field(default_factory=list)
    raw_response: Any = None
    is_mock: bool = False
    error: Optional[str] = None

    @property
    def has_function_calls(self) -> bool:
        return len(self.function_calls) > 0

    @property
    def primary_tool_call(self) -> Optional[ToolCall]:
        return self.function_calls[0] if self.function_calls else None


class GeminiRoboticsClient:
    """
    Client for Gemini Robotics ER 2 (default: 'gemini-robotics-er-2-preview').
    Uses the official modern google.genai SDK.
    Supports offline mock mode for deterministic unit testing without live API keys.
    """

    def __init__(self, config: Optional[GeminiRoboticsConfig] = None, mock_mode: bool = False):
        self.config = config or GeminiRoboticsConfig()
        self.mock_mode = mock_mode
        self._mock_responses: List[GeminiResponse] = []
        self._client = None

        if not self.mock_mode and self.config.is_configured():
            try:
                from google import genai
                self._client = genai.Client(api_key=self.config.api_key)
                log.info(f"Initialized Gemini Robotics Client with model: {self.config.model_name}")
            except Exception as e:
                log.warning(f"Could not initialize live Google GenAI Client ({e}). Falling back to mock mode.")
                self.mock_mode = True
        elif not self.mock_mode and not self.config.is_configured():
            # If live mode requested but not configured, keep mock_mode=False so callers know key is missing
            log.warning("GEMINI_API_KEY is not configured; live client unavailable.")

    @property
    def is_live(self) -> bool:
        """True if the client is configured and connected to the real Gemini API."""
        return not self.mock_mode and self._client is not None

    def test_connection(self) -> Dict[str, Any]:
        """
        Actively verifies if GEMINI_API_KEY is present and the model can actually be invoked.
        """
        if not self.config.is_configured():
            return {
                "success": False,
                "model": self.config.model_name,
                "error": "GEMINI_API_KEY not found in environment or .env",
                "is_mock": True,
            }
        if not self._client:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.config.api_key)
            except Exception as e:
                return {
                    "success": False,
                    "model": self.config.model_name,
                    "error": f"Failed to initialize google-genai client: {e}",
                    "is_mock": False,
                }
        try:
            import time
            t0 = time.time()
            resp = self._client.models.generate_content(
                model=self.config.model_name,
                contents="ping",
            )
            elapsed_ms = (time.time() - t0) * 1000
            return {
                "success": True,
                "model": self.config.model_name,
                "latency_ms": elapsed_ms,
                "response_text": getattr(resp, "text", None),
                "is_mock": False,
            }
        except Exception as e:
            return {
                "success": False,
                "model": self.config.model_name,
                "error": str(e),
                "is_mock": False,
            }

    def set_mock_responses(self, responses: List[GeminiResponse]):
        """Injects deterministic responses for testing."""
        self.mock_mode = True
        self._mock_responses = list(responses)

    def reason(
        self,
        prompt: str,
        context: Optional[str] = None,
        tools: Optional[Sequence[Callable]] = None,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> GeminiResponse:
        """
        Submits grounded context and instructions to Gemini ER 2 for reasoning
        and tool selection. Supports multimodal visual observations via image_bytes.
        """
        full_prompt = f"{context}\n\n{prompt}" if context else prompt

        if self.mock_mode:
            if self._mock_responses:
                resp = self._mock_responses.pop(0)
                resp.is_mock = True
                return resp
            resp = self._default_mock_reason(prompt, tools, has_image=(image_bytes is not None))
            resp.is_mock = True
            return resp

        if not self._client:
            return GeminiResponse(
                text="Gemini client not configured. Set GEMINI_API_KEY or enable mock_mode.",
                is_mock=False,
                error="GEMINI_API_KEY not configured",
            )

        try:
            from google.genai import types

            tool_list = None
            if tools:
                if isinstance(tools, (list, tuple)):
                    if all(hasattr(t, "function_declarations") for t in tools):
                        tool_list = list(tools)
                    elif all(isinstance(t, getattr(types, "FunctionDeclaration", object)) for t in tools):
                        tool_list = [types.Tool(function_declarations=list(tools))]
                    else:
                        clean_tools = []
                        import functools
                        for t in tools:
                            if callable(t) and hasattr(t, "__annotations__") and "return" in t.__annotations__:
                                def _make_wrapper(fn):
                                    @functools.wraps(fn)
                                    def _w(*args, **kwargs):
                                        return fn(*args, **kwargs)
                                    _w.__annotations__ = {k: v for k, v in fn.__annotations__.items() if k != "return"}
                                    return _w
                                clean_tools.append(_make_wrapper(t))
                            else:
                                clean_tools.append(t)
                        tool_list = clean_tools
                elif hasattr(tools, "function_declarations"):
                    tool_list = [tools]
                else:
                    tool_list = list(tools)

            generate_config = types.GenerateContentConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                system_instruction=self.config.system_instruction,
                tools=tool_list,
            )

            contents: Any
            if image_bytes is not None:
                img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                contents = [img_part, full_prompt]
            else:
                contents = full_prompt

            resp = self._client.models.generate_content(
                model=self.config.model_name,
                contents=contents,
                config=generate_config,
            )

            function_calls = []
            if hasattr(resp, "function_calls") and resp.function_calls:
                for fc in resp.function_calls:
                    function_calls.append(ToolCall(name=fc.name, args=dict(fc.args or {})))

            return GeminiResponse(
                text=getattr(resp, "text", None),
                function_calls=function_calls,
                raw_response=resp,
                is_mock=False,
            )
        except Exception as e:
            log.error(f"Gemini ER 2 inference error: {e}")
            return GeminiResponse(
                text=f"Reasoning error: {e}",
                is_mock=False,
                error=str(e),
            )

    def plan(
        self,
        user_instruction: str,
        context: Optional[str] = None,
        tools: Optional[Sequence[Callable]] = None,
    ) -> GeminiResponse:
        """Alias for task planning."""
        return self.reason(user_instruction, context=context, tools=tools)

    def generate(self, prompt: str) -> str:
        """Simple text generation without tool calls."""
        res = self.reason(prompt, tools=None)
        return res.text or ""

    def _default_mock_reason(
        self,
        prompt: str,
        tools: Optional[Sequence[Any]],
        has_image: bool = False,
    ) -> GeminiResponse:
        """Heuristic fallback for offline / mock unit testing."""
        import math
        low = prompt.lower()
        tool_names: List[str] = []
        for t in (tools or []):
            if hasattr(t, "name") and isinstance(t.name, str):
                tool_names.append(t.name)
            elif hasattr(t, "__name__") and isinstance(t.__name__, str):
                tool_names.append(t.__name__)
            elif hasattr(t, "function_declarations") and t.function_declarations:
                for fd in t.function_declarations:
                    if hasattr(fd, "name"):
                        tool_names.append(fd.name)
            else:
                tool_names.append(str(t))

        # If a turn or navigation action just completed, perform final look_at on the target object
        if ("action completed: turn_toward_object" in low or "action completed: navigate_to_object" in low) and "look_at_object" in tool_names:
            target_obj_name = "chair"
            if "Original User Command:" in prompt:
                orig_cmd = prompt.split("Original User Command:")[1].split("\n")[0].strip().strip('"')
                for prefix in ["find the ", "find ", "look at the ", "look at "]:
                    if prefix in orig_cmd.lower():
                        target_obj_name = orig_cmd.lower().split(prefix, 1)[1].split(" ")[0].strip()
                        break
            return GeminiResponse(
                text=f"Base repositioning complete. Now executing final active gaze at {target_obj_name}.",
                function_calls=[ToolCall(name="look_at_object", args={"object_name": target_obj_name})]
            )

        # If look_at just completed, conclude verbally
        if "action completed: look_at" in low:
            return GeminiResponse(
                text="The target has been acquired and I am now looking directly at it."
            )

        # Extract user command from prompt if wrapped in grounded reality
        user_cmd = prompt
        if "User Command: \"" in prompt:
            user_cmd = prompt.split("User Command: \"")[1].split("\"")[0]
        elif "User Command:" in prompt:
            user_cmd = prompt.split("User Command:")[1].split("\n")[0].strip().strip('"')
        cmd_low = user_cmd.lower().strip()

        # ---------------------------------------------------------------------
        # Object-Grounded LookAt Reasoning (Phase 4 Step 3)
        # ---------------------------------------------------------------------
        is_look_at = (
            cmd_low.startswith("look at")
            or " look at " in cmd_low
            or cmd_low.startswith("gaze at")
            or " gaze at " in cmd_low
            or "turn toward" in cmd_low
            or "turn to" in cmd_low
            or "navigate to" in cmd_low
            or "behind you" in cmd_low
        )

        if is_look_at and any(t in tool_names for t in ["look_at_object", "look_at", "turn_toward_object", "navigate_to_object"]):
            cmd_after = cmd_low
            # Check if this is explicitly a turn or navigation request or behind the robot
            is_turn_request = "behind you" in cmd_low or "turn toward" in cmd_low or "turn to" in cmd_low
            is_nav_request = ("navigate to" in cmd_low or "approach" in cmd_low) and not is_turn_request

            for prefix in ["find the ", "find ", "turn toward the ", "turn toward ", "turn to the ", "turn to ", "navigate to the ", "navigate to ", "gaze at ", "look at "]:
                if prefix in cmd_after:
                    cmd_after = cmd_after.split(prefix, 1)[1].strip()
                    break
            if " behind you" in cmd_after:
                cmd_after = cmd_after.split(" behind you")[0].strip()
            if " and look at it" in cmd_after:
                cmd_after = cmd_after.split(" and look at it")[0].strip()
            cmd_after = cmd_after.rstrip(".!?")
            for art in ["the ", "a ", "an ", "this ", "that "]:
                if cmd_after.startswith(art):
                    cmd_after = cmd_after[len(art):].strip()
            target = cmd_after

            world_objects = _parse_world_objects_from_prompt(prompt)

            # Determine selected tool name based on intent
            if is_turn_request and "turn_toward_object" in tool_names:
                selected_tool = "turn_toward_object"
            elif is_nav_request and "navigate_to_object" in tool_names:
                selected_tool = "navigate_to_object"
            elif "look_at_object" in tool_names:
                selected_tool = "look_at_object"
            else:
                selected_tool = "look_at"

            # CASE F: Exact ID match (e.g. 'chair_001')
            exact_match = next((o for o in world_objects if o["id"].lower() == target.lower()), None)
            if exact_match:
                # CASE E: Invalid coordinates
                if not all(math.isfinite(val) for val in exact_match["pos"]):
                    return GeminiResponse(
                        text=f"Cannot look at '{exact_match['id']}': coordinates are invalid/non-finite."
                    )
                # CASE D: Stale
                if not exact_match["visible"]:
                    return GeminiResponse(
                        text=f"Object '{exact_match['id']}' is stale / no longer visible. Cannot perform active gaze."
                    )
                if selected_tool in ("turn_toward_object", "navigate_to_object", "look_at_object"):
                    return GeminiResponse(
                        text=f"Executing {selected_tool} for {exact_match['id']}.",
                        function_calls=[ToolCall(name=selected_tool, args={"object_name": exact_match["id"]})]
                    )
                else:
                    return GeminiResponse(
                        text=f"Directing active gaze to {exact_match['id']}.",
                        function_calls=[ToolCall(name="look_at", args={
                            "x": exact_match["pos"][0],
                            "y": exact_match["pos"][1],
                            "z": exact_match["pos"][2],
                        })]
                    )

            # Match by class name
            matching = [
                o for o in world_objects
                if o["class"].lower() == target.lower() or target.lower() in o["class"].lower()
            ]

            # CASE C: Missing / No object found
            if not matching:
                return GeminiResponse(
                    text=f"Unresolved object: Object '{target}' has not been sighted in the environment."
                )

            visible_matching = [o for o in matching if o["visible"]]

            # CASE D: Stale matching objects
            if not visible_matching:
                stale_ids = [o["id"] for o in matching]
                return GeminiResponse(
                    text=f"Object '{target}' ({', '.join(stale_ids)}) was observed previously but is no longer currently visible."
                )

            # CASE B: Multiple matching objects (Ambiguous)
            if len(visible_matching) > 1:
                cand_ids = [o["id"] for o in visible_matching]
                return GeminiResponse(
                    text=f"Clarification required: Multiple '{target}' objects are visible ({', '.join(cand_ids)}). Which one do you want me to look at?"
                )

            # CASE A: Exactly one visible object
            chosen = visible_matching[0]

            # CASE E: Invalid coordinates
            if not all(math.isfinite(val) for val in chosen["pos"]):
                return GeminiResponse(
                    text=f"Cannot look at '{chosen['id']}': authoritative coordinates are invalid/non-finite."
                )

            if selected_tool in ("turn_toward_object", "navigate_to_object", "look_at_object"):
                return GeminiResponse(
                    text=f"Executing {selected_tool} toward {chosen['id']} ({chosen['class']}).",
                    function_calls=[ToolCall(name=selected_tool, args={"object_name": target})]
                )
            else:
                return GeminiResponse(
                    text=f"Gazing at {chosen['id']} ({chosen['class']}).",
                    function_calls=[ToolCall(name="look_at", args={
                        "x": chosen["pos"][0],
                        "y": chosen["pos"][1],
                        "z": chosen["pos"][2],
                    })]
                )

        if ("see" in low or "inspect" in low or "visual" in low or "surroundings" in low) and "inspect_visual_scene" in tool_names:
            return GeminiResponse(
                text="Inspecting the visual scene using robot camera.",
                function_calls=[ToolCall(name="inspect_visual_scene", args={})]
            )
        elif has_image:
            return GeminiResponse(
                text="Based on the camera observation, I see a dining table, chairs, and a refrigerator in the kitchen."
            )
        elif "kitchen" in low and "navigate_to_room" in tool_names:
            return GeminiResponse(
                text="I will navigate to the Kitchen & Dining area.",
                function_calls=[ToolCall(name="navigate_to_room", args={"room": "Kitchen & Dining"})]
            )
        elif "bedroom" in low and "navigate_to_room" in tool_names:
            return GeminiResponse(
                text="Navigating to the Master Bedroom.",
                function_calls=[ToolCall(name="navigate_to_room", args={"room": "Master Bedroom"})]
            )
        elif "study" in low and "navigate_to_room" in tool_names:
            return GeminiResponse(
                text="Heading to the Home Study.",
                function_calls=[ToolCall(name="navigate_to_room", args={"room": "Home Study"})]
            )
        elif "explore" in low:
            if ("apartment" in low or "all" in low or "house" in low) and "explore_apartment" in tool_names:
                return GeminiResponse(
                    text="Initiating autonomous multi-room exploration of the apartment.",
                    function_calls=[ToolCall(name="explore_apartment", args={})]
                )
            for r_name in ["bedroom", "study", "kitchen", "living", "hallway"]:
                if r_name in low and "explore_room" in tool_names:
                    return GeminiResponse(
                        text=f"Exploring {r_name} autonomously.",
                        function_calls=[ToolCall(name="explore_room", args={"room_id": f"room:{r_name}"})]
                    )

        elif "stop" in low and "stop" in tool_names:
            return GeminiResponse(
                text="Stopping robot motors.",
                function_calls=[ToolCall(name="stop", args={})]
            )
        elif ("where is" in low or "find" in low) and "find_object" in tool_names:
            for obj in ["coke", "can", "laptop", "book", "desk", "bed"]:
                if obj in low:
                    return GeminiResponse(
                        text=f"Checking Knowledge Graph for {obj}.",
                        function_calls=[ToolCall(name="find_object", args={"object_name": obj})]
                    )

        return GeminiResponse(text=f"Mock response for instruction: {prompt}")


def _parse_world_objects_from_prompt(prompt: str) -> List[Dict[str, Any]]:
    """Extracts world objects from WORLD OBJECTS: block or #OBJECTS: TOON in prompt."""
    objects: List[Dict[str, Any]] = []

    # 1. Parse structured WORLD OBJECTS section
    if "WORLD OBJECTS:" in prompt:
        block = prompt.split("WORLD OBJECTS:")[1].split("===")[0].split("User Command:")[0]
        current_obj: Optional[Dict[str, Any]] = None
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("("):
                continue
            if line.startswith("- "):
                if current_obj and "id" in current_obj:
                    objects.append(current_obj)
                obj_id = line[2:].strip()
                current_obj = {
                    "id": obj_id,
                    "class": obj_id.split("_")[0] if "_" in obj_id else obj_id,
                    "visible": True,
                    "pos": (0.0, 0.0, 0.0),
                }
            elif current_obj is not None:
                if line.startswith("class:"):
                    current_obj["class"] = line.split("class:", 1)[1].strip()
                elif line.startswith("visible:"):
                    v_str = line.split("visible:", 1)[1].strip().lower()
                    current_obj["visible"] = (v_str == "true" or v_str == "1")
                elif line.startswith("position:"):
                    p_str = line.split("position:", 1)[1].strip().strip("()[]")
                    try:
                        parts = [float(val.strip()) for val in p_str.split(",")]
                        if len(parts) >= 3:
                            current_obj["pos"] = (parts[0], parts[1], parts[2])
                    except ValueError:
                        if "nan" in p_str.lower():
                            current_obj["pos"] = (float("nan"), 0.0, 0.0)
                        elif "inf" in p_str.lower():
                            current_obj["pos"] = (float("inf"), 0.0, 0.0)

        if current_obj and "id" in current_obj:
            objects.append(current_obj)

    # 2. Parse #OBJECTS: from TOON format if not already captured
    if "#OBJECTS:" in prompt:
        import re
        toon_part = prompt.split("#OBJECTS:")[1].split("#")[0].split("\n")[0]
        matches = re.findall(r"([a-zA-Z0-9_-]+)\[(.*?)\]", toon_part)
        for obj_id, fields_str in matches:
            if any(o["id"].lower() == obj_id.lower() for o in objects):
                continue
            fdict = {}
            for field in fields_str.split(","):
                if ":" in field:
                    k, v = field.split(":", 1)
                    fdict[k.strip()] = v.strip()
            c_name = fdict.get("class", obj_id.split("_")[0])
            vis = fdict.get("vis", "1") in ["1", "true"]
            pos = (0.0, 0.0, 0.0)
            if "pos" in fdict:
                p_str = fdict["pos"].strip("()")
                try:
                    parts = [float(x.strip()) for x in p_str.split(",")]
                    if len(parts) >= 3:
                        pos = (parts[0], parts[1], parts[2])
                except ValueError:
                    if "nan" in p_str.lower():
                        pos = (float("nan"), 0.0, 0.0)
                    elif "inf" in p_str.lower():
                        pos = (float("inf"), 0.0, 0.0)

            objects.append({
                "id": obj_id,
                "class": c_name,
                "visible": vis,
                "pos": pos,
            })

    return objects
