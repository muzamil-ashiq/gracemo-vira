"""
GRaCEmo ViRa — Autonomous Robotics Engine Launcher
Press SPACE / Enter to Speak | Type + Enter for Text | Ctrl+C to Quit
"""

import os
import sys
import time
import signal
import select
import tty
import termios
import threading
import subprocess
import warnings
from pathlib import Path
import numpy as np

os.environ["JACK_NO_START_SERVER"] = "1"
os.environ["ALSA_LOG_LEVEL"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["ORT_LOGGING_LEVEL"] = "3"

warnings.filterwarnings("ignore", category=UserWarning)

# Silence ALSA C-level spam
import ctypes
try:
    ctypes.CDLL("libasound.so.2").snd_lib_error_set_handler(None)
except Exception:
    pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(highlight=False)

root_dir = Path(__file__).resolve().parent.parent
kernel_dir = root_dir / "kernel"
adapters_dir = root_dir / "adapters"

sys.path.insert(0, str(adapters_dir / "sdk"))
sys.path.insert(0, str(adapters_dir / "vision"))
sys.path.insert(0, str(adapters_dir / "voice"))
sys.path.insert(0, str(adapters_dir / "brain"))

from gracemo_sdk import AdapterClient
from gracemo_vision.detector import VisionAdapter
from gracemo_voice.audio_engine import VoiceAdapter, _play_chime
from gracemo_brain.reasoner import BrainAdapter

running = True
voice_adapter: VoiceAdapter = None
brain_adapter: BrainAdapter = None
kernel_process = None


def shutdown(signum=None, frame=None):
    global running, kernel_process
    if not running:
        return
    running = False
    print("\nStopping GRaCEmo ViRa...", flush=True)
    if kernel_process:
        kernel_process.kill()
    os.system("fuser -k 7780/tcp 2>/dev/null || true")
    os._exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


# ─── Output helpers ───────────────────────────────────────────────────────────

def print_person(text: str):
    console.print(f"\n[bold cyan]Person:[/bold cyan] [white]{text}[/white]")

def print_vira(text: str):
    console.print(f"[bold magenta]ViRa:  [/bold magenta] [white]{text}[/white]")

def print_status(text: str):
    console.print(f"[dim]{text}[/dim]")


# ─── Kernel ───────────────────────────────────────────────────────────────────

def ensure_kernel():
    global kernel_process
    try:
        r = requests.get("http://127.0.0.1:7780/health", timeout=0.4)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    binary = kernel_dir / "target" / "debug" / "gracemo-kernel"
    if not binary.exists():
        subprocess.run(["cargo", "build", "-p", "gracemo-kernel"],
                       cwd=str(kernel_dir), check=True)

    kernel_process = subprocess.Popen([str(binary)], cwd=str(kernel_dir),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(40):
        try:
            r = requests.get("http://127.0.0.1:7780/health", timeout=0.4)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


# ─── Input handler ────────────────────────────────────────────────────────────

def handle_input(text: str):
    global brain_adapter
    if not text or not text.strip():
        return
    print_person(f'"{text}"')
    if brain_adapter:
        brain_adapter.think_and_respond(text)


# ─── Interactive Voice & Text Loop ────────────────────────────────────────────

def run_interactive_terminal_loop():
    global running, voice_adapter
    fd = sys.stdin.fileno()

    if not os.isatty(fd):
        console.print("[dim]Non-interactive terminal detected. Type + Enter mode.[/dim]\n")
        while running:
            try:
                line = input()
                if line.strip():
                    handle_input(line.strip())
            except Exception:
                break
        return

    old_settings = termios.tcgetattr(fd)
    console.print("[bold green]● Ready.[/bold green] [dim]Press SPACE / Enter to Speak  |  Type + Enter for Text  |  Ctrl+C to quit[/dim]\n")

    try:
        tty.setcbreak(fd)
        typed_buffer = []

        while running:
            # Poll stdin with 0.05s timeout
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)

            if rlist:
                char = sys.stdin.read(1)

                if char in ('\x03', '\x04'):
                    break

                # SPACE or empty Enter triggers voice recording
                if char == ' ' or (char in ('\r', '\n') and len(typed_buffer) == 0):
                    if voice_adapter and not voice_adapter.is_speaking.is_set():
                        _play_chime(freq=1100)
                        sys.stdout.write("\r\033[K\033[1;31m● LISTENING (Speak now... stops automatically when done)\033[0m")
                        sys.stdout.flush()

                        # Record utterance with VAD auto-stop
                        audio_data = voice_adapter.record_utterance(max_duration_sec=6.0)
                        _play_chime(freq=660)

                        if audio_data is not None:
                            sys.stdout.write("\r\033[K[dim]  Transcribing voice...[/dim]\r")
                            sys.stdout.flush()
                            text = voice_adapter.transcribe_audio(audio_data)
                            sys.stdout.write("\r\033[K")
                            sys.stdout.flush()
                            if text:
                                handle_input(text)
                            else:
                                console.print("[dim]  (no clear speech recognized — try again)[/dim]")
                        else:
                            sys.stdout.write("\r\033[K[dim]  (no speech detected)[/dim]\n")
                            sys.stdout.flush()

                # User is typing text
                else:
                    if char in ('\r', '\n'):
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        line = "".join(typed_buffer).strip()
                        typed_buffer = []
                        if line:
                            handle_input(line)
                    elif char in ('\x7f', '\x08'):  # Backspace
                        if typed_buffer:
                            typed_buffer.pop()
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                    else:
                        typed_buffer.append(char)
                        sys.stdout.write(char)
                        sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global voice_adapter, brain_adapter

    print("Booting GRaCEmo ViRa Engine...", flush=True)

    if not ensure_kernel():
        print("ERROR: Kernel failed to start.", flush=True)
        return
    print(" - Kernel:  Online", flush=True)

    print(" - Vision:  Loading...", flush=True)
    vision = VisionAdapter()
    threading.Thread(target=vision.start, kwargs={"show_preview": False}, daemon=True).start()

    print(" - Voice:   Loading...", flush=True)
    voice_adapter = VoiceAdapter()

    print(" - Brain:   Loading...", flush=True)
    brain_adapter = BrainAdapter()
    threading.Thread(target=brain_adapter.start, daemon=True).start()

    # Wire TTS speak actions from kernel back to terminal (Single response listener)
    voice_adapter.start_action_listener(
        on_speak_start=lambda text: print_vira(f'"{text}"')
    )

    # Boot panel
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold]Kernel[/bold]", "[bold green]ONLINE[/bold green]", "[dim]http://127.0.0.1:7780[/dim]")
    table.add_row("[bold]Vision[/bold]", "[bold green]ACTIVE[/bold green]", "[dim]YOLOv11 + YuNet (CUDA:0)[/dim]")
    table.add_row("[bold]Voice[/bold]",  "[bold green]READY[/bold green]",  f"[dim]Faster-Whisper ({voice_adapter.device_used}) + Silero VAD[/dim]")
    table.add_row("[bold]Brain[/bold]",  "[bold green]ACTIVE[/bold green]", "[dim]NVIDIA NIM (Grounded Reasoner)[/dim]")

    console.print()
    console.print(Panel(
        table,
        title="[bold cyan]GRaCEmo ViRa — Autonomous Robotics Engine v0.0.1[/bold cyan]",
        border_style="bright_blue"
    ))

    # Greeting speech in background thread so loop is ready immediately
    threading.Thread(
        target=voice_adapter.speak,
        args=("GRaCEmo ViRa online. I am listening and watching.",),
        kwargs={"on_start": lambda t: print_vira(f'"{t}"')},
        daemon=True
    ).start()

    # Run the interactive loop
    run_interactive_terminal_loop()


if __name__ == "__main__":
    main()
