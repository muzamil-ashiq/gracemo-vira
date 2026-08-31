#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Modern Gazebo Sim (New Gazebo / Fortress) & ROS 2 Launcher
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"

echo "================================================================="
echo "  GRaCEmo ViRa — Autonomous Robotics Simulation (Modern Gazebo) "
echo "================================================================="

# 1. Clean up stale processes
~/.local/bin/distrobox enter gracemo-ros2 -- bash -c "killall -9 gz-sim ruby ign kernel_bridge 2>/dev/null || true" >/dev/null 2>&1 || true
fuser -k 7780/tcp 2>/dev/null || true

# 2. Ensure Kernel is running
if ! curl -s http://127.0.0.1:7780/health >/dev/null 2>&1; then
    echo "Starting GRaCEmo Kernel in background..."
    "$DIR/kernel/target/debug/gracemo-kernel" >/dev/null 2>&1 &
    sleep 1
fi

echo "✓ Kernel is online at http://127.0.0.1:7780"

# 3. Launch Modern Gazebo Sim & Kernel Bridge inside Distrobox
echo "Launching Modern Gazebo 3D Simulation & Kernel Bridge..."
~/.local/bin/distrobox enter gracemo-ros2 -- bash -c "
    source /opt/ros/humble/setup.bash
    source $WS_DIR/install/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export QT_X11_NO_MITSHM=1
    MODELS_DIR='$WS_DIR/install/gracemo_gazebo/share/gracemo_gazebo/models'
    FUEL_CACHE=\$HOME/.ignition/fuel/fuel.gazebosim.org/openrobotics/models
    export IGN_GAZEBO_RESOURCE_PATH=\$MODELS_DIR:\$FUEL_CACHE
    export GZ_SIM_RESOURCE_PATH=\$MODELS_DIR:\$FUEL_CACHE
    export SDF_PATH=\$MODELS_DIR:\$FUEL_CACHE
    echo '📦 Model resource path: '\$IGN_GAZEBO_RESOURCE_PATH
    ros2 launch gracemo_gazebo sim.launch.py
"
