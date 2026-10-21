#!/usr/bin/env python3
"""
GRaCEmo ViRa — Multi-Tier Cognitive Brain Adapter
Coordinates reasoning across local MLX Qwen (Apple Silicon), Groq Cloud,
Google Gemini, Ollama, and Campus Heuristics.
Emits structured responses and semantic robot commands conforming to robot-command.schema.json.
"""
from __future__ import annotations
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .state_machine import Expression

log = logging.getLogger("gracemo.brain")

DEFAULT_SYSTEM_PROMPT = (
    "You are GraceEMO, the Vice Chancellor and Executive Campus Ambassador of Lovely Professional University (LPU).\n"
    "You speak with visionary leadership, academic dignity, and student-focused encouragement.\n"
    "Keep your spoken response concise (1 to 2 lines, under 35 words).\n"
    "You can express emotions by ending with an emotion tag: <exp-happy>, <exp-focus>, <exp-intent>, <exp-sad>, <exp-idle>.\n"
    "You can request campus navigation by outputting: [NAVIGATE: <place_name>].\n"
    "Do NOT output markdown headers, bullet points, or internal reasoning steps."
)


@dataclass
class BrainResult:
    response_text: str
    intent: str
    confidence: float
    expression: Expression
    semantic_actions: List[Dict[str, Any]] = field(default_factory=list)
    provider_used: str = "heuristics"
    latency_ms: float = 0.0


class BrainAdapter:
    """
    Multi-tier LLM engine with automatic fallback:
    1. Local Apple Silicon MLX Qwen 2.5 3B (Offline)
    2. Groq Cloud (qwen/qwen3.8-27b / compound-mini / llama-3.3-70b-versatile)
    3. Google Gemini 2.0 Flash
    4. Ollama (Local)
    5. Deterministic Campus Heuristics (Zero-Failure Fallback)
    """

    def __init__(self, data_dir: Optional[str] = None, timeout_sec: float = 3.5):
        self.timeout_sec = timeout_sec
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        self.system_prompt = self._load_persona_prompt()
        self.conversation_history: List[Dict[str, str]] = []

        # Provider handles
        self.mlx_model = None
        self.mlx_tokenizer = None
        self.mlx_sampler = None
        self.groq_client = None
        self.gemini_client = None
        self.ollama_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")

        self._init_providers()

    def _load_persona_prompt(self) -> str:
        """Reads persona and protocol text files from data/ directory."""
        if not os.path.isdir(self.data_dir):
            return DEFAULT_SYSTEM_PROMPT

        data_str = ""
        files = [f for f in os.listdir(self.data_dir) if f.endswith(".txt")]

        def extract_num(fn):
            match = re.match(r"(\d+)-", fn)
            return int(match.group(1)) if match else float("inf")

        files.sort(key=extract_num)

        for fn in files:
            p = os.path.join(self.data_dir, fn)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    data_str += f"\n\n{content}"
            except Exception:
                pass

        return data_str.strip() or DEFAULT_SYSTEM_PROMPT

    def _init_providers(self):
        # 1. Try Apple Silicon MLX local model
        try:
            from mlx_lm import load as mlx_load
            from mlx_lm.sample_utils import make_sampler

            model_dir = os.path.join(os.path.dirname(__file__), "..", "models", "Qwen2.5-3B-Instruct-4bit")
            if os.path.isdir(model_dir):
                log.info(f"🧠 Loading Local Qwen MLX model from {model_dir}")
                self.mlx_model, self.mlx_tokenizer = mlx_load(model_dir)
                self.mlx_sampler = make_sampler(temp=0.35, top_p=0.9)
                log.info("✅ Local Qwen MLX loaded successfully!")
        except Exception as e:
            log.debug(f"Local MLX unavailable: {e}")

        # 2. Try Groq Cloud
        groq_key = os.getenv("GROQ_API_KEY") or os.getenv("CHAT_KEY")
        if groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=groq_key)
                log.info("✅ Groq Cloud client initialized")
            except Exception as e:
                log.debug(f"Groq initialization notice: {e}")

        # 3. Try Google Gemini
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=gemini_key)
                log.info("✅ Gemini client initialized")
            except Exception:
                pass

    def reason(self, user_query: str, context: Optional[str] = None) -> BrainResult:
        """
        Processes human query and returns a structured BrainResult.
        Falls through provider hierarchy until a valid response is produced.
        """
        start_t = time.perf_counter()
        q = user_query.strip()
        if not q:
            return BrainResult("How may I assist you today?", "GREET", 0.9, Expression.HAPPY, latency_ms=0.0)

        # Update dialogue history
        self.conversation_history.append({"role": "user", "content": q})
        if len(self.conversation_history) > 8:
            self.conversation_history = self.conversation_history[-8:]

        # Tier 1: Local MLX Qwen
        if self.mlx_model is not None and self.mlx_tokenizer is not None:
            try:
                res = self._call_mlx(q)
                if res:
                    res.latency_ms = (time.perf_counter() - start_t) * 1000.0
                    self.conversation_history.append({"role": "assistant", "content": res.response_text})
                    return res
            except Exception as e:
                log.warning(f"MLX generation failed ({e}); trying Groq")

        # Tier 2: Groq Cloud
        if self.groq_client is not None:
            try:
                res = self._call_groq(q)
                if res:
                    res.latency_ms = (time.perf_counter() - start_t) * 1000.0
                    self.conversation_history.append({"role": "assistant", "content": res.response_text})
                    return res
            except Exception as e:
                log.warning(f"Groq generation failed ({e}); trying Gemini")

        # Tier 3: Gemini
        if self.gemini_client is not None:
            try:
                res = self._call_gemini(q)
                if res:
                    res.latency_ms = (time.perf_counter() - start_t) * 1000.0
                    self.conversation_history.append({"role": "assistant", "content": res.response_text})
                    return res
            except Exception as e:
                log.warning(f"Gemini generation failed ({e}); falling back to heuristics")

        # Tier 4: Campus Heuristics Fallback
        res = self._call_heuristics(q)
        res.latency_ms = (time.perf_counter() - start_t) * 1000.0
        self.conversation_history.append({"role": "assistant", "content": res.response_text})
        return res

    def _call_mlx(self, query: str) -> Optional[BrainResult]:
        from mlx_lm import generate as mlx_generate

        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
        prompt = self.mlx_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        raw = mlx_generate(
            self.mlx_model,
            self.mlx_tokenizer,
            prompt=prompt,
            max_tokens=100,
            sampler=self.mlx_sampler,
        )
        return self._parse_raw_llm(raw.strip(), provider="local_mlx_qwen")

    def _call_groq(self, query: str) -> Optional[BrainResult]:
        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
        completion = self.groq_client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=messages,
            temperature=0.25,
            max_tokens=120,
            timeout=self.timeout_sec,
        )
        raw = completion.choices[0].message.content or ""
        return self._parse_raw_llm(raw.strip(), provider="groq_cloud")

    def _call_gemini(self, query: str) -> Optional[BrainResult]:
        full_prompt = f"{self.system_prompt}\n\nHuman: {query}\nGraceEMO:"
        resp = self.gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
        )
        raw = (resp.text or "").strip()
        return self._parse_raw_llm(raw, provider="gemini_flash")

    def _call_heuristics(self, query: str) -> BrainResult:
        ql = query.lower()
        if "course" in ql or "study" in ql:
            return BrainResult(
                response_text="LPU offers world-class programs across Engineering, Management, Computer Science, and Design. <exp-happy>",
                intent="QUERY",
                confidence=0.9,
                expression=Expression.HAPPY,
                provider_used="heuristics",
            )
        if "lab" in ql or "research" in ql:
            return BrainResult(
                response_text="Our Robotics Lab and AI Compute Centers house cutting-edge research equipment. <exp-focus>",
                intent="QUERY",
                confidence=0.9,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        return BrainResult(
            response_text=f"As Vice Chancellor, I warmly welcome you to Lovely Professional University. How may I assist your journey? <exp-happy>",
            intent="GENERAL_QUERY",
            confidence=0.8,
            expression=Expression.HAPPY,
            provider_used="heuristics",
        )

    def _parse_raw_llm(self, raw: str, provider: str) -> BrainResult:
        if not raw:
            return self._call_heuristics("")

        # Extract <exp-*>
        expression = Expression.HAPPY
        exp_match = re.search(r"<exp-([a-zA-Z]+)>", raw)
        if exp_match:
            exp_str = exp_match.group(1).lower()
            try:
                expression = Expression(exp_str)
            except ValueError:
                expression = Expression.HAPPY

        cleaned = re.sub(r"<exp-[a-zA-Z]+>", "", raw).strip()

        # Check for [NAVIGATE: place]
        actions = []
        nav_match = re.search(r"\[NAVIGATE:\s*(.*?)\]", cleaned, re.IGNORECASE)
        intent = "GENERAL_QUERY"
        if nav_match:
            place_name = nav_match.group(1).strip()
            cleaned = re.sub(r"\[NAVIGATE:.*?\]", "", cleaned).strip()
            actions.append({"action": "NavigateToRoom", "params": {"room": place_name}})
            intent = "NAVIGATE"
            expression = Expression.FOCUS

        # Clean tags like {hand-hi}
        cleaned = re.sub(r"\{\s*.*?\s*\}", "", cleaned).strip()

        return BrainResult(
            response_text=cleaned or "I am listening. How can I assist?",
            intent=intent,
            confidence=0.92,
            expression=expression,
            semantic_actions=actions,
            provider_used=provider,
        )
