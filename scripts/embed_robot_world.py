import subprocess
import re

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

# Clean out any old robot models and comments
world_content = re.sub(r'\s*<!--\s*🤖\s*GRaCEmo ViRa ROBOT MODEL\s*-->', '', world_content)
world_content = re.sub(r'\s*<!--\s*ROBOT MODEL\s*-->', '', world_content)
world_content = re.sub(r'\s*<model name=[\'"]gracemo_vira[\'"]>.*?</model>', '', world_content, flags=re.DOTALL)

# Default 3D perspective camera looking at the hallway robot
world_content = re.sub(r'<camera name=[\'"]user_camera[\'"]>.*?</camera>', """<camera name="user_camera">
        <pose>-2.5 -4.5 3.5 0 0.55 1.1</pose>
        <view_controller>orbit</view_controller>
        <projection_type>perspective</projection_type>
      </camera>""", world_content, flags=re.DOTALL)

# Insert robot model before </world>
new_world = world_content.replace("</world>", f"""    <!-- =====================================================================
         🤖 GRaCEmo ViRa ROBOT MODEL
         ===================================================================== -->
    {robot_model_xml}

  </world>""")

with open(world_file, "w") as f:
    f.write(new_world)

print("Synchronized apartment_floor.world with sleek robot! Lines:", new_world.count("\n"))
