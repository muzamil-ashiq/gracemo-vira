#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Piece 1 Mobile Base Interactive Studio Viewer
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Clean any existing gz sim instances
pkill -9 -f "gz sim" 2>/dev/null || true
sleep 1

# Compile piece_1_base to URDF & SDF
echo "Compiling Piece 1 Base..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    source $DIR/ros2_ws/install/setup.bash 2>/dev/null || true
    xacro $DIR/ros2_ws/src/gracemo_description/urdf/piece_1_base.urdf.xacro > /tmp/piece_1.urdf
    gz sdf -p /tmp/piece_1.urdf > /tmp/piece_1.sdf
    python3 $DIR/scripts/render_model_piece.py /tmp/piece_1.sdf /tmp/piece_1_view.jpg
"

echo "Launching Gazebo GUI Studio..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    gz sim -r /tmp/studio_render.world
"
