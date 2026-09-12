#!/usr/bin/env python3
"""
GraceEMO Interaction — Main Entry Point
========================================
Standalone interaction module — NO ROS 2 required.

Usage:
  python main.py              # Rich terminal CLI (text input)
  python main.py --voice      # Full STT+TTS (microphone + speakers)
  python main.py --tts-only   # Text input + spoken responses
  python main.py --serve      # REST API server (port 8420)
  python main.py --voice --serve  # STT+TTS + API server simultaneously

Environment:
  GEMINI_API_KEY   — Google Gemini (primary LLM)
  GROQ_API_KEY     — Groq Cloud (fallback LLM)
  OLLAMA_API_BASE  — Ollama local (optional, default http://localhost:11434/v1)
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Load .env if present
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(levelname)s %(name)s: %(message)s",
)

from core.llm_engine import LLMEngine
from core.tts_engine import TTSEngine
from core.stt_engine import STTEngine
from core.interaction_loop import InteractionLoop


# ──────────────────────────────────────────────────────────────────────
# Rich terminal helpers
# ──────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"

INTENT_COLORS = {
    "STOP":         RED,
    "NAVIGATE":     CYAN,
    "GREET":        GREEN,
    "HAND_HI":      GREEN,
    "HAND_UP":      YELLOW,
    "HAND_DOWN":    YELLOW,
    "LOOK_AT":      BLUE,
    "STATUS_REPORT":MAGENTA,
    "IDENTITY":     MAGENTA,
    "GENERAL_QUERY":WHITE,
    "QUERY":        WHITE,
    "COMMAND":      WHITE,
}

def clr(text: str, *codes: str) -> str:
    return "".join(codes) + text + RESET

def banner():
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  🤖  GraceEMO — Standalone Interaction Engine  v1.0     ║",
        "║       Lovely Professional University Campus Robot        ║",
        "╚══════════════════════════════════════════════════════════╝",
    ]
    for l in lines:
        print(clr(l, CYAN, BOLD))

def print_response(user_in: str, intent: str, confidence: float, answer: str, action: str, backend: str):
    ic = INTENT_COLORS.get(intent, WHITE)
    conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
    conf_color = GREEN if confidence >= 0.85 else (YELLOW if confidence >= 0.6 else RED)

    print()
    print(clr(f"  ┌─ Input: \"{user_in}\"", DIM))
    print(clr(f"  ├─ Intent:     ", DIM) + clr(f"{intent}", ic, BOLD) +
          clr(f"  [{conf_bar}] {confidence:.0%}", conf_color))
    print(clr(f"  ├─ Action:     ", DIM) + clr(action, YELLOW))
    print(clr(f"  ├─ LLM:        ", DIM) + clr(backend, BLUE))
    print(clr(f"  └─ Response:   ", DIM) + clr(f"\"{answer}\"", GREEN, BOLD))
    print()

def print_status(msg: str, color: str = WHITE):
    print(clr(f"  ⟫ {msg}", color, DIM))


# ──────────────────────────────────────────────────────────────────────
# CLI interactive loop
# ──────────────────────────────────────────────────────────────────────

def run_cli(loop: InteractionLoop):
    history: list[dict] = []

    print()
    print_status("Type a command or question. Type 'quit' to exit.", CYAN)
    print_status("Examples: 'hello', 'go to lab', 'who are you', 'stop', 'hands up'", DIM)
    print()

    while True:
        try:
            user_in = input(clr("  GraceEMO > ", CYAN, BOLD)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print_status("Session ended.", DIM)
            break

        if not user_in:
            continue
        if user_in.lower() in ("quit", "exit", "bye", "q"):
            loop.speak("Goodbye! Have a great day at LPU!")
            break

        # Handle special debug commands
        if user_in == "/status":
            print(json.dumps(loop.state.to_dict(), indent=2))
            continue
        if user_in == "/history":
            for i, h in enumerate(history[-10:], 1):
                print(clr(f"  {i:2}. [{h['intent']}] {h['input']!r} → {h['answer']!r}", DIM))
            continue

        # Run through interaction pipeline
        try:
            # We also capture LLM response for display
            from core.models import AskQuestionRequest
            cmd = loop.dialogue.parse(user_in)
            
            # Capture LLM response for intent/confidence display
            llm_resp = None
            if cmd.intent in ("QUERY", "COMMAND", "GENERAL_QUERY") or True:
                llm_resp = loop.llm.ask(AskQuestionRequest(
                    question=user_in,
                    context=json.dumps(loop.state.to_dict()),
                ))
            
            result = loop.handle_text(user_in)
            intent = llm_resp.intent if llm_resp else cmd.intent
            confidence = llm_resp.confidence if llm_resp else cmd.confidence
            answer = llm_resp.answer if llm_resp else result.text or ""

            print_response(
                user_in, intent, confidence, answer,
                result.action, loop.llm_backend
            )

            history.append({
                "input": user_in, "intent": intent,
                "answer": answer, "action": result.action,
            })
        except Exception as e:
            print_status(f"Error: {e}", RED)


# ──────────────────────────────────────────────────────────────────────
# Voice mode (STT continuous listening)
# ──────────────────────────────────────────────────────────────────────

def run_voice(loop: InteractionLoop, stt: STTEngine):
    print()
    print_status(f"🎙️  Voice mode active. Wake word: \"hey gracemo\"", GREEN)
    print_status("Press Ctrl+C to stop.", DIM)
    print()

    def on_transcript(text: str):
        if not text:
            return
        print(clr(f"\n  🗣️  Heard: \"{text}\"", YELLOW))
        try:
            result = loop.handle_text(text)
            print(clr(f"  → Action: {result.action} | Response: \"{result.text}\"", GREEN))
        except Exception as e:
            print_status(f"Error: {e}", RED)

    stt.start(callback=on_transcript)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        print_status("Voice mode stopped.", DIM)


# ──────────────────────────────────────────────────────────────────────
# REST API server
# ──────────────────────────────────────────────────────────────────────

def run_server(loop: InteractionLoop, port: int = 8420):
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
        import uvicorn
    except ImportError:
        print_status("fastapi/uvicorn not installed. Run: pip install fastapi uvicorn", RED)
        return

    app = FastAPI(title="GraceEMO Interaction API", version="1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/")
    def root():
        return {
            "robot": "GraceEMO",
            "status": loop.state.status,
            "llm_backend": loop.llm_backend,
            "task": loop.state.current_task,
        }

    @app.post("/interact")
    def interact(body: dict):
        text = body.get("text", "").strip()
        if not text:
            return JSONResponse({"error": "text required"}, status_code=400)
        result = loop.handle_text(text)
        return {
            "action":  result.action,
            "target":  result.target,
            "text":    result.text,
            "state":   loop.state.to_dict(),
        }

    @app.get("/state")
    def state():
        return loop.state.to_dict()

    @app.get("/places")
    def places():
        return {k: {"x": v[0], "y": v[1], "name": v[2]} for k, v in loop.known_places.items()}

    @app.post("/greet")
    def greet():
        result = loop.greet()
        return {"action": result.action, "text": result.text}

    print_status(f"🌐 REST API server starting on http://0.0.0.0:{port}", CYAN)
    print_status(f"   POST /interact  {{ \"text\": \"go to lab\" }}", DIM)
    print_status(f"   GET  /state", DIM)
    print_status(f"   GET  /places", DIM)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GraceEMO Standalone Interaction Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--voice",    action="store_true", help="Enable microphone STT input")
    parser.add_argument("--tts-only", action="store_true", help="Enable TTS output (text input)")
    parser.add_argument("--serve",    action="store_true", help="Start REST API server")
    parser.add_argument("--port",     type=int, default=8420, help="REST API port (default: 8420)")
    parser.add_argument("--no-tts",   action="store_true", help="Disable TTS output entirely")
    parser.add_argument("--wake-word",default="hey gracemo", help="STT wake word")
    parser.add_argument("--verbose",  action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    banner()
    print()

    # Build engines
    print_status("Initializing LLM engine...", DIM)
    llm = LLMEngine()
    print_status(f"LLM backend: {llm.backend_name}", GREEN if llm.backend_name != 'heuristics' else YELLOW)

    enable_tts = not args.no_tts
    tts = None
    if enable_tts:
        print_status("Initializing TTS engine...", DIM)
        tts = TTSEngine()
        print_status(f"TTS backend: {tts.backend}", GREEN if tts.backend != 'print' else YELLOW)

    loop = InteractionLoop(llm=llm, tts=tts, enable_tts=enable_tts)

    # Server mode (non-blocking if combined with voice/cli)
    import threading
    if args.serve:
        t = threading.Thread(
            target=run_server, kwargs={"loop": loop, "port": args.port}, daemon=True
        )
        t.start()
        time.sleep(0.5)

    # Voice mode
    if args.voice:
        stt = STTEngine(wake_word=args.wake_word, require_wake_word=True)
        print_status(f"STT backend: {stt.backend}", GREEN if stt.backend != 'stdin' else YELLOW)
        run_voice(loop, stt)
    elif args.serve and not args.voice:
        # Server-only mode: block on server thread
        print_status("Running in server-only mode (no CLI). Press Ctrl+C to stop.", CYAN)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print_status("Server stopped.", DIM)
    else:
        # Default: rich terminal CLI
        run_cli(loop)


if __name__ == "__main__":
    main()
