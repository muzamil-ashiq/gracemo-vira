#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Prototype Master Launcher & Lifecycle Orchestrator
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$DIR/ros2_ws"
PID_FILE="/tmp/gracemo_prototype.pid"
PIDS_LIST="/tmp/gracemo_prototype_pids.txt"

echo "================================================================="
echo "  🤖 GRaCEmo ViRa — Integrated Prototype v1.0 Launcher"
echo "  Ubuntu 24.04 | ROS 2 Jazzy | Gazebo Harmonic 8"
echo "================================================================="

# ------------------------------------------------------------------------------
# STEP 1: Process Concurrency & Duplicate Instance Prevention
# ------------------------------------------------------------------------------
RESTART_REQUESTED=false
WAIT_READY=false
LAUNCH_ARGS=()

for arg in "$@"; do
    if [ "$arg" == "--restart" ] || [ "$arg" == "-r" ]; then
        RESTART_REQUESTED=true
    elif [ "$arg" == "--wait-ready" ] || [ "$arg" == "--verify" ]; then
        WAIT_READY=true
    else
        LAUNCH_ARGS+=("$arg")
    fi
done

ALREADY_RUNNING=false
if pgrep -f "prototype.launch.py" > /dev/null || pgrep -f "gz sim server" > /dev/null; then
    ALREADY_RUNNING=true
fi

if [ "$ALREADY_RUNNING" = true ]; then
    if [ "$RESTART_REQUESTED" = true ]; then
        echo "🔄 Existing simulation or prototype processes detected. Performing clean restart..."
        "$DIR/scripts/stop_prototype.sh"
        sleep 1
    else
        echo "⚠️ WARNING: GRaCEmo ViRa prototype is already running!"
        echo "   Active processes:"
        ps aux | grep -E "prototype.launch.py|gz sim server|gracemo_command_coordinator" | grep -v grep | awk '{print "   PID: " $2 " | " $11 " " $12}'
        echo "   To restart cleanly, pass --restart or run: $DIR/scripts/stop_prototype.sh"
        exit 0
    fi
fi

# Clean up any stale pidfiles/sockets
rm -f "$PID_FILE" "$PIDS_LIST" 2>/dev/null || true

# ------------------------------------------------------------------------------
# STEP 2: Deterministic ROS 2 & Gazebo Harmonic Environment Setup
# ------------------------------------------------------------------------------
source /opt/ros/jazzy/setup.bash
unset ROS_LOCALHOST_ONLY 2>/dev/null || true
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_DOMAIN_ID=0
export GZ_IP=127.0.0.1
export GZ_PARTITION=gracemo

if [ -f "$WS_DIR/install/setup.bash" ]; then
    source "$WS_DIR/install/setup.bash"
else
    echo "⚙️ Workspace not built yet. Building now..."
    cd "$WS_DIR"
    colcon build --symlink-install
    source "$WS_DIR/install/setup.bash"
fi

# Record master launcher PID
echo $$ > "$PID_FILE"

# ------------------------------------------------------------------------------
# STEP 3: Launch Authoritative GRaCEmo Kernel Daemon (MNSE)
# ------------------------------------------------------------------------------
KERNEL_BIN=""
if [ -x "$DIR/kernel/target/debug/gracemo-kernel" ]; then
    KERNEL_BIN="$DIR/kernel/target/debug/gracemo-kernel"
elif [ -x "$DIR/../../../VIRA-agent-bridge-migration/kernel/target/debug/gracemo-kernel" ]; then
    KERNEL_BIN="$DIR/../../../VIRA-agent-bridge-migration/kernel/target/debug/gracemo-kernel"
elif [ -x "/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/kernel/target/debug/gracemo-kernel" ]; then
    KERNEL_BIN="/home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/kernel/target/debug/gracemo-kernel"
fi
KERNEL_PID=""
if [ -n "$KERNEL_BIN" ] && [ -x "$KERNEL_BIN" ]; then
    echo "🧠 Launching authoritative GRaCEmo Kernel daemon (MNSE)..."
    "$KERNEL_BIN" > /tmp/gracemo_kernel.log 2>&1 &
    KERNEL_PID=$!
    echo $KERNEL_PID >> "$PIDS_LIST"
    echo "🧠 Kernel daemon online (PID: $KERNEL_PID). REST: http://127.0.0.1:7780 | Sock: /tmp/gracemo.sock"
fi

# ------------------------------------------------------------------------------
# STEP 4: Signal Traps & Safe Cleanup Handling
# ------------------------------------------------------------------------------
cleanup() {
    echo "🛑 Caught termination signal. Initiating clean shutdown..."
    "$DIR/scripts/stop_prototype.sh"
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------------------
# STEP 5: Launch Master Prototype & Staggered Systems
# ------------------------------------------------------------------------------
echo "🚀 Launching ROS 2 Jazzy & Gazebo Harmonic Prototype Stack..."

if [ "$WAIT_READY" = true ]; then
    # Launch in background of this script, run verification, then await
    ros2 launch gracemo_bringup prototype.launch.py "${LAUNCH_ARGS[@]}" &
    LAUNCH_PID=$!
    echo $LAUNCH_PID >> "$PIDS_LIST"
    
    echo "⏳ Waiting for system initialization and executing readiness verification..."
    sleep 8
    if python3 "$DIR/scripts/verify_system_readiness.py"; then
        echo "🎉 All 11 Readiness Stages Confirmed. System is fully healthy and ready for autonomous commands."
    else
        echo "❌ Readiness verification detected issues! Check logs for diagnostics."
    fi
    wait $LAUNCH_PID
else
    ros2 launch gracemo_bringup prototype.launch.py "${LAUNCH_ARGS[@]}"
fi
