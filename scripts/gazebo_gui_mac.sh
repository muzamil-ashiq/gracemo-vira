#!/usr/bin/env bash
# Launch Gazebo Harmonic on macOS via Docker (ros2_learn) + optional GUI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${GRACEEMO_CONTAINER:-ros2_learn}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Starting container $CONTAINER..."
  docker start "$CONTAINER" >/dev/null
fi

# --- GUI path (native Gazebo window via XQuartz) ---
if [[ "${1:-gui}" == "gui" ]]; then
  if ! open -Ra XQuartz 2>/dev/null; then
    echo "Install XQuartz first: https://www.xquartz.org/" >&2
    exit 1
  fi
  open -a XQuartz
  sleep 2
  xhost +localhost 2>/dev/null || xhost + 2>/dev/null || true

  echo "Launching Gazebo with GUI (campus + GRACEEMO-01)..."
  docker exec "$CONTAINER" bash -lc "
    source /opt/ros/jazzy/setup.bash
    source /workspace/GraceEMO-Final/graceemo_ws/install/setup.bash
    export DISPLAY=host.docker.internal:0
    export QT_X11_NO_MITSHM=1
    export LIBGL_ALWAYS_INDIRECT=1
    export LIBGL_ALWAYS_SOFTWARE=1
    ros2 launch gracemo_gazebo gazebo.launch.py gui:=true
  "
  exit 0
fi

# --- Headless server (works reliably on Mac Docker) ---
if [[ "$1" == "headless" ]]; then
  echo "Launching Gazebo headless (physics + /cmd_vel /scan /odom)..."
  docker exec "$CONTAINER" bash -lc "
    source /opt/ros/jazzy/setup.bash
    source /workspace/GraceEMO-Final/graceemo_ws/install/setup.bash
    unset DISPLAY
    export GZ_SIM_HEADLESS_RENDERING=1
    ros2 launch gracemo_gazebo gazebo.launch.py gui:=false
  "
  exit 0
fi

# --- Full Phase 1 on Gazebo ---
if [[ "$1" == "full" ]]; then
  docker exec "$CONTAINER" bash -lc "
    source /opt/ros/jazzy/setup.bash
    source /workspace/GraceEMO-Final/graceemo_ws/install/setup.bash
    unset DISPLAY
    export GZ_SIM_HEADLESS_RENDERING=1
    ros2 launch gracemo_bringup gazebo_sim.launch.py
  "
  exit 0
fi

echo "Usage: $0 [gui|headless|full]" >&2
exit 1
