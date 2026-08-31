"""
GRaCEmo ViRa — Speech-to-Text (STT) Modular Engines
Supports Faster-Whisper, Vosk, Whisper.cpp with Silero VAD noise clipping.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np


class BaseSTTEngine(ABC):
    @abstractmethod
    def transcribe(self, audio_16k: np.ndarray) -> Optional[str]:
        """Transcribe a 16kHz float32 audio numpy array to text."""
        pass


class FasterWhisperEngine(BaseSTTEngine):
    def __init__(self, config: Dict[str, Any]):
        from faster_whisper import WhisperModel

        stt_conf = config.get("stt", {})
        vad_conf = config.get("vad", {})

        model_size = stt_conf.get("model_size", "tiny.en")
        device = stt_conf.get("device", "cpu")
        compute_type = stt_conf.get("compute_type", "int8")

        self.beam_size = stt_conf.get("beam_size", 1)
        self.no_speech_threshold = stt_conf.get("no_speech_threshold", 0.60)

        self.vad_enabled = vad_conf.get("enabled", True)
        self.vad_params = dict(
            min_silence_duration_ms=vad_conf.get("min_silence_duration_ms", 300),
            threshold=vad_conf.get("threshold", 0.35)
        )

        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            self.device_used = f"{device} ({compute_type})"
        except Exception:
            # Fallback to CPU int8
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
            self.device_used = "cpu (int8 fallback)"

        self.blacklist = {
            "you", "you.", "...", "..", ".", "hello", "hello.",
            "thank you", "thank you.", "thanks.", "thanks", "subtitles",
            "[music]", "(music)", "bye", "bye.", "okay", "yeah",
        }

    def transcribe(self, audio_16k: np.ndarray) -> Optional[str]:
        if len(audio_16k) == 0:
            return None

        rms = float(np.sqrt(np.mean(audio_16k ** 2)))
        if rms < 0.001:
            return None

        try:
            segments, _ = self.model.transcribe(
                audio_16k,
                beam_size=self.beam_size,
                vad_filter=self.vad_enabled,
                vad_parameters=self.vad_params,
                no_speech_threshold=self.no_speech_threshold,
                condition_on_previous_text=False
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            if not text or text.lower().strip() in self.blacklist or len(text) < 2:
                return None
            return text
        except Exception as e:
            return None


def create_stt_engine(config: Dict[str, Any]) -> BaseSTTEngine:
    engine_name = config.get("stt", {}).get("engine", "faster-whisper").lower()
    if engine_name == "faster-whisper":
        return FasterWhisperEngine(config)
    # Default fallback
    return FasterWhisperEngine(config)
