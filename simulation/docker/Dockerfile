FROM osrf/ros:jazzy-desktop

ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=all
ENV QT_QPA_PLATFORM=xcb

# Install Navigation2, SLAM Toolbox, and Gazebo Harmonic bridge
RUN apt-get update && apt-get install -y \
    ros-jazzy-navigation2 \
    ros-jazzy-nav2-bringup \
    ros-jazzy-slam-toolbox \
    ros-jazzy-ros-gz \
    ros-jazzy-xacro \
    ros-jazzy-teleop-twist-keyboard \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
