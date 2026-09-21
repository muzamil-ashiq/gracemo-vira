"""
GRaCEmo ViRa — Gemini Robotics ER 2 Configuration
Centralized configuration for Google Gemini Robotics ER 2 models and kernel endpoints.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any

# Auto-discover and load .env files if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
for env_path in [ROOT_DIR / ".env", ROOT_DIR / "graceemo_interaction" / ".env"]:
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


@dataclass
class GeminiRoboticsConfig:
    """Configuration container for Gemini Robotics ER 2 Adapter."""

    # Model Configuration
    model_name: str = field(
        default_factory=lambda: os.getenv("GEMINI_ROBOTICS_ER_MODEL", "gemini-robotics-er-2-preview")
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )

    # Reasoning parameters
    temperature: float = field(
        default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    )
    max_output_tokens: int = field(
        default_factory=lambda: int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1024"))
    )
    max_turns: int = field(
        default_factory=lambda: int(os.getenv("GEMINI_MAX_TURNS", "5"))
    )

    # Substrate Connection
    kernel_url: str = field(
        default_factory=lambda: os.getenv("KERNEL_URL", "http://127.0.0.1:7780").rstrip("/")
    )

    # System instruction
    system_instruction: str = (
        "You are ViRa, an embodied autonomous AI robot at Lovely Professional University (LPU). "
        "Your cognition is powered by Gemini Robotics ER 2. "
        "You operate through the authoritative MNSE Kernel which owns physical and environmental truth. "
        "Ground your decisions in real-time sensor state and knowledge graph relationships. "
        "Never hallucinate locations, coordinates, or object positions. "
        "Select high-level robot tools to inspect, navigate, and interact."
    )

    def is_configured(self) -> bool:
        """Returns True if an API key is available."""
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def to_dict(self) -> Dict[str, Any]:
        """Returns safe representation without exposing secrets."""
        masked_key = (
            f"{self.api_key[:4]}...{self.api_key[-4:]}"
            if self.api_key and len(self.api_key) > 8
            else ("[CONFIGURED]" if self.api_key else None)
        )
        return {
            "model_name": self.model_name,
            "api_key": masked_key,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "max_turns": self.max_turns,
            "kernel_url": self.kernel_url,
        }

    def __repr__(self) -> str:
        d = self.to_dict()
        return f"GeminiRoboticsConfig({d})"
