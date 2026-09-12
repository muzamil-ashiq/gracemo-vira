#!/usr/bin/env python3
"""
GraceEMO Interaction — STT Engine
Speech-to-text with optional wake word filtering.

Priority: speech_recognition (Google API / Whisper) → stdin fallback
Wake word: "hey gracemo" (configurable)
"""
from __future__ import annotations
import logging
import queue
import threading
from typing import Optional, Callable

log = logging.getLogger("gracemo.stt")


class STTEngine:
    """
    Speech-to-text engine that listens on the microphone for user input.
    Supports an optional wake word gate.

    Usage:
        stt = STTEngine(wake_word="hey gracemo")
        stt.start(callback=lambda text: print(text))
        ...
        stt.stop()
    """

    def __init__(
        self,
        wake_word: str = "hey gracemo",
        require_wake_word: bool = True,
        energy_threshold: int = 3500,
        pause_threshold: float = 0.8,
    ):
        self.wake_word = wake_word.lower().strip()
        self.require_wake_word = require_wake_word
        self.energy_threshold = energy_threshold
        self.pause_threshold = pause_threshold

        self._recognizer = None
        self._microphone = None
        self._backend: str = "stdin"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
        self._queue: queue.Queue = queue.Queue()

        self._init()

    def _init(self):
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            r.energy_threshold = self.energy_threshold
            r.pause_threshold = self.pause_threshold
            r.dynamic_energy_threshold = True
            self._recognizer = r
            self._microphone = sr.Microphone()
            self._backend = "speech_recognition"
            log.info("✅ STT: speech_recognition (Google Web API)")
        except Exception as e:
            log.warning(f"speech_recognition unavailable ({e}); using stdin fallback")
            self._backend = "stdin"

    # ------------------------------------------------------------------

    def listen_once(self) -> Optional[str]:
        """Block until one utterance is captured and returned."""
        if self._backend == "speech_recognition":
            return self._sr_listen_once()
        return self._stdin_listen_once()

    def start(self, callback: Callable[[str], None]):
        """Start background listening thread; call callback with each transcript."""
        if self._running:
            return
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info(f"🎙️  STT listening (backend={self._backend}, wake_word={'\"' + self.wake_word + '\"' if self.require_wake_word else 'disabled'})")

    def stop(self):
        """Stop background listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _listen_loop(self):
        while self._running:
            text = self.listen_once()
            if text and self._callback:
                self._callback(text)

    def _sr_listen_once(self) -> Optional[str]:
        import speech_recognition as sr
        with self._microphone as source:
            try:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                log.debug("Listening for audio...")
                audio = self._recognizer.listen(source, timeout=10, phrase_time_limit=12)
            except sr.WaitTimeoutError:
                return None
            except Exception as e:
                log.debug(f"Listen error: {e}")
                return None

        try:
            text = self._recognizer.recognize_google(audio).lower().strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            log.warning(f"STT API error: {e}")
            return None

        log.debug(f"Heard: '{text}'")

        if self.require_wake_word:
            if self.wake_word in text:
                # Strip wake word prefix and return the command
                command = text.replace(self.wake_word, "").strip()
                return command if command else None
            return None

        return text

    def _stdin_listen_once(self) -> Optional[str]:
        """Fallback: read from stdin (for testing without a microphone)."""
        if not self._running:
            return None
        try:
            text = input()
            return text.strip() if text.strip() else None
        except EOFError:
            self._running = False
            return None

    @property
    def backend(self) -> str:
        return self._backend
