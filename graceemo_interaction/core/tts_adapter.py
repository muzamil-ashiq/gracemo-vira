#!/usr/bin/env python3
"""
GRaCEmo ViRa — Modular Text-to-Speech (TTS) Adapter
Implements high-fidelity Indian English neural speech (Edge-TTS en-IN-NeerjaNeural)
with offline pyttsx3 fallback.
Supports non-blocking cancellable playback for instant user barge-in and STOP.
"""
from __future__ import annotations
import asyncio
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("gracemo.tts")


class TTSAdapter:
    """
    Cancellable Speech Synthesizer and Player.
    Features:
      - High-fidelity neural voice (en-IN-NeerjaNeural)
      - Offline fallback to pyttsx3
      - Non-blocking execution with on_start and on_done callbacks
      - Instant cancellation on stop() via subprocess termination
    """

    def __init__(self, voice: str = "en-IN-NeerjaNeural", output_dir: Optional[str] = None):
        self.voice = voice
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "..")
        self.mp3_path = os.path.join(self.output_dir, "output.mp3")
        self.wav_path = os.path.join(self.output_dir, "output.wav")

        self._lock = threading.Lock()
        self._current_process: Optional[subprocess.Popen] = None
        self._is_speaking_flag = threading.Event()
        self._stop_requested = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def is_speaking(self) -> bool:
        return self._is_speaking_flag.is_set()

    def stop(self):
        """Immediately interrupt and terminate any currently playing audio."""
        self._stop_requested.set()
        with self._lock:
            if self._current_process:
                try:
                    self._current_process.terminate()
                    self._current_process.kill()
                except Exception:
                    pass
                self._current_process = None
        self._is_speaking_flag.clear()
        log.info("🛑 TTS playback stopped immediately")

    def speak(
        self,
        text: str,
        on_start: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
        blocking: bool = False,
    ):
        """Synthesize and play speech. Non-blocking by default."""
        clean_text = text.strip()
        if not clean_text:
            if on_done:
                on_done()
            return

        # Interrupt any prior utterance
        self.stop()
        self._stop_requested.clear()

        def _run():
            self._is_speaking_flag.set()
            if on_start:
                try:
                    on_start()
                except Exception as e:
                    log.error(f"Error in on_start: {e}")

            try:
                # 1. Synthesize audio
                success = self._synthesize(clean_text)
                if success and not self._stop_requested.is_set():
                    # 2. Play audio
                    self._play_audio()
            except Exception as e:
                log.warning(f"TTS playback exception: {e}")
            finally:
                self._is_speaking_flag.clear()
                if on_done:
                    try:
                        on_done()
                    except Exception as e:
                        log.error(f"Error in on_done: {e}")

        if blocking:
            _run()
        else:
            self._worker_thread = threading.Thread(target=_run, daemon=True, name="tts-worker")
            self._worker_thread.start()

    def _synthesize(self, text: str) -> bool:
        # Tier 1: Edge-TTS
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice=self.voice)
            asyncio.run(communicate.save(self.mp3_path))

            # Fast ffmpeg conversion to 24kHz 16-bit mono WAV
            subprocess.run(
                ["ffmpeg", "-y", "-i", self.mp3_path, "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", self.wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=5.0,
            )
            return True
        except Exception as e:
            log.debug(f"Edge-TTS synthesis unavailable ({e}); trying pyttsx3 offline")

        # Tier 2: pyttsx3 offline
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text, self.wav_path)
            engine.runAndWait()
            return True
        except Exception as e2:
            log.warning(f"pyttsx3 synthesis unavailable: {e2}")

        return False

    def _play_audio(self):
        if not os.path.exists(self.wav_path):
            return

        with self._lock:
            if self._stop_requested.is_set():
                return

            if sys.platform == "darwin":
                self._current_process = subprocess.Popen(
                    ["afplay", self.wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif os.path.exists("/usr/bin/pw-play"):
                self._current_process = subprocess.Popen(
                    ["/usr/bin/pw-play", self.wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif os.path.exists("/usr/bin/aplay"):
                self._current_process = subprocess.Popen(
                    ["/usr/bin/aplay", "-q", self.wav_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                try:
                    import pygame
                    pygame.mixer.music.load(self.wav_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and not self._stop_requested.is_set():
                        time.sleep(0.05)
                    return
                except Exception:
                    pass

        if self._current_process:
            self._current_process.wait()
            with self._lock:
                self._current_process = None
