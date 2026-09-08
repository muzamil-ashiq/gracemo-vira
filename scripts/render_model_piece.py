#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import cv2
import numpy as np
import gz.transport13 as gz_transport
from gz.msgs10.image_pb2 import Image

def render_piece(sdf_path: str, output_image_path: str, camera_pose="0.75 -0.75 0.45 0 0.38 2.356"):
    # 1. Read SDF snippet of the model
    with open(sdf_path, "r") as f:
        model_sdf = f.read()

    start = model_sdf.find("<model name=")
    end = model_sdf.rfind("</model>") + len("</model>")
    robot_model_xml = model_sdf[start:end]

    # Inject base spawn pose at ground origin
    pose_tag = "    <pose>0 0 0 0 0 0</pose>\n"
    tag_end = robot_model_xml.find(">") + 1
    robot_model_xml = robot_model_xml[:tag_end] + "\n" + pose_tag + robot_model_xml[tag_end:]

    # 2. Construct studio world
    studio_world = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="model_studio">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <!-- Studio Lighting -->
    <light type="directional" name="sun_key">
      <cast_shadows>true</cast_shadows>
      <pose>2 -2 4 0 0 0</pose>
      <diffuse>0.9 0.9 0.95 1</diffuse>
      <specular>0.4 0.4 0.4 1</specular>
      <direction>-0.5 0.5 -1</direction>
    </light>
    <light type="directional" name="sun_fill">
      <cast_shadows>false</cast_shadows>
      <pose>-2 2 3 0 0 0</pose>
      <diffuse>0.4 0.4 0.45 1</diffuse>
      <direction>0.5 -0.5 -0.8</direction>
    </light>

    <!-- Studio Floor -->
    <model name="studio_floor">
      <static>true</static>
      <link name="floor_link">
        <collision name="c">
          <geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry>
        </collision>
        <visual name="v">
          <geometry><plane><normal>0 0 1</normal><size>10 10</size></plane></geometry>
          <material>
            <ambient>0.82 0.84 0.86 1</ambient>
            <diffuse>0.82 0.84 0.86 1</diffuse>
            <specular>0.1 0.1 0.1 1</specular>
          </material>
        </visual>
      </link>
    </model>

    <!-- Studio Inspection Camera -->
    <model name="studio_camera">
      <static>true</static>
      <pose>{camera_pose}</pose>
      <link name="camera_link">
        <sensor name="studio_cam" type="camera">
          <topic>/studio/camera/image_raw</topic>
          <update_rate>30.0</update_rate>
          <camera>
            <horizontal_fov>1.05</horizontal_fov>
            <image>
              <width>1280</width>
              <height>720</height>
              <format>R8G8B8</format>
            </image>
            <clip><near>0.05</near><far>10.0</far></clip>
          </camera>
          <always_on>1</always_on>
          <visualize>true</visualize>
        </sensor>
      </link>
    </model>

    <!-- Robot Model Piece -->
    {robot_model_xml}

  </world>
</sdf>
"""

    world_tmp = "/tmp/studio_render.world"
    with open(world_tmp, "w") as f:
        f.write(studio_world)

    # 3. Launch Gazebo headless with rendering
    print(f"Launching Gazebo Studio to render {sdf_path}...")
    cmd = ["gz", "sim", "-s", "-r", world_tmp]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    captured = [False]
    node = gz_transport.Node()

    def on_image(msg: Image):
        if captured[0]:
            return
        w, h = msg.width, msg.height
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        cv2.imwrite(output_image_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        captured[0] = True
        print(f"✓ Render saved successfully to {output_image_path} ({w}x{h})")

    node.subscribe(Image, "/studio/camera/image_raw", on_image)

    # Wait up to 8 seconds for image capture
    t0 = time.time()
    while not captured[0] and time.time() - t0 < 8.0:
        time.sleep(0.1)

    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except Exception:
        proc.kill()

    return captured[0]

if __name__ == "__main__":
    sdf = sys.argv[1] if len(sys.argv) > 1 else "/tmp/piece_1.sdf"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/piece_1_render.jpg"
    cam = sys.argv[3] if len(sys.argv) > 3 else "0.75 -0.75 0.45 0 0.38 2.356"
    success = render_piece(sdf, out, camera_pose=cam)
    sys.exit(0 if success else 1)
