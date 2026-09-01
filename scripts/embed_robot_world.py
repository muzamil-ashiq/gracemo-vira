#!/usr/bin/env python3
import subprocess
import os

# 1. Convert xacro to URDF
xacro_file = "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro"
urdf_file = "/tmp/robot.urdf"
subprocess.run(["xacro", xacro_file, "-o", urdf_file], check=True)

# 2. Convert URDF to SDF
res = subprocess.run(["gz", "sdf", "-p", urdf_file], capture_output=True, text=True, check=True)
robot_sdf = res.stdout

start = robot_sdf.find("<model name=")
end = robot_sdf.rfind("</model>") + len("</model>")
robot_model_xml = robot_sdf[start:end]

# 3. Read apartment_floor.world
world_file = "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/src/gracemo_gazebo/worlds/apartment_floor.world"
with open(world_file, "r") as f:
    world_content = f.read()

# Replace existing robot model block safely by exact string markers
m_start = world_content.find("<model name='gracemo_vira'>")
if m_start == -1:
    m_start = world_content.find('<model name="gracemo_vira">')

if m_start != -1:
    # Find matching </model> for gracemo_vira
    m_end = world_content.find("</model>", m_start) + len("</model>")
    new_world = world_content[:m_start] + robot_model_xml + world_content[m_end:]
else:
    new_world = world_content.replace("</world>", f"    {robot_model_xml}\n  </world>")

with open(world_file, "w") as f:
    f.write(new_world)

print("Synchronized apartment_floor.world with sleek robot! Lines:", new_world.count("\n"))
