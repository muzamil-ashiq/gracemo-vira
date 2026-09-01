"""
GRACEEMO-01 — 240-Frame Motion Validation Animation
Keyframes demonstration sequence testing head, arm, greeting and neutral poses.
"""

import math
import bpy
from mathutils import Euler

def insert_keyframe_safe(obj, data_path, frame):
    """Insert keyframe if object exists."""
    if obj:
        obj.keyframe_insert(data_path=data_path, frame=frame)

def build_test_animation():
    """Build the 240-frame motion validation timeline."""
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 240

    c_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
    c_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    c_l_sh = bpy.data.objects.get("CTRL_LEFT_SHOULDER")
    c_l_el = bpy.data.objects.get("CTRL_LEFT_ELBOW")

    # Clear previous animation data on controllers
    for o in [c_yaw, c_pitch, c_r_sh, c_r_el, c_l_sh, c_l_el]:
        if o and o.animation_data:
            o.animation_data_clear()

    def key_all(frame):
        for o in [c_yaw, c_pitch, c_r_sh, c_r_el, c_l_sh, c_l_el]:
            insert_keyframe_safe(o, "rotation_euler", frame)

    # Frame 1: IDLE
    if c_yaw: c_yaw.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_pitch: c_pitch.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_r_sh: c_r_sh.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_r_el: c_r_el.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_l_sh: c_l_sh.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_l_el: c_l_el.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    key_all(1)

    # Frame 30: HEAD LOOK LEFT (Yaw = +35 deg)
    if c_yaw: c_yaw.rotation_euler = Euler((0.0, 0.0, math.radians(35)), 'XYZ')
    key_all(30)

    # Frame 60: HEAD CENTER
    if c_yaw: c_yaw.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    key_all(60)

    # Frame 90: RIGHT ARM RAISE (Forward pitch = -75 deg)
    if c_r_sh: c_r_sh.rotation_euler = Euler((math.radians(-75), 0.0, 0.0), 'XYZ')
    if c_r_el: c_r_el.rotation_euler = Euler((math.radians(-20), 0.0, 0.0), 'XYZ')
    key_all(90)

    # Frame 120: RIGHT ARM LOWER
    if c_r_sh: c_r_sh.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_r_el: c_r_el.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    key_all(120)

    # Frame 150: LEFT ARM RAISE (Forward pitch = -75 deg)
    if c_l_sh: c_l_sh.rotation_euler = Euler((math.radians(-75), 0.0, 0.0), 'XYZ')
    if c_l_el: c_l_el.rotation_euler = Euler((math.radians(-20), 0.0, 0.0), 'XYZ')
    key_all(150)

    # Frame 180: BOTH ARMS NEUTRAL
    if c_l_sh: c_l_sh.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_l_el: c_l_el.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    key_all(180)

    # Frame 210: GREETING (Right arm forward raise + wave)
    if c_r_sh: c_r_sh.rotation_euler = Euler((math.radians(-45), math.radians(-30), 0.0), 'XYZ')
    if c_r_el: c_r_el.rotation_euler = Euler((math.radians(-25), 0.0, 0.0), 'XYZ')
    if c_pitch: c_pitch.rotation_euler = Euler((math.radians(-10), 0.0, 0.0), 'XYZ')
    key_all(210)

    # Frame 240: IDLE
    if c_pitch: c_pitch.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_r_sh: c_r_sh.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    if c_r_el: c_r_el.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    key_all(240)

    # Reset playhead to frame 1
    scene.frame_set(1)
    return True
