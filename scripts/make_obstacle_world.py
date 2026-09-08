#!/usr/bin/env python3
"""
Generates the Obstacle Arena World for testing Piece 2 Sensor-Driven Avoidance.
"""
import os
import subprocess

def make_obstacle_world():
    # 1. Compile piece_2 to SDF
    sdf_tmp = "/tmp/piece_2.sdf"
    urdf_tmp = "/tmp/piece_2.urdf"
    subprocess.run([
        "xacro",
        "/home/mab/Applications/lpu-project/gracemo-vira/ros2_ws/src/gracemo_description/urdf/piece_2_sensors.urdf.xacro"
    ], stdout=open(urdf_tmp, "w"), check=True)

    subprocess.run([
        "gz", "sdf", "-p", urdf_tmp
    ], stdout=open(sdf_tmp, "w"), check=True)

    with open(sdf_tmp, "r") as f:
        sdf_text = f.read()

    start = sdf_text.find("<model name=")
    end = sdf_text.rfind("</model>") + len("</model>")
    robot_model_xml = sdf_text[start:end]

    # Spawn pose at (0, 0, 0)
    pose_tag = "    <pose>0 0 0 0 0 0</pose>\n"
    tag_end = robot_model_xml.find(">") + 1
    robot_model_xml = robot_model_xml[:tag_end] + "\n" + pose_tag + robot_model_xml[tag_end:]

    world_xml = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="obstacle_arena">
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

    <!-- Lighting -->
    <light type="directional" name="sun_key">
      <cast_shadows>true</cast_shadows>
      <pose>3 -3 5 0 0 0</pose>
      <diffuse>0.9 0.9 0.95 1</diffuse>
      <specular>0.3 0.3 0.3 1</specular>
      <direction>-0.5 0.5 -1</direction>
    </light>
    <light type="directional" name="sun_fill">
      <cast_shadows>false</cast_shadows>
      <pose>-3 3 4 0 0 0</pose>
      <diffuse>0.4 0.4 0.45 1</diffuse>
      <direction>0.5 -0.5 -0.8</direction>
    </light>

    <!-- Arena Floor -->
    <model name="arena_floor">
      <static>true</static>
      <link name="floor_link">
        <collision name="c">
          <geometry><plane><normal>0 0 1</normal><size>12 12</size></plane></geometry>
        </collision>
        <visual name="v">
          <geometry><plane><normal>0 0 1</normal><size>12 12</size></plane></geometry>
          <material>
            <ambient>0.80 0.82 0.85 1</ambient>
            <diffuse>0.80 0.82 0.85 1</diffuse>
            <specular>0.1 0.1 0.1 1</specular>
          </material>
        </visual>
      </link>
    </model>

    <!-- Perimeter Arena Walls (6m x 6m) -->
    <!-- North Wall -->
    <model name="wall_north">
      <static>true</static>
      <pose>0 3.0 0.4 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>6.2 0.2 0.8</size></box></geometry></collision>
        <visual name="v">
          <geometry><box><size>6.2 0.2 0.8</size></box></geometry>
          <material><ambient>0.3 0.35 0.4 1</ambient><diffuse>0.3 0.35 0.4 1</diffuse></material>
        </visual>
      </link>
    </model>
    <!-- South Wall -->
    <model name="wall_south">
      <static>true</static>
      <pose>0 -3.0 0.4 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>6.2 0.2 0.8</size></box></geometry></collision>
        <visual name="v">
          <geometry><box><size>6.2 0.2 0.8</size></box></geometry>
          <material><ambient>0.3 0.35 0.4 1</ambient><diffuse>0.3 0.35 0.4 1</diffuse></material>
        </visual>
      </link>
    </model>
    <!-- East Wall -->
    <model name="wall_east">
      <static>true</static>
      <pose>3.0 0 0.4 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>0.2 6.0 0.8</size></box></geometry></collision>
        <visual name="v">
          <geometry><box><size>0.2 6.0 0.8</size></box></geometry>
          <material><ambient>0.3 0.35 0.4 1</ambient><diffuse>0.3 0.35 0.4 1</diffuse></material>
        </visual>
      </link>
    </model>
    <!-- West Wall -->
    <model name="wall_west">
      <static>true</static>
      <pose>-3.0 0 0.4 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>0.2 6.0 0.8</size></box></geometry></collision>
        <visual name="v">
          <geometry><box><size>0.2 6.0 0.8</size></box></geometry>
          <material><ambient>0.3 0.35 0.4 1</ambient><diffuse>0.3 0.35 0.4 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- OBSTACLE 1: Central Crimson Column right in front of spawn (X=1.3m, Y=0.0m) -->
    <model name="obstacle_center_column">
      <static>true</static>
      <pose>1.30 0.0 0.40 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><cylinder><radius>0.18</radius><length>0.80</length></cylinder></geometry></collision>
        <visual name="v">
          <geometry><cylinder><radius>0.18</radius><length>0.80</length></cylinder></geometry>
          <material><ambient>0.85 0.20 0.20 1</ambient><diffuse>0.85 0.20 0.20 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- OBSTACLE 2: Amber Pillar (X=1.8m, Y=1.1m) -->
    <model name="obstacle_left_pillar">
      <static>true</static>
      <pose>1.80 1.10 0.40 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><cylinder><radius>0.16</radius><length>0.80</length></cylinder></geometry></collision>
        <visual name="v">
          <geometry><cylinder><radius>0.16</radius><length>0.80</length></cylinder></geometry>
          <material><ambient>0.95 0.60 0.10 1</ambient><diffuse>0.95 0.60 0.10 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- OBSTACLE 3: Emerald Crate (X=1.8m, Y=-1.1m) -->
    <model name="obstacle_right_crate">
      <static>true</static>
      <pose>1.80 -1.10 0.30 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry><box><size>0.40 0.40 0.60</size></box></geometry></collision>
        <visual name="v">
          <geometry><box><size>0.40 0.40 0.60</size></box></geometry>
          <material><ambient>0.15 0.70 0.35 1</ambient><diffuse>0.15 0.70 0.35 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- Overview Camera for Live Watching -->
    <model name="arena_overview_camera">
      <static>true</static>
      <pose>-2.2 0.0 3.2 0 0.85 0</pose>
      <link name="camera_link">
        <sensor name="cam" type="camera">
          <topic>/arena/camera/image_raw</topic>
          <update_rate>20.0</update_rate>
          <camera>
            <horizontal_fov>1.30</horizontal_fov>
            <image><width>1280</width><height>720</height><format>R8G8B8</format></image>
            <clip><near>0.1</near><far>15.0</far></clip>
          </camera>
          <always_on>1</always_on>
          <visualize>true</visualize>
        </sensor>
      </link>
    </model>

    <!-- Robot Model Piece 2 -->
    {robot_model_xml}

  </world>
</sdf>
"""
    out_world = "/tmp/studio_obstacles.world"
    with open(out_world, "w") as f:
        f.write(world_xml)
    print(f"✓ Generated {out_world} with Arena, Obstacles, and Piece 2 Robot!")
    return out_world

if __name__ == "__main__":
    make_obstacle_world()
