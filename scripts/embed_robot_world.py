import subprocess

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

# Read apartment_floor.world
world_file = "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/src/gracemo_gazebo/worlds/apartment_floor.world"
with open(world_file, "r") as f:
    world_content = f.read()

# Make sure camera view is isometric angled view
old_cam = "<pose>0.0 0.0 22.0 0 1.5 0</pose>"
new_cam = "<pose>-3.0 -8.0 7.5 0 0.65 1.1</pose>"
if old_cam in world_content:
    world_content = world_content.replace(old_cam, new_cam)

# Remove any existing gracemo_vira model from world if present
if '<model name="gracemo_vira">' in world_content or "<model name='gracemo_vira'>" in world_content:
    import re
    world_content = re.sub(r'\s*<model name=[\'"]gracemo_vira[\'"]>.*?</model>', '', world_content, flags=re.DOTALL)

# Insert robot model before </world>
new_world = world_content.replace("</world>", f"""    <!-- ROBOT MODEL -->
    {robot_model_xml}

  </world>""")

with open(world_file, "w") as f:
    f.write(new_world)

print("Embedded robot in world successfully! Total lines:", new_world.count("\n"))
