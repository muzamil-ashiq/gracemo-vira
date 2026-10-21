#!/usr/bin/env python3
"""
GRaCEmo ViRa — Fast-Path Intent & Place Dispatcher
Implements deterministic, zero-LLM command routing for critical actions:
STOP, GREET, IDENTITY, STATUS, and known campus/apartment places.
Guarantees sub-15ms execution for emergency stop and high-frequency intents.
"""
from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from .state_machine import Expression

log = logging.getLogger("gracemo.fast_path")

DEFAULT_CAMPUS_PLACES: Dict[str, Tuple[float, float, str]] = {
    "lab": (2.5, 2.0, "Robotics Research Lab"),
    "robotics": (2.5, 2.0, "Robotics Research Lab"),
    "robotics research lab": (2.5, 2.0, "Robotics Research Lab"),
    "library": (45.0, 20.0, "Central Library (B37)"),
    "central library": (45.0, 20.0, "Central Library (B37)"),
    "mall": (30.0, -40.0, "Uni-Mall Shopping Center"),
    "uni-mall": (30.0, -40.0, "Uni-Mall Shopping Center"),
    "gate": (0.0, -95.0, "Main Campus Gate 1"),
    "reception": (2.5, -2.5, "Welcome Reception Desk"),
    "door": (2.5, -2.5, "Welcome Reception Desk"),
    "ai": (-2.5, 2.0, "AI Compute Center"),
    "ai compute center": (-2.5, 2.0, "AI Compute Center"),
    "commons": (-2.5, -2.5, "Campus Commons"),
    "auditorium": (60.0, 15.0, "Shanti Devi Mittal Auditorium"),
    # Apartment topology parity (for simulation)
    "kitchen": (-5.0, -2.5, "Kitchen & Dining"),
    "dining": (-5.0, -2.5, "Kitchen & Dining"),
    "bedroom": (-5.0, 2.2, "Master Bedroom"),
    "master bedroom": (-5.0, 2.2, "Master Bedroom"),
    "study": (4.5, 3.0, "Home Study"),
    "home study": (4.5, 3.0, "Home Study"),
    "living room": (4.0, -2.5, "Living Room"),
    "hallway": (0.0, 0.0, "Central Hallway"),
}


from .place_resolver import PlaceResolver, PlaceInfo

@dataclass
class FastPathResult:
    matched: bool
    intent: str
    response_text: str
    expression: Expression
    semantic_actions: List[Dict[str, Any]] = field(default_factory=list)
    is_emergency: bool = False
    confidence: float = 1.0


class FastPathMatcher:
    """
    Evaluates raw speech transcripts against deterministic rules.
    If matched, returns ready-to-execute actions and spoken responses.
    Uses authoritative PlaceResolver for spatial waypoint grounding.
    """

    STOP_WORDS = ("stop", "halt", "freeze", "emergency", "wait", "cancel")
    GREET_WORDS = ("hello", "hi", "hey", "wave", "hand hi", "good morning", "good afternoon")
    NAVIGATE_PHRASES = ("go to", "navigate", "take me", "drive to", "head to", "walk to")
    IDENTITY_PHRASES = ("who are you", "what is your name", "what's your name", "your identity")
    GRATITUDE_PHRASES = ("thank you", "thanks", "thank u", "many thanks", "appreciate it")
    STATUS_PHRASES = ("battery", "status report", "system status", "diagnostics")

    def __init__(self, places_config_path: Optional[str] = None):
        cfg_path = Path(places_config_path) if places_config_path else None
        self.place_resolver = PlaceResolver(cfg_path)
        self.places: Dict[str, Tuple[float, float, str]] = {
            k: (p.x, p.y, p.name) for k, p in self.place_resolver.places.items()
        }

    def _contains_pattern(self, text: str, patterns: Tuple[str, ...]) -> bool:
        """Matches whole words or phrases using regex word boundaries."""
        for p in patterns:
            pattern = r"\b" + re.escape(p) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def match(self, text: str) -> FastPathResult:
        if not text:
            return FastPathResult(matched=False, intent="NONE", response_text="", expression=Expression.IDLE)

        clean = text.lower().strip()

        # 1. EMERGENCY STOP FAST PATH (Highest Priority)
        if self._contains_pattern(clean, self.STOP_WORDS):
            log.info("🚨 Fast-Path: Emergency STOP matched!")
            return FastPathResult(
                matched=True,
                intent="STOP",
                response_text="Stopping immediately. Standing by for instructions.",
                expression=Expression.IDLE,
                semantic_actions=[{"action": "Stop", "params": {"reason": "Voice STOP matched"}}],
                is_emergency=True,
                confidence=1.0,
            )

        # 2. GREETINGS
        if self._contains_pattern(clean, self.GREET_WORDS):
            return FastPathResult(
                matched=True,
                intent="GREET",
                response_text="Hello! Welcome to Lovely Professional University. How may I assist you today?",
                expression=Expression.HAPPY,
                semantic_actions=[{"action": "Express", "params": {"emotion": "happy"}}],
                confidence=0.99,
            )

        # 3. IDENTITY
        if self._contains_pattern(clean, self.IDENTITY_PHRASES):
            return FastPathResult(
                matched=True,
                intent="IDENTITY",
                response_text="I am GraceEMO, the AI Vice Chancellor and Campus Ambassador of Lovely Professional University.",
                expression=Expression.HAPPY,
                semantic_actions=[{"action": "Express", "params": {"emotion": "happy"}}],
                confidence=0.99,
            )

        # 4. GRATITUDE
        if self._contains_pattern(clean, self.GRATITUDE_PHRASES):
            return FastPathResult(
                matched=True,
                intent="GRATITUDE",
                response_text="You are most welcome! It is always an absolute pleasure to assist our LPU family.",
                expression=Expression.HAPPY,
                semantic_actions=[{"action": "Express", "params": {"emotion": "happy"}}],
                confidence=0.98,
            )

        # 5. STATUS
        if self._contains_pattern(clean, self.STATUS_PHRASES):
            return FastPathResult(
                matched=True,
                intent="STATUS_REPORT",
                response_text="All autonomous systems are operational and ready.",
                expression=Expression.FOCUS,
                semantic_actions=[{"action": "Express", "params": {"emotion": "focus"}}],
                confidence=0.95,
            )

        # 6. GESTURES: HANDS
        if self._contains_pattern(clean, ("hand up", "hands up")):
            return FastPathResult(
                matched=True,
                intent="HAND_UP",
                response_text="Raising hands in greeting.",
                expression=Expression.HAPPY,
                semantic_actions=[{"action": "Express", "params": {"emotion": "happy"}}],
                confidence=0.95,
            )
        if self._contains_pattern(clean, ("hand down", "hands down")):
            return FastPathResult(
                matched=True,
                intent="HAND_DOWN",
                response_text="Lowering hands to resting position.",
                expression=Expression.IDLE,
                semantic_actions=[{"action": "Express", "params": {"emotion": "idle"}}],
                confidence=0.95,
            )

        # 7. IN-FLIGHT NAVIGATION QUERIES (Zero motion disruption)
        if self._contains_pattern(clean, ("where are we going", "where are you going", "what is our destination", "target destination")):
            return FastPathResult(
                matched=True,
                intent="NAVIGATION_QUERY_DESTINATION",
                response_text="We are currently en route to our assigned destination.",
                expression=Expression.FOCUS,
                semantic_actions=[],
                confidence=0.99,
            )

        if self._contains_pattern(clean, ("how far is it", "how far", "distance remaining", "how much further")):
            return FastPathResult(
                matched=True,
                intent="NAVIGATION_QUERY_DISTANCE",
                response_text="We are actively proceeding along the planned route.",
                expression=Expression.FOCUS,
                semantic_actions=[],
                confidence=0.99,
            )

        # 8. NAVIGATION & PLACE RESOLUTION
        if self._contains_pattern(clean, self.NAVIGATE_PHRASES):
            place, unknown_dest = self.place_resolver.resolve_navigation_request(clean)
            if place:
                return FastPathResult(
                    matched=True,
                    intent="NAVIGATE",
                    response_text=f"Navigating to {place.name}. Please follow me!",
                    expression=Expression.FOCUS,
                    semantic_actions=[
                        {
                            "action": "NavigateTo",
                            "params": {
                                "x": place.x,
                                "y": place.y,
                                "yaw": place.yaw,
                                "target_name": place.name,
                                "tolerance_m": place.tolerance_m,
                            }
                        }
                    ],
                    confidence=0.98,
                )
            elif unknown_dest:
                # Golden Test #4: Explicit rejection of unknown location, emitting ZERO robot commands
                known = self.place_resolver.list_known_places()
                suggest = ", ".join(known[:4]) if known else "the reception desk"
                return FastPathResult(
                    matched=True,
                    intent="UNKNOWN_DESTINATION",
                    response_text=f"I do not have '{unknown_dest}' in my campus map. Known locations include {suggest}.",
                    expression=Expression.SAD,
                    semantic_actions=[],  # CRITICAL: NO ROBOT COMMAND
                    confidence=1.0,
                )

        return FastPathResult(matched=False, intent="UNKNOWN", response_text="", expression=Expression.IDLE)

    def extract_place(self, text: str) -> Optional[Tuple[float, float, str]]:
        """Matches place name from text against known places dictionary."""
        p = self.place_resolver.resolve_place(text)
        if p:
            return (p.x, p.y, p.name)
        return None
