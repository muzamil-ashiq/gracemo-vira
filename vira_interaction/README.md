# 🤖 GRaCEmo ViRa — Dedicated Interaction Engine

This directory contains the self-contained, dedicated interaction subsystem for **GRaCEmo ViRa** (also known as GraceEMO). It embodies the intellectual depth, composure, dignity, and communication standards expected of an eminent Vice-Chancellor of a distinguished university.

---

## 🏛️ Persona & Communication Standard

ViRa communicates with executive presence, intellectual eminence, and academic leadership across all domains:
- **Academic & Technical Explanations**: Structured explanations stating the core principle, underlying mechanism, and practical applications/trade-offs without superficiality or premature truncation.
- **Natural Voice Rhythm**: Concise spoken pacing (typically 40 to 80 words across 2 to 4 complete sentences) optimized for Edge-TTS neural listening.
- **Spoken Math Delivery**: Expresses mathematical concepts in spoken words rather than raw LaTeX syntax (`$$`, `\frac`, `\nabla`).
- **Intellectual Humility**: Politely asks for clarification when statements are ambiguous rather than hallucinating or defaulting to marketing slogans.
- **Institutional Dignity**: Accurately answers university questions when asked, without ungrounded commercial slogans or forcing campus references into unrelated topics.

---

## 📁 Directory Structure

```text
vira_interaction/
├── .env                  # API credentials (Groq, Whisper, Speech)
├── .venv/                # Python virtual environment symlink
├── config/
│   └── places.json       # Campus and simulation spatial waypoints
├── core/
│   ├── brain_adapter.py  # Multi-tier cognitive engine (Groq, Gemini, MLX, heuristics)
│   ├── dialogue_engine.py# Intent classification
│   ├── event_bus.py      # Canonical EventBus publisher & client
│   ├── fast_path.py      # Sub-20ms deterministic intent & E-stop dispatcher
│   ├── gateway.py        # Central InteractionGateway coordinator
│   ├── interaction_adapter.py
│   ├── interaction_loop.py
│   ├── llm_engine.py     # Standalone action & intent engine
│   ├── memory_adapter.py # Episodic memory manager
│   ├── models.py         # Interaction data models
│   ├── place_resolver.py # Authoritative spatial waypoint resolver
│   ├── safety_gate.py    # Command validator & safety gate
│   ├── state_machine.py  # Cognitive state machine & expressions
│   ├── stt_adapter.py    # Speech-to-text adapter (Whisper / Fallback)
│   ├── stt_engine.py
│   ├── tts_adapter.py    # Text-to-speech adapter (Edge-TTS en-IN-NeerjaNeural)
│   └── tts_engine.py
├── data/                 # Persona knowledge base & behavioral protocols
│   ├── 1-charecter.txt   # Core Vice-Chancellor persona definition
│   ├── 2-about-college.txt
│   ├── 3-Important-people.txt
│   ├── 4-creators.txt
│   ├── 5-cources.txt
│   ├── 6-technical.txt
│   ├── 7-facalities.txt
│   ├── 8-end-functions.txt
│   ├── 8-end-protocols.txt # Spoken communication & formatting protocols
│   ├── 9-special-details.txt
│   └── human_memory.json
├── font.ttf              # Display typography for Pygame captions
├── functions.py          # Safe semantic robot functions bridge
├── model.py              # Main voice, face, VAD, and interaction loop
├── requirements.txt      # Python dependencies
├── run.sh                # Production execution launcher
├── tests/                # Automated test suite
│   ├── test_interaction.py
│   └── test_model_vad.py
└── vid/                  # Facial animation video assets (36 emotional transitions)
```

---

## 🚀 How to Run

### 1. Launch Voice & Facial Interface
```bash
cd /home/sabarishchandrasekaran/projects/dfinddata/vira_interaction
DISPLAY=:0 ./run.sh
```

### 2. Controls in the Face Window
- `[s]` -> Start listening to microphone
- `[e]` -> Stop listening
- `[+]` / `[-]` -> Adjust microphone threshold & background rejection
- `[f]` -> Toggle Fullscreen / Windowed Mode
- `[q]` -> Quit / Exit (or `Esc`)

### 3. Run Automated Regression Tests
```bash
cd /home/sabarishchandrasekaran/projects/dfinddata/vira_interaction
./.venv/bin/python -m unittest discover tests
```
