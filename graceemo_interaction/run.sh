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

echo "=================================================================="
echo "  🤖 GraceEMO — Native Voice & Face Expression Interaction Engine"
echo "=================================================================="
echo "  Working Directory: $DIR"
echo "  Python Binary:     $PYTHON_BIN"
echo "  Local Qwen Model:  $DIR/models/Qwen2.5-3B-Instruct-4bit"
echo "------------------------------------------------------------------"
echo "  Controls in GraceEMO Window:"
echo "    [s]   -> START listening to microphone"
echo "    [e]   -> STOP listening"
echo "    [f]   -> Toggle Fullscreen / Windowed Mode"
echo "    [q]   -> Quit / Exit (or Esc)"
echo "=================================================================="

# Check if model exists
if [ -d "$DIR/models/Qwen2.5-3B-Instruct-4bit" ]; then
    echo "✓ Local Qwen 2.5 3B (4-bit MLX) detected."
fi

# Run the interaction engine
exec "$PYTHON_BIN" -u "$DIR/model.py" "$@"
