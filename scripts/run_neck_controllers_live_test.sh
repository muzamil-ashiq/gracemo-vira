#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"

echo "Cleaning up any stale Gazebo and ROS processes..."
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gz-sim" 2>/dev/null || true
pkill -9 -f "ros2 launch" 2>/dev/null || true
sleep 1

source /opt/ros/humble/setup.bash
source "$WS_DIR/install/setup.bash"
export GZ_SIM_RESOURCE_PATH="$WS_DIR/install/gracemo_gazebo/share/gracemo_gazebo/models:$HOME/.gz/fuel/fuel.gazebosim.org/openrobotics/models:/opt/ros/humble/share"

echo "Launching Gazebo simulation in background..."
ros2 launch gracemo_gazebo sim.launch.py > /tmp/sim_neck_test.log 2>&1 &
SIM_PID=$!

cleanup() {
    echo "Shutting down simulation (PID: $SIM_PID)..."
    kill -TERM "$SIM_PID" 2>/dev/null || true
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f "gz-sim" 2>/dev/null || true
    pkill -9 -f "ros2 launch" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting 5s for simulation to initialize..."
sleep 5

echo "Executing live neck controller physics test..."
python3 "$DIR/tests/test_neck_controllers_live.py"

echo "Live test complete!"
