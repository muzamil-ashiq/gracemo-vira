#!/usr/bin/env python3
"""
Generates a Rich Multi-Obstacle Arena for continuous navigation & avoidance testing.
Contains 14 varied obstacles: columns, crates, barriers, and chicane corridors.
"""
import os
import subprocess

def make_rich_obstacle_world():
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

    pose_tag = "    <pose>0 0 0 0 0 0</pose>\n"
    tag_end = robot_model_xml.find(">") + 1
    robot_model_xml = robot_model_xml[:tag_end] + "\n" + pose_tag + robot_model_xml[tag_end:]

    # Define list of 14 diverse obstacles
    # (name, type, x, y, z, r, l, sx, sy, sz, color_ambient, color_diffuse)
    obstacles = [
        # Columns
        ("col_crimson_1", "cylinder",  1.5,  0.0, 0.4, 0.22, 0.8, None, None, None, "0.85 0.2 0.2 1"),
        ("col_amber_2",   "cylinder",  1.2,  1.6, 0.4, 0.18, 0.8, None, None, None, "0.95 0.6 0.1 1"),
        ("col_teal_3",    "cylinder",  1.2, -1.6, 0.4, 0.18, 0.8, None, None, None, "0.1 0.7 0.8 1"),
        ("col_purple_4",  "cylinder", -1.4,  1.4, 0.4, 0.20, 0.8, None, None, None, "0.6 0.2 0.8 1"),
        ("col_blue_5",    "cylinder", -1.4, -1.4, 0.4, 0.20, 0.8, None, None, None, "0.2 0.3 0.9 1"),
        ("col_emerald_6", "cylinder",  3.0,  0.8, 0.4, 0.25, 0.8, None, None, None, "0.1 0.8 0.3 1"),
        ("col_gold_7",    "cylinder", -2.8,  0.0, 0.4, 0.22, 0.8, None, None, None, "0.9 0.75 0.1 1"),

        # Crates and Boxes
        ("crate_wood_1",  "box",  2.5, -1.5, 0.3, None, None, 0.5, 0.5, 0.6, "0.7 0.5 0.3 1"),
        ("crate_steel_2", "box", -2.2,  2.2, 0.3, None, None, 0.6, 0.4, 0.6, "0.4 0.45 0.5 1"),
        ("crate_brick_3", "box", -2.2, -2.2, 0.3, None, None, 0.5, 0.6, 0.6, "0.65 0.3 0.2 1"),
        ("crate_cyan_4",  "box",  0.0,  2.8, 0.3, None, None, 0.4, 0.8, 0.6, "0.1 0.6 0.7 1"),
        ("crate_rose_5",  "box",  0.0, -2.8, 0.3, None, None, 0.4, 0.8, 0.6, "0.8 0.3 0.5 1"),

        # Partition Barrier Chicane
        ("barrier_left",  "box",  2.8,  2.2, 0.35, None, None, 1.2, 0.2, 0.7, "0.3 0.35 0.4 1"),
        ("barrier_right", "box", -0.5, -1.0, 0.35, None, None, 0.2, 1.0, 0.7, "0.3 0.35 0.4 1"),
    ]

    obs_xml = ""
    for name, otype, x, y, z, r, l, sx, sy, sz, col in obstacles:
        if otype == "cylinder":
            geom = f"<cylinder><radius>{r}</radius><length>{l}</length></cylinder>"
        else:
            geom = f"<box><size>{sx} {sy} {sz}</size></box>"

        obs_xml += f"""
    <model name="{name}">
      <static>true</static>
      <pose>{x} {y} {z} 0 0 0</pose>
      <link name="l">
        <collision name="c"><geometry>{geom}</geometry></collision>
        <visual name="v">
          <geometry>{geom}</geometry>
          <material><ambient>{col}</ambient><diffuse>{col}</diffuse></material>
        </visual>
      </link>
    </model>"""

    world_xml = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="rich_obstacle_arena">
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

    <!-- Studio Overhead Sun & Fill Lighting -->
    <light type="directional" name="sun_key">
      <cast_shadows>true</cast_shadows>
      <pose>4 -4 6 0 0 0</pose>
      <diffuse>0.9 0.9 0.95 1</diffuse>
      <specular>0.3 0.3 0.3 1</specular>
      <direction>-0.5 0.5 -1</direction>
    </light>
    <light type="directional" name="sun_fill">
      <cast_shadows>false</cast_shadows>
      <pose>-4 4 5 0 0 0</pose>
      <diffuse>0.45 0.45 0.5 1</diffuse>
      <direction>0.5 -0.5 -0.8</direction>
    </light>

    <!-- Arena Floor (8m x 8m) -->
    <model name="arena_floor">
      <static>true</static>
      <link name="floor_link">
        <collision name="c">
          <geometry><plane><normal>0 0 1</normal><size>16 16</size></plane></geometry>
        </collision>
        <visual name="v">
          <geometry><plane><normal>0 0 1</normal><size>16 16</size></plane></geometry>
          <material>
            <ambient>0.82 0.84 0.87 1</ambient>
            <diffuse>0.82 0.84 0.87 1</diffuse>
            <specular>0.1 0.1 0.1 1</specular>
          </material>
        </visual>
      </link>
    </model>

    <!-- Outer Perimeter Walls (8m x 8m) -->
    <model name="wall_n"><static>true</static><pose>0 4.0 0.4 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>8.2 0.2 0.8</size></box></geometry></collision><visual name="v"><geometry><box><size>8.2 0.2 0.8</size></box></geometry><material><ambient>0.28 0.32 0.38 1</ambient><diffuse>0.28 0.32 0.38 1</diffuse></material></visual></link></model>
    <model name="wall_s"><static>true</static><pose>0 -4.0 0.4 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>8.2 0.2 0.8</size></box></geometry></collision><visual name="v"><geometry><box><size>8.2 0.2 0.8</size></box></geometry><material><ambient>0.28 0.32 0.38 1</ambient><diffuse>0.28 0.32 0.38 1</diffuse></material></visual></link></model>
    <model name="wall_e"><static>true</static><pose>4.0 0 0.4 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.2 8.0 0.8</size></box></geometry></collision><visual name="v"><geometry><box><size>0.2 8.0 0.8</size></box></geometry><material><ambient>0.28 0.32 0.38 1</ambient><diffuse>0.28 0.32 0.38 1</diffuse></material></visual></link></model>
    <model name="wall_w"><static>true</static><pose>-4.0 0 0.4 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.2 8.0 0.8</size></box></geometry></collision><visual name="v"><geometry><box><size>0.2 8.0 0.8</size></box></geometry><material><ambient>0.28 0.32 0.38 1</ambient><diffuse>0.28 0.32 0.38 1</diffuse></material></visual></link></model>

    <!-- 14 Varied Obstacles -->
    {obs_xml}

    <!-- Overhead Arena Overview Camera -->
    <model name="arena_overview_camera">
      <static>true</static>
      <pose>0.0 -4.5 5.5 0 0.90 1.5708</pose>
      <link name="camera_link">
        <sensor name="cam" type="camera">
          <topic>/arena/camera/image_raw</topic>
          <update_rate>20.0</update_rate>
          <camera>
            <horizontal_fov>1.40</horizontal_fov>
            <image><width>1280</width><height>720</height><format>R8G8B8</format></image>
            <clip><near>0.1</near><far>20.0</far></clip>
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
    print(f"✓ Generated 14-obstacle arena in {out_world}")
    return out_world

if __name__ == "__main__":
    make_rich_obstacle_world()
