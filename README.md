# 🤖 GraceEMO — Standalone Interaction Engine

A fully standalone Python module containing the **pure human-robot interaction pipeline** extracted from the GraceEMO ROS 2 monorepo.

**No ROS 2. No Gazebo. No navigation stack. Just talk to your robot.**

---

## What's Included

```
gracemo_interaction/
├── core/
│   ├── models.py           # Python dataclasses (VoiceCommand, ActionResult, etc.)
│   ├── llm_engine.py       # Multi-backend LLM: Gemini → Groq → Ollama → heuristics
│   ├── dialogue_engine.py  # Fast intent classifier (no LLM needed)
│   ├── interaction_loop.py # Main loop: text → intent → action → speak
│   ├── tts_engine.py       # TTS: pyttsx3 → gTTS → print
│   └── stt_engine.py       # STT: microphone + wake word ("hey gracemo")
├── config/
│   └── places.json         # LPU campus places map
├── tests/
│   └── test_interaction.py # Unit tests (no API key needed)
├── main.py                 # Entry point
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
cd gracemo_interaction

# Install dependencies
pip install -r requirements.txt

# Copy and fill in API keys
cp .env.example .env
# Edit .env: add GEMINI_API_KEY and/or GROQ_API_KEY

# Run (text mode)
python main.py
```

---

## Run Modes

| Mode | Command |
|---|---|
| Rich terminal CLI (text input) | `python main.py` |
| TTS-only (text input, spoken output) | `python main.py --tts-only` |
| Full voice (microphone + speaker) | `python main.py --voice` |
| REST API server | `python main.py --serve` |
| Voice + REST API | `python main.py --voice --serve` |
| No TTS, just text output | `python main.py --no-tts` |

### REST API (--serve)

```bash
python main.py --serve --port 8420
```

```bash
# Send a command
curl -X POST http://localhost:8420/interact \
  -H "Content-Type: application/json" \
  -d '{"text": "go to the lab"}'

# Get robot state
curl http://localhost:8420/state

# List known places
curl http://localhost:8420/places

# Trigger greeting
curl -X POST http://localhost:8420/greet
```

---

## LLM Backend Priority

| Priority | Backend | Key Required |
|---|---|---|
| 1 | Google Gemini 2.0 Flash (`google.genai`) | `GEMINI_API_KEY` |
| 2 | Google Gemini 2.0 Flash (legacy SDK) | `GEMINI_API_KEY` |
| 3 | Groq Cloud LPU (`llama-3.3-70b`) | `GROQ_API_KEY` |
| 4 | Ollama local (`llama3`) | None (local) |
| 5 | Campus heuristics | None (always works) |

---

## Supported Intents

| Intent | Example Phrases |
|---|---|
| `STOP` | "stop", "halt", "freeze", "emergency" |
| `NAVIGATE` | "go to lab", "take me to library", "drive to gate" |
| `GREET` / `HAND_HI` | "hello", "hi", "wave" |
| `HAND_UP` | "hands up" |
| `HAND_DOWN` | "hands down" |
| `IDENTITY` | "who are you", "what's your name" |
| `STATUS_REPORT` | "battery status", "system status" |
| `GENERAL_QUERY` | Everything else → LLM |

---

## Connecting to a Real Robot

Use action hooks to plug physical robot actions:

```python
from core.interaction_loop import InteractionLoop

loop = InteractionLoop()

# Register your robot's actual movement function
loop.set_action_hook("navigate_to", lambda target, x, y: your_robot.drive(x, y))
loop.set_action_hook("speak",       lambda text="": your_robot.tts(text))
loop.set_action_hook("hand_hi",     lambda: your_robot.wave())
loop.set_action_hook("stop",        lambda: your_robot.stop())

# Process input
loop.handle_text("go to the lab")
```

---

## Run Tests

```bash
cd gracemo_interaction
python -m pytest tests/ -v
```

No API key required — tests use the heuristics fallback path.

---

## Campus Places

Defined in `config/places.json`. Edit to add your own locations:

```json
{
  "cafeteria": [10.0, -5.0, "Main Cafeteria"],
  "auditorium": [50.0, 30.0, "University Auditorium"]
}
```

---

## Source Attribution

Extracted and refactored from the GraceEMO ROS 2 monorepo:
- `gracemo_brain/llm_node.py` → `core/llm_engine.py`
- `gracemo_voice/dialogue_node.py` → `core/dialogue_engine.py`  
- `gracemo_brain/planner_node.py` (interaction slice) → `core/interaction_loop.py`
- `gracemo_interfaces/msg/VoiceCommand.msg` + `srv/AskQuestion.srv` → `core/models.py`
