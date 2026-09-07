#!/usr/bin/env bash
# GRaCEmo ViRa — 1-Click Verification Script
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$ROOT/scripts/verify_all.py" "$@"
