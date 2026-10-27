#!/usr/bin/env bash
# ==============================================================================
# GraceEMO — Standalone Native Voice & Facial Expression Interaction Engine
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/.local/lib:${LD_LIBRARY_PATH:-}"
export PORTAUDIO_PATH="$HOME/.local/lib/libportaudio.so"
export PYTHONUNBUFFERED=1

# Resolve Python binary (local venv or system python3)
if [ -f "$DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    echo "❌ Error: python3 not found. Please install Python 3.10+."
    exit 1
fi

# Check display environment on Linux
if [ "$(uname -s)" = "Linux" ] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "⚠️  Warning: Neither DISPLAY nor WAYLAND_DISPLAY is set."
    echo "   GraceEMO requires an X11 or Wayland display for the Pygame face window."
    echo "   Tip: prefix your command with DISPLAY=:0 (e.g., DISPLAY=:0 ./run.sh)"
fi

# Validate essential application components
for req in "$DIR/model.py" "$DIR/data" "$DIR/vid" "$DIR/font.ttf" "$DIR/config/places.json"; do
    if [ ! -e "$req" ]; then
        echo "❌ Error: Essential component missing: $req"
        exit 1
    fi
done

echo "=================================================================="
echo "  🤖 GRaCEmo ViRa — Native Voice & Face Expression Interaction Engine"
echo "=================================================================="
echo "  Working Directory: $DIR"
echo "  Python Binary:     $PYTHON_BIN"
if [ -d "$DIR/models/Qwen2.5-3B-Instruct-4bit" ]; then
    echo "  Local Qwen Model:  $DIR/models/Qwen2.5-3B-Instruct-4bit"
else
    echo "  Local Qwen Model:  Not installed (cloud fallback active)"
fi
echo "------------------------------------------------------------------"
echo "  Controls in GraceEMO Window:"
echo "    [s]       -> START listening to microphone"
echo "    [e]       -> STOP listening"
echo "    [+] / [-] -> Adjust microphone threshold & background rejection"
echo "    [f]       -> Toggle Fullscreen / Windowed Mode"
echo "    [q]       -> Quit / Exit (or Esc)"
echo "=================================================================="

# Run the interaction engine
exec "$PYTHON_BIN" -u "$DIR/model.py" "$@"
