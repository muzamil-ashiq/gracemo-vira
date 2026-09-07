#!/usr/bin/env python3
import subprocess
import os
import re

# 1. Convert xacro to URDF
xacro_file = "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro"
urdf_file = "/tmp/robot.urdf"
cmd = f"source /opt/ros/humble/setup.bash && source /home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/install/setup.bash 2>/dev/null && xacro {xacro_file} -o {urdf_file}"
subprocess.run(["bash", "-c", cmd], check=True)

# 2. Convert URDF to SDF
res = subprocess.run(["gz", "sdf", "-p", urdf_file], capture_output=True, text=True, check=True)
robot_sdf = res.stdout

start = robot_sdf.find("<model name=")
end = robot_sdf.rfind("</model>") + len("</model>")
robot_model_xml = robot_sdf[start:end]

# 2a. Inject initial pose in the bedroom (co-axial with book at X=-4.322, safe clearance Y=2.50)
pose_tag = "    <pose>-4.322 2.50 0.025 0 0 1.570796</pose>\n"
tag_end = robot_model_xml.find(">") + 1
robot_model_xml = robot_model_xml[:tag_end] + "\n" + pose_tag + robot_model_xml[tag_end:]

# 2b. Fix contact sensor collision name mismatch caused by gz sdf -p link lumping
robot_model_xml = robot_model_xml.replace(
    "<collision>finger_left_collision</collision>",
    "<collision>finger_left_link_fixed_joint_lump__finger_left_collision_collision</collision>"
)
robot_model_xml = robot_model_xml.replace(
    "<collision>finger_right_collision</collision>",
    "<collision>finger_right_link_fixed_joint_lump__finger_right_collision_collision</collision>"
)

# 2c. Inject high-friction physical contact surfaces into finger links
friction_surface = """        <surface>
          <friction>
            <ode>
              <mu>3.5</mu>
              <mu2>3.5</mu2>
              <fdir1>0 0 1</fdir1>
              <slip1>0.0</slip1>
              <slip2>0.0</slip2>
            </ode>
          </friction>
          <contact>
            <ode>
              <kp>1000000.0</kp>
              <kd>100.0</kd>
              <min_depth>0.0</min_depth>
              <max_vel>0.0</max_vel>
            </ode>
          </contact>
        </surface>
      </collision>"""

robot_model_xml = re.sub(
    r"(<collision name='finger_(?:left|right)_link_fixed_joint_lump__finger_(?:left|right)_collision_collision'>\s*<pose>[^<]+</pose>\s*<geometry>\s*<box>\s*<size>[^<]+</size>\s*</box>\s*</geometry>)\s*</collision>",
    r"\1\n" + friction_surface,
    robot_model_xml
)

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

# Ensure book_math is in its pristine pose on nightstand with 60mm width facing fingers
new_world = re.sub(
    r'<model name="book_math">(\s*)<pose>[^<]+</pose>',
    r'<model name="book_math">\1<pose>-4.20 3.28 0.62 0 0 1.570796</pose>',
    new_world
)

with open(world_file, "w") as f:
    f.write(new_world)

install_world = "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/install/gracemo_gazebo/share/gracemo_gazebo/worlds/apartment_floor.world"
if os.path.exists(install_world):
    with open(install_world, "w") as f:
        f.write(new_world)

print("Synchronized apartment_floor.world with sleek robot & high-friction pads! Lines:", new_world.count("\n"))
