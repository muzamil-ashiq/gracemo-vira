#!/usr/bin/env python3
"""
GraceEMO Interaction — TTS Engine
Offline-first text-to-speech.
Priority: pyttsx3 (no internet) → gTTS (needs internet) → print only
"""
from __future__ import annotations
import logging
import os
import tempfile

log = logging.getLogger("gracemo.tts")


class TTSEngine:
    """
    Text-to-speech engine with graceful fallback chain.
    Call speak(text) to play audio or print to console.
    """

    def __init__(self, rate: int = 165, volume: float = 1.0):
        self._engine = None
        self._backend: str = "none"
        self._rate = rate
        self._volume = volume
        self._init()

    def _init(self):
        # 1. pyttsx3 — offline, cross-platform
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            # Prefer a female voice if available
            voices = engine.getProperty("voices")
            for v in voices:
                if "female" in v.name.lower() or "zira" in v.id.lower() or "samantha" in v.id.lower():
                    engine.setProperty("voice", v.id)
                    break
            self._engine = engine
            self._backend = "pyttsx3"
            log.info("✅ TTS: pyttsx3 (offline)")
            return
        except Exception as e:
            log.debug(f"pyttsx3 unavailable: {e}")

        # 2. gTTS — online
        try:
            from gtts import gTTS
            import pygame
            pygame.mixer.init()
            self._backend = "gtts"
            log.info("✅ TTS: gTTS + pygame (online)")
            return
        except Exception as e:
            log.debug(f"gTTS unavailable: {e}")

        log.warning("⚠️  TTS: no audio engine — will print only")
        self._backend = "print"

    # ------------------------------------------------------------------

    def speak(self, text: str):
        """Speak text aloud (or print if no audio engine available)."""
        if not text:
            return

        if self._backend == "pyttsx3":
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                return
            except Exception as e:
                log.warning(f"pyttsx3 speak error: {e}")

        if self._backend == "gtts":
            try:
                from gtts import gTTS
                import pygame
                tts = gTTS(text=text, lang="en", slow=False)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp = f.name
                tts.save(tmp)
                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                os.unlink(tmp)
                return
            except Exception as e:
                log.warning(f"gTTS speak error: {e}")

        # Fallback: just print
        print(f"[GraceEMO]: {text}")

    def stop(self):
        if self._backend == "pyttsx3" and self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    @property
    def backend(self) -> str:
        return self._backend
