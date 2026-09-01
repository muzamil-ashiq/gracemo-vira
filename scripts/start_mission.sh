#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Real-Time Visual Mission Controller
# Distrobox: gracemo-harmonic
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"

echo "================================================================="
echo "  GRaCEmo ViRa — Live Vision HUD & Autonomous Mission Control"
echo "================================================================="

distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    source $WS_DIR/install/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    export PYTHONPATH='$DIR/adapters/sdk:$DIR/adapters/vision:$DIR/adapters/voice:$DIR/adapters/brain:\$PYTHONPATH'
    python3 $DIR/scripts/mission_visualizer.py
"
