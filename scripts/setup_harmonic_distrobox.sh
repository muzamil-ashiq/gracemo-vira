#!/usr/bin/env bash
set -e

echo "=== [1/5] Base packages ==="
sudo apt-get update -qq
sudo apt-get install -y curl gnupg2 lsb-release locales python3-pip git build-essential

sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

echo "=== [2/5] ROS 2 Humble apt source ==="
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list

echo "=== [3/5] Gazebo Harmonic apt source ==="
sudo curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
  --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable jammy main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list

sudo apt-get update -qq

echo "=== [4/5] Gazebo Harmonic ==="
sudo apt-get install -y gz-harmonic

echo "=== [5/5] ROS 2 Humble + ros_gz bridge ==="
sudo apt-get install -y \
  ros-humble-desktop \
  ros-humble-ros-gz \
  ros-humble-ros-gz-bridge \
  ros-humble-ros-gz-sim \
  ros-humble-ros-gz-interfaces \
  ros-humble-ros-gz-image \
  ros-humble-xacro \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  ros-humble-nav2-bringup \
  ros-humble-slam-toolbox \
  python3-colcon-common-extensions

echo "✅ Done! Run: gz sim --version && ros2 --version"
