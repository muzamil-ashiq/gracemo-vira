#!/usr/bin/env bash
# ==============================================================================
# GRaCEmo ViRa — RViz 2 Robotics Inspection Studio Launcher
# Bridges Gazebo Harmonic simulation to ROS 2 & launches RViz 2 with:
# - 3D Robot Model (URDF + TF)
# - Real-time Planar LiDAR LaserScan (cyan point cloud)
# - Real-time Head Eyes Camera Feed (floating HUD image)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Clean previous simulation & bridges
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "parameter_bridge" 2>/dev/null || true
pkill -9 -f "robot_state_publisher" 2>/dev/null || true
pkill -9 -f "rviz2" 2>/dev/null || true
sleep 1

echo "1. Compiling Piece 3 Model & Obstacle Arena..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    python3 $DIR/scripts/make_obstacle_world.py
"

echo "2. Launching Gazebo Physics & Sensor Engine in background..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    gz sim -s -r /tmp/studio_obstacles.world
" &
GZ_PID=$!
sleep 2

echo "3. Publishing Robot State & TF..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    ros2 run robot_state_publisher robot_state_publisher /tmp/piece_3.urdf
" &
RSP_PID=$!
sleep 1

echo "4. Starting ROS-Gazebo Bridge (LiDAR, Camera, Odom, CmdVel)..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    ros2 run ros_gz_bridge parameter_bridge \
        /scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
        /camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image \
        /camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image \
        /odom@nav_msgs/msg/Odometry[gz.msgs.Odometry \
        /cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist
" &
BRIDGE_PID=$!
sleep 1.5

echo "5. Launching RViz 2..."
distrobox enter gracemo-harmonic -- bash -c "
    source /opt/ros/humble/setup.bash
    export DISPLAY='${DISPLAY:-:0}'
    export WAYLAND_DISPLAY='${WAYLAND_DISPLAY:-}'
    export QT_X11_NO_MITSHM=1
    rviz2 -d $DIR/ros2_ws/src/gracemo_description/rviz/piece_view.rviz
"

# Cleanup on RViz exit
kill $GZ_PID $RSP_PID $BRIDGE_PID 2>/dev/null || true
