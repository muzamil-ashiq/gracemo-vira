#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"

source /opt/ros/humble/setup.bash
source "$WS_DIR/install/setup.bash"
export GZ_SIM_RESOURCE_PATH="$WS_DIR/install/gracemo_gazebo/share/gracemo_gazebo/models:$HOME/.gz/fuel/fuel.gazebosim.org/openrobotics/models:/opt/ros/humble/share"

echo "Launching Gazebo apartment simulation + bridges..."
ros2 launch gracemo_gazebo sim.launch.py > /tmp/sim_nav_grounding_test.log 2>&1 &
SIM_PID=$!

cleanup() {
    echo "Cleaning up inner simulation (PID: $SIM_PID)..."
    kill -TERM "$SIM_PID" 2>/dev/null || true
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f "gz-sim" 2>/dev/null || true
    pkill -9 -f "ros2 launch" 2>/dev/null || true
    pkill -9 -f "kernel_bridge" 2>/dev/null || true
    pkill -9 -f "sensor_bridge" 2>/dev/null || true
}
trap cleanup EXIT

echo "Waiting 7s for Gazebo Harmonic physics and sensor bridges to initialize..."
sleep 7

echo "Executing Phase 4 Step 4 Live Navigation Grounding Validation..."
python3 "$DIR/tests/test_navigation_grounding_live.py"

echo "Inner simulation validation completed successfully!"
