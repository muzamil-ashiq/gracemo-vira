#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Single-Terminal Full Gazebo & Autonomous Stack Launcher
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

cleanup() {
    echo -e "\n🛑 Stopping all simulation and autonomous nodes..."
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f "gracemo-kernel" 2>/dev/null || true
    pkill -9 -f "ros2 launch" 2>/dev/null || true
    fuser -k 7780/tcp 2>/dev/null || true
    kill 0 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

# 1. Clean up stale processes
echo "🧹 Cleaning up stale processes..."
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gracemo-kernel" 2>/dev/null || true
pkill -9 -f "ros2 launch" 2>/dev/null || true
fuser -k 7780/tcp 2>/dev/null || true
sleep 1

# 2. Source environments
source /opt/ros/jazzy/setup.bash
source "$DIR/ros2_ws/install/setup.bash"

export DISPLAY="${DISPLAY:-:0}"
export ROS_DOMAIN_ID=0
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_PARTITION=gracemo
export GZ_IP=127.0.0.1
export QT_X11_NO_MITSHM=1
export GZ_SIM_RESOURCE_PATH="$DIR/ros2_ws/install/gracemo_gazebo/share/gracemo_gazebo/models:$HOME/.gz/fuel/fuel.gazebosim.org/openrobotics/models:$HOME/.ignition/fuel/fuel.gazebosim.org/openrobotics/models:/opt/ros/jazzy/share"

# 3. Start authoritative Kernel daemon
echo "🧠 [1/3] Starting GRaCEmo Kernel daemon (MNSE)..."
"$DIR/kernel/target/debug/gracemo-kernel" > /tmp/gracemo_kernel.log 2>&1 &
sleep 2

# 4. Launch Full Stack (Gazebo Simulation, Nav2 SLAM, RViz2, Sensor & Interaction Bridges)
echo "🚀 [2/3] Launching complete ROS 2 & Gazebo Harmonic autonomous stack..."
ros2 launch gracemo_gazebo vira_complete.launch.py &
sleep 5

# 5. Open Gazebo 3D GUI Window
echo "🖥️  [3/3] Opening Gazebo 3D simulation GUI window..."
gz sim -g &

# Keep script running; Ctrl+C will trigger clean shutdown
echo "✅ Full simulation & autonomous stack running! Press Ctrl+C anytime to stop."
wait
