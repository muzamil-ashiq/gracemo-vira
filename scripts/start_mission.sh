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

# Find distrobox binary
DISTROBOX="distrobox"
if [ -f "$HOME/.local/bin/distrobox" ]; then
    DISTROBOX="$HOME/.local/bin/distrobox"
fi

$DISTROBOX enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    source $WS_DIR/install/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    python3 $DIR/scripts/mission_visualizer.py
"
