#!/usr/bin/env python3
"""
GraceEMO Interaction — Dialogue Engine
Standalone (no ROS 2) equivalent of gracemo_voice/dialogue_node.py.

Converts raw speech transcript → VoiceCommand with classified intent.
"""
from __future__ import annotations
from .models import VoiceCommand


class DialogueEngine:
    """
    Lightweight intent classifier for GraceEMO voice input.
    Mirrors the logic in dialogue_node.py::on_speech_input().
    """

    STOP_WORDS = ("stop", "halt", "freeze", "emergency", "wait")
    NAVIGATE_PHRASES = ("go to", "navigate", "take me", "drive to", "head to", "walk to")
    GREET_WORDS = ("hello", "hi", "hey", "wave", "hand hi")
    QUERY_MARKERS = ("what", "who", "where", "when", "how", "why", "?")

    def parse(self, transcript: str, confidence: float = 0.95) -> VoiceCommand:
        """
        Classify the transcript into a VoiceCommand with intent.

        Intents: STOP | NAVIGATE | GREET | HAND_UP | HAND_DOWN |
                 QUERY | COMMAND | GENERAL_QUERY
        """
        text = transcript.strip()
        low = text.lower()
        entities = text.split()

        # Priority order matches dialogue_node.py
        if any(w in low for w in self.STOP_WORDS):
            return VoiceCommand(text, "STOP", confidence, entities)

        if any(p in low for p in self.NAVIGATE_PHRASES):
            return VoiceCommand(text, "NAVIGATE", confidence, entities)

        if any(w in low for w in self.GREET_WORDS):
            return VoiceCommand(text, "GREET", confidence, entities)

        if "hand up" in low or "hands up" in low:
            return VoiceCommand(text, "HAND_UP", confidence, entities)

        if "hand down" in low or "hands down" in low:
            return VoiceCommand(text, "HAND_DOWN", confidence, entities)

        if any(m in low for m in self.QUERY_MARKERS):
            return VoiceCommand(text, "QUERY", confidence, entities)

        return VoiceCommand(text, "COMMAND", confidence, entities)
