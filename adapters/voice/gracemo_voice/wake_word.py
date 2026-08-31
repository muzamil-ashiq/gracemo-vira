"""
GRaCEmo ViRa — Wake Word Modular Engines
Supports OpenWakeWord (hey_jarvis, alexa, custom hey_vira).
"""

import os
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import numpy as np


class BaseWakeWordEngine(ABC):
    @abstractmethod
    def start_listening(self, stream, on_wake: Callable):
        """Start listening on the given audio stream and invoke on_wake on keyword trigger."""
        pass


class OpenWakeWordEngine(BaseWakeWordEngine):
    def __init__(self, config: Dict[str, Any]):
        self.running = True
        ww_conf = config.get("wake_word", {})
        self.model_name = ww_conf.get("model", "hey_jarvis")
        self.threshold = float(ww_conf.get("threshold", 0.50))
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            import openwakeword as _oww
            from openwakeword.model import Model as OWWModel
            pkg_dir = os.path.dirname(_oww.__file__)
            
            # Find matching model file
            model_file = f"{self.model_name}_v0.1.onnx"
            model_path = os.path.join(pkg_dir, "resources", "models", model_file)
            if not os.path.exists(model_path):
                model_path = os.path.join(pkg_dir, "resources", "models", "hey_jarvis_v0.1.onnx")

            self.model = OWWModel(wakeword_model_paths=[model_path], vad_threshold=0.45)
        except Exception as e:
            print(f"[OpenWakeWordEngine] Warning: Could not initialize model: {e}")
            self.model = None

    def start_listening(self, stream, on_wake: Callable):
        if not self.model:
            return

        chunk_size = 1280
        while self.running:
            try:
                raw = stream.read(chunk_size, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.int16)
                pred = self.model.predict(audio)
                if any(score > self.threshold for score in pred.values()):
                    on_wake()
                    self.model.reset()
            except Exception:
                pass
            time.sleep(0.01)


def create_wake_word_engine(config: Dict[str, Any]) -> Optional[BaseWakeWordEngine]:
    if not config.get("wake_word", {}).get("enabled", True):
        return None
    return OpenWakeWordEngine(config)
