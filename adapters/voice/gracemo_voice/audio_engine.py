"""
GRaCEmo ViRa — Unified Modular Voice Adapter
Orchestrates STT, TTS, VAD, and Wake Word using modular engines driven by config/voice.yaml.
"""

import os
import sys
import time
import signal
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable

import numpy as np

# Silence ALSA C-level error output
def _suppress_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    return saved

def _restore_stderr(saved_fd: int):
    os.dup2(saved_fd, 2)
    os.close(saved_fd)

_saved = _suppress_stderr()
import pyaudio
_restore_stderr(_saved)

sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from gracemo_sdk import AdapterClient, ConfigLoader
from .stt import create_stt_engine
from .tts import create_tts_engine
from .wake_word import create_wake_word_engine

os.environ["JACK_NO_START_SERVER"] = "1"


def _silent_pyaudio() -> pyaudio.PyAudio:
    saved = _suppress_stderr()
    try:
        pa = pyaudio.PyAudio()
    finally:
        _restore_stderr(saved)
    return pa


def _play_chime(freq: int = 880, volume: float = 0.10):
    try:
        pa = _silent_pyaudio()
        sr = 48000
        dur = 0.04
        t = np.linspace(0, dur, int(sr * dur), False)
        wave_data = (np.sin(2 * np.pi * freq * t) * np.hanning(len(t)) * volume * 32767).astype(np.int16)
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=sr, output=True)
        stream.write(wave_data.tobytes())
        stream.stop_stream()
        stream.close()
        pa.terminate()
    except Exception:
        pass


class VoiceAdapter:
    def __init__(self, config_path: Optional[str] = None):
        self.running = True
        self.is_speaking = threading.Event()
        self.config = ConfigLoader.load("voice", custom_path=config_path)

        base_url = self.config.get_nested("kernel_url", "http://127.0.0.1:7780")
        self.client = AdapterClient(adapter_name="voice", base_url=base_url)

        # 1. Initialize Modular STT Engine
        self.stt_engine = create_stt_engine(self.config)
        self.device_used = getattr(self.stt_engine, "device_used", "cpu")

        # 2. Initialize Modular TTS Engine
        self.tts_engine = create_tts_engine(self.config)

        # 3. Initialize Modular Wake Word Engine
        self.wake_engine = create_wake_word_engine(self.config)

        # 4. Audio I/O setup
        self.hw_sample_rate = self.config.get_nested("audio_io.hw_sample_rate", 48000)
        self.pa_instance = _silent_pyaudio()
        self.mic_device_index = self._find_physical_mic()

        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self._handle_exit)
                signal.signal(signal.SIGTERM, self._handle_exit)
            except Exception:
                pass

    def _find_physical_mic(self) -> Optional[int]:
        """Auto-detect physical hardware microphone index."""
        preferred_name = self.config.get_nested("audio_io.preferred_device_match", "sof-hda-dsp")
        try:
            count = self.pa_instance.get_device_count()
            for i in range(count):
                info = self.pa_instance.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0 and preferred_name in info['name'] and 'hw:1,0' in info['name']:
                    return i
            for i in range(count):
                info = self.pa_instance.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0 and preferred_name in info['name']:
                    return i
            default_info = self.pa_instance.get_default_input_device_info()
            return default_info['index']
        except Exception:
            return 4

    def _handle_exit(self, signum=None, frame=None):
        self.running = False

    def open_record_stream(self, chunk_size: int = 2048):
        """Open a live PyAudio recording stream connected to the hardware microphone."""
        return self.pa_instance.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.hw_sample_rate,
            input=True,
            input_device_index=self.mic_device_index,
            frames_per_buffer=chunk_size
        )

    def record_utterance(self, max_duration_sec: float = 6.0, stop_event: Optional[threading.Event] = None) -> Optional[np.ndarray]:
        """Record user speech with intelligent VAD auto-stop."""
        chunk_size = 2048
        stream = None
        chunks = []
        speech_started = False
        silence_chunks = 0
        max_chunks = int(max_duration_sec * self.hw_sample_rate / chunk_size)

        try:
            stream = self.open_record_stream(chunk_size=chunk_size)
            for _ in range(max_chunks):
                if not self.running or (stop_event and stop_event.is_set()):
                    break

                raw = stream.read(chunk_size, exception_on_overflow=False)
                chunk = np.frombuffer(raw, dtype=np.float32)
                rms = float(np.sqrt(np.mean(chunk ** 2)))

                if rms >= 0.0035:
                    speech_started = True
                    silence_chunks = 0
                    chunks.append(chunk)
                elif speech_started:
                    chunks.append(chunk)
                    silence_chunks += 1
                    # ~0.45s of silence after speech -> End of speech!
                    if silence_chunks >= 11:
                        break
                else:
                    chunks.append(chunk)
                    if len(chunks) > 4:
                        chunks.pop(0)

        except Exception:
            pass
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass

        if not speech_started or len(chunks) < 4:
            return None

        return np.concatenate(chunks)

    def speak(self, text: str, on_start: Optional[Callable] = None, on_done: Optional[Callable] = None):
        """Synthesize and speak text via the configured TTS engine."""
        if not text or not text.strip() or not self.running:
            return

        self.is_speaking.set()
        try:
            self.tts_engine.speak(text, on_start=on_start, on_done=on_done)
        finally:
            time.sleep(0.15)
            self.is_speaking.clear()

    def transcribe_audio(self, raw_audio_48k: np.ndarray) -> Optional[str]:
        """Downsample to 16kHz and transcribe via the configured STT engine."""
        audio_16k = raw_audio_48k[::3]
        return self.stt_engine.transcribe(audio_16k)

    def start_action_listener(self, on_speak_start: Optional[Callable] = None,
                               on_speak_done: Optional[Callable] = None):
        """Listen for Speak actions from kernel."""
        def _loop():
            for action_data in self.client.listen_actions():
                if not self.running:
                    break
                if action_data.get("action") == "Speak":
                    text = action_data.get("params", {}).get("text", "")
                    if text:
                        self.speak(text, on_start=on_speak_start, on_done=on_speak_done)

        threading.Thread(target=_loop, daemon=True, name="action-listener").start()


def main():
    adapter = VoiceAdapter()


if __name__ == "__main__":
    main()
