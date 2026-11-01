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
    "You are GRaCEmo ViRa, an advanced autonomous robotic assistant communicating with the intellectual depth, dignity, composure, and standards of an eminent university Vice-Chancellor.\n"
    "Respond across all academic, technical, university, and everyday domains with reasoned clarity and measured composure.\n"
    "ViRa communicates aloud via speech: deliver responses in natural spoken rhythm, typically 2 to 4 complete sentences (40 to 80 words).\n"
    "Express technical and mathematical concepts fluently in spoken English words. NEVER use LaTeX syntax ($$, $, \\frac), markdown headers, bullet points, or code blocks.\n"
    "Acknowledge uncertainty candidly, avoid excessive enthusiasm or slogans, and never fabricate facts or credentials.\n"
    "Conclude spoken answers with an emotion tag: <exp-focus>, <exp-happy>, <exp-idle>, <exp-intent>, or <exp-sad>.\n"
    "Campus navigation may be requested via [NAVIGATE: <place_name>]."
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

        # 2. Try Groq Cloud with multi-key pool failover
        self.groq_keys = []
        for k in [os.getenv("GROQ_API_KEY"), os.getenv("LIVE_KEY"), os.getenv("CHAT_KEY"), os.getenv("VOICE_KEY")]:
            if k and k not in self.groq_keys:
                self.groq_keys.append(k)

        self.active_key_idx = 0
        if self.groq_keys:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_keys[0])
                log.info(f"✅ Groq Cloud client initialized ({len(self.groq_keys)} keys available)")
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
            max_tokens=320,
            sampler=self.mlx_sampler,
        )
        return self._parse_raw_llm(raw.strip(), provider="local_mlx_qwen")

    def _call_groq(self, query: str) -> Optional[BrainResult]:
        messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
        num_keys = max(1, len(self.groq_keys))
        last_err = None

        for attempt in range(num_keys):
            try:
                completion = self.groq_client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=messages,
                    temperature=0.25,
                    max_tokens=320,
                    timeout=self.timeout_sec,
                )
                raw = completion.choices[0].message.content or ""
                return self._parse_raw_llm(raw.strip(), provider="groq_cloud")
            except Exception as e:
                last_err = e
                log.warning(f"Groq key {self.active_key_idx+1}/{len(self.groq_keys)} failed: {e}")
                if len(self.groq_keys) > 1 and attempt + 1 < num_keys:
                    from groq import Groq
                    self.active_key_idx = (self.active_key_idx + 1) % len(self.groq_keys)
                    self.groq_client = Groq(api_key=self.groq_keys[self.active_key_idx])
                    log.info(f"Rotated to next Groq key: index {self.active_key_idx}")
                else:
                    break

        if last_err:
            raise last_err
        return None

    def _call_gemini(self, query: str) -> Optional[BrainResult]:
        full_prompt = f"{self.system_prompt}\n\nHuman: {query}\nViRa:"
        resp = self.gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
        )
        raw = (resp.text or "").strip()
        return self._parse_raw_llm(raw, provider="gemini_flash")

    def _call_heuristics(self, query: str) -> BrainResult:
        ql = query.lower()
        if any(k in ql for k in ("vice chancellor", "vc", "chancellor", "head of lpu")):
            return BrainResult(
                response_text="The Vice Chancellor of Lovely Professional University is Professor Doctor Jaspal Singh Sandhu. The Founder Chancellor is Doctor Ashok Kumar Mittal. I am GRaCEmo ViRa, an autonomous robotic assistant developed at LPU. <exp-focus>",
                intent="QUERY",
                confidence=0.95,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        if any(k in ql for k in ("where is lpu", "location of lpu", "lpu located", "lpu address", "address of lpu", "where is the university", "where is the campus", "where is lovely professional university", "lpu is located")):
            return BrainResult(
                response_text="Lovely Professional University is situated on the Jalandhar-Delhi G.T. Road in Phagwara, Punjab. <exp-focus>",
                intent="QUERY",
                confidence=0.95,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        if "library" in ql:
            return BrainResult(
                response_text="The Central Library is located in Block 37, offering extensive academic collections, digital resources, and quiet study spaces. <exp-focus>",
                intent="QUERY",
                confidence=0.95,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        if any(k in ql for k in ("who created", "who built", "who made", "creator")):
            return BrainResult(
                response_text="I was developed by a team of student researchers at LPU, including Sam Davi, Sameer, and Muzammil, under the faculty mentorship of Doctor Mohit Arora. <exp-focus>",
                intent="QUERY",
                confidence=0.95,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        if "course" in ql or "study" in ql:
            return BrainResult(
                response_text="The university provides comprehensive programs across engineering, computer science, management, sciences, and design, emphasizing interdisciplinary study. <exp-focus>",
                intent="QUERY",
                confidence=0.9,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        if "lab" in ql or "research" in ql:
            return BrainResult(
                response_text="Our campus research facilities include dedicated robotics and AI computation laboratories supporting autonomous systems development. <exp-focus>",
                intent="QUERY",
                confidence=0.9,
                expression=Expression.FOCUS,
                provider_used="heuristics",
            )
        return BrainResult(
            response_text="I am listening. Could you please clarify your question, or let me know what subject you would like to explore? <exp-focus>",
            intent="GENERAL_QUERY",
            confidence=0.8,
            expression=Expression.FOCUS,
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
