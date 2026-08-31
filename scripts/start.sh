#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

export PYTHONUNBUFFERED=1
export JACK_NO_START_SERVER=1
export ALSA_LOG_LEVEL=0

# Kill any stale process on the kernel port
fuser -k 7780/tcp 2>/dev/null || true

exec "$DIR/adapters/.venv/bin/python" -u "$DIR/scripts/live_demo.py"
