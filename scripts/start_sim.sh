#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Gazebo Harmonic + ROS 2 Humble Launcher
# Distrobox: gracemo-harmonic
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"

echo "================================================================="
echo "  GRaCEmo ViRa — Gazebo Harmonic 8 + ROS 2 Humble"
echo "================================================================="

# 1. Clean up stale Gazebo processes
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c \
  "killall -9 gz-sim gz ruby kernel_bridge 2>/dev/null || true" \
  >/dev/null 2>&1 || true

# 2. Build workspace and update embedded robot
echo "Building ROS 2 workspace..."
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    cd $WS_DIR
    colcon build --symlink-install 2>&1 | tail -3
    source $WS_DIR/install/setup.bash
    python3 $DIR/scripts/embed_robot_world.py
"

# 3. Launch Gazebo Harmonic + ROS bridge inside distrobox
echo "Launching Gazebo Harmonic..."
~/.local/bin/distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    source $WS_DIR/install/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    export GZ_SIM_RESOURCE_PATH='$WS_DIR/install/gracemo_gazebo/share/gracemo_gazebo/models'
    ros2 launch gracemo_gazebo sim.launch.py
"
