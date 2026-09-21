# 🤖 GraceEMO — Standalone Native Interaction & Local Qwen Engine

Welcome to the complete, self-contained **GraceEMO Native Voice & Animated Facial Interaction Engine**, bundled together with the **Native Local Qwen 2.5 LLM (4-bit MLX)** for high-speed offline inference on Apple Silicon!

---

## 📦 What's Inside This Bundle

| Component | Description |
| :--- | :--- |
| **`model.py`** | Main interaction engine: Pygame video expression renderer, ambient noise gate, audio recorder, local Qwen LLM, TTS speech player, and robot gesture extractor. |
| **`models/Qwen2.5-3B-Instruct-4bit/`** | **Native Local Qwen 2.5 Model** (1.6 GB pre-quantized 4-bit safetensors weights + tokenizer + configs). Runs 100% offline via Apple Silicon MLX GPU acceleration! |
| **`data/`** | Knowledge base defining the **Vice Chancellor & Campus Ambassador** persona at Lovely Professional University (LPU), creators credit, academic programs, facilities, and protocols. |
| **`vid/`** | All **38 facial animation video clips** rendering smooth emotional transitions (`idle-idle`, `happy-happy`, `focus-idle`, `angry-sad`, `intent-intent`, etc.). |
| **`functions.py`** | Mechanical robotic action functions and gesture dispatchers. |
| **`wake-word/`** | Picovoice Porcupine wake-word detection models (`mint.ppn`, `pi.ppn`). |
| **`gracemo_interaction/`** | Full alternative Web Console & FastAPI interaction dashboard if you wish to run the browser interface. |
| **`run.sh` / `run_native_voice.sh`** | One-click launcher scripts. |

---

## ⚡ Quickstart Guide

### 1. Requirements
- **macOS** with Apple Silicon (M1, M2, M3, M4) recommended for MLX GPU acceleration.
- **Python 3.10** or **3.11**.
- Microphone and Speakers.

### 2. Setup Virtual Environment & Install Dependencies
Open Terminal in this bundle directory:

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

*(Optional note for Mac users: If installing `pyaudio` prompts about portaudio, you can run `brew install portaudio`)*

### 3. Launch GraceEMO
Simply run:

```bash
./run.sh
```
*(or `./run_native_voice.sh`, or `python3 model.py`)*

---

## 🎮 Interactive Controls

When the GraceEMO face window appears:

| Key | Action |
| :---: | :--- |
| **`s`** | **Start Listening** — Opens microphone, detects speech, and animates focused face. |
| **`e`** | **Stop Listening** — Manually stops recording immediately. |
| **`f`** | **Toggle Fullscreen / Window** — Switch between 1024x768 and borderless display. |
| **`q`** or **`Esc`** | **Exit** — Safely shuts down audio streams and closes the window. |

---

## 🧠 LLM Inference Options

1. **Native Local Offline Qwen (Default)**:
   - When launched on Apple Silicon, `model.py` automatically loads `./models/Qwen2.5-3B-Instruct-4bit`.
   - Generates intelligent Vice Chancellor responses directly on your Mac GPU with zero internet connection required!
2. **Groq Cloud API (Optional Fallback)**:
   - If configured in `.env` (`GROQ_API_KEY`), the engine can also access Groq cloud LPU models (`compound-mini`, `whisper-large-v3-turbo`) for instant cloud speech-to-text.

---

## 👥 Credits

Developed by the student robotics and AI research team at **Lovely Professional University (LPU)**:
- **Sam Davi**
- **John Allson**
- **Sarvesh**
- **Alex Matthew**
- **Balamurugan**
*Under the mentorship of **Dr. Mohit Arora**.*
