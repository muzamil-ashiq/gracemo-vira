#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — Prototype Master Shutdown & Safe Halt System
# ==============================================================================

set -e

echo "================================================================="
echo "  🛑 GRaCEmo ViRa — Clean Shutdown & Safe Robot Halt"
echo "  Ubuntu 24.04 | ROS 2 Jazzy | Gazebo Harmonic 8"
echo "================================================================="

# Source ROS 2 environment for safe halt command
source /opt/ros/jazzy/setup.bash 2>/dev/null || true
export GZ_IP=127.0.0.1
export GZ_PARTITION=gracemo
unset ROS_LOCALHOST_ONLY 2>/dev/null || true
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST

PID_FILE="/tmp/gracemo_prototype.pid"
PIDS_LIST="/tmp/gracemo_prototype_pids.txt"

# ------------------------------------------------------------------------------
# STEP 1: Assert Safe Robot Stop (Zero Velocity & Emergency Stop Flag)
# ------------------------------------------------------------------------------
echo "🛑 Step 1: Asserting immediate safe robot stop..."
python3 -c "
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from geometry_msgs.msg import Twist

try:
    rclpy.init()
    node = Node('safe_shutdown_halt')
    estop_pub = node.create_publisher(Bool, '/terrain/emergency_stop', 10)
    cmd_pub = node.create_publisher(Twist, '/cmd_vel', 10)
    
    # Publish E-Stop
    e = Bool()
    e.data = True
    estop_pub.publish(e)
    
    # Publish zero velocity
    t = Twist()
    cmd_pub.publish(t)
    
    rclpy.spin_once(node, timeout_sec=0.2)
    node.destroy_node()
    rclpy.shutdown()
    print('   ✓ Emergency stop asserted and zero velocity command sent.')
except Exception as ex:
    print(f'   ⚠️ Note: ROS e-stop publish skipped: {ex}')
" 2>/dev/null || true

# ------------------------------------------------------------------------------
# STEP 2: Graceful Process Termination (SIGINT / SIGTERM)
# ------------------------------------------------------------------------------
echo "🛑 Step 2: Gracefully stopping prototype processes..."

if [ -f "$PID_FILE" ]; then
    MASTER_PID=$(cat "$PID_FILE")
    if kill -0 "$MASTER_PID" 2>/dev/null; then
        echo "   Sending SIGINT to master launcher PID $MASTER_PID..."
        kill -INT "$MASTER_PID" 2>/dev/null || true
    fi
fi

if [ -f "$PIDS_LIST" ]; then
    while read -r p; do
        if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
            kill -INT "$p" 2>/dev/null || true
        fi
    done < "$PIDS_LIST"
fi

# Also signal known prototype process groups
pkill -INT -f "prototype.launch.py" 2>/dev/null || true
pkill -INT -f "gracemo_command_coordinator" 2>/dev/null || true
pkill -INT -f "gracemo_interaction_node" 2>/dev/null || true
pkill -INT -f "gracemo-kernel" 2>/dev/null || true

# Wait up to 3 seconds for graceful exit
for i in {1..6}; do
    sleep 0.5
    if ! pgrep -f "prototype.launch.py" > /dev/null; then
        break
    fi
done

# ------------------------------------------------------------------------------
# STEP 3: Ensure Gazebo Harmonic & Background Workers are Reaped
# ------------------------------------------------------------------------------
echo "🛑 Step 3: Reaping any remaining simulation or background processes..."
pkill -TERM -f "gz sim" 2>/dev/null || true
pkill -TERM -f "gz-sim" 2>/dev/null || true
pkill -TERM -f "ruby.*gz" 2>/dev/null || true
sleep 1

# Force kill any stubborn remnants
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gz-sim" 2>/dev/null || true
pkill -9 -f "ruby.*gz" 2>/dev/null || true
pkill -9 -f "gracemo_command_coordinator" 2>/dev/null || true
pkill -9 -f "gracemo_interaction_node" 2>/dev/null || true
pkill -9 -f "terrain_monitor_node" 2>/dev/null || true
pkill -9 -f "attitude_diagnostics_node" 2>/dev/null || true
pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
pkill -9 -f "gracemo-kernel" 2>/dev/null || true

# ------------------------------------------------------------------------------
# STEP 4: Clean up temporary files, pidfiles, and sockets
# ------------------------------------------------------------------------------
rm -f "$PID_FILE" "$PIDS_LIST" "/tmp/gracemo.sock" 2>/dev/null || true

# ------------------------------------------------------------------------------
# STEP 5: Verification of Clean State
# ------------------------------------------------------------------------------
REMAINING=""
for i in {1..6}; do
    REMAINING=$(ps aux | grep -E "gz sim|gracemo_command_coordinator|gracemo_interaction_node" | grep -v grep || true)
    if [ -z "$REMAINING" ]; then
        break
    fi
    sleep 0.5
done

if [ -z "$REMAINING" ]; then
    echo "✅ SUCCESS: Clean shutdown completed. No orphaned processes remain."
    exit 0
else
    echo "⚠️ WARNING: The following processes could not be verified clean:"
    echo "$REMAINING"
    exit 1
fi
