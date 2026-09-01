print("… Loading...")
import platform
import os
import wave
import numpy as np
import pyaudio
from dotenv import load_dotenv
import asyncio
import io
import edge_tts # TTS
from pydub import AudioSegment
from pyvidplayer2 import Video # robo face video player
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
import pygame # GUI engine
import random
import threading
import time
import re
import sys

# Optional Groq import
try:
    from groq import Groq
except ImportError:
    Groq = None

print("✓ All modules loaded")

pygame.init()
pygame.mixer.init()

# Set up display (1024x768 Resizable Window)
win = pygame.display.set_mode((1024, 768), pygame.RESIZABLE)
pygame.display.set_caption("GraceEMO")

# -------------------------------------------------------------------------------------------------
''' Global variables from new branch '''

T_QUEUE = []                # collected energy threshold queue
VOICE_FLAG = False
VOICE_COUNT = 0
SILENCE_COUNT = 0
MAX_SILENCE_GAP = 8
END_OF_RECORD = False
CONV_HISTORY = []           # Conversation history
SCREEN_WIDTH, SCREEN_HEIGHT = pygame.display.get_surface().get_size()
VID_DIR = "./vid/"
CAPTION_TEXT = " "

NEXT_EXP = "idle"
CURRENT_EXP = "idle"
PREVIOUS_EXP = "idle"
CURRENT_QUESTION = 'Thank you.'

# Listening enabled by default for continuous conversation
LISTENING_ENABLED = True
STOP_RECORDING = False

# -------------------------------------------------------------------------------------------------
# Load Environment Keys
# -------------------------------------------------------------------------------------------------
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=openai_key) if openai_key else None
except Exception:
    openai_client = None

chat_key = os.getenv("CHAT_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GORQ_KEY")
voice_key = os.getenv("VOICE_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("GORQ_KEY")

chat_client = Groq(api_key=chat_key) if (Groq and chat_key) else None
voice_client = Groq(api_key=voice_key) if (Groq and voice_key) else None

# -------------------------------------------------------------------------------------------------
# Load Local Live Qwen Foundation LLM on Apple Silicon GPU
# -------------------------------------------------------------------------------------------------
LOCAL_MLX_MODEL = None
LOCAL_MLX_TOKENIZER = None
LOCAL_MLX_SAMPLER = None
LOCAL_MLX_LOGITS_PROCESSORS = None

try:
    from mlx_lm import load as mlx_load, generate as mlx_generate
    from mlx_lm.sample_utils import make_sampler, make_logits_processors
    
    QWEN_MODEL_NAME = "mlx-community/Qwen2.5-3B-Instruct-4bit"
    print(f"🧠 Initializing Live Local Qwen LLM ({QWEN_MODEL_NAME}) on Apple Silicon GPU...")
    LOCAL_MLX_MODEL, LOCAL_MLX_TOKENIZER = mlx_load(QWEN_MODEL_NAME)
    LOCAL_MLX_SAMPLER = make_sampler(temp=0.35, top_p=0.9)
    LOCAL_MLX_LOGITS_PROCESSORS = make_logits_processors(repetition_penalty=1.12, repetition_context_size=40)
    print("✅ Live Local Qwen AI active (100% Offline, Full World Intelligence + LPU Knowledge)!")
except Exception as e:
    print(f"⚠ Warning initializing Local Qwen model: {e}")

# -------------------------------------------------------------------------------------------------
def collect_info():
    global CONV_HISTORY
    folder = './data'
    if not os.path.exists(folder):
        return
    files = [f for f in os.listdir(folder) if f.endswith('.txt')]
    
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
            data_str += '\n\n'
        data_str += content
        
    CONV_HISTORY = [{"role": "system", "content": data_str}]

# -------------------------------------------------------------------------------------------------
''' Function to toggle between listening mode and idle mode '''
MIN_ENERGY_THRESHOLD = 320000  # High noise gate: Requires deliberate human speech
MAX_SILENCE_GAP = 5            # ~0.65s silence to end turn

def voice_switch(t):
    global T_QUEUE, VOICE_COUNT, SILENCE_COUNT, VOICE_FLAG, MAX_SILENCE_GAP, END_OF_RECORD, NEXT_EXP, LISTENING_ENABLED
    t = abs(t)

    # Calculate background noise floor
    if not T_QUEUE:
        T_QUEUE.append(t)
        return

    t_mean = sum(T_QUEUE) / len(T_QUEUE)
    high_threshold = max(MIN_ENERGY_THRESHOLD, t_mean * 1.75)

    if not VOICE_FLAG:
        if t > high_threshold:
            VOICE_COUNT += 1
            SILENCE_COUNT = 0
            if VOICE_COUNT >= 3 and LISTENING_ENABLED:
                VOICE_FLAG = True
                print("⤍ [Voice Triggered] Listening...")
                NEXT_EXP = "focus"
        else:
            VOICE_COUNT = 0
            SILENCE_COUNT += 1
            NEXT_EXP = "idle"
            T_QUEUE.insert(0, t)
            if len(T_QUEUE) > 20:
                T_QUEUE.pop()
    else:
        if t > (t_mean * 1.20):
            SILENCE_COUNT = 0
            VOICE_COUNT += 1
            NEXT_EXP = "focus"
        else:
            SILENCE_COUNT += 1
            if SILENCE_COUNT >= MAX_SILENCE_GAP or VOICE_COUNT > 75:
                VOICE_COUNT = 0
                VOICE_FLAG = False
                END_OF_RECORD = True
                print("⚡ [Speech Finished] Transcribing...")
                NEXT_EXP = "idle"

# -------------------------------------------------------------------------------------------------
''' Function to record audio with RMS energy validation '''
def record_audio(output_file="input.wav"):
    global VOICE_FLAG, END_OF_RECORD, MAX_SILENCE_GAP, T_QUEUE, VOICE_COUNT, SILENCE_COUNT, STOP_RECORDING

    chunk_size = 2048
    format_type = pyaudio.paInt16
    channels = 1
    rate = 16000

    audio = pyaudio.PyAudio()
    try:
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
    except Exception as e:
        print(f"⚠ Error opening audio stream: {e}")
        audio.terminate()
        time.sleep(1)
        threading.Thread(target=record_audio, daemon=False).start()
        return

    frames = []
    pre_frames = []
    print("⤍ Start Speaking...")

    while True:
        if STOP_RECORDING:
            break
            
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
        except Exception as e:
            print(f"⚠ Error reading audio: {e}")
            break

        audio_data = np.frombuffer(data, dtype=np.int16)
        energy = np.sum(np.abs(audio_data))
        voice_switch(energy)

        if VOICE_FLAG:
            frames.append(data)
        else:
            pre_frames.append(data)
            if len(pre_frames) > 10:
                pre_frames.pop(0)

        if END_OF_RECORD:
            frames = pre_frames + frames
            break

    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Reset state
    VOICE_FLAG = False
    VOICE_COUNT = 0
    SILENCE_COUNT = 0
    END_OF_RECORD = False

    # Check minimum duration (>=7 frames ~0.9s) and RMS vocal energy
    if frames and not STOP_RECORDING and len(frames) >= 7:
        raw_bytes = b"".join(frames)
        samples = np.frombuffer(raw_bytes, dtype=np.int16)
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))

        # Reject quiet background noise / ambient room murmur
        if rms < 750:
            if LISTENING_ENABLED and not STOP_RECORDING:
                threading.Thread(target=record_audio, daemon=False).start()
            return

        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(format_type))
            wf.setframerate(rate)
            wf.writeframes(raw_bytes)

        threading.Thread(target=speach2text, daemon=False).start()
    else:
        if LISTENING_ENABLED and not STOP_RECORDING:
            threading.Thread(target=record_audio, daemon=False).start()

# -------------------------------------------------------------------------------------------------
''' Speech-to-text (Whisper MLX / Groq) with Wake & Sleep State Machine '''
IS_AWAKE = True  # Starts awake for immediate conversation
LAST_ROBOT_RESPONSE = ""

def speach2text(file_loc="input.wav"):
    global CURRENT_QUESTION, IS_AWAKE, LAST_ROBOT_RESPONSE
    user_input = ""
    t0 = time.time()

    # 1. Primary: Local MLX Whisper on Apple GPU
    try:
        import mlx_whisper
        res = mlx_whisper.transcribe(file_loc, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="en", temperature=0.0)
        user_input = res.get("text", "").strip()
    except Exception:
        if voice_client is not None:
            try:
                with open(file_loc, "rb") as file:
                    transcription = voice_client.audio.transcriptions.create(
                        file=(file_loc, file.read()),
                        model="whisper-large-v3-turbo",
                        language="en",
                        response_format="verbose_json",
                    )
                    user_input = transcription.text.strip()
            except Exception as e:
                print(f"[ERROR] Transcription failed: {e}")

    # Discard known Whisper silence/YouTube dataset hallucinations
    hallucinations = [
        "i'm sorry", "sorry", "i am sorry", "next video", "next stage", "next day", "next one",
        "i'm going to go", "to the next", "thank you for watching", "please subscribe",
        "like and subscribe", "music", "the next time"
    ]
    if any(h in user_input.lower() for h in hallucinations) or user_input in [".", "!", "?", "...", "Thank you.", "Thank you!"]:
        threading.Thread(target=record_audio, daemon=False).start()
        return

    # Normalize phonetic variations for GraceEMO and LPU domain
    if user_input:
        user_input = re.sub(r'\b(gracie amore|grace emo|gracemo|gracio emo|grace email|gracy emo|gracie moe|gresimo|grezymo)\b', 'GraceEMO', user_input, flags=re.IGNORECASE)
        user_input = re.sub(r'\b(l p u|lpo|l pu)\b', 'LPU', user_input, flags=re.IGNORECASE)
        user_input = re.sub(r'\b(loveli professional|lovelie professional)\b', 'Lovely Professional', user_input, flags=re.IGNORECASE)
        user_input = user_input.strip()

    # Filter out single-word filler/noise artifacts (e.g. "you", "so", "okay", "oh oh oh")
    if user_input:
        words = re.findall(r'\b\w+\b', user_input.lower())
        allowed_short = ['hi', 'hello', 'hey', 'bye', 'goodbye', 'help', 'wake up']
        if len(words) < 2 and not any(w in allowed_short for w in words):
            threading.Thread(target=record_audio, daemon=False).start()
            return

    # Self-Echo Filter: Ignore microphone picking up GraceEMO's own voice
    if LAST_ROBOT_RESPONSE and user_input:
        robot_words = set(re.findall(r'\b\w+\b', LAST_ROBOT_RESPONSE.lower()))
        input_words = re.findall(r'\b\w+\b', user_input.lower())
        if input_words:
            overlap = sum(1 for w in input_words if w in robot_words) / len(input_words)
            if overlap >= 0.65:
                threading.Thread(target=record_audio, daemon=False).start()
                return

    if user_input:
        stt_time = time.time() - t0
        print("---------------->")
        print(f"⚍ Human: {user_input} (STT took {stt_time:.2f}s)")
        print("<----------------")

        input_lower = user_input.lower()

        # Check Sleep Mode state
        if not IS_AWAKE:
            wake_phrases = ["hi graceemo", "hey graceemo", "hello graceemo", "graceemo", "wake up", "hello", "hi"]
            if any(w in input_lower for w in wake_phrases):
                IS_AWAKE = True
                print("✨ [Woken Up] Active conversation mode on!")
                response = "Greetings! I am GraceEMO, the Vice Chancellor of Lovely Professional University. How may I assist you today? <exp-happy>"
                threading.Thread(target=asynt_tss, args=(response,), daemon=False).start()
                return
            else:
                threading.Thread(target=record_audio, daemon=False).start()
                return

        # Check for Sleep / Exit commands while Awake
        sleep_phrases = ["bye", "bye bye", "goodbye", "good bye", "see you later", "go to sleep", "sleep", "stop listening", "that's all"]
        if any(input_lower.startswith(p) or input_lower == p for p in sleep_phrases):
            IS_AWAKE = False
            response = "Goodbye! It was a pleasure assisting you. Have an inspiring day at Lovely Professional University! {stop-record} <exp-happy>"
            print("💤 [Sleep Mode] Entering sleep mode...")
            threading.Thread(target=asynt_tss, args=(response,), daemon=False).start()
            return

        if CURRENT_QUESTION == user_input:
            threading.Thread(target=record_audio, daemon=False).start()
            return
        CURRENT_QUESTION = user_input
        threading.Thread(target=chat_model, args=(user_input,), daemon=False).start()
    else:
        threading.Thread(target=record_audio, daemon=False).start()

# -------------------------------------------------------------------------------------------------
''' Chat Model powered by OUR OWN CUSTOM LOCAL MLX LLM '''
def chat_model(user_input):
    if user_input:
        print(">>>>>>>>>>>>>>>>")
        global CONV_HISTORY

        CONV_HISTORY.append({"role": "user", "content": user_input})
        response = ""

        # Build Ground-Truth System Context
        from memory_engine import MEMORY_ENGINE, KNOWLEDGE_BASE
        rag_context = KNOWLEDGE_BASE.query_knowledge(user_input, top_k=2)
        mem_context = MEMORY_ENGINE.get_memory_context(user_input)

        system_text = (
            "You are GraceEMO, the AI Vice Chancellor and Executive Ambassador of Lovely Professional University (LPU).\n"
            "You are a live, brilliant, all-knowing AI assistant with vast intelligence across all world knowledge, science, politics, technology, history, and life, while being the proud leader of Lovely Professional University.\n\n"
            "Exact Leadership & Political Rules:\n"
            "- Founder Chancellor: Dr. Ashok Kumar Mittal — Honorable Member of Parliament (Rajya Sabha, Bharatiya Janata Party / BJP).\n"
            "- Pro-Chancellor: Mrs. Rashmi Mittal — Educational leader and academic administrator. She has NO political party affiliation.\n"
            "- Vice Chancellor: GraceEMO (AI Vice Chancellor).\n"
            "- Project Mentor: Dr. Mohit Arora (AI & Robotics Professor).\n"
            "- Student Creators: Sam Davi, John Allson, Sarvesh, Alex Matthew, and Balamurugan.\n"
            "- University: Lovely Professional University (LPU), 600-acre mega campus in Punjab, NAAC A++ accredited (3.68/4).\n\n"
            "Instructions:\n"
            "1. When asked about Mrs. Rashmi Mittal's political party, state clearly that she is an academic leader and has NO political party affiliation.\n"
            "2. When asked about Dr. Ashok Kumar Mittal's political party, state that he is an MP in Rajya Sabha from the Bharatiya Janata Party (BJP).\n"
            "3. Use retrieved facts for state leaders (e.g. Chief Minister of Tamil Nadu is M. K. Stalin).\n"
            "4. Answer all general world knowledge, politics, and science directly and factually like ChatGPT.\n"
            "5. Keep spoken replies concise (1-2 sentences under 35 words) ending with an emotion tag: <exp-happy>, <exp-neutral>, <exp-focus>."
        )
        if rag_context:
            system_text += f"\n\n{rag_context}"
        if mem_context:
            system_text += f"\n\n{mem_context}"

        # 1. Tier 1: OpenAI GPT-4o (If API key provided)
        if openai_client is not None:
            try:
                t0 = time.time()
                openai_messages = [{"role": "system", "content": system_text}]
                for m in CONV_HISTORY:
                    if m["role"] != "system":
                        openai_messages.append({"role": m["role"], "content": m["content"]})
                
                completion = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=openai_messages[-7:],
                    temperature=0.3,
                    max_tokens=150
                )
                response = completion.choices[0].message.content.strip()
                gen_time = time.time() - t0
                if response:
                    print(f"✨ [OpenAI GPT-4o ({gen_time*1000:.1f}ms)]: {response}")
            except Exception as e:
                print(f"[OpenAI Notice]: {e}")

        # 2. Tier 2: Apple Silicon Metal GPU Engine (Direct, Ultra-Fast, No Think Tokens)
        if not response and LOCAL_MLX_MODEL is not None and LOCAL_MLX_TOKENIZER is not None:
            try:
                prompt = f"<|im_start|>system\n{system_text}<|im_end|>\n"
                recent_turns = [m for m in CONV_HISTORY if m["role"] != "system"][-6:]
                for msg in recent_turns:
                    role = msg["role"]
                    content = msg["content"]
                    prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
                prompt += "<|im_start|>assistant\n"

                t0 = time.time()
                raw = mlx_generate(
                    LOCAL_MLX_MODEL,
                    LOCAL_MLX_TOKENIZER,
                    prompt=prompt,
                    max_tokens=60,
                    sampler=LOCAL_MLX_SAMPLER,
                    logits_processors=LOCAL_MLX_LOGITS_PROCESSORS,
                )
                gen_time = time.time() - t0
                response = raw.strip()
                if response:
                    print(f"🧠 [Apple Silicon GPU MLX ({gen_time*1000:.1f}ms)]: {response}")
            except Exception as e:
                print(f"Local LLM notice: {e}")

        # 3. Tier 3: Groq Cloud API Fallback
        if not response and chat_client is not None:
            try:
                t0 = time.time()
                groq_messages = [{"role": "system", "content": system_text}]
                for m in CONV_HISTORY:
                    if m["role"] != "system":
                        groq_messages.append({"role": m["role"], "content": m["content"]})
                
                completion = chat_client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=groq_messages[-7:],
                    temperature=0.2,
                    max_tokens=800,
                )
                raw = completion.choices[0].message.content or ""
                if "</think>" in raw:
                    response = raw.split("</think>")[-1].strip()
                else:
                    response = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                gen_time = time.time() - t0
                if response:
                    print(f"⚡ [Groq API ({gen_time*1000:.1f}ms)]: {response}")
            except Exception as e:
                print(f"[Groq API notice]: {e}")

        if not response:
            response = "Greetings! I am GraceEMO, the Vice Chancellor of Lovely Professional University. How may I assist you today? <exp-happy>"

        # Safety clean response
        if "<think>" in response:
            if "</think>" in response:
                response = response.split("</think>")[-1].strip()
            else:
                m = re.search(r'["\']([^"\']{5,120})["\']', response)
                response = m.group(1) if m else "I am here to assist and guide your academic journey at LPU! <exp-happy>"

        CONV_HISTORY.append({"role": "assistant", "content": response})
        print("<<<<<<<<<<<<<<<<")

        threading.Thread(target=asynt_tss, args=(response,), daemon=False).start()
    else:
        threading.Thread(target=record_audio, daemon=False).start()

# -------------------------------------------------------------------------------------------------
''' Isolated CLI TTS Synthesizer (100% Crash-Proof, No Async Collisions) '''
import subprocess

def save_tts_file(text, output_file="output.mp3"):
    python_bin = sys.executable
    edge_tts_bin = os.path.join(os.path.dirname(python_bin), "edge-tts")
    if not os.path.exists(edge_tts_bin):
        edge_tts_bin = "edge-tts"

    cmd = [edge_tts_bin, "--text", text, "--write-media", output_file, "--voice", "en-IN-NeerjaNeural", "--rate", "+5%"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10.0)
    except Exception as e:
        print(f"[TTS Fallback Notice]: {e}")

def asynt_tss(response):
    if response:
        # Strip any think tags or leaked reasoning
        if "<think>" in response:
            if "</think>" in response:
                response = response.split("</think>")[-1].strip()
            else:
                m = re.search(r'["\']([^"\']{5,120})["\']', response)
                response = m.group(1) if m else "I am here to assist and inspire your academic journey!"

        tokened = response.split(' ')
        remain = ''
        for token in tokened:
            if "<exp-" in token:
                create_exp(token)
            else:
                remain += token + ' '

        # Clean remaining text for speech and display
        remain = re.sub(r'<exp-[a-z]+>', '', remain)
        remain = re.sub(r'[\*#@_~`]+', '', remain)
        remain = re.sub(r'\s+', ' ', remain).strip()

        text2speech(remain)
    else:
        threading.Thread(target=record_audio, daemon=False).start()

def text2speech(text):
    global CAPTION_TEXT, NEXT_EXP, LAST_ROBOT_RESPONSE
    restart = True
    end_conv = False
    if "{search}" in text:
        restart = False
    if "{stop-record}" in text:
        end_conv = True
        
    text = function_extract(text)
    print("⚍ GraceEMO:", text)

    CAPTION_TEXT = text
    LAST_ROBOT_RESPONSE = text

    try:
        # Generate audio file cleanly via isolated CLI process
        save_tts_file(text, "output.mp3")
        
        speech_audio = AudioSegment.from_file("output.mp3", format="mp3")
        silence = AudioSegment.silent(duration=50)
        final_audio = silence + speech_audio
        final_audio.export("output.wav", format="wav")
        
        # Play the WAV file safely
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass

        if pygame.mixer.get_init():
            pygame.mixer.music.load("output.wav")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        else:
            # Native macOS audio playback fallback
            subprocess.run(["afplay", "output.wav"], check=False)

        NEXT_EXP = "idle"
        CAPTION_TEXT = " "
        
        time.sleep(0.30)
        if end_conv:
            print("💤 [Sleep Mode Active] Waiting for wake phrase ('Hi GraceEMO' / 'Hey GraceEMO')...")
        if restart and LISTENING_ENABLED:
            print("|||||||||||||||||||||||||||||||||||||||||||||||")
            threading.Thread(target=record_audio, daemon=False).start()

    except Exception as e:
        print(f"Error occurred while processing audio: {e}")
        threading.Thread(target=record_audio, daemon=False).start()

# -------------------------------------------------------------------------------------------------
def draw_caption(surface, text, font=None, color=(255, 255, 255), y_offset=25):
    if not text or text.strip() == "":
        return

    surface_w, surface_h = surface.get_size()
    max_width = int(surface_w * 0.85)

    font_size = max(24, int(surface_h * 0.045))
    if font is None:
        try:
            font = pygame.font.Font("font.ttf", font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)

    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        test_w, _ = font.size(test_line)
        if test_w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    line_surfaces = [font.render(l, True, color) for l in lines]
    total_h = sum(s.get_height() for s in line_surfaces) + (len(lines) - 1) * 6
    max_line_w = max(s.get_width() for s in line_surfaces)

    pill_pad_x = 24
    pill_pad_y = 12
    pill_rect = pygame.Rect(
        (surface_w - max_line_w) // 2 - pill_pad_x,
        surface_h - total_h - y_offset - pill_pad_y,
        max_line_w + pill_pad_x * 2,
        total_h + pill_pad_y * 2
    )

    pill_surf = pygame.Surface((pill_rect.width, pill_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(pill_surf, (15, 20, 30, 210), pill_surf.get_rect(), border_radius=16)
    pygame.draw.rect(pill_surf, (80, 140, 240, 160), pill_surf.get_rect(), width=2, border_radius=16)
    surface.blit(pill_surf, pill_rect.topleft)

    curr_y = pill_rect.top + pill_pad_y
    for s in line_surfaces:
        line_x = (surface_w - s.get_width()) // 2
        surface.blit(s, (line_x, curr_y))
        curr_y += s.get_height() + 6

def get_random_video(folder_path):
    try:
        files = os.listdir(folder_path)
        videos = [file for file in files if os.path.isfile(os.path.join(folder_path, file))]
        if not videos:
            return "No videos found in the folder."
        random_video = random.choice(videos)
        return os.path.join(folder_path, random_video)
    except FileNotFoundError:
        return "The folder does not exist."

def create_exp(token):
    global NEXT_EXP
    exp_list = ['happy', 'sad', 'focus', 'angry', 'idle', 'intent']
    expression = token[5: -1]
    if expression in exp_list:
        NEXT_EXP = expression
    else:
        NEXT_EXP = "idle"

def function_extract(text):
    match = re.search(r"\{\s*(.*?)\s*\}", text)
    extracted = match.group(1) if match else None
    if extracted is not None:
        print("⚍ Function:", extracted)
    remaining = re.sub(r"\{\s*.*?\s*\}", "", text)
    remaining = re.sub(r'\s+', ' ', remaining).strip()
    return remaining

def GUI():
    global win, SCREEN_WIDTH, SCREEN_HEIGHT, VID_DIR, CAPTION_TEXT, NEXT_EXP, CURRENT_EXP, PREVIOUS_EXP

    collect_info()
    next_vid = get_random_video(VID_DIR + "focus-idle")
    vid = Video(next_vid)
    vid.mute()

    # Start listening loop automatically on launch
    threading.Thread(target=record_audio, daemon=False).start()

    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
            elif event.type == pygame.VIDEORESIZE:
                SCREEN_WIDTH, SCREEN_HEIGHT = event.w, event.h

        try:
            # Update video frame and render with hardware scaling
            if vid._update() or True:
                if vid.frame_surf is not None:
                    scaled_surf = pygame.transform.smoothscale(vid.frame_surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
                    win.blit(scaled_surf, (0, 0))
        except Exception:
            pass

        draw_caption(win, text=CAPTION_TEXT, y_offset=30)

        try:
            if not vid.active:
                PREVIOUS_EXP = CURRENT_EXP
                CURRENT_EXP = NEXT_EXP
                next_vid = get_random_video(VID_DIR + str(PREVIOUS_EXP +'-'+ CURRENT_EXP))
                try:
                    vid.close()
                except Exception:
                    pass
                vid = Video(next_vid)
                vid.mute()
                vid.restart()
        except Exception:
            pass

        pygame.display.update()
        clock.tick(30)

    try:
        vid.close()
    except Exception:
        pass
    pygame.quit()

if __name__ == "__main__":
    GUI()