#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Piece 2 Sensor Obstacle Arena Studio Launcher
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pkill -9 -f "gz sim" 2>/dev/null || true
sleep 1

echo "Building Piece 2 Obstacle Arena..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    python3 $DIR/scripts/make_obstacle_world.py
"

echo "Launching Gazebo GUI Arena..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    gz sim -r /tmp/studio_obstacles.world
"
