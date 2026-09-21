#!/usr/bin/env python3
"""
GraceEMO Interaction — Interaction Loop
Standalone (no ROS 2) equivalent of the interaction slice from
gracemo_brain/planner_node.py.

Pipeline:
  text input
    → DialogueEngine.parse()  (fast local intent)
    → LLMEngine.ask()         (Gemini/Groq/Ollama/heuristics)
    → dispatch action         (speak, navigate, stop, hand/head gestures)
    → TTSEngine.speak()
"""
from __future__ import annotations
import json
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple

from .models import (
    ActionResult, AskQuestionRequest, AskQuestionResponse,
    InspectorState, VoiceCommand,
)
from .llm_engine import LLMEngine
from .dialogue_engine import DialogueEngine
from .tts_engine import TTSEngine

log = logging.getLogger("gracemo.loop")

# Default campus places map (mirrors FALLBACK_PLACES in planner_node.py)
DEFAULT_PLACES: Dict[str, Tuple[float, float, str]] = {
    "door":      (2.5,  -2.5,  "Welcome Reception Desk"),
    "reception": (2.5,  -2.5,  "Welcome Reception Desk"),
    "lab":       (2.5,   2.0,  "Robotics Research Lab"),
    "robotics":  (2.5,   2.0,  "Robotics Research Lab"),
    "commons":   (-2.5, -2.5,  "Campus Commons"),
    "kitchen":   (-2.5, -2.5,  "Campus Commons"),
    "ai":        (-2.5,  2.0,  "AI Compute Center"),
    "library":   (45.0, 20.0,  "Central Library (B37)"),
    "mall":      (30.0, -40.0, "Uni-Mall Shopping Center"),
    "gate":      (0.0,  -95.0, "Main Campus Gate 1"),
}


class InteractionLoop:
    """
    The core human-robot interaction engine.

    Accepts text (or VoiceCommand) and:
      1. Classifies intent via DialogueEngine
      2. Calls LLMEngine for reasoning
      3. Dispatches actions (speak, navigate, gesture)
      4. Speaks response via TTSEngine

    Action hooks (navigate, hand_*, look_*) are no-ops by default.
    Connect them to your robot via set_action_hook().
    """

    def __init__(
        self,
        llm: Optional[LLMEngine] = None,
        tts: Optional[TTSEngine] = None,
        enable_tts: bool = True,
        places: Optional[Dict[str, Tuple[float, float, str]]] = None,
    ):
        self.llm = llm or LLMEngine()
        self.dialogue = DialogueEngine()
        self.tts = tts or (TTSEngine() if enable_tts else None)
        self.state = InspectorState()
        self.known_places: Dict[str, Tuple[float, float, str]] = dict(places or DEFAULT_PLACES)
        self._last_greeting = 0.0

        # Action hooks: set via set_action_hook(name, fn)
        self._hooks: Dict[str, Callable] = {}

        log.info(f"InteractionLoop online (llm={self.llm.backend_name}, tts={self.tts.backend if self.tts else 'disabled'})")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_text(self, text: str) -> ActionResult:
        """
        Main entry point: process raw text input through the full pipeline.
        Returns an ActionResult describing what was dispatched.
        """
        if not text.strip():
            return ActionResult()

        self.state.last_voice = text

        # Step 1: Local intent classification
        cmd = self.dialogue.parse(text)
        log.debug(f"DialogueEngine intent: {cmd.intent}")

        # Step 2: Fast-path dispatch for deterministic commands
        result = self._fast_dispatch(cmd)
        if result is not None:
            return result

        # Step 3: LLM reasoning for ambiguous commands
        llm_resp = self._ask_llm(text)
        return self._dispatch_llm_response(llm_resp)

    def greet(self) -> ActionResult:
        """Autonomous greeting when a person is detected nearby."""
        self.stop()
        self.look_home()
        self.hand_hi()
        return self.speak("Hello! I am GraceEMO. Welcome to campus. How may I assist you?")

    def set_action_hook(self, action: str, fn: Callable):
        """
        Register a hook for a physical robot action.
        fn receives relevant args: fn(target, x, y) for navigate_to, fn() for others.

        Actions: navigate_to, stop, speak, hand_hi, hand_up, hand_down, look_home, look_at
        """
        self._hooks[action] = fn

    # ------------------------------------------------------------------
    # Action implementations (no-op + hook dispatch)
    # ------------------------------------------------------------------

    def speak(self, text: str) -> ActionResult:
        log.info(f"🤖 GraceEMO: \"{text}\"")
        if self.tts:
            self.tts.speak(text)
        self._fire_hook("speak", text=text)
        return ActionResult(action="speak", text=text)

    def stop(self) -> ActionResult:
        self.state.nav_active = False  # type: ignore[attr-defined]
        self.state.current_task = "IDLE"
        self._fire_hook("stop")
        log.info("🛑 STOP")
        return ActionResult(action="stop")

    def hand_hi(self) -> ActionResult:
        log.info("👋 HAND_HI")
        self._fire_hook("hand_hi")
        return ActionResult(action="hand_hi")

    def hand_up(self) -> ActionResult:
        log.info("🙌 HAND_UP")
        self._fire_hook("hand_up")
        return ActionResult(action="hand_up")

    def hand_down(self) -> ActionResult:
        log.info("👐 HAND_DOWN")
        self._fire_hook("hand_down")
        return ActionResult(action="hand_down")

    def look_home(self) -> ActionResult:
        log.info("👁️  LOOK_HOME")
        self._fire_hook("look_home")
        return ActionResult(action="look_home")

    def look_at(self, yaw: float, pitch: float = 0.15) -> ActionResult:
        log.info(f"👀 LOOK_AT yaw={yaw:.2f} pitch={pitch:.2f}")
        self._fire_hook("look_at", x=yaw, y=pitch)
        return ActionResult(action="look_at", x=yaw, y=pitch)

    def navigate_to(self, place_key: str) -> ActionResult:
        key = (place_key or "").lower().strip()
        entry = self._lookup_place(key)
        if entry is None:
            resp = self.speak(f"I don't know where {key or 'that'} is.")
            return resp
        x, y, name = entry
        self.state.current_task = f"NAVIGATE:{name}"
        self.speak(f"Going to {name}.")
        self._fire_hook("navigate_to", target=name, x=x, y=y)
        log.info(f"🗺️  NAVIGATE_TO {name} ({x:.2f}, {y:.2f})")
        return ActionResult(action="navigate_to", target=name, x=x, y=y)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fast_dispatch(self, cmd: VoiceCommand) -> Optional[ActionResult]:
        """Handle deterministic intents without calling the LLM."""
        intent = cmd.intent

        if intent == "STOP":
            r = self.stop()
            self.speak("Stopping now.")
            return r

        if intent == "NAVIGATE":
            place = self._extract_place(cmd.transcript, cmd.entities)
            return self.navigate_to(place)

        if intent == "GREET":
            self.hand_hi()
            return self.speak("Hello! Welcome to LPU campus.")

        if intent == "HAND_UP":
            self.hand_up()
            return self.speak("Hands raised.")

        if intent == "HAND_DOWN":
            self.hand_down()
            return self.speak("Hands lowered.")

        return None  # Fall through to LLM

    def _ask_llm(self, text: str) -> AskQuestionResponse:
        req = AskQuestionRequest(
            question=text,
            context=json.dumps(self.state.to_dict()),
        )
        return self.llm.ask(req)

    def _dispatch_llm_response(self, resp: AskQuestionResponse) -> ActionResult:
        """Execute actions from LLM response."""
        result = ActionResult()
        for act in (resp.suggested_actions or []):
            if act.startswith("navigate_to"):
                place = act.split(":")[-1] if ":" in act else self._extract_place(self.state.last_voice, [])
                result = self.navigate_to(place)
                return result  # navigate is terminal
            elif act == "stop":
                result = self.stop()
                if resp.answer:
                    self.speak(resp.answer)
                return result
            elif act == "hand_hi":
                self.hand_hi()
            elif act == "hand_up":
                self.hand_up()
            elif act == "hand_down":
                self.hand_down()
            elif act == "look_home":
                self.look_home()

        if resp.answer:
            result = self.speak(resp.answer)

        return result

    def _fire_hook(self, action: str, **kwargs):
        fn = self._hooks.get(action)
        if fn:
            try:
                fn(**kwargs)
            except Exception as e:
                log.warning(f"Hook '{action}' error: {e}")

    def _lookup_place(self, key: str) -> Optional[Tuple[float, float, str]]:
        if key in self.known_places:
            return self.known_places[key]
        for name, data in self.known_places.items():
            if key in name or name in key:
                return data
        return None

    def _extract_place(self, text: str, entities: List[str]) -> str:
        blob = (text or "").lower()
        for name in sorted(self.known_places.keys(), key=len, reverse=True):
            if name in blob:
                return name
        for e in entities:
            el = e.lower()
            if el in self.known_places:
                return el
        return "door"

    @property
    def llm_backend(self) -> str:
        return self.llm.backend_name
