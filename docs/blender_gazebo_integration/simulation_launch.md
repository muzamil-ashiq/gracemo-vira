# Simulation Launch and Lifecycle Guide

This document provides exact, verified commands for launching, controlling, and cleanly restarting the GRaCEmo ViRa Gazebo Harmonic simulation and autonomy stack.

---

## 1. Environment Preparation

Before launching, source ROS 2 Jazzy and the integrated workspace:

```bash
# Source ROS 2 Jazzy core:
source /opt/ros/jazzy/setup.bash

# Source the primary integrated prototype workspace:
source ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash

# Export Gazebo resource paths (automatically handled by launch file, provided here for manual inspection):
export GZ_SIM_RESOURCE_PATH=~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/gracemo_robot_description/share:$GZ_SIM_RESOURCE_PATH
```

---

## 2. Launch Commands

### Mode A: Full Autonomy Bringup (Simulation + Nav2 + Coordinator + Interaction)
Launches the entire production robotics stack in a single coordinated command:

```bash
cd ~/projects/VIRA/prototypes/gracemo_integrated_v1
bash scripts/run_prototype.sh headless:=false
```
*Use `headless:=true` for background evaluation or automated testing.*

### Mode B: Primary Simulation Only (Gazebo Harmonic + Spawner + ros_gz_bridge)
To run only the physical simulation and sensor bridges:

```bash
# Interactive GUI mode:
ros2 launch gracemo_simulation simulation.launch.py headless:=false

# Headless mode:
ros2 launch gracemo_simulation simulation.launch.py headless:=true
```

### Mode C: Interactive Voice & Navigation Console
In a separate terminal, test high-level conversational commands:

```bash
source /opt/ros/jazzy/setup.bash
source ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/install/setup.bash
python3 ~/projects/VIRA/prototypes/gracemo_integrated_v1/scripts/test_voice_commands.py
```

---

## 3. Clean Shutdown and Restart Procedure

To guarantee that all Gazebo server daemons, bridges, and ROS 2 lifecycle nodes terminate without leaving orphan processes:

```bash
# 1. Terminate running processes:
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gz-sim" 2>/dev/null || true
pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
pkill -9 -f "robot_state_publisher" 2>/dev/null || true
pkill -9 -f "nav2" 2>/dev/null || true
pkill -9 -f "coordinator_node" 2>/dev/null || true
pkill -9 -f "interaction_node" 2>/dev/null || true

# 2. Verify all ports and daemons are clear:
ps aux | grep -E "gz|ros2|ruby" | grep -v grep

# 3. Restart simulation:
ros2 launch gracemo_bringup prototype.launch.py headless:=true
```
