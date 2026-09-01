"""
GRACEEMO-01 — Predefined Poses, Hand Actions, Mobility & Reset System
Non-destructive demonstration poses and joint manipulations.
"""

import math
import bpy
from mathutils import Euler

def reset_robot_pose():
    """Reset all controllers, links, hands, fingers, and wheels to default neutral."""
    # Reset all controller empties
    ctrl_names = [
        "CTRL_NECK_YAW", "CTRL_NECK_PITCH", "CTRL_NECK_ROLL",
        "CTRL_LEFT_SHOULDER", "CTRL_LEFT_ELBOW", "CTRL_LEFT_WRIST", "CTRL_LEFT_HAND",
        "CTRL_RIGHT_SHOULDER", "CTRL_RIGHT_ELBOW", "CTRL_RIGHT_WRIST", "CTRL_RIGHT_HAND",
        "CTRL_LEFT_WHEEL", "CTRL_RIGHT_WHEEL", "CTRL_LEFT_FRONT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL",
        "CTRL_LEFT_HAND_IK", "CTRL_RIGHT_HAND_IK"
    ]
    for name in ctrl_names:
        o = bpy.data.objects.get(name)
        if o:
            o.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')

    # Reset finger knuckle rotations
    for side in ["LEFT", "RIGHT"]:
        for i in range(1, 5):
            kn = bpy.data.objects.get(f"HAND_{side}_Knuckle_{i}")
            if kn:
                kn.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
        th = bpy.data.objects.get(f"HAND_{side}_Thumb")
        if th:
            th.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')

    # Reset link empties
    link_names = [
        "neck_yaw_link", "head_link",
        "left_shoulder_link", "left_elbow_link", "left_wrist_link", "left_hand_link",
        "right_shoulder_link", "right_elbow_link", "right_wrist_link", "right_hand_link",
        "left_wheel", "right_wheel", "left_front_wheel", "right_front_wheel"
    ]
    for name in link_names:
        o = bpy.data.objects.get(name)
        if o:
            o.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')

    # Reset IK influence to 0.0 (FK neutral)
    for prefix in ["left", "right"]:
        for l_name, c_name in [(f"{prefix}_upper_arm_link", "IK_Follow_Upper"), (f"{prefix}_elbow_link", "IK_Follow_Fore")]:
            obj = bpy.data.objects.get(l_name)
            if obj:
                c = obj.constraints.get(c_name)
                if c:
                    c.influence = 0.0

    bpy.context.view_layer.update()
    return True

# -------------------------------------------------------------
# Hand Articulation Controls (Open, Close, Point, Grab)
# -------------------------------------------------------------
def set_hand_state(side, state="OPEN"):
    """Manipulate finger and thumb joints for OPEN, CLOSE, POINT, GRAB."""
    side = side.upper()
    curl_angle = 0.0
    thumb_angle = 0.0
    point_mode = False

    if state == "OPEN":
        curl_angle = 0.0
        thumb_angle = 0.0
    elif state == "CLOSE":
        curl_angle = 1.35
        thumb_angle = 1.05
    elif state == "GRAB":
        curl_angle = 1.15
        thumb_angle = 0.95
    elif state == "POINT":
        point_mode = True
        curl_angle = 1.35
        thumb_angle = 0.90

    for i in range(1, 5):
        kn = bpy.data.objects.get(f"HAND_{side}_Knuckle_{i}")
        if kn:
            # If pointing, keep index finger (Finger 1) extended
            if point_mode and i == 1:
                kn.rotation_euler.x = 0.0
            else:
                kn.rotation_euler.x = curl_angle

    th = bpy.data.objects.get(f"HAND_{side}_Thumb")
    if th:
        th.rotation_euler.x = thumb_angle

    bpy.context.view_layer.update()

def hand_left_open(): set_hand_state("LEFT", "OPEN")
def hand_left_close(): set_hand_state("LEFT", "CLOSE")
def hand_left_point(): set_hand_state("LEFT", "POINT")
def hand_left_grab(): set_hand_state("LEFT", "GRAB")

def hand_right_open(): set_hand_state("RIGHT", "OPEN")
def hand_right_close(): set_hand_state("RIGHT", "CLOSE")
def hand_right_point(): set_hand_state("RIGHT", "POINT")
def hand_right_grab(): set_hand_state("RIGHT", "GRAB")

# -------------------------------------------------------------
# Predefined Non-Destructive Poses
# -------------------------------------------------------------
def pose_idle():
    """Neutral standing posture."""
    reset_robot_pose()

def pose_greeting():
    """Right arm raised in greeting wave (~40 deg pitch, ~30 deg roll)."""
    reset_robot_pose()
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    if c_r_sh:
        c_r_sh.rotation_euler = Euler((math.radians(-42), math.radians(-30), 0.0), 'XYZ')
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    if c_r_el:
        c_r_el.rotation_euler = Euler((math.radians(-25), 0.0, 0.0), 'XYZ')
    c_r_wr = bpy.data.objects.get("CTRL_RIGHT_WRIST")
    if c_r_wr:
        c_r_wr.rotation_euler = Euler((math.radians(-15), 0.0, math.radians(20)), 'XYZ')
    c_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
    if c_pitch:
        c_pitch.rotation_euler = Euler((math.radians(-8), 0.0, 0.0), 'XYZ')
    hand_right_open()
    bpy.context.view_layer.update()

def pose_namaste():
    """Both arms brought forward/center in respectful gesture."""
    reset_robot_pose()
    c_l_sh = bpy.data.objects.get("CTRL_LEFT_SHOULDER")
    if c_l_sh:
        c_l_sh.rotation_euler = Euler((math.radians(-35), math.radians(20), math.radians(-15)), 'XYZ')
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    if c_r_sh:
        c_r_sh.rotation_euler = Euler((math.radians(-35), math.radians(-20), math.radians(15)), 'XYZ')
    c_l_el = bpy.data.objects.get("CTRL_LEFT_ELBOW")
    if c_l_el:
        c_l_el.rotation_euler = Euler((math.radians(-75), 0.0, 0.0), 'XYZ')
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    if c_r_el:
        c_r_el.rotation_euler = Euler((math.radians(-75), 0.0, 0.0), 'XYZ')
    c_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
    if c_pitch:
        c_pitch.rotation_euler = Euler((math.radians(-12), 0.0, 0.0), 'XYZ')
    hand_left_open()
    hand_right_open()
    bpy.context.view_layer.update()

def pose_point():
    """Right arm extended forward pointing toward target direction."""
    reset_robot_pose()
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    if c_r_sh:
        c_r_sh.rotation_euler = Euler((math.radians(-85), math.radians(-10), 0.0), 'XYZ')
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    if c_r_el:
        c_r_el.rotation_euler = Euler((math.radians(-10), 0.0, 0.0), 'XYZ')
    c_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
    if c_yaw:
        c_yaw.rotation_euler = Euler((0.0, 0.0, math.radians(15)), 'XYZ')
    hand_right_point()
    bpy.context.view_layer.update()

def pose_guide():
    """Robot points toward a destination with guiding arm angle."""
    reset_robot_pose()
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    if c_r_sh:
        c_r_sh.rotation_euler = Euler((math.radians(-65), math.radians(-35), 0.0), 'XYZ')
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    if c_r_el:
        c_r_el.rotation_euler = Euler((math.radians(-20), 0.0, 0.0), 'XYZ')
    c_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
    if c_yaw:
        c_yaw.rotation_euler = Euler((0.0, 0.0, math.radians(25)), 'XYZ')
    hand_right_open()
    bpy.context.view_layer.update()

def pose_assist():
    """Both arms forward in supportive/holding posture."""
    reset_robot_pose()
    for side, sign in [("LEFT", 1), ("RIGHT", -1)]:
        c_sh = bpy.data.objects.get(f"CTRL_{side}_SHOULDER")
        if c_sh:
            c_sh.rotation_euler = Euler((math.radians(-45), sign * math.radians(10), 0.0), 'XYZ')
        c_el = bpy.data.objects.get(f"CTRL_{side}_ELBOW")
        if c_el:
            c_el.rotation_euler = Euler((math.radians(-40), 0.0, 0.0), 'XYZ')
        c_wr = bpy.data.objects.get(f"CTRL_{side}_WRIST")
        if c_wr:
            c_wr.rotation_euler = Euler((math.radians(15), 0.0, 0.0), 'XYZ')
    hand_left_open()
    hand_right_open()
    bpy.context.view_layer.update()

# -------------------------------------------------------------
# Wheel Mobility Test Functions
# -------------------------------------------------------------
def wheels_forward(dist=0.5):
    """Rotate wheels forward corresponding to linear distance."""
    # delta_theta = dist / R (R = 0.12m)
    rot = dist / 0.12
    for w in ["CTRL_LEFT_WHEEL", "CTRL_RIGHT_WHEEL", "CTRL_LEFT_FRONT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL"]:
        o = bpy.data.objects.get(w)
        if o:
            o.rotation_euler.x += rot
    bpy.context.view_layer.update()

def wheels_reverse(dist=0.5):
    wheels_forward(-dist)

def wheels_rotate(angle_deg=30.0):
    """Differential turn in place."""
    ang_rad = math.radians(angle_deg)
    # L = 0.42m track width, R = 0.12m
    wheel_rot = (ang_rad * (0.42 / 2.0)) / 0.12
    for w in ["CTRL_LEFT_WHEEL", "CTRL_LEFT_FRONT_WHEEL"]:
        o = bpy.data.objects.get(w)
        if o: o.rotation_euler.x -= wheel_rot
    for w in ["CTRL_RIGHT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL"]:
        o = bpy.data.objects.get(w)
        if o: o.rotation_euler.x += wheel_rot
    bpy.context.view_layer.update()

def wheels_stop():
    for w in ["CTRL_LEFT_WHEEL", "CTRL_RIGHT_WHEEL", "CTRL_LEFT_FRONT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL"]:
        o = bpy.data.objects.get(w)
        if o: o.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
    bpy.context.view_layer.update()
