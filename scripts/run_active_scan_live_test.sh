#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=========================================================================="
echo "  GRaCEmo ViRa — Phase 5 Step 1 Live Active Visual Scan Test Runner"
echo "=========================================================================="

# 1. Cleanup any existing stale processes and databases
echo "Cleaning up any stale Gazebo, ROS, and Kernel processes and databases..."
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gz-sim" 2>/dev/null || true
pkill -9 -f "ros2 launch" 2>/dev/null || true
pkill -9 -f "kernel_bridge" 2>/dev/null || true
pkill -9 -f "sensor_bridge" 2>/dev/null || true
pkill -9 -f "gracemo-kernel" 2>/dev/null || true
rm -rf ~/.gracemo/*.db* /tmp/gracemo_kernel_graph.db* /tmp/gracemo_ledger.db* /tmp/gracemo_camera_*.jpg /tmp/scan_debug_frame.jpg
sleep 1

# 1b. Embed robot in bedroom spawn pose
distrobox enter gracemo-harmonic -- python3 "$DIR/scripts/embed_robot_world.py" bedroom

# 2. Start Rust Kernel daemon on the host
echo "Starting GRaCEmo Kernel daemon on http://127.0.0.1:7780..."
"$DIR/kernel/target/debug/gracemo-kernel" > /tmp/kernel_active_scan_test.log 2>&1 &
KERNEL_PID=$!
sleep 1

# Verify Kernel health
python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7780/health', timeout=1.0)" || (echo "Kernel failed to start" && exit 1)
echo "✓ GRaCEmo Kernel active at http://127.0.0.1:7780"

cleanup() {
    echo "Cleaning up simulation and Kernel (PID: $KERNEL_PID)..."
    kill -TERM "$KERNEL_PID" 2>/dev/null || true
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f "gz-sim" 2>/dev/null || true
    pkill -9 -f "ros2 launch" 2>/dev/null || true
    pkill -9 -f "kernel_bridge" 2>/dev/null || true
    pkill -9 -f "sensor_bridge" 2>/dev/null || true
    pkill -9 -f "gracemo-kernel" 2>/dev/null || true
    rm -rf ~/.gracemo/*.db* /tmp/gracemo_kernel_graph.db* /tmp/gracemo_ledger.db* /tmp/gracemo_camera_*.jpg /tmp/scan_debug_frame.jpg
}
trap cleanup EXIT

# 3. Execute inner simulation runner inside distrobox container
chmod +x "$DIR/scripts/sim_active_scan_inner.sh"
distrobox enter gracemo-harmonic -- "$DIR/scripts/sim_active_scan_inner.sh"

echo "=========================================================================="
echo "✓ Phase 5 Step 1 Live Active Visual Scan Test Suite: ALL GATES GREEN"
echo "=========================================================================="
