#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC) V1.0 Launcher
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "================================================================="
echo "  🚀 GRaCEmo ViRa — Unified Autonomous Robotics Control Center"
echo "  PySide6 | ROS 2 Jazzy | Gazebo Harmonic | Engineering Workstation"
echo "================================================================="

# Source ROS 2 Jazzy
source /opt/ros/jazzy/setup.bash

# Sourcing workspace overlays if present
if [ -f "$DIR/ros2_ws/install/setup.bash" ]; then
    source "$DIR/ros2_ws/install/setup.bash"
fi
if [ -f "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash" ]; then
    source "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash"
fi

# Deterministic DDS and Gazebo environment
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_DOMAIN_ID=0
export GZ_PARTITION=gracemo
export GZ_IP=127.0.0.1
export PYTHONPATH="$DIR:$PYTHONPATH"

# Launch Control Center Desktop Application
exec python3 "$DIR/gracemo_control_center/main.py" "$@"
