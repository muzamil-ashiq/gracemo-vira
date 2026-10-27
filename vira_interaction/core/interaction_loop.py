#!/usr/bin/env python3
"""
GRaCEmo ViRa — Interaction Loop (Phase 2 Refactor)
Integrates the production InteractionGateway, SafetyGate, and EventBus
while maintaining complete backwards compatibility with existing CLI, Voice, and REST callers.
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
from .gateway import InteractionGateway, GatewayResult
from .state_machine import CognitiveState, Expression

log = logging.getLogger("gracemo.loop")

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
    The core human-robot interaction loop.
    Coordinates between CLI/Web callers and the production InteractionGateway.
    """

    def __init__(
        self,
        llm: Optional[LLMEngine] = None,
        tts: Optional[TTSEngine] = None,
        enable_tts: bool = True,
        places: Optional[Dict[str, Tuple[float, float, str]]] = None,
        gateway: Optional[InteractionGateway] = None,
    ):
        self.llm = llm or LLMEngine()
        self.dialogue = DialogueEngine()
        self.tts = tts or (TTSEngine() if enable_tts else None)
        self.enable_tts = enable_tts
        self.state = InspectorState()
        self.known_places: Dict[str, Tuple[float, float, str]] = dict(places or DEFAULT_PLACES)
        self._hooks: Dict[str, Callable] = {}

        # Production Interaction Gateway
        self.gateway = gateway or InteractionGateway()

        log.info(f"InteractionLoop online (gateway active, tts={'enabled' if enable_tts else 'disabled'})")

    def handle_text(self, text: str) -> ActionResult:
        """
        Main entry point: processes text through the production InteractionGateway.
        Dispatches validated semantic actions to both EventBus and registered hooks.
        """
        if not text or not text.strip():
            return ActionResult()

        self.state.last_voice = text

        # Route through Production Interaction Gateway
        gw_result: GatewayResult = self.gateway.process_text(text)

        # Map to legacy ActionResult
        primary_action = "speak"
        target_name = ""
        target_x = 0.0
        target_y = 0.0

        for act in gw_result.semantic_commands:
            action_name = act.get("action")
            params = act.get("params", {})

            if action_name == "NavigateTo":
                primary_action = "navigate_to"
                target_name = params.get("target_name", "designated location")
                target_x = float(params.get("x", 0.0))
                target_y = float(params.get("y", 0.0))
                self.state.current_task = f"NAVIGATE:{target_name}"
                self._fire_hook("navigate_to", target=target_name, x=target_x, y=target_y)

            elif action_name == "NavigateToRoom":
                primary_action = "navigate_to"
                target_name = params.get("room", "designated room")
                self.state.current_task = f"NAVIGATE:{target_name}"
                self._fire_hook("navigate_to", target=target_name, x=0.0, y=0.0)

            elif action_name == "Stop":
                primary_action = "stop"
                self.state.current_task = "IDLE"
                self._fire_hook("stop")

            elif action_name == "Express":
                emotion = params.get("emotion", "idle")
                self._fire_hook("express", emotion=emotion)

        # Trigger TTS if speech response was generated and TTS is enabled
        if gw_result.response:
            if self.enable_tts and self.tts:
                self.tts.speak(gw_result.response)
            self._fire_hook("speak", text=gw_result.response)

        return ActionResult(
            action=primary_action,
            target=target_name,
            text=gw_result.response,
            x=target_x,
            y=target_y,
        )

    def greet(self) -> ActionResult:
        """Autonomous greeting when a person is detected nearby."""
        return self.handle_text("hello")

    def set_action_hook(self, action: str, fn: Callable):
        self._hooks[action] = fn

    def speak(self, text: str) -> ActionResult:
        log.info(f"🤖 GraceEMO: \"{text}\"")
        if self.enable_tts and self.tts:
            self.tts.speak(text)
        self._fire_hook("speak", text=text)
        return ActionResult(action="speak", text=text)

    def stop(self) -> ActionResult:
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

    def _fire_hook(self, action: str, **kwargs):
        fn = self._hooks.get(action)
        if fn:
            try:
                fn(**kwargs)
            except Exception as e:
                log.warning(f"Hook '{action}' error: {e}")

    @property
    def llm_backend(self) -> str:
        return "InteractionGateway"
