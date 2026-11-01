#!/usr/bin/env python3
"""
GRaCEmo ViRa — Modular Speech-to-Text (STT) Adapter
Coordinates transcription across Groq Whisper (cloud fast path with domain grounding),
local Whisper, and SpeechRecognition fallback.
Filters silence and ghost hallucinations.
"""
from __future__ import annotations
import io
import logging
import os
import time
import wave
from dataclasses import dataclass
from typing import Optional
import numpy as np

log = logging.getLogger("gracemo.stt")

WHISPER_PROMPT = (
    "GraceEMO, Lovely Professional University, LPU. Questions about Vice Chancellor "
    "Professor Doctor Jaspal Singh Sandhu, Founder Chancellor Doctor Ashok Kumar Mittal, "
    "Pro-Chancellor Missus Rashmi Mittal, Doctor Mohit Arora, admissions, central library, "
    "Uni-Mall, robotics research lab, campus navigation, placements, fees, and faculty."
)

GHOST_HALLUCINATIONS = {
    "thanks for watching", "subtitles by", "bye.", "you", "so", ".",
    "thank you for watching", "thank you.", "bye", "subscribe",
    "i am sorry, sir.", "i am sorry sir", "im gonna die", "die in sm",
}


@dataclass
class STTResult:
    text: str
    confidence: float
    provider: str
    latency_ms: float = 0.0
    is_valid: bool = True


class STTAdapter:
    """
    Unified Speech-to-Text Adapter.
    Tiers:
      1. Groq Cloud Whisper (whisper-large-v3-turbo)
      2. SpeechRecognition (Google Web API)
      3. Fallback / Stdin
    """

    def __init__(self, groq_client=None, timeout_sec: float = 3.0):
        self.timeout_sec = timeout_sec
        self.groq_client = groq_client
        if self.groq_client is None:
            groq_key = os.getenv("GROQ_API_KEY") or os.getenv("VOICE_KEY")
            if groq_key:
                try:
                    from groq import Groq
                    self.groq_client = Groq(api_key=groq_key)
                except Exception as e:
                    log.debug(f"Groq STT client unavailable: {e}")

    def transcribe(self, audio_data: np.ndarray | bytes | str, sample_rate: int = 16000) -> STTResult:
        """
        Transcribes audio data (numpy array, raw bytes, or WAV file path).
        """
        start_t = time.perf_counter()

        # 1. Convert input to WAV bytes
        wav_bytes = self._prepare_wav_bytes(audio_data, sample_rate)
        if not wav_bytes:
            return STTResult("", 0.0, "none", is_valid=False)

        # Tier 1: Groq Cloud Whisper
        if self.groq_client is not None:
            try:
                res = self._transcribe_groq(wav_bytes)
                if res and res.is_valid:
                    res.latency_ms = (time.perf_counter() - start_t) * 1000.0
                    return res
            except Exception as e:
                log.warning(f"Groq Whisper transcription error ({e}); falling back")

        # Tier 2: SpeechRecognition (Google Web Speech API)
        res = self._transcribe_speech_recognition(wav_bytes)
        res.latency_ms = (time.perf_counter() - start_t) * 1000.0
        return res

    def _prepare_wav_bytes(self, audio_data: np.ndarray | bytes | str, sample_rate: int) -> Optional[bytes]:
        if isinstance(audio_data, str) and os.path.exists(audio_data):
            try:
                with open(audio_data, "rb") as f:
                    return f.read()
            except Exception:
                return None

        if isinstance(audio_data, np.ndarray):
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                # Ensure int16
                if audio_data.dtype != np.int16:
                    audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
                else:
                    audio_int16 = audio_data
                wf.writeframes(audio_int16.tobytes())
            return buf.getvalue()

        if isinstance(audio_data, bytes):
            return audio_data

        return None

    def _transcribe_groq(self, wav_bytes: bytes) -> STTResult:
        transcription = self.groq_client.audio.transcriptions.create(
            file=("speech.wav", wav_bytes),
            model="whisper-large-v3-turbo",
            language="en",
            prompt=WHISPER_PROMPT,
            temperature=0.0,
            timeout=self.timeout_sec,
        )
        text = (transcription.text or "").strip()
        is_valid = self._filter_ghosts(text)
        return STTResult(
            text=text if is_valid else "",
            confidence=0.95 if is_valid else 0.0,
            provider="groq_whisper_turbo",
            is_valid=is_valid,
        )

    def _transcribe_speech_recognition(self, wav_bytes: bytes) -> STTResult:
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = r.record(source)
            text = r.recognize_google(audio).strip()
            is_valid = self._filter_ghosts(text)
            return STTResult(
                text=text if is_valid else "",
                confidence=0.88 if is_valid else 0.0,
                provider="google_web_stt",
                is_valid=is_valid,
            )
        except Exception as e:
            log.debug(f"SpeechRecognition fallback unavailable: {e}")
            return STTResult("", 0.0, "none", is_valid=False)

    def _filter_ghosts(self, text: str) -> bool:
        if not text or len(text) < 2:
            return False
        clean = text.lower().strip()
        exact_ghosts = {"you", "so", ".", "thank you.", "thank you", "bye.", "bye", "watching", "subscribe"}
        if clean in exact_ghosts:
            return False
        phrase_ghosts = [
            "thanks for watching", "thank you for watching", "subtitles by",
            "amara.org", "im gonna die", "i am sorry, sir", "i am sorry sir",
            "die in sm", "please subscribe", "i am sorry"
        ]
        for p in phrase_ghosts:
            if p in clean:
                return False
        import re
        words = re.findall(r"\b\w+\b", clean)
        if len(words) >= 6:
            for n in (2, 3):
                ngrams = [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]
                for ng in set(ngrams):
                    if ngrams.count(ng) >= 3:
                        return False
        return True
