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
                        tool_list = list(tools)
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

        if ("see" in low or "look" in low or "inspect" in low or "visual" in low) and "inspect_visual_scene" in tool_names:
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
