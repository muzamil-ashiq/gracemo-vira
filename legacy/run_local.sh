#!/bin/bash
# Script to run GraceEMO locally on macOS
export PATH="/opt/homebrew/bin:$PATH"

# Resolve absolute path to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    PYTHON_BIN="python3"
fi

echo "Starting GraceEMO locally using $PYTHON_BIN..."
echo "Press ESC or Q in the window to quit."

$PYTHON_BIN -u model.py "$@"
