#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/kernel/target/debug/gracemo-kernel"

if [ ! -f "$BIN" ]; then
    echo "⚙️ Compiling gracemo-kernel..."
    cargo build --manifest-path "$ROOT/kernel/Cargo.toml" --bin gracemo-kernel
fi

echo "🚀 Starting GRaCEmo Kernel on http://127.0.0.1:7780..."
exec "$BIN"
