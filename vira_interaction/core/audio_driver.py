"""
GRaCEmo ViRa — Modular Audio Ingestion & Voice Command Interface
Phase 4 Implementation:
- Abstract AudioDriverInterface
- PyAudioDriver (ALSA / PulseAudio real microphone capture at 16 kHz)
- MockAudioDriver (Deterministic test harness injecting speech events)
- VoiceCommandParser (Allowlisted speech-to-structured-command normalizer with STOP priority)
"""

from __future__ import annotations
import abc
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any, Tuple

log = logging.getLogger("gracemo.interaction.audio_driver")


@dataclass
class AudioChunk:
    """Standardized audio chunk."""
    raw_data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM
    timestamp: float = field(default_factory=time.time)
    is_mock: bool = False


@dataclass
class ParsedVoiceCommand:
    """Structured voice command."""
    verb: str                      # "STOP", "FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT", "FOLLOW", "UNKNOWN"
    linear_vel_mps: float = 0.0
    angular_vel_rps: float = 0.0
    is_emergency_stop: bool = False
    raw_transcript: str = ""
    confidence: float = 1.0


class AudioDriverInterface(abc.ABC):
    """Abstract base for audio drivers."""

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def is_mock(self) -> bool:
        ...

    @abc.abstractmethod
    def start(self) -> bool:
        ...

    @abc.abstractmethod
    def stop(self) -> None:
        ...

    @abc.abstractmethod
    def read_chunk(self, chunk_size: int = 1024) -> Optional[AudioChunk]:
        ...


class PyAudioDriver(AudioDriverInterface):
    """Real microphone driver using PyAudio / ALSA."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device_index: Optional[int] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self._pa = None
        self._stream = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected and (self._stream is not None)

    @property
    def is_mock(self) -> bool:
        return False

    def start(self) -> bool:
        try:
            import pyaudio
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=1024
            )
            self._is_connected = True
            log.info("PyAudioDriver: Microphone stream opened successfully.")
            return True
        except Exception as e:
            log.warning(f"PyAudioDriver: Could not open audio input: {e}")
            self._is_connected = False
            return False

    def stop(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        self._is_connected = False

    def read_chunk(self, chunk_size: int = 1024) -> Optional[AudioChunk]:
        if not self.is_connected or not self._stream:
            return None
        try:
            data = self._stream.read(chunk_size, exception_on_overflow=False)
            return AudioChunk(
                raw_data=data,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=2,
                timestamp=time.time(),
                is_mock=False
            )
        except Exception as e:
            log.warning(f"PyAudioDriver read error: {e}")
            self._is_connected = False
            return None


class MockAudioDriver(AudioDriverInterface):
    """Mock audio driver for testing and simulation."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._is_connected = False
        self._pending_chunks: List[AudioChunk] = []

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_mock(self) -> bool:
        return True

    def start(self) -> bool:
        self._is_connected = True
        return True

    def stop(self) -> None:
        self._is_connected = False
        self._pending_chunks.clear()

    def inject_chunk(self, chunk: AudioChunk) -> None:
        self._pending_chunks.append(chunk)

    def read_chunk(self, chunk_size: int = 1024) -> Optional[AudioChunk]:
        if not self._is_connected:
            return None
        if self._pending_chunks:
            return self._pending_chunks.pop(0)
        # Return 0-filled synthetic audio
        return AudioChunk(
            raw_data=b"\x00" * (chunk_size * 2),
            sample_rate=self.sample_rate,
            channels=1,
            sample_width=2,
            timestamp=time.time(),
            is_mock=True
        )


class VoiceCommandParser:
    """
    Normalizes recognized speech transcripts to allowlisted structured commands.
    Safety Policy:
    - STOP has absolute priority over any compound phrase.
    - Ambiguous or unknown phrases return "UNKNOWN" with 0 velocity.
    - Motion velocities are strictly bounded to conservative safe limits.
    """

    STOP_KEYWORDS = ("stop", "halt", "freeze", "emergency", "hold on", "cancel")
    FORWARD_KEYWORDS = ("forward", "go straight", "move forward", "ahead")
    BACKWARD_KEYWORDS = ("backward", "reverse", "back up", "step back")
    LEFT_KEYWORDS = ("turn left", "left", "spin left", "look left")
    RIGHT_KEYWORDS = ("turn right", "right", "spin right", "look right")
    FOLLOW_KEYWORDS = ("follow", "follow me", "come with me", "walk with me")

    @classmethod
    def parse(cls, transcript: str) -> ParsedVoiceCommand:
        t = transcript.strip().lower()
        if not t:
            return ParsedVoiceCommand(verb="UNKNOWN", raw_transcript=transcript)

        # 1. STOP priority check
        for kw in cls.STOP_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="STOP",
                    linear_vel_mps=0.0,
                    angular_vel_rps=0.0,
                    is_emergency_stop=True,
                    raw_transcript=transcript
                )

        # 2. FOLLOW priority check
        for kw in cls.FOLLOW_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="FOLLOW",
                    linear_vel_mps=0.0,  # Velocity will be calculated from target distance by BehaviorManager
                    angular_vel_rps=0.0,
                    raw_transcript=transcript
                )

        # 3. Directional movement checks
        for kw in cls.FORWARD_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="FORWARD",
                    linear_vel_mps=0.20,
                    angular_vel_rps=0.0,
                    raw_transcript=transcript
                )

        for kw in cls.BACKWARD_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="BACKWARD",
                    linear_vel_mps=-0.15,
                    angular_vel_rps=0.0,
                    raw_transcript=transcript
                )

        for kw in cls.LEFT_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="TURN_LEFT",
                    linear_vel_mps=0.0,
                    angular_vel_rps=0.40,
                    raw_transcript=transcript
                )

        for kw in cls.RIGHT_KEYWORDS:
            if kw in t:
                return ParsedVoiceCommand(
                    verb="TURN_RIGHT",
                    linear_vel_mps=0.0,
                    angular_vel_rps=-0.40,
                    raw_transcript=transcript
                )

        # Default fallback: safe UNKNOWN (zero velocity)
        return ParsedVoiceCommand(verb="UNKNOWN", linear_vel_mps=0.0, angular_vel_rps=0.0, raw_transcript=transcript)
