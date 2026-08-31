"""
GRaCEmo ViRa — Grounded Brain & Reasoning Adapter
Orchestrates multi-modal reasoning across Vision, Memory, and Voice.
Driven by config/brain.yaml.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from gracemo_sdk import AdapterClient, ConfigLoader


class BrainAdapter:
    def __init__(self, config_path: Optional[str] = None):
        self.running = True
        self.config = ConfigLoader.load("brain", custom_path=config_path)

        base_url = self.config.get_nested("kernel_url", "http://127.0.0.1:7780")
        self.client = AdapterClient(adapter_name="brain", base_url=base_url)

        llm_conf = self.config.get("llm", {})
        self.provider = llm_conf.get("provider", "nvidia").lower()
        self.model_name = llm_conf.get("model", "google/diffusiongemma-26b-a4b-it")
        self.base_url = llm_conf.get("base_url", "https://integrate.api.nvidia.com/v1")
        self.api_key = os.getenv(llm_conf.get("api_key_env", "NVIDIA_API_KEY")) or llm_conf.get("api_key", "")
        self.temperature = float(llm_conf.get("temperature", 0.2))
        self.max_tokens = int(llm_conf.get("max_tokens", 35))
        self.timeout_sec = float(llm_conf.get("timeout_sec", 5.0))

        self.system_prompt = self.config.get_nested("prompts.system", "You are ViRa, an autonomous AI robot. Ground your replies in sensory state. Reply in 1 concise, direct spoken sentence.")
        self.history_size = int(self.config.get_nested("memory.dialogue_history_turns", 4))
        self.dialogue_history: List[Dict[str, str]] = []
        self.last_processed_voice = None

        self._init_llm_client()

    def _init_llm_client(self):
        if self.provider in ["nvidia", "openai", "ollama", "vllm"]:
            from openai import OpenAI
            if self.api_key or self.provider == "ollama":
                key = self.api_key if self.api_key else "ollama"
                self.llm_client = OpenAI(base_url=self.base_url, api_key=key, timeout=self.timeout_sec)
            else:
                self.llm_client = None
        elif self.provider == "gemini":
            from google import genai
            if self.api_key:
                self.llm_client = genai.Client(api_key=self.api_key)
            else:
                self.llm_client = None
        else:
            self.llm_client = None

    def think_and_respond(self, user_query: str) -> Optional[str]:
        if not getattr(self, "llm_client", None) or not self.running:
            return None

        cleaned_query = user_query.strip()
        if len(cleaned_query) < 2:
            return None

        # 1. Fetch current grounded world snapshot from Kernel
        snapshot = self.client.get_snapshot() or {}
        vision_info = snapshot.get("last_vision_detection")

        # 2. Build multi-turn context
        history_text = ""
        if self.dialogue_history:
            for turn in self.dialogue_history[-2:]:
                history_text += f"Person: {turn['user']}\nViRa: {turn['bot']}\n"

        context_prompt = (
            f"Sensory state: Vision={json.dumps(vision_info)}\n"
            f"{history_text}"
            f"Person: \"{cleaned_query}\"\n"
            f"ViRa (1 short spoken sentence):"
        )

        try:
            reply_text = ""
            if self.provider in ["nvidia", "openai", "ollama", "vllm"]:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": context_prompt}
                ]
                resp = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                reply_text = resp.choices[0].message.content.strip()
            elif self.provider == "gemini":
                resp = self.llm_client.models.generate_content(
                    model=self.model_name,
                    contents=context_prompt,
                )
                reply_text = resp.text.strip()

            if not reply_text:
                return None

            # 3. Update conversation memory
            self.dialogue_history.append({"user": cleaned_query, "bot": reply_text})
            if len(self.dialogue_history) > self.history_size:
                self.dialogue_history = self.dialogue_history[-self.history_size:]

            # 4. Emit ActionRequested to Kernel
            self.client.emit("ActionRequested", {
                "action": "Speak",
                "params": {"text": reply_text}
            }, source="Brain")

            return reply_text
        except Exception as e:
            return None

    def start(self):
        self.client.emit("AdapterConnected", {"name": "brain"}, source="Brain")
        while self.running:
            time.sleep(0.5)


def main():
    adapter = BrainAdapter()
    adapter.start()


if __name__ == "__main__":
    main()
