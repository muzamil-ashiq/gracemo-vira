#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Gazebo Harmonic + ROS 2 Humble Launcher
# Distrobox: gracemo-harmonic
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}") /.." && pwd)"
WS_DIR="$DIR/ros2_ws"

echo "================================================================="
echo "  GRaCEmo ViRa — Gazebo Harmonic Simulation"
echo "================================================================="

# 1. Clean up stale processes
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c "killall -9 gz-sim ruby gz kernel_bridge 2>/dev/null || true" >/dev/null 2>&1 || true
fuser -k 7780/tcp 2>/dev/null || true

# 2. Ensure Kernel is running
if ! curl -s http://127.0.0.1:7780/health >/dev/null 2>&1; then
    echo "Starting GRaCEmo Kernel in background..."
    "$DIR/kernel/target/debug/gracemo-kernel" >/dev/null 2>&1 &
    sleep 1
fi

echo "✓ Kernel is online at http://127.0.0.1:7780"

# 3. Build workspace first
echo "Building workspace..."
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    cd $WS_DIR
    colcon build --symlink-install 2>&1 | tail -5
"

# 4. Launch Gazebo Harmonic inside distrobox
echo "Launching Gazebo Harmonic + ROS 2..."
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    source $WS_DIR/install/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export QT_X11_NO_MITSHM=1
    export GZ_SIM_RESOURCE_PATH='$WS_DIR/install/gracemo_gazebo/share/gracemo_gazebo/models'
    echo '📦 GZ_SIM_RESOURCE_PATH: '\$GZ_SIM_RESOURCE_PATH
    ros2 launch gracemo_gazebo sim.launch.py
"
