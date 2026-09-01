#!/usr/bin/env bash
# Regenerate all GRACEEMO-01 Blender artifacts (blends, previews, GLB, manifest).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"

if [[ ! -x "$BLENDER" ]]; then
  echo "Blender not found at: $BLENDER" >&2
  echo "Set BLENDER=/path/to/Blender and retry." >&2
  exit 1
fi

echo "== GRACEEMO-01 engineering prototype =="
"$BLENDER" --background --python "$ROOT/GraceEMO_Blender_Generator.py"

echo "== LPU campus scene =="
"$BLENDER" --background --python "$ROOT/blender/scripts/build_graceemo_lpu.py"

echo ""
echo "Done. See blender/ARTIFACTS.json for the full artifact list."
ls -lah "$ROOT/blender/"*.blend "$ROOT/blender/"*.png "$ROOT/blender/"*.glb 2>/dev/null || true
