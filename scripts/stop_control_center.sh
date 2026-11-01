#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Stop Unified Autonomous Robotics Control Center (UARCC)
# ==============================================================================

set -e

echo "🛑 Stopping GRaCEmo ViRa Control Center instances..."

# Send graceful SIGTERM first
pkill -f "gracemo_control_center/main.py" 2>/dev/null || true
pkill -f "control_center" 2>/dev/null || true
sleep 1

# Check if any remain
if pgrep -f "gracemo_control_center/main.py" > /dev/null; then
    echo "⚠️ Force reaping lingering GUI processes..."
    pkill -9 -f "gracemo_control_center/main.py" 2>/dev/null || true
fi

echo "✅ All UARCC Control Center processes stopped cleanly."
