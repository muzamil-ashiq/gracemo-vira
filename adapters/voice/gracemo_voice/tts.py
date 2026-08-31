"""
GRaCEmo ViRa — Text-to-Speech (TTS) Modular Engines
Supports Edge-TTS (Cloud Neural) and Kokoro (Local GPU <80ms).
"""

import os
import sys
import time
import tempfile
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Callable


class BaseTTSEngine(ABC):
    @abstractmethod
    def speak(self, text: str, on_start: Optional[Callable] = None, on_done: Optional[Callable] = None):
        """Synthesize and play audio for the given text."""
        pass


class EdgeTTSEngine(BaseTTSEngine):
    def __init__(self, config: Dict[str, Any]):
        tts_conf = config.get("tts", {})
        self.voice = tts_conf.get("voice", "en-US-JennyNeural")
        self.rate = tts_conf.get("rate", "+12%")
        self.volume = tts_conf.get("volume", "+0%")

        venv_bin = Path(sys.executable).parent
        self.edge_tts_bin = str(venv_bin / "edge-tts")
        if not os.path.exists(self.edge_tts_bin):
            self.edge_tts_bin = "edge-tts"

    def speak(self, text: str, on_start: Optional[Callable] = None, on_done: Optional[Callable] = None):
        if not text or not text.strip():
            return

        if on_start:
            on_start(text)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                temp_path = fp.name

            cmd = [
                self.edge_tts_bin,
                "--voice", self.voice,
                "--rate", self.rate,
                "--volume", self.volume,
                "--text", text,
                "--write-media", temp_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            player = (
                f"mpv --no-terminal --really-quiet '{temp_path}' 2>/dev/null || "
                f"pw-play '{temp_path}' 2>/dev/null || "
                f"ffplay -nodisp -autoexit -loglevel quiet '{temp_path}' 2>/dev/null"
            )
            os.system(player)
        except Exception:
            pass
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            time.sleep(0.1)
            if on_done:
                on_done()


class KokoroTTSEngine(BaseTTSEngine):
    def __init__(self, config: Dict[str, Any]):
        tts_conf = config.get("tts", {})
        self.voice = tts_conf.get("voice", "af_sarah")
        self.speed = float(tts_conf.get("speed", 1.1))
        self.initialized = False
        try:
            from kokoro import KPipeline
            self.pipeline = KPipeline(lang_code="a")
            self.initialized = True
        except Exception as e:
            self.fallback = EdgeTTSEngine(config)

    def speak(self, text: str, on_start: Optional[Callable] = None, on_done: Optional[Callable] = None):
        if not getattr(self, "initialized", False):
            self.fallback.speak(text, on_start=on_start, on_done=on_done)
            return

        if on_start:
            on_start(text)

        try:
            import soundfile as sf
            generator = self.pipeline(text, voice=self.voice, speed=self.speed, split_pattern=r"\n+")
            for _, _, audio in generator:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
                    temp_path = fp.name
                sf.write(temp_path, audio, 24000)
                os.system(f"mpv --no-terminal --really-quiet '{temp_path}' 2>/dev/null || pw-play '{temp_path}' 2>/dev/null")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception:
            pass
        finally:
            if on_done:
                on_done()


def create_tts_engine(config: Dict[str, Any]) -> BaseTTSEngine:
    engine_name = config.get("tts", {}).get("engine", "edge-tts").lower()
    if engine_name == "kokoro":
        return KokoroTTSEngine(config)
    return EdgeTTSEngine(config)
