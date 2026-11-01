print("… Loading...")
import platform
import os
import wave
import numpy as np
import math
from contextlib import contextmanager

@contextmanager
def suppress_c_stderr():
    """Silences low-level C stderr diagnostics from ALSA/PortAudio/JACK."""
    try:
        null_fd = os.open(os.devnull, os.O_WRONLY)
        save_fd = os.dup(2)
        os.dup2(null_fd, 2)
        os.close(null_fd)
        yield
    except Exception:
        yield
    finally:
        try:
            os.dup2(save_fd, 2)
            os.close(save_fd)
        except Exception:
            pass

# Suppress ALSA / Jack stderr error noise
try:
    from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
    asound = cdll.LoadLibrary('libasound.so.2')
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
    def py_error_handler(filename, line, function, err, fmt):
        pass
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound.snd_lib_error_set_handler(c_error_handler)
except Exception:
    pass

from groq import Groq
import pyaudio
from dotenv import load_dotenv
import asyncio
import io
import edge_tts # TTS
from pydub import AudioSegment
from pyvidplayer2 import Video # robo face video player
import pygame # GUI engine
import random
import threading
import time
import re
import sys
import json
import struct
import subprocess
from collections import deque
from pynput import keyboard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

# Load environment variables (.env in new/ or root)
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

if platform.machine() != 'x86_64':
    print("… RaspberryPi mode on - mechanical parts disabled")
    # from gpiozero import AngularServo
    # import functions

print("✓ All modules loaded")

pygame.init()
with suppress_c_stderr():
    pygame.mixer.init()

# Set up display (Windowed on Mac by default, Fullscreen toggleable via 'f')
fullscreen = os.getenv("FULLSCREEN", "0") == "1"
if fullscreen:
    win = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
else:
    win = pygame.display.set_mode((1024, 768), pygame.RESIZABLE)
pygame.display.set_caption("GraceEMO")

# -------------------------------------------------------------------------------------------------
''' Global variables '''

T_QUEUE = []                # collected energy threshold queue
VOICE_FLAG = False
VOICE_COUNT = 0
SILENCE_COUNT = 0
MAX_SILENCE_GAP = 8
END_OF_RECORD = False
CONV_HISTORY = []           # Conversation history to know past
SCREEN_WIDTH, SCREEN_HEIGHT = pygame.display.get_surface().get_size()

VID_DIR = os.path.join(BASE_DIR, "vid") + "/"
if not os.path.isdir(VID_DIR):
    VID_DIR = os.path.join(ROOT_DIR, "vid") + "/"

DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.isdir(DATA_DIR):
    DATA_DIR = os.path.join(ROOT_DIR, "data")

FONT_PATH = os.path.join(BASE_DIR, "font.ttf")
if not os.path.exists(FONT_PATH):
    FONT_PATH = os.path.join(ROOT_DIR, "font.ttf")

CAPTION_TEXT = " "

NEXT_EXP = "idle"
CURRENT_EXP = "idle"
PREVIOUS_EXP = "idle"
CURRENT_QUESTION = 'Thank you.'

# Keyboard control for listening
LISTENING_ENABLED = False   # 's' to start, 'e' to stop
STOP_RECORDING = False      # Signal to stop the recording loop

# Proximity & Dynamic VAD Parameters (Adaptive Noise Floor & Hysteresis)
DEFAULT_VAD_CONFIG = {
    "EMA_ALPHA": 0.05,
    "R_MIN": 0.15,
    "R_MAX": 0.60,
    "ADAPT_K": 0.45,
    "HYSTERESIS_BETA": 0.45,
    "DELTA_MIN": 800.0,
    "T_MIN": 1500.0,
    "T_MIN_MIN": 800.0,
    "T_MIN_MAX": 6000.0,
    "B_T_MIN": 200.0,
    "R_MIN_LOWER_BOUND": 0.05,
    "R_MIN_UPPER_BOUND": 0.50,
    "R_MAX_LOWER_BOUND": 0.25,
    "R_MAX_UPPER_BOUND": 0.90,
}

R_MIN_LOWER_BOUND = DEFAULT_VAD_CONFIG["R_MIN_LOWER_BOUND"]
R_MIN_UPPER_BOUND = DEFAULT_VAD_CONFIG["R_MIN_UPPER_BOUND"]
R_MAX_LOWER_BOUND = DEFAULT_VAD_CONFIG["R_MAX_LOWER_BOUND"]
R_MAX_UPPER_BOUND = DEFAULT_VAD_CONFIG["R_MAX_UPPER_BOUND"]

def validate_vad_config(
    delta_min: float,
    t_min: float,
    r_min: float,
    r_max: float,
    hysteresis_beta: float,
    adapt_k: float,
    ema_alpha: float = 0.05,
    t_min_min: float = 800.0,
    t_min_max: float = 6000.0,
    b_t_min: float = 200.0
) -> None:
    """
    Validates active VAD configuration parameters against mathematical and stability constraints.
    Raises ValueError with descriptive reason if any constraint is violated.
    """
    params = {
        "DELTA_MIN": delta_min,
        "T_MIN": t_min,
        "R_MIN": r_min,
        "R_MAX": r_max,
        "HYSTERESIS_BETA": hysteresis_beta,
        "ADAPT_K": adapt_k,
        "EMA_ALPHA": ema_alpha,
        "T_MIN_MIN": t_min_min,
        "T_MIN_MAX": t_min_max,
        "B_T_MIN": b_t_min,
    }
    for name, val in params.items():
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            raise ValueError(f"VAD configuration parameter '{name}' must be a finite number, got {val}")

    if delta_min <= 0:
        raise ValueError(f"DELTA_MIN must be strictly positive (> 0), got {delta_min}")

    if t_min <= 0:
        raise ValueError(f"T_MIN must be strictly positive (> 0), got {t_min}")

    if not (0.0 <= r_min <= r_max):
        raise ValueError(f"Dynamic ratio bounds must satisfy 0 <= R_MIN <= R_MAX, got R_MIN={r_min}, R_MAX={r_max}")

    if not (0.0 <= hysteresis_beta < 1.0):
        raise ValueError(f"HYSTERESIS_BETA must satisfy 0 <= HYSTERESIS_BETA < 1, got {hysteresis_beta}")

    if adapt_k < 0:
        raise ValueError(f"ADAPT_K must be nonnegative (>= 0), got {adapt_k}")

    if not (0.0 < ema_alpha <= 1.0):
        raise ValueError(f"EMA_ALPHA must satisfy 0 < EMA_ALPHA <= 1, got {ema_alpha}")

    if t_min_min <= 0 or t_min_max <= t_min_min:
        raise ValueError(f"T_MIN bounds must satisfy 0 < T_MIN_MIN < T_MIN_MAX, got T_MIN_MIN={t_min_min}, T_MIN_MAX={t_min_max}")

    if b_t_min <= 0:
        raise ValueError(f"B_T_MIN must be strictly positive (> 0), got {b_t_min}")

def _load_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = float(raw)
        if not math.isfinite(val):
            print(f"⚠ Invalid non-finite VAD config for {name}='{raw}'. Using safe default {default}")
            return default
        return val
    except ValueError:
        print(f"⚠ Invalid numeric VAD config for {name}='{raw}'. Using safe default {default}")
        return default

EMA_ALPHA = _load_env_float("EMA_ALPHA", DEFAULT_VAD_CONFIG["EMA_ALPHA"])
R_MIN = _load_env_float("R_MIN", DEFAULT_VAD_CONFIG["R_MIN"])
R_MAX = _load_env_float("R_MAX", DEFAULT_VAD_CONFIG["R_MAX"])
ADAPT_K = _load_env_float("ADAPT_K", DEFAULT_VAD_CONFIG["ADAPT_K"])
HYSTERESIS_BETA = _load_env_float("HYSTERESIS_BETA", DEFAULT_VAD_CONFIG["HYSTERESIS_BETA"])
DELTA_MIN = _load_env_float("DELTA_MIN", DEFAULT_VAD_CONFIG["DELTA_MIN"])
T_MIN = _load_env_float("T_MIN", DEFAULT_VAD_CONFIG["T_MIN"])
T_MIN_MIN = _load_env_float("T_MIN_MIN", DEFAULT_VAD_CONFIG["T_MIN_MIN"])
T_MIN_MAX = _load_env_float("T_MIN_MAX", DEFAULT_VAD_CONFIG["T_MIN_MAX"])
B_T_MIN = _load_env_float("B_T_MIN", DEFAULT_VAD_CONFIG["B_T_MIN"])

MIN_SPEECH_FRAMES = 2                                         # 2 frames * 128ms = ~260ms minimum speech onset
END_OF_SPEECH_FRAMES = int(os.getenv("END_OF_SPEECH_FRAMES", "11"))   # 11 frames * 128ms = ~1.4s silence window to end speech
MIN_TOTAL_VOICE_FRAMES = 3                                    # Minimum 3 voiced chunks (~380ms) to reject clicks/coughs
MAX_SPEECH_FRAMES = 120                                       # Maximum recording duration (~15 seconds)

# Validate active configuration and enforce safe defaults if invalid
try:
    validate_vad_config(
        delta_min=DELTA_MIN,
        t_min=T_MIN,
        r_min=R_MIN,
        r_max=R_MAX,
        hysteresis_beta=HYSTERESIS_BETA,
        adapt_k=ADAPT_K,
        ema_alpha=EMA_ALPHA,
        t_min_min=T_MIN_MIN,
        t_min_max=T_MIN_MAX,
        b_t_min=B_T_MIN
    )
except ValueError as _cfg_err:
    print(f"⚠ Active VAD configuration validation failed: {_cfg_err}")
    print("✓ Restoring all VAD parameters to safe documented defaults.")
    EMA_ALPHA = DEFAULT_VAD_CONFIG["EMA_ALPHA"]
    R_MIN = DEFAULT_VAD_CONFIG["R_MIN"]
    R_MAX = DEFAULT_VAD_CONFIG["R_MAX"]
    ADAPT_K = DEFAULT_VAD_CONFIG["ADAPT_K"]
    HYSTERESIS_BETA = DEFAULT_VAD_CONFIG["HYSTERESIS_BETA"]
    DELTA_MIN = DEFAULT_VAD_CONFIG["DELTA_MIN"]
    T_MIN = DEFAULT_VAD_CONFIG["T_MIN"]
    T_MIN_MIN = DEFAULT_VAD_CONFIG["T_MIN_MIN"]
    T_MIN_MAX = DEFAULT_VAD_CONFIG["T_MIN_MAX"]
    B_T_MIN = DEFAULT_VAD_CONFIG["B_T_MIN"]

# Dynamic VAD State Variables
B_T = 800.0                   # Ambient noise estimate B_t
B_T_INITIALIZED = False
VOICE_FRAMES_COUNT = 0
SILENCE_FRAMES_COUNT = 0
SESSION_VOICE_FRAMES = 0

# -------------------------------------------------------------------------------------------------

# Resolve working Groq keys (optional)
default_groq_key = os.getenv("GROQ_API_KEY") or os.getenv("CHAT_KEY") or os.getenv("VOICE_KEY")
chat_key = os.getenv("CHAT_KEY") or default_groq_key
voice_key = os.getenv("VOICE_KEY") or default_groq_key
live_key = os.getenv("LIVE_KEY") or default_groq_key

# Create Groq clients if keys provided
chat_client = Groq(api_key=chat_key) if chat_key else None
voice_client = Groq(api_key=voice_key) if voice_key else None
live_client = Groq(api_key=live_key) if live_key else None

# Deterministic Dialogue & Production Interaction Gateway
try:
    from core.dialogue_engine import DialogueEngine
    dialogue_engine = DialogueEngine()
except Exception as e:
    dialogue_engine = None

try:
    from core.gateway import InteractionGateway
    from core.interaction_adapter import InteractionAdapter
    gateway = InteractionGateway()
    interaction_adapter = InteractionAdapter(gateway.event_bus, gateway.fsm, gateway.tts)
    print("✅ Production InteractionGateway & EventBus connected!")
except Exception as e:
    print(f"ℹ InteractionGateway notice: {e}")
    gateway = None
    interaction_adapter = None

PLACES_PATH = os.path.join(BASE_DIR, "config", "places.json")
CAMPUS_PLACES = {}
if os.path.exists(PLACES_PATH):
    try:
        with open(PLACES_PATH, "r", encoding="utf-8") as pf:
            raw_places = json.load(pf)
            CAMPUS_PLACES = {k: v for k, v in raw_places.items() if not k.startswith("_")}
    except Exception as e:
        print(f"Places configuration notice: {e}")

WHISPER_PROMPT = (
    "GraceEMO, Lovely Professional University, LPU, Vice Chancellor, "
    "Dr. Jaspal Singh Sandhu, Dr. Ashok Kumar Mittal, Rashmi Mittal, "
    "Dr. Mohit Arora, Uni-Mall, robotics research lab."
)

def extract_campus_place(text: str) -> str:
    blob = text.lower()
    for key, val in sorted(CAMPUS_PLACES.items(), key=lambda item: len(item[0]), reverse=True):
        if key in blob:
            return val[2] if isinstance(val, (list, tuple)) and len(val) > 2 else key
        if isinstance(val, (list, tuple)) and len(val) > 2 and val[2].lower() in blob:
            return val[2]
    place_keywords = {
        "lab": "Robotics Research Lab",
        "robotics": "Robotics Research Lab",
        "library": "Central Library (B37)",
        "mall": "Uni-Mall Shopping Center",
        "uni-mall": "Uni-Mall Shopping Center",
        "gate": "Main Campus Gate 1",
        "reception": "Welcome Reception Desk",
        "door": "Welcome Reception Desk",
        "ai": "AI Compute Center",
        "commons": "Campus Commons",
        "canteen": "Campus Food Court",
        "auditorium": "Shanti Devi Mittal Auditorium"
    }
    for kw, target in place_keywords.items():
        if kw in blob:
            return target
    return "the designated campus location"


# -------------------------------------------------------------------------------------------------
# Local Native Qwen Model Setup (Apple Silicon GPU / Offline MLX)
# -------------------------------------------------------------------------------------------------
LOCAL_MLX_MODEL = None
LOCAL_MLX_TOKENIZER = None
LOCAL_MLX_SAMPLER = None
LOCAL_MLX_LOGITS_PROCESSORS = None

try:
    from mlx_lm import load as mlx_load, generate as mlx_generate
    from mlx_lm.sample_utils import make_sampler, make_logits_processors

    candidate_paths = [
        os.getenv("LOCAL_MODEL_PATH"),
        os.path.join(BASE_DIR, "models", "Qwen2.5-3B-Instruct-4bit"),
        os.path.join(ROOT_DIR, "models", "Qwen2.5-3B-Instruct-4bit"),
        os.path.expanduser("~/.cache/huggingface/hub/models--mlx-community--Qwen2.5-3B-Instruct-4bit/snapshots/4f83f8f146fdf28b512a06562b671d7af4fab457"),
        "mlx-community/Qwen2.5-3B-Instruct-4bit"
    ]
    model_source = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            model_source = p
            break

    if model_source is None:
        model_source = "mlx-community/Qwen2.5-3B-Instruct-4bit"

    print(f"🧠 Loading Native Local Qwen model from: {model_source}")
    LOCAL_MLX_MODEL, LOCAL_MLX_TOKENIZER = mlx_load(model_source)
    LOCAL_MLX_SAMPLER = make_sampler(temp=0.35, top_p=0.9)
    LOCAL_MLX_LOGITS_PROCESSORS = make_logits_processors(repetition_penalty=1.12, repetition_context_size=40)
    print("✅ Live Local Qwen LLM active (100% Offline, Apple Silicon GPU acceleration)!")
except Exception as e:
    if "mlx" in str(e).lower() or platform.system() != "Darwin":
        print(f"ℹ Local Qwen MLX model unavailable on {platform.system()} ({e})")
    else:
        print(f"ℹ Local Qwen model notice: {e}")
    if chat_client is not None:
        print("✓ Falling back to Groq Cloud API.")
    else:
        print("⚠ Note: No local Qwen model or Groq API key loaded.")

# -------------------------------------------------------------------------------------------------

def collect_info():
    global CONV_HISTORY
    folder = DATA_DIR
    if not os.path.isdir(folder):
        print(f"⚠ Warning: Data folder not found at {folder}")
        return

    files = [f for f in os.listdir(folder) if f.endswith('.txt')]
    
    # Sort files based on the numeric prefix in the filename
    def extract_num(filename):
        match = re.match(r'(\d+)-', filename)
        return int(match.group(1)) if match else float('inf')
    
    files.sort(key=extract_num)
    
    data_str = ''
    for filename in files:
        file_path = os.path.join(folder, filename)
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if data_str:
            data_str += '\n\n'  # Append two newline breaks between file contents
        data_str += content
        
    CONV_HISTORY.append({"role": "system", "content": data_str })
    print(f"✓ Loaded {len(files)} knowledge files into conversation system prompt")

# -------------------------------------------------------------------------------------------------

# Global audio instance and thread safety lock
GLOBAL_AUDIO = None
AUDIO_LOCK = threading.Lock()
RECORDING_LOCK = threading.Lock()
IS_RECORDING = False

def get_audio():
    global GLOBAL_AUDIO
    with AUDIO_LOCK:
        if GLOBAL_AUDIO is None:
            with suppress_c_stderr():
                GLOBAL_AUDIO = pyaudio.PyAudio()
        return GLOBAL_AUDIO

def start_listening_safely():
    global LISTENING_ENABLED, STOP_RECORDING, IS_RECORDING
    if not IS_RECORDING:
        LISTENING_ENABLED = True
        STOP_RECORDING = False
        threading.Thread(target=record_audio, daemon=True).start()

def adjust_threshold(delta_ratio: float = 0.05, delta_T_min: int = 200):
    global R_MIN, R_MAX, T_MIN, CAPTION_TEXT
    R_MIN = float(np.clip(round(R_MIN + delta_ratio, 2), R_MIN_LOWER_BOUND, R_MIN_UPPER_BOUND))
    R_MAX = float(np.clip(round(R_MAX + delta_ratio, 2), R_MAX_LOWER_BOUND, R_MAX_UPPER_BOUND))
    T_MIN = float(np.clip(round(T_MIN + delta_T_min, 1), T_MIN_MIN, T_MIN_MAX))
    caption = f"VAD Sensitivity: r_min={R_MIN:.2f}, r_max={R_MAX:.2f}, T_min={T_MIN:.0f}"
    status = "Stricter (ignores more background people)" if delta_ratio > 0 else "More sensitive"
    print(f"\n🔊 {caption} -> {status}")
    CAPTION_TEXT = caption

def set_threshold_ratio(val: float) -> bool:
    """
    Sets the active VAD base sensitivity ratio (R_MIN) and updates R_MAX within valid bounds.
    Rejects NaN, Inf, non-numeric, and out-of-bound values.
    Returns True if successfully updated, False otherwise.
    """
    global R_MIN, R_MAX, CAPTION_TEXT
    if not isinstance(val, (int, float)) or not math.isfinite(val):
        print(f"⚠ Invalid threshold ratio '{val}'. Must be a finite number between {R_MIN_LOWER_BOUND:.2f} and {R_MIN_UPPER_BOUND:.2f}.")
        return False
    if val < R_MIN_LOWER_BOUND or val > R_MIN_UPPER_BOUND:
        print(f"⚠ Threshold ratio {val:.2f} is out of bounds [{R_MIN_LOWER_BOUND:.2f}, {R_MIN_UPPER_BOUND:.2f}].")
        return False

    R_MIN = float(round(val, 2))
    # Maintain R_MAX proportionally ahead while respecting configured bounds [0.25, 0.90]
    R_MAX = float(np.clip(round(R_MIN + 0.45, 2), R_MAX_LOWER_BOUND, R_MAX_UPPER_BOUND))
    caption = f"VAD Sensitivity: r_min={R_MIN:.2f}, r_max={R_MAX:.2f}, T_min={T_MIN:.0f}"
    print(f"\n🔊 Active threshold ratio set: {caption}")
    CAPTION_TEXT = caption
    return True

def handle_thresh_cli(arg: str) -> bool:
    """
    Parses and applies threshold command from CLI string.
    Returns True if valid and applied, False if invalid or rejected.
    """
    if not arg or not isinstance(arg, str):
        print(f"⚠ Invalid threshold input. Expected numeric value between {R_MIN_LOWER_BOUND:.2f} and {R_MIN_UPPER_BOUND:.2f}.")
        return False
    try:
        val = float(arg.strip())
    except (ValueError, AttributeError):
        print(f"⚠ Invalid threshold input '{arg}'. Expected numeric value between {R_MIN_LOWER_BOUND:.2f} and {R_MIN_UPPER_BOUND:.2f}.")
        return False
    return set_threshold_ratio(val)

def compute_vad_thresholds(b_t: float):
    """Computes (T_start, T_continue, r_t, margin) from current noise floor and VAD settings."""
    q_t = b_t / (b_t + DELTA_MIN)
    r_t = float(np.clip(R_MIN + ADAPT_K * q_t, R_MIN, R_MAX))
    margin = max(r_t * b_t, DELTA_MIN)
    t_start = max(T_MIN, b_t + margin)
    t_continue = max(b_t + 0.35 * margin, HYSTERESIS_BETA * t_start)
    return t_start, t_continue, r_t, margin

''' Keyboard listener callback function '''
def on_press(key):
    global LISTENING_ENABLED, STOP_RECORDING
    try:
        if hasattr(key, 'char') and key.char:
            c = key.char
            if c == 's':
                if not LISTENING_ENABLED:
                    print("⤍ [KEYBOARD] Listening STARTED - Press 'e' to stop")
                    start_listening_safely()
            elif c == 'e':
                if LISTENING_ENABLED:
                    LISTENING_ENABLED = False
                    STOP_RECORDING = True
                    print("⤍ [KEYBOARD] Listening STOPPED - Press 's' to start again")
            elif c in ('+', '=', ']'):
                adjust_threshold(+0.05, +200)
            elif c in ('-', '_', '['):
                adjust_threshold(-0.05, -200)
    except AttributeError:
        pass

''' Function to toggle between listening mode and idle mode using Dynamic VAD Formula '''
def voice_switch(audio_data):
    global B_T, B_T_INITIALIZED, VOICE_FRAMES_COUNT, SILENCE_FRAMES_COUNT, SESSION_VOICE_FRAMES
    global VOICE_FLAG, END_OF_RECORD, NEXT_EXP, LISTENING_ENABLED
    global EMA_ALPHA, R_MIN, R_MAX, ADAPT_K, HYSTERESIS_BETA, DELTA_MIN, T_MIN
    global MIN_SPEECH_FRAMES, END_OF_SPEECH_FRAMES, MAX_SPEECH_FRAMES, B_T_MIN

    # A. Validate incoming audio buffer before calculating RMS
    if audio_data is None:
        t_start, t_cont, _, _ = compute_vad_thresholds(B_T)
        return 0.0, t_start, t_cont

    try:
        arr = np.asarray(audio_data, dtype=np.float32)
    except Exception:
        t_start, t_cont, _, _ = compute_vad_thresholds(B_T)
        return 0.0, t_start, t_cont

    if arr.size == 0 or not np.all(np.isfinite(arr)):
        t_start, t_cont, _, _ = compute_vad_thresholds(B_T)
        return 0.0, t_start, t_cont

    # 1. A. Short-time audio energy E_t (zero-centered RMS to remove DC offset)
    centered = arr - float(np.mean(arr))
    E_t = float(np.sqrt(np.mean(centered ** 2)))

    # Initialize ambient noise estimate on first frame (bounded by B_T_MIN)
    if not B_T_INITIALIZED:
        B_T = max(B_T_MIN, E_t)
        B_T_INITIALIZED = True

    # 1. B. Continuously estimate ambient noise (EMA) - updated ONLY when idle (no speech)
    # Stabilized with B_T_MIN lower bound to prevent indefinite decay toward zero
    if not VOICE_FLAG:
        B_T = max(B_T_MIN, (1.0 - EMA_ALPHA) * B_T + EMA_ALPHA * E_t)

    # 2. Dynamic sensitivity ratio r_t, start threshold T_start, and continuation threshold T_continue
    T_start, T_continue, r_t, margin = compute_vad_thresholds(B_T)

    # State transition logic with hysteresis and minimum speech duration
    if not VOICE_FLAG:
        # Idle state: waiting for energy to exceed T_start for MIN_SPEECH_FRAMES (260ms)
        if E_t > T_start:
            VOICE_FRAMES_COUNT += 1
            SILENCE_FRAMES_COUNT = 0
            if VOICE_FRAMES_COUNT >= MIN_SPEECH_FRAMES and LISTENING_ENABLED:
                VOICE_FLAG = True
                END_OF_RECORD = False
                SESSION_VOICE_FRAMES = VOICE_FRAMES_COUNT
                NEXT_EXP = "focus"
                print(f"✓ [Speech Start] (RMS: {E_t:.0f} > T_start: {T_start:.0f}, Noise B_t: {B_T:.0f}, Ratio r_t: {r_t:.2f})")
        else:
            VOICE_FRAMES_COUNT = 0
            SILENCE_FRAMES_COUNT += 1
            if not LISTENING_ENABLED:
                NEXT_EXP = "idle"
    else:
        # Recording state: continue recording while E_t > T_continue
        if E_t > T_continue:
            # If silence already began (>=2 frames), an isolated low-energy noise fluctuation shouldn't cancel silence
            if SILENCE_FRAMES_COUNT >= 2 and E_t < (T_continue + 0.30 * margin):
                SILENCE_FRAMES_COUNT += 1
            else:
                SILENCE_FRAMES_COUNT = 0
                VOICE_FRAMES_COUNT += 1
                SESSION_VOICE_FRAMES += 1
        else:
            SILENCE_FRAMES_COUNT += 1
            # End-of-speech silence duration (~1.4s) or maximum speech duration limit (~15s)
            if SILENCE_FRAMES_COUNT >= END_OF_SPEECH_FRAMES or VOICE_FRAMES_COUNT >= MAX_SPEECH_FRAMES:
                total_ms = (VOICE_FRAMES_COUNT + SILENCE_FRAMES_COUNT) * 128
                silence_ms = SILENCE_FRAMES_COUNT * 128
                VOICE_FLAG = False
                END_OF_RECORD = True
                print(f"⤍ [Speech End] (Silence: {silence_ms}ms, Total: {total_ms}ms, Voiced Chunks: {SESSION_VOICE_FRAMES})")
                VOICE_FRAMES_COUNT = 0
                NEXT_EXP = "idle"

    return E_t, T_start, T_continue

# -------------------------------------------------------------------------------------------------

def record_audio(output_file="input.wav"):
    global VOICE_FLAG, END_OF_RECORD, VOICE_FRAMES_COUNT, SILENCE_FRAMES_COUNT, SESSION_VOICE_FRAMES
    global STOP_RECORDING, LISTENING_ENABLED, CAPTION_TEXT, IS_RECORDING, END_OF_SPEECH_FRAMES
    global MIN_TOTAL_VOICE_FRAMES, T_MIN

    if not RECORDING_LOCK.acquire(blocking=False):
        return

    IS_RECORDING = True
    # audio recording parameters (2048 samples = 128ms window ~130ms)
    chunk_size = 2048                   # Number of frames per buffer
    format_type = pyaudio.paInt16       # 16-bit resolution
    channels = 1                        # Mono audio
    rate = 16000                        # Sample rate (Hz)

    audio = get_audio()
    stream = None
    
    # Fix PyAudio device error by specifying default input device
    try:
        with suppress_c_stderr():
            default_input = audio.get_default_input_device_info()
            stream = audio.open(
                format=format_type,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=default_input['index'],
                frames_per_buffer=chunk_size,
                stream_callback=None
            )
        print(f"⤍ Using input device: {default_input['name']}")
    except Exception as e:
        print(f"⚠ Error opening audio stream: {e}")
        IS_RECORDING = False
        RECORDING_LOCK.release()
        return

    frames = []
    # Ring buffer for pre-speech frames (4 frames = 512ms pre-roll)
    pre_frames = deque(maxlen=4)
    print("⤍ Start Speaking...")
    CAPTION_TEXT = "Listening... (Speak your question)"
    SESSION_VOICE_FRAMES = 0

    try:
        while True:
            # Check if stop signal received
            if STOP_RECORDING:
                print("⤍ Recording stopped by user")
                break
                
            try:
                data = stream.read(chunk_size, exception_on_overflow=False)
            except Exception as e:
                print(f"⚠ Error reading audio: {e}")
                break

            audio_data = np.frombuffer(data, dtype=np.int16)
            voice_switch(audio_data)

            if VOICE_FLAG:
                frames.append(data)
            else:
                if not END_OF_RECORD:
                    pre_frames.append(data)
                else:
                    break
    finally:
        # Stop and close the stream
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        IS_RECORDING = False
        RECORDING_LOCK.release()

    print("********************")

    # Only process if we have frames and didn't stop manually
    if STOP_RECORDING or not frames:
        print("⤍ No audio recorded or stopped by user")
        VOICE_FLAG = False
        VOICE_FRAMES_COUNT = 0
        SILENCE_FRAMES_COUNT = 0
        END_OF_RECORD = False
        if not STOP_RECORDING and LISTENING_ENABLED:
            time.sleep(0.3)
            start_listening_safely()
        return

    # Filter 1: Reject brief clicks / coughs / throat clears
    if SESSION_VOICE_FRAMES < MIN_TOTAL_VOICE_FRAMES:
        print(f"⤍ [Filtered] Sound too brief ({SESSION_VOICE_FRAMES} voiced chunks < {MIN_TOTAL_VOICE_FRAMES}). Discarding noise spike...")
        VOICE_FLAG = False
        VOICE_FRAMES_COUNT = 0
        SILENCE_FRAMES_COUNT = 0
        END_OF_RECORD = False
        if not STOP_RECORDING and LISTENING_ENABLED:
            time.sleep(0.3)
            start_listening_safely()
        return

    # Backward scan: find the last chunk with real speech energy above noise floor
    margin = max(R_MIN * B_T, DELTA_MIN)
    speech_thresh = B_T + 0.15 * margin
    last_voiced_idx = len(frames) - 1
    for i in range(len(frames) - 1, -1, -1):
        chunk_arr = np.frombuffer(frames[i], dtype=np.int16)
        c = chunk_arr.astype(np.float32) - float(np.mean(chunk_arr))
        rms_c = float(np.sqrt(np.mean(c**2))) if len(c) > 0 else 0.0
        if rms_c > speech_thresh:
            last_voiced_idx = i
            break

    # Keep at least 6 frames (~770ms) of acoustic trailing silence after last voiced chunk
    cutoff_idx = min(len(frames), last_voiced_idx + 7)
    recorded_frames = frames[:cutoff_idx]

    final_frames = list(pre_frames) + recorded_frames
    raw_bytes = b"".join(final_frames)
    audio_arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)

    # Zero-center (remove DC offset)
    audio_arr = audio_arr - float(np.mean(audio_arr))
    rms = float(np.sqrt(np.mean(audio_arr ** 2))) if len(audio_arr) > 0 else 0.0

    # Filter 2: Proximity interaction floor: reject quiet distant murmurs
    if rms < (T_MIN * 0.60):
        print(f"⤍ [Filtered] Speech too distant/quiet (RMS: {rms:.0f} < {T_MIN*0.60:.0f}). Discarding background murmur...")
        VOICE_FLAG = False
        VOICE_FRAMES_COUNT = 0
        SILENCE_FRAMES_COUNT = 0
        END_OF_RECORD = False
        if not STOP_RECORDING and LISTENING_ENABLED:
            time.sleep(0.3)
            start_listening_safely()
        return

    # Peak normalize audio with bounded gain (max 4.0x boost) to avoid amplifying background hiss
    peak = float(np.max(np.abs(audio_arr)))
    if peak > 400.0:
        scale = min(4.0, 26000.0 / peak)
        audio_arr = np.clip(audio_arr * scale, -32768.0, 32767.0)
    normalized_bytes = audio_arr.astype(np.int16).tobytes()

    # Save the recorded audio to a .wav file
    output_path = os.path.join(BASE_DIR, output_file)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(format_type))
        wf.setframerate(rate)
        wf.writeframes(normalized_bytes)

    duration_sec = len(normalized_bytes) / (rate * 2)
    print(f"⤍ Saved {duration_sec:.2f}s audio (RMS: {rms:.0f}, Peak: {peak:.0f}) to {output_file}")

    CAPTION_TEXT = "Processing speech..."
    start_stt = threading.Thread(target=speach2text, args=(output_path,), daemon=True)
    start_stt.start()

    # reset global variables
    VOICE_FLAG = False
    VOICE_FRAMES_COUNT = 0
    SILENCE_FRAMES_COUNT = 0
    END_OF_RECORD = False

def fetch_live_data():
    print(">>>>>>>>>>>>>>>>SA")
    global live_client, CURRENT_QUESTION

    response = ""
    if live_client is not None:
        try:
            completion = live_client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {"role": "system", "content": "You are a real-time factual assistant. Give a direct, concise 1-2 sentence answer without markdown tables or asterisks."},
                    {"role": "user", "content": CURRENT_QUESTION}
                ],
                temperature=0.2,
                max_tokens=200,
                stream=False
            )
            response = completion.choices[0].message.content or ""
            response = re.sub(r"[*#_`|]", "", response).strip()
            print("<<<<<<<<<<<<<<<<SA")
        except Exception as e:
            print(f"Primary search model error: {e}")
            try:
                completion = live_client.chat.completions.create(
                    model="groq/compound-mini",
                    messages=[{"role": "user", "content": f"Answer concisely in 1-2 sentences: {CURRENT_QUESTION}"}],
                    temperature=0.3,
                    max_tokens=150,
                    stream=False
                )
                response = completion.choices[0].message.content or ""
                response = re.sub(r"[*#_`|]", "", response).strip()
            except Exception as e2:
                print(f"Fallback search failed: {e2}")
                response = "I was unable to retrieve live search data right now."
    else:
        response = f"Live search requires a configured API key for: {CURRENT_QUESTION}"

    response = "Searched results: " + response
    print("⚍", response)
    start_chat = threading.Thread(target=chat_model, args=(response,), daemon=False)
    start_chat.start()

def clean_and_deduplicate_speech(text: str) -> str:
    """
    Deduplicates repeated sentences and trailing looping phrases produced by Whisper
    decoding loops, while preserving valid questions.
    """
    if not text:
        return ""
    t = text.strip()

    # 1. Deduplicate identical sentences (e.g. 'Hello. Hello. Hello.')
    sentences = re.split(r'(?<=[.!?])\s+', t)
    unique_sentences = []
    seen = set()
    for s in sentences:
        s_norm = re.sub(r'[^\w\s]', '', s).strip().lower()
        if s_norm and s_norm not in seen:
            seen.add(s_norm)
            unique_sentences.append(s.strip())
    t = ' '.join(unique_sentences)

    # 2. Strip trailing repeated phrases (e.g. 'I am using it. I am using it. I am using it.')
    pattern = r'(\b[\w\s\',-]{3,35}?\b)(?:[.,!?\s]+\1){2,}[.,!?\s]*$'
    t = re.sub(pattern, r'\1.', t, flags=re.IGNORECASE)

    # 3. Clean up acoustic starter artifacts (e.g. 'Queso, ')
    t = re.sub(r'^(queso|so|okay|hey|um|uh)[\s,]+', '', t, flags=re.IGNORECASE)

    return t.strip()

def is_hallucination_or_noise(text: str, segments=None) -> bool:
    t = text.strip().lower()
    if not t or len(t) < 2:
        return True

    exact_ghosts = {"you", "so", ".", "thank you.", "thank you", "bye.", "bye", "watching", "subscribe"}
    if t in exact_ghosts:
        return True

    phrase_ghosts = [
        "thanks for watching", "thank you for watching", "subtitles by",
        "amara.org", "im gonna die", "i am sorry, sir", "i am sorry sir",
        "die in sm", "please subscribe"
    ]
    t_clean = re.sub(r"[^\w\s]", "", t)
    for p in phrase_ghosts:
        if p in t or p in t_clean:
            return True

    if segments:
        all_no_speech = all(
            (getattr(s, "no_speech_prob", 0) if hasattr(s, "no_speech_prob") else (s.get("no_speech_prob", 0) if isinstance(s, dict) else 0)) > 0.85
            for s in segments
        )
        if all_no_speech and len(segments) > 0:
            return True

    valid_single_words = {"stop", "hi", "hey", "hello", "help", "wait", "freeze", "halt", "yes", "no"}
    words = re.findall(r"\b\w+\b", t)
    if len(words) == 1 and words[0] not in valid_single_words:
        return True
    if len(words) < 2 and len(t) < 4:
        return True

    return False

def speach2text(file_loc="input.wav"):
    global CURRENT_QUESTION, voice_client, LISTENING_ENABLED, CAPTION_TEXT
    if voice_client is None:
        print("⚠ voice_client is not configured (missing API key). Set GROQ_API_KEY in .env.")
        return

    try:
        print("---------------->")
        with open(file_loc, "rb") as file:
            transcription = voice_client.audio.transcriptions.create(
                file=(os.path.basename(file_loc), file.read()),
                model="whisper-large-v3-turbo",
                language="en",
                prompt=WHISPER_PROMPT,
                temperature=0.0,
                response_format="verbose_json",
            )
            raw_input = transcription.text.strip()
            # If verbose segments are present, filter out trailing slices with high no_speech_prob
            segments = getattr(transcription, "segments", [])
            valid_segment_texts = []
            if segments:
                for s in segments:
                    no_speech = getattr(s, "no_speech_prob", 0) if hasattr(s, "no_speech_prob") else (s.get("no_speech_prob", 0) if isinstance(s, dict) else 0)
                    seg_text = getattr(s, "text", "") if hasattr(s, "text") else (s.get("text", "") if isinstance(s, dict) else "")
                    if no_speech < 0.60 and seg_text.strip():
                        valid_segment_texts.append(seg_text.strip())
                if valid_segment_texts:
                    raw_input = " ".join(valid_segment_texts)

            raw_input = re.sub(r"^[“\"']+|[”\"']+$", "", raw_input).strip()
            user_input = clean_and_deduplicate_speech(raw_input)
            detected_lang = (getattr(transcription, "language", "") or "english").lower()
            print("<----------------")
            print(f"⚍ Detected Language: {detected_lang} | Human: {user_input}")

            # Filter background Hindi / non-English chatter
            non_english_langs = ["hindi", "hi", "urdu", "ur", "punjabi", "pa", "bengali", "bn", "tamil", "ta", "telugu", "te"]
            if detected_lang in non_english_langs:
                print(f"⤍ [Filtered] Detected background {detected_lang.upper()} chatter ('{user_input}'). Ignoring...")
                time.sleep(0.3)
                start_listening_safely()
                return

            # Filter Whisper silence artifacts & ghost hallucinations
            segments = getattr(transcription, "segments", [])
            if is_hallucination_or_noise(user_input, segments):
                print(f"⤍ [Filtered] Hallucination / silence artifact ignored ('{user_input}').")
                start_listening_safely()
                return

            if CURRENT_QUESTION == user_input:
                start_listening_safely()
                return
            CURRENT_QUESTION = user_input
            CAPTION_TEXT = f"Human: {user_input}"
            start_chat = threading.Thread(target=chat_model, args=(user_input,), daemon=True)
            start_chat.start()
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        CAPTION_TEXT = "Transcription error. Resuming listening..."
        time.sleep(0.5)
        start_listening_safely()

def chat_model(user_input):
    if user_input:
        print(">>>>>>>>>>>>>>>>")
        global CONV_HISTORY, chat_client, LOCAL_MLX_MODEL, LOCAL_MLX_TOKENIZER, NEXT_EXP, gateway

        # Route through Production Interaction Gateway (EventBus, SafetyGate, FSM, and Tracing)
        if gateway is not None:
            gw_res = gateway.process_text(user_input)
            response = gw_res.response
            if gw_res.expression:
                NEXT_EXP = gw_res.expression.value
            print(f"🤖 [Gateway Response ({gw_res.latency_ms:.1f}ms)]: {response}")
            CONV_HISTORY.append({"role": "user", "content": user_input})
            CONV_HISTORY.append({"role": "assistant", "content": response})
            print("<<<<<<<<<<<<<<<<")
            start_tts = threading.Thread(target=asynt_tss, args=(response,), daemon=True)
            start_tts.start()
            return

        CONV_HISTORY.append({"role": "user", "content": user_input})
        response = None
        low_input = user_input.lower().strip()

        # Step A: Deterministic Gratitude Check
        gratitude_phrases = ["thank you", "thanks", "thank u", "many thanks", "appreciate it"]
        if any(g in low_input for g in gratitude_phrases):
            response = "You are very welcome. I am glad to be of assistance. <exp-happy>"

        # Step B: Fast-Path Intent Dispatch via DialogueEngine
        if not response and dialogue_engine is not None:
            try:
                cmd = dialogue_engine.parse(user_input)
                intent = cmd.intent
                if intent == "STOP":
                    response = "Stopping immediately. Standing by for instructions. <exp-idle>"
                elif intent == "NAVIGATE":
                    place_name = extract_campus_place(user_input)
                    response = f"Navigating to {place_name}. Please follow me! <exp-focus>"
                elif intent == "GREET":
                    response = "Hello. It is a pleasure to be with you. How may I be of assistance today? {hand-hi} <exp-happy>"
                elif intent == "HAND_UP":
                    response = "Raising both hands. {hand-up} <exp-happy>"
                elif intent == "HAND_DOWN":
                    response = "Lowering hands. {hand-down} <exp-idle>"
            except Exception as e:
                print(f"DialogueEngine parse notice: {e}")

        # Step C: LLM Reasoning for Queries and Knowledge
        # 1. Tier 1: Live Local Native Qwen Model (Apple Silicon GPU / Offline MLX)
        if not response and LOCAL_MLX_MODEL is not None and LOCAL_MLX_TOKENIZER is not None:
            try:
                t0 = time.time()
                prompt = LOCAL_MLX_TOKENIZER.apply_chat_template(
                    CONV_HISTORY,
                    tokenize=False,
                    add_generation_prompt=True
                )
                raw = mlx_generate(
                    LOCAL_MLX_MODEL,
                    LOCAL_MLX_TOKENIZER,
                    prompt=prompt,
                    max_tokens=240,
                    sampler=LOCAL_MLX_SAMPLER,
                    logits_processors=LOCAL_MLX_LOGITS_PROCESSORS,
                )
                gen_time = time.time() - t0
                response = raw.strip()
                if response:
                    print(f"🧠 [Apple Silicon Local Qwen ({gen_time*1000:.1f}ms)]: {response}")
            except Exception as e:
                print(f"Local Qwen generation notice: {e}")

        # 2. Tier 2: Groq Cloud API with qwen/qwen3.8-27b (High Accuracy Ground Truth)
        if not response and chat_client is not None:
            # Maintain sliding window history: system prompt + last 6 turns
            history_window = [CONV_HISTORY[0]] + CONV_HISTORY[-6:] if len(CONV_HISTORY) > 7 else list(CONV_HISTORY)
            try:
                completion = chat_client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=history_window,
                    temperature=0.2,
                    top_p=0.85,
                    max_tokens=240,
                    stream=False
                )
                response = completion.choices[0].message.content
                print("<<<<<<<<<<<<<<<< (Groq qwen3.8-27b)")
            except Exception as e:
                print(f"Groq primary (qwen3.8-27b) error: {e}")
                try:
                    completion = chat_client.chat.completions.create(
                        model="groq/compound-mini",
                        messages=history_window,
                        temperature=0.3,
                        top_p=0.8,
                        max_tokens=240,
                        stream=False
                    )
                    response = completion.choices[0].message.content
                    print("<<<<<<<<<<<<<<<< (Groq compound-mini fallback)")
                except Exception as e2:
                    print(f"Groq fallback failed: {e2}")

        if not response:
            response = "I am listening. Could you please clarify your question, or let me know what subject you would like to explore? <exp-focus>"

        CONV_HISTORY.append({"role": "assistant", "content": response})
        print("<<<<<<<<<<<<<<<<")

        start_tts = threading.Thread(target=asynt_tss, args=(response,), daemon=True)
        start_tts.start()
    else:
        start_listening_safely()

def phonetic_speech_normalize(text: str) -> str:
    """
    Normalizes abbreviations, titles, and academic credentials into full spoken English
    so TTS (Edge-TTS / espeak) pronounces words fluently (e.g. 'Doctor' instead of 'dr').
    """
    if not text:
        return ""
    t = text
    # 1. Remove emotion/avatar tags like <exp-happy>, <exp-idle>
    t = re.sub(r"<exp-[a-zA-Z0-9_-]+>", "", t)
    # 2. Remove curly action brackets like {hand-hi}, {search}
    t = re.sub(r"\{[^{}]*\}", "", t)
    # 3. Parenthesized titles like (Dr.) or (Prof.)
    t = re.sub(r"\(\s*Prof\.?\s*\(?\s*Dr\.?\s*\)?\s*\)", "Professor Doctor", t, flags=re.IGNORECASE)
    t = re.sub(r"\(\s*Dr\.?\s*\)", "Doctor", t, flags=re.IGNORECASE)
    t = re.sub(r"\(\s*Prof\.?\s*\)", "Professor", t, flags=re.IGNORECASE)
    t = re.sub(r"\(\s*Doctor\s*\)", "Doctor", t, flags=re.IGNORECASE)
    t = re.sub(r"\(\s*Professor\s*\)", "Professor", t, flags=re.IGNORECASE)
    # 4. Combined titles like Prof. (Dr.) or Prof. Dr.
    t = re.sub(r"\bProf\.?\s*\(?\s*Dr\.?\s*\)?\b", "Professor Doctor", t, flags=re.IGNORECASE)
    t = re.sub(r"\bProf\.?\s+Dr\.?\b", "Professor Doctor", t, flags=re.IGNORECASE)
    # 5. Standalone titles followed by a name or capital letter
    t = re.sub(r"\bDr\.(?=\s+[A-Z])", "Doctor", t)
    t = re.sub(r"\bDr\b(?=\s+[A-Z])", "Doctor", t)
    t = re.sub(r"\bProf\.(?=\s+[A-Z])", "Professor", t)
    t = re.sub(r"\bProf\b(?=\s+[A-Z])", "Professor", t)
    t = re.sub(r"\bMr\.(?=\s+[A-Z])", "Mister", t)
    t = re.sub(r"\bMr\b(?=\s+[A-Z])", "Mister", t)
    t = re.sub(r"\bMrs\.(?=\s+[A-Z])", "Missus", t)
    t = re.sub(r"\bMrs\b(?=\s+[A-Z])", "Missus", t)
    t = re.sub(r"\bMs\.(?=\s+[A-Z])", "Miz", t)
    t = re.sub(r"\bMs\b(?=\s+[A-Z])", "Miz", t)
    # 6. Academic roles & university acronyms
    t = re.sub(r"\bPro-VC\b", "Pro Vice-Chancellor", t, flags=re.IGNORECASE)
    t = re.sub(r"\bVC\b", "Vice Chancellor", t)
    t = re.sub(r"\bUGC\b", "U G C", t)
    t = re.sub(r"\bNIRF\b", "N I R F", t)
    # 7. Clean markdown formatting and LaTeX syntax for spoken delivery
    t = re.sub(r"#{1,6}\s*", "", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"\$\$(.*?)\$\$", r"\1", t)
    t = re.sub(r"\$([^\$]+)\$", r"\1", t)
    t = re.sub(r"\\([a-zA-Z]+)", r"\1", t)
    # 8. Clean up whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

async def text2speech(text):
    restart = True
    end_conv = False
    if "{search}" in text:
        restart = False
    if "{stop-record}" in text:
        end_conv = True
    text = function_extract(text)
    if not text.strip() and end_conv:
        text = "Goodbye! Have a great day."
    print("⚍ GraceEMO:", text)
    global CAPTION_TEXT, NEXT_EXP, LISTENING_ENABLED

    CAPTION_TEXT = text
    tts_played = False
    spoken_text = phonetic_speech_normalize(text)

    try:
        if spoken_text.strip():
            # Select the language for TTS
            communicate = edge_tts.Communicate(spoken_text, voice='en-IN-NeerjaNeural')
            audio_buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and chunk["data"]:
                    audio_buffer.write(chunk["data"])

            if audio_buffer.tell() > 0:
                audio_buffer.seek(0)
                # Convert to AudioSegment (MP3)
                speech_audio = AudioSegment.from_file(audio_buffer, format="mp3")

                # Ensure there is no noise by adding a small silent segment at the start if needed
                silence = AudioSegment.silent(duration=50)  # 50ms silence before speech
                final_audio = silence + speech_audio
                
                # Export final audio as WAV
                output_wav_path = os.path.join(BASE_DIR, "output.wav")
                final_audio.export(output_wav_path, format="wav")

                # Audio Playback
                if sys.platform == "darwin":
                    subprocess.run(["afplay", output_wav_path])
                elif os.path.exists("/usr/bin/pw-play"):
                    subprocess.run(["/usr/bin/pw-play", output_wav_path])
                elif os.path.exists("/usr/bin/aplay"):
                    subprocess.run(["/usr/bin/aplay", "-q", output_wav_path])
                else:
                    pygame.mixer.music.load(output_wav_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                tts_played = True
    except Exception as e:
        print(f"⚠ Edge TTS notice: {e}")

    # Offline local fallback if Edge TTS fails or network issues occur
    if not tts_played and spoken_text.strip() and os.path.exists("/usr/bin/espeak-ng"):
        try:
            output_wav_path = os.path.join(BASE_DIR, "output.wav")
            subprocess.run(["/usr/bin/espeak-ng", "-s", "150", "-w", output_wav_path, spoken_text], check=True)
            if os.path.exists("/usr/bin/pw-play"):
                subprocess.run(["/usr/bin/pw-play", output_wav_path])
            elif os.path.exists("/usr/bin/aplay"):
                subprocess.run(["/usr/bin/aplay", "-q", output_wav_path])
            else:
                pygame.mixer.music.load(output_wav_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
        except Exception as e_esp:
            print(f"⚠ Local TTS fallback notice: {e_esp}")

    NEXT_EXP = "idle"
    if end_conv:
        print("⤍ Back to sleep")
        CAPTION_TEXT = "[s] Speak  |  [f] Fullscreen  |  [q] Quit"
        LISTENING_ENABLED = False
    elif restart and LISTENING_ENABLED and not STOP_RECORDING:
        print("|||||||||||||||||||||||||||||||||||||||||||||||")
        time.sleep(0.3)
        start_listening_safely()

    CAPTION_TEXT = " "

def draw_caption(surface, text, font, color, y_offset=10):
    """
        Draws a caption at the bottom of the screen.
    """
    if not text or not text.strip():
        return
    # Strip emojis and unrenderable symbols to prevent missing-glyph boxes
    clean_text = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\ufe0f]', '', text).strip()
    if not clean_text:
        return
    if font is None:
        if os.path.exists(FONT_PATH):
            font = pygame.font.Font(FONT_PATH, 22)
        else:
            font = pygame.font.SysFont(None, 24)

    caption_surface = font.render(clean_text, True, color)
    caption_rect = caption_surface.get_rect(
        center=(
            surface.get_width() // 2,
            surface.get_height() - y_offset - caption_surface.get_height() // 2,
        )
    )
    surface.blit(caption_surface, caption_rect)

def get_random_video(folder_path):
    '''
        Get a random video from a folder
    '''
    try:
        files = os.listdir(folder_path)
        videos = [file for file in files if file.endswith(('.mkv', '.mp4', '.avi')) and os.path.isfile(os.path.join(folder_path, file))]
        if not videos:
            return None
        random_video = random.choice(videos)
        return os.path.join(folder_path, random_video)
    except FileNotFoundError:
        return None

def extract_and_apply_exp(text):
    global NEXT_EXP
    exp_list = ['happy', 'sad', 'focus', 'angry', 'idle', 'intent']
    match = re.search(r"<exp-([a-zA-Z]+)>", text)
    if match:
        exp = match.group(1).lower()
        if exp in exp_list:
            NEXT_EXP = exp
    clean_text = re.sub(r"<exp-[a-zA-Z]+>", "", text)
    return clean_text.strip()

def asynt_tss(response):
    if response:
        remain = extract_and_apply_exp(response)
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(text2speech(remain))
        except Exception as e:
            print(f"TTS error: {e}")
            start_listening_safely()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)
    else:
        start_listening_safely()

def create_exp(token):
    global NEXT_EXP
    exp_list = ['happy', 'sad', 'focus', 'angry', 'idle', 'intent']
    clean = re.sub(r"[^a-zA-Z]", "", token.replace("exp-", ""))
    if clean in exp_list:
        NEXT_EXP = clean
    else:
        NEXT_EXP = "idle"

def function_extract(text):
    matches = re.findall(r"\{\s*(.*?)\s*\}", text)
    for extracted in matches:
        print("⚍ Function:", extracted)
        thread = threading.Thread(target=function_call, args=(extracted,))
        thread.start()

    remaining = re.sub(r"\{\s*.*?\s*\}", "", text)
    remaining = re.sub(r'\s+', ' ', remaining).strip()
    return remaining

def function_call(fn):
    fn_low = fn.lower().strip()
    if fn_low in ('stop-record', 'stop'):
        pass
    elif fn_low == 'search':
        print("⤍ searching...")
        live_search = threading.Thread(target=fetch_live_data, daemon=True)
        live_search.start()
    else:
        print(f"⤍ [Action]: {fn}")

def terminal_input_listener():
    time.sleep(1.0)
    print("💬 [Input Ready] Press 's' to speak, '+' / '-' to adjust threshold, or type your question below:")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            text = line.strip()
            if not text:
                continue
            if text in ('+', '++'):
                adjust_threshold(+0.05, +200)
                continue
            elif text in ('-', '--'):
                adjust_threshold(-0.05, -200)
                continue
            elif text.startswith('thresh'):
                parts = text.split()
                if len(parts) > 1:
                    handle_thresh_cli(parts[1])
                else:
                    print(f"ℹ Current VAD sensitivity: r_min={R_MIN:.2f}, r_max={R_MAX:.2f}, T_min={T_MIN:.0f}. Usage: thresh <{R_MIN_LOWER_BOUND:.2f}-{R_MIN_UPPER_BOUND:.2f}>")
                continue
            elif text.lower() == 's':
                on_press(type('Key', (), {'char': 's'})())
            elif text.lower() == 'e':
                on_press(type('Key', (), {'char': 'e'})())
            elif text.lower() in ('q', 'exit', 'quit'):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                break
            else:
                print(f"\n⚍ Human (Typed): {text}")
                global CURRENT_QUESTION, CAPTION_TEXT
                CURRENT_QUESTION = text
                CAPTION_TEXT = f"Human: {text}"
                threading.Thread(target=chat_model, args=(text,), daemon=True).start()
        except Exception:
            break

def GUI():
    global win, SCREEN_WIDTH, SCREEN_HEIGHT, VID_DIR, CAPTION_TEXT, NEXT_EXP, CURRENT_EXP, PREVIOUS_EXP, fullscreen

    collect_info()
    
    # Load initial video
    init_folder = os.path.join(VID_DIR, "focus-idle")
    next_vid = get_random_video(init_folder)
    if not next_vid or not os.path.exists(next_vid):
        # Fallback to any folder in VID_DIR
        subdirs = [d for d in os.listdir(VID_DIR) if os.path.isdir(os.path.join(VID_DIR, d))]
        if subdirs:
            next_vid = get_random_video(os.path.join(VID_DIR, subdirs[0]))

    if not next_vid:
        print(f"⚠ Error: No videos found in {VID_DIR}")
        return

    # Connect production interaction adapter to EventBus
    if interaction_adapter and gateway:
        def _sync_exp(exp):
            global NEXT_EXP
            NEXT_EXP = exp.value
        interaction_adapter.set_expression_callback(_sync_exp)
        gateway.event_bus.start_sse_listener()

    with suppress_c_stderr():
        vid = Video(next_vid)

    # Start keyboard listener: Pygame window handles keys directly;
    # global OS listener is opt-in on Linux to avoid GNOME Shell permission prompts
    if os.getenv("ENABLE_GLOBAL_HOTKEYS", "0") == "1" or sys.platform == "darwin":
        try:
            listener = keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except Exception as e:
            print(f"ℹ Global keyboard hook notice: {e} (Pygame window key controls active)")

    # Start terminal input reader in non-blocking daemon thread
    term_thread = threading.Thread(target=terminal_input_listener, daemon=True)
    term_thread.start()

    print("\n=======================================================")
    print("  🤖 GraceEMO Dynamic VAD & Proximity Interaction Active")
    print("  Formula: E_t RMS vs Adaptive T_start & T_continue")
    print(f"  Parameters: r_min={R_MIN:.2f}, r_max={R_MAX:.2f}, beta={HYSTERESIS_BETA:.2f}, T_min={T_MIN:.0f}")
    print("  Controls (optional):")
    print("    [s]       -> Force start listening")
    print("    [e]       -> Force stop & process immediately")
    print("    [+] / [-] -> Increase / Decrease VAD sensitivity threshold")
    print("    [f]       -> Toggle Fullscreen / Window")
    print("    [q] / Esc -> Exit")
    print("    Terminal  : Type text, '+' / '-', or questions and press Enter")
    print("=======================================================\n")

    # Auto-start hands-free voice listening immediately!
    print("⤍ [Auto-Voice] Hands-free automatic voice interaction active!")
    LISTENING_ENABLED = True
    STOP_RECORDING = False
    CAPTION_TEXT = "Listening... (Speak your question)"
    start_listening_safely()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h
                win = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    on_press(type('Key', (), {'char': 's'})())
                elif event.key == pygame.K_e:
                    on_press(type('Key', (), {'char': 'e'})())
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_RIGHTBRACKET):
                    adjust_threshold(+0.05, +200)
                elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_LEFTBRACKET):
                    adjust_threshold(-0.05, -200)
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        win = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        win = pygame.display.set_mode((1024, 768), pygame.RESIZABLE)
                    SCREEN_WIDTH, SCREEN_HEIGHT = pygame.display.get_surface().get_size()
                elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        vid.mute()
        vid.resize(size=(SCREEN_WIDTH, SCREEN_HEIGHT))

        # Draw the video frame
        vid.draw(win, pos=(0, 0), force_draw=True)
        draw_caption(win, text=CAPTION_TEXT, font=None, color=(49, 113, 225), y_offset=30)

        if not vid.active:
            PREVIOUS_EXP = CURRENT_EXP
            CURRENT_EXP = NEXT_EXP
            trans_folder = os.path.join(VID_DIR, f"{PREVIOUS_EXP}-{CURRENT_EXP}")
            next_vid = get_random_video(trans_folder)
            if not next_vid:
                next_vid = get_random_video(os.path.join(VID_DIR, "idle-idle"))
            if next_vid:
                try:
                    vid.close()
                except Exception:
                    pass
                with suppress_c_stderr():
                    vid = Video(next_vid)
                vid.restart()

        pygame.display.update()
        pygame.time.wait(16)

    STOP_RECORDING = True
    LISTENING_ENABLED = False
    try:
        vid.close()
    except Exception:
        pass
    try:
        pygame.quit()
    except Exception:
        pass
    if GLOBAL_AUDIO is not None:
        try:
            GLOBAL_AUDIO.terminate()
        except Exception:
            pass
    print("GraceEMO stopped.")
    os._exit(0)

if __name__ == "__main__":
    GUI()
