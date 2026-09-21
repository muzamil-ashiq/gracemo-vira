print("… Loading...")
import platform
import os
import wave
import numpy as np
from groq import Groq
import pyaudio
from dotenv import load_dotenv
import asyncio
import io
import edge_tts # TTS
from pydub import AudioSegment
from pyvidplayer2 import Video # robo face video player
os.environ['SDL_AUDIODRIVER'] = 'dummy'
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

# Deterministic Dialogue & Campus Places System (from git repository)
try:
    from core.dialogue_engine import DialogueEngine
    dialogue_engine = DialogueEngine()
except Exception as e:
    dialogue_engine = None

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
    "Founder Chancellor Dr. Ashok Kumar Mittal, Pro-Chancellor Mrs. Rashmi Mittal, "
    "Dr. Mohit Arora, Sam Davi, Sameer, Muzammil, John Allson, Sarvesh, Alex Matthew, Balamurugan, "
    "Robotics Research Lab, AI Compute Center, Uni-Mall, Central Library, Punjab, Phagwara, NAAC A++, NIRF."
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

''' Keyboard listener callback function '''
def on_press(key):
    global LISTENING_ENABLED, STOP_RECORDING, CAPTION_TEXT, NEXT_EXP
    try:
        char = getattr(key, 'char', None)
        if char == 's':
            if not LISTENING_ENABLED:
                LISTENING_ENABLED = True
                STOP_RECORDING = False
                CAPTION_TEXT = "🎙️ Listening... (Speak clearly, press 'e' when finished)"
                NEXT_EXP = "focus"
                print("\n⤍ [KEYBOARD] Listening STARTED - Speak your question now (Press 'e' or Enter to finish)")
                start_record = threading.Thread(target=record_audio, daemon=False)
                start_record.start()
        elif char == 'e':
            if LISTENING_ENABLED:
                LISTENING_ENABLED = False
                STOP_RECORDING = True
                CAPTION_TEXT = "Processing speech..."
                print("\n⤍ [KEYBOARD] Listening STOPPED - Processing speech...")
    except Exception:
        pass

''' Function to toggle between listening mode and idle mode based on audio energy '''
def voice_switch(energy):
    global T_QUEUE, VOICE_COUNT, SILENCE_COUNT, VOICE_FLAG, END_OF_RECORD, NEXT_EXP, LISTENING_ENABLED
    
    if not T_QUEUE:
        T_QUEUE.append(energy)
        return

    t_mean = sum(T_QUEUE) / len(T_QUEUE)
    high_threshold = max(180000, t_mean * 1.25)  # 25% above ambient floor

    if energy > high_threshold:
        VOICE_COUNT += 1
        SILENCE_COUNT = 0
        if VOICE_COUNT >= 2 and not VOICE_FLAG:
            VOICE_FLAG = True
            NEXT_EXP = "focus"
            print("✓ [Voice Active]")
    else:
        SILENCE_COUNT += 1
        if not VOICE_FLAG:
            T_QUEUE.append(energy)
            if len(T_QUEUE) > 20:
                T_QUEUE.pop(0)

        # Automatic end-of-speech detection: silence after voice was detected
        if VOICE_FLAG and SILENCE_COUNT > 11:  # ~1.4s of silence after speaking
            print("⤍ End of speech detected (auto-processing)")
            END_OF_RECORD = True

# -------------------------------------------------------------------------------------------------

def record_audio(output_file="input.wav"):
    global VOICE_FLAG, END_OF_RECORD, T_QUEUE, VOICE_COUNT, SILENCE_COUNT, STOP_RECORDING, LISTENING_ENABLED, CAPTION_TEXT

    chunk_size = 2048
    format_type = pyaudio.paInt16
    channels = 1
    rate = 16000

    audio = pyaudio.PyAudio()
    stream = None
    
    try:
        default_input = audio.get_default_input_device_info()
        stream = audio.open(
            format=format_type,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=default_input['index'],
            frames_per_buffer=chunk_size,
        )
    except Exception as e:
        print(f"⚠ Error opening audio stream: {e}")
        audio.terminate()
        LISTENING_ENABLED = False
        CAPTION_TEXT = "Microphone error. You can type in the terminal."
        return

    # Calibrate ambient noise floor
    calib = []
    for _ in range(5):
        try:
            d = stream.read(chunk_size, exception_on_overflow=False)
            arr = np.frombuffer(d, dtype=np.int16)
            centered = arr - int(arr.mean())
            calib.append(int(np.sum(np.abs(centered))))
        except Exception:
            pass
    if calib:
        T_QUEUE = calib.copy()

    pre_frames = deque(maxlen=10)
    speech_frames = []
    VOICE_FLAG = False
    VOICE_COUNT = 0
    SILENCE_COUNT = 0
    END_OF_RECORD = False

    CAPTION_TEXT = "🎙️ Listening... (Speak your question)"

    while not STOP_RECORDING and LISTENING_ENABLED:
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
        except Exception as e:
            print(f"⚠ Audio read warning: {e}")
            break

        audio_data = np.frombuffer(data, dtype=np.int16)
        energy = int(np.sum(np.abs(audio_data - int(audio_data.mean()))))
        voice_switch(energy)

        if VOICE_FLAG:
            speech_frames.append(data)
            if END_OF_RECORD:
                break
        else:
            pre_frames.append(data)

    # Stop and close the stream
    try:
        stream.stop_stream()
        stream.close()
    except Exception:
        pass
    audio.terminate()

    LISTENING_ENABLED = False
    STOP_RECORDING = False

    final_frames = list(pre_frames) + speech_frames

    # Process audio if speech was captured (at least 2 speech chunks)
    if len(speech_frames) >= 2:
        print(f"******************** [Captured {len(speech_frames)} speech chunks] ********************")
        CAPTION_TEXT = "Transcribing audio..."
        output_path = os.path.join(BASE_DIR, output_file)
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(format_type))
            wf.setframerate(rate)
            wf.writeframes(b"".join(final_frames))

        start_stt = threading.Thread(target=speach2text, args=(output_path,), daemon=False)
        start_stt.start()
    else:
        # If stopped without speech, auto-resume listening if still running
        if not STOP_RECORDING:
            time.sleep(0.3)
            LISTENING_ENABLED = True
            threading.Thread(target=record_audio, daemon=False).start()

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

def speach2text(file_loc="input.wav"):
    global CURRENT_QUESTION, voice_client, LISTENING_ENABLED
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
                response_format="verbose_json",
                prompt=WHISPER_PROMPT,
                temperature=0.0,
            )
            user_input = transcription.text.strip()
            print("<----------------")
            print("⚍ Human:", user_input)

            # Filter Whisper silence artifacts & ghost hallucinations
            lower = user_input.lower().strip()
            ghosts = ["thanks for watching", "subtitles by", "bye.", "you", "so", "."]
            if not user_input or lower in ghosts or len(user_input) < 2:
                print("⤍ [Filtered] Silence or ambient noise artifact ignored. Auto-resuming listening...")
                CAPTION_TEXT = "🎙️ Listening... (Speak your question)"
                time.sleep(0.3)
                LISTENING_ENABLED = True
                threading.Thread(target=record_audio, daemon=False).start()
                return

            CURRENT_QUESTION = user_input
            CAPTION_TEXT = f"Human: {user_input}"
            start_chat = threading.Thread(target=chat_model, args=(user_input,), daemon=False)
            start_chat.start()
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        CAPTION_TEXT = "Transcription error. Resuming listening..."
        time.sleep(0.5)
        LISTENING_ENABLED = True
        threading.Thread(target=record_audio, daemon=False).start()

def chat_model(user_input):
    if user_input:
        print(">>>>>>>>>>>>>>>>")
        global CONV_HISTORY, chat_client, LOCAL_MLX_MODEL, LOCAL_MLX_TOKENIZER

        CONV_HISTORY.append({"role": "user", "content": user_input})
        response = None
        low_input = user_input.lower().strip()

        # Step A: Deterministic Gratitude Check
        gratitude_phrases = ["thank you", "thanks", "thank u", "many thanks", "appreciate it"]
        if any(g in low_input for g in gratitude_phrases):
            response = "You are most welcome! Always an absolute pleasure to assist our LPU family. <exp-happy>"

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
                    response = "Hello! Welcome to Lovely Professional University. How may I assist you today? {hand-hi} <exp-happy>"
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
                    max_tokens=120,
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
                    max_tokens=150,
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
                        max_tokens=150,
                        stream=False
                    )
                    response = completion.choices[0].message.content
                    print("<<<<<<<<<<<<<<<< (Groq compound-mini fallback)")
                except Exception as e2:
                    print(f"Groq fallback failed: {e2}")

        if not response:
            response = "I am GraceEMO, Vice Chancellor at LPU. How may I assist you today? <exp-happy>"

        CONV_HISTORY.append({"role": "assistant", "content": response})
        print("<<<<<<<<<<<<<<<<")

        start_tts = threading.Thread(target=asynt_tss, args=(response,), daemon=False)
        start_tts.start()
    else:
        record_audio()

async def text2speech(text):
    restart = True
    end_conv = False
    if "{search}" in text:
        restart = False
    if "{stop-record}" in text:
        end_conv = True
    text = function_extract(text)
    print("⚍ GraceEMO:", text)
    global CAPTION_TEXT, NEXT_EXP

    CAPTION_TEXT = text

    # Select the language for TTS
    communicate = edge_tts.Communicate(text, voice='en-IN-NeerjaNeural')
    
    # Use edge-tts and convert to WAV
    try:
        mp3_path = os.path.join(BASE_DIR, "output.mp3")
        output_wav_path = os.path.join(BASE_DIR, "output.wav")
        await communicate.save(mp3_path)
        
        # Fast direct ffmpeg conversion to 24kHz 16-bit mono WAV
        ffmpeg_bin = "/home/sam/.local/bin/ffmpeg" if os.path.exists("/home/sam/.local/bin/ffmpeg") else "ffmpeg"
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", mp3_path, "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", output_wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        # Audio Playback:
        # On macOS: afplay
        # On Linux: pw-play / aplay
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

        NEXT_EXP = "idle"
        if end_conv:
            print("⤍ Back to sleep")
            CAPTION_TEXT = "[s] Speak  |  [f] Fullscreen  |  [q] Quit"
            LISTENING_ENABLED = False
        else:
            print("\n⤍ [Auto-Listening] GraceEMO is listening for your next question...")
            CAPTION_TEXT = "🎙️ Listening... (Speak your question)"
            LISTENING_ENABLED = True
            STOP_RECORDING = False
            time.sleep(0.4)
            threading.Thread(target=record_audio, daemon=False).start()
    except Exception as e:
        print(f"Error occurred while processing audio: {e}")

def draw_caption(surface, text, font, color, y_offset=10):
    """
        Draws a caption at the bottom of the screen.
    """
    if font is None:
        if os.path.exists(FONT_PATH):
            font = pygame.font.Font(FONT_PATH, 22)
        else:
            font = pygame.font.SysFont(None, 24)

    caption_surface = font.render(text, True, color)
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
        asyncio.run(text2speech(remain))
    else:
        record_audio()

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
        live_search = threading.Thread(target=fetch_live_data, daemon=False)
        live_search.start()
    else:
        print(f"⤍ [Action]: {fn}")

def terminal_input_listener():
    time.sleep(1.0)
    print("💬 [Input Ready] Press 's' to speak, or type your question below and press Enter:")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            text = line.strip()
            if not text:
                continue
            if text.lower() == 's':
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
                threading.Thread(target=chat_model, args=(text,), daemon=False).start()
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

    vid = Video(next_vid)

    # Start keyboard listener in non-blocking mode
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
    print("  🤖 GraceEMO Automatic Hands-Free Voice Interaction Active")
    print("  Speak your question naturally at any time!")
    print("  Controls (optional):")
    print("    [s] -> Force start listening")
    print("    [e] -> Force stop & process immediately")
    print("    [f] -> Toggle Fullscreen / Window")
    print("    [q] / Esc -> Exit")
    print("    Terminal: You can also type questions and press Enter")
    print("=======================================================\n")

    # Auto-start hands-free voice listening immediately!
    print("⤍ [Auto-Voice] Hands-free automatic voice interaction active!")
    LISTENING_ENABLED = True
    STOP_RECORDING = False
    CAPTION_TEXT = "🎙️ Listening... (Speak your question)"
    auto_thread = threading.Thread(target=record_audio, daemon=False)
    auto_thread.start()

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
                vid = Video(next_vid)
                vid.restart()

        pygame.display.update()
        pygame.time.wait(16)

    vid.close()
    pygame.quit()
    print("GraceEMO stopped.")

if __name__ == "__main__":
    GUI()
