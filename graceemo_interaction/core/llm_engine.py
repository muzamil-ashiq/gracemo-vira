#!/usr/bin/env python3
"""
GraceEMO Interaction — LLM Engine
Standalone (no ROS 2) equivalent of gracemo_brain/llm_node.py.

Backend priority chain:
  1. Google Gemini (google.genai SDK)  → GEMINI_API_KEY
  2. Google Gemini (legacy SDK)        → GEMINI_API_KEY / GOOGLE_API_KEY
  3. Groq Cloud LPU                    → GROQ_API_KEY
  4. Ollama (local)                    → OLLAMA_API_BASE (default localhost:11434)
  5. Campus heuristics (always works)
"""
from __future__ import annotations
import json
import os
import re
import logging
from typing import Optional

from .models import AskQuestionRequest, AskQuestionResponse

log = logging.getLogger("gracemo.llm")

CAMPUS_PLACES = (
    "door", "lab", "reception", "commons", "kitchen",
    "robotics", "ai", "library", "mall", "gate",
)

SYSTEM_PROMPT = (
    "You are GraceEMO, an autonomous wheeled campus assistant robot at Lovely Professional University (LPU).\n"
    "You are equipped with differential drive wheels, a pan/tilt neck camera, and dual 90-degree pitch arms.\n"
    "Analyze the user's query and current sensory/telemetry context.\n"
    "Return a strictly valid JSON object (no markdown, no backticks) with this exact schema:\n"
    "{\n"
    '  "answer": "1 concise, polite spoken sentence for TTS playback",\n'
    '  "intent": "NAVIGATE" | "STOP" | "GREET" | "HAND_HI" | "HAND_UP" | "HAND_DOWN" | "LOOK_AT" | "STATUS_REPORT" | "IDENTITY" | "GENERAL_QUERY",\n'
    '  "confidence": 0.95,\n'
    '  "suggested_actions": ["navigate_to:<place>"] | ["stop"] | ["hand_hi"] | ["hand_up"] | ["hand_down"] | ["speak"]\n'
    "}\n"
    "Available campus places: door, lab, reception, commons, kitchen, robotics, ai, library, mall, gate."
)


def _extract_place_heuristic(text: str) -> str:
    t = text.lower()
    for p in CAMPUS_PLACES:
        if p in t:
            return p
    return "door"


def _parse_llm_json(raw: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    clean = re.sub(r"\s*```$", "", clean).strip()
    return json.loads(clean)


class LLMEngine:
    """
    Multi-backend LLM engine for the GraceEMO interaction pipeline.
    Falls back gracefully through Gemini → Groq → Ollama → heuristics.
    """

    def __init__(self):
        self._backend: Optional[str] = None
        self._gemini_client = None
        self._gemini_legacy = None
        self._groq_client = None
        self._ollama_base: Optional[str] = None

        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        groq_key = os.environ.get("GROQ_API_KEY")
        ollama_base = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434/v1")

        # 1. Try google.genai (modern SDK)
        if gemini_key and self._backend is None:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=gemini_key)
                self._backend = "gemini_genai"
                log.info("✅ Backend: Gemini 2.0 Flash (google.genai SDK)")
            except Exception as e:
                log.debug(f"google.genai unavailable: {e}")

        # 2. Try google.generativeai (legacy SDK)
        if gemini_key and self._backend is None:
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=gemini_key)
                self._gemini_legacy = legacy_genai.GenerativeModel("gemini-2.0-flash")
                self._backend = "gemini_legacy"
                log.info("✅ Backend: Gemini 2.0 Flash (google.generativeai legacy SDK)")
            except Exception as e:
                log.debug(f"google.generativeai unavailable: {e}")

        # 3. Try Groq
        if groq_key and self._backend is None:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=groq_key)
                self._backend = "groq"
                log.info("✅ Backend: Groq Cloud LPU (llama-3.3-70b-versatile)")
            except Exception as e:
                log.debug(f"Groq unavailable: {e}")

        # 4. Try Ollama (local)
        if self._backend is None:
            try:
                import requests
                r = requests.get(f"{ollama_base.rstrip('/v1')}/api/tags", timeout=2)
                if r.ok and r.json().get("models"):
                    self._ollama_base = ollama_base
                    self._backend = "ollama"
                    log.info(f"✅ Backend: Ollama local ({ollama_base})")
            except Exception as e:
                log.debug(f"Ollama unavailable: {e}")

        if self._backend is None:
            log.warning("⚠️  No LLM API available — campus heuristics only")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, request: AskQuestionRequest) -> AskQuestionResponse:
        q = request.question.strip()
        ctx = request.context or "Normal campus state"

        if self._backend is not None:
            try:
                return self._call_llm(q, ctx)
            except Exception as e:
                log.warning(f"LLM call failed ({e}); falling back to heuristics")

        return self._heuristics(q)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _call_llm(self, question: str, context: str) -> AskQuestionResponse:
        user_content = f"Sensory State Context: {context}\nUser Voice Query: \"{question}\""
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_content}"
        raw = ""

        if self._backend == "gemini_genai":
            resp = self._gemini_client.models.generate_content(
                model="gemini-2.0-flash", contents=full_prompt
            )
            raw = (resp.text or "").strip()

        elif self._backend == "gemini_legacy":
            result = self._gemini_legacy.generate_content(full_prompt)
            raw = (result.text or "").strip()

        elif self._backend == "groq":
            chat = self._groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=256,
            )
            raw = chat.choices[0].message.content or ""

        elif self._backend == "ollama":
            import requests
            body = {
                "model": "llama3",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
            }
            r = requests.post(
                f"{self._ollama_base.rstrip('/v1')}/api/chat",
                json=body, timeout=30,
            )
            r.raise_for_status()
            raw = r.json().get("message", {}).get("content", "")

        if not raw:
            raise ValueError("Empty LLM response")

        parsed = _parse_llm_json(raw)
        actions = parsed.get("suggested_actions", ["speak"])
        if not isinstance(actions, list):
            actions = ["speak"]
        return AskQuestionResponse(
            answer=str(parsed.get("answer", "I understand.")),
            intent=str(parsed.get("intent", "GENERAL_QUERY")).upper(),
            confidence=float(parsed.get("confidence", 0.85)),
            suggested_actions=[str(a) for a in actions],
        )

    # ------------------------------------------------------------------
    # Deterministic heuristics fallback (always available, no API)
    # ------------------------------------------------------------------

    def _heuristics(self, q: str) -> AskQuestionResponse:
        ql = q.lower()

        if any(w in ql for w in ("stop", "halt", "freeze", "emergency")):
            return AskQuestionResponse("Stopping immediately.", "STOP", 0.99, ["stop"])

        if any(p in ql for p in ("go to", "navigate", "take me", "drive to", "head to")):
            place = _extract_place_heuristic(q)
            return AskQuestionResponse(
                f"Navigating to {place}.", "NAVIGATE", 0.95, [f"navigate_to:{place}"]
            )

        if any(w in ql for w in ("hello", "hi", "wave", "hand hi")):
            return AskQuestionResponse(
                "Hello! Welcome to LPU campus.", "HAND_HI", 0.95, ["hand_hi", "speak"]
            )

        if "hand up" in ql or "hands up" in ql:
            return AskQuestionResponse("Raising both hands.", "HAND_UP", 0.95, ["hand_up"])

        if "hand down" in ql or "hands down" in ql:
            return AskQuestionResponse("Lowering hands.", "HAND_DOWN", 0.95, ["hand_down"])

        if "who are you" in ql or "your name" in ql:
            return AskQuestionResponse(
                "I am GraceEMO, an autonomous campus assistant robot at Lovely Professional University.",
                "IDENTITY", 0.99, ["speak"],
            )

        if "battery" in ql or "status" in ql:
            return AskQuestionResponse(
                "All systems are operational.", "STATUS_REPORT", 0.9, ["speak"]
            )

        return AskQuestionResponse(
            f"I heard: {q}. Standing by for instructions.",
            "GENERAL_QUERY", 0.7, ["speak"],
        )

    @property
    def backend_name(self) -> str:
        return self._backend or "heuristics"
