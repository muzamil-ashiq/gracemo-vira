#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Observability & Telemetry Suite
# Launches:
# 1. ROS-Gazebo Parameter Bridge (Topics: /scan, /odom, /camera/image_raw, /cmd_vel)
# 2. Foxglove Bridge (WebSocket: ws://localhost:8765)
# 3. FastAPI & WebSocket Decision Timeline Dashboard (HTTP: http://localhost:8000)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Clean previous instances
pkill -9 -f "foxglove_bridge" 2>/dev/null || true
pkill -9 -f "scripts/dashboard/server.py" 2>/dev/null || true
sleep 1

echo "=================================================================="
echo "  GRaCEmo ViRa — Observability & Telemetry Suite"
echo "=================================================================="

# 1. Start Foxglove Bridge (Port 8765)
echo "▶ Starting Foxglove Bridge on ws://localhost:8765..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    ros2 run foxglove_bridge foxglove_bridge
" &
FOXGLOVE_PID=$!
sleep 1.5

# 2. Start FastAPI & WebSocket Dashboard (Port 8000)
echo "▶ Starting Real-Time Observability Dashboard on http://localhost:8000..."
distrobox enter gracemo-harmonic -- bash -c "
    python3 $DIR/scripts/dashboard/server.py 8000
" &
DASHBOARD_PID=$!
sleep 1.5

echo ""
echo "=================================================================="
echo "  ✓ Observability Suite Running Successfully!"
echo "=================================================================="
echo "  1. Web Dashboard (Event Timeline & Telemetry):"
echo "     --> http://localhost:8000"
echo ""
echo "  2. Foxglove Studio (3D Point Cloud & Telemetry):"
echo "     --> Open Foxglove Studio and connect to: ws://localhost:8765"
echo ""
echo "  3. RViz 2 (Native ROS 2 3D Visualizer):"
echo "     --> Run: bash scripts/view_piece_rviz.sh"
echo "=================================================================="
echo "Press Ctrl+C to stop all observability services."

trap "kill $FOXGLOVE_PID $DASHBOARD_PID 2>/dev/null || true; exit 0" INT TERM
wait
