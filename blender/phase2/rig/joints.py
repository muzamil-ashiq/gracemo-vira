"""
GRACEEMO-01 — Joint Constraint & Driver Bindings
Binds controller empties to the underlying robot link frames.
"""

import bpy
from .limits import JOINT_LIMITS, apply_limit_rotation

def add_or_update_copy_rotation(target_obj, subtarget_name, name="Copy_Rotation", use_x=True, use_y=True, use_z=True, space='LOCAL'):
    """Cleanly bind target_obj to follow rotation of subtarget_name."""
    subtarget = bpy.data.objects.get(subtarget_name)
    if not target_obj or not subtarget:
        return None
    c = target_obj.constraints.get(name)
    if not c:
        c = target_obj.constraints.new('COPY_ROTATION')
        c.name = name
    c.target = subtarget
    c.use_x = use_x
    c.use_y = use_y
    c.use_z = use_z
    c.target_space = space
    c.owner_space = space
    return c

def bind_joints_to_controllers():
    """Establish deterministic constraint bindings and limits."""
    # -------------------------------------------------------------
    # 1. Head & Neck Bindings
    # -------------------------------------------------------------
    neck_yaw = bpy.data.objects.get("neck_yaw_link")
    ctrl_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
    if neck_yaw and ctrl_yaw:
        add_or_update_copy_rotation(neck_yaw, "CTRL_NECK_YAW", "Follow_Yaw", use_x=False, use_y=False, use_z=True)
        apply_limit_rotation(ctrl_yaw, min_z=JOINT_LIMITS["NECK_YAW_MIN"], max_z=JOINT_LIMITS["NECK_YAW_MAX"])

    head = bpy.data.objects.get("head_link")
    ctrl_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
    ctrl_roll = bpy.data.objects.get("CTRL_NECK_ROLL")
    if head and ctrl_pitch:
        add_or_update_copy_rotation(head, "CTRL_NECK_PITCH", "Follow_Pitch", use_x=True, use_y=False, use_z=False)
        apply_limit_rotation(ctrl_pitch, min_x=JOINT_LIMITS["NECK_PITCH_MIN"], max_x=JOINT_LIMITS["NECK_PITCH_MAX"])
    if head and ctrl_roll:
        add_or_update_copy_rotation(head, "CTRL_NECK_ROLL", "Follow_Roll", use_x=False, use_y=True, use_z=False)
        apply_limit_rotation(ctrl_roll, min_y=JOINT_LIMITS["NECK_ROLL_MIN"], max_y=JOINT_LIMITS["NECK_ROLL_MAX"])

    # -------------------------------------------------------------
    # 2. Left Arm Bindings
    # -------------------------------------------------------------
    l_sh = bpy.data.objects.get("left_shoulder_link")
    c_l_sh = bpy.data.objects.get("CTRL_LEFT_SHOULDER")
    if l_sh and c_l_sh:
        add_or_update_copy_rotation(l_sh, "CTRL_LEFT_SHOULDER", "Follow_L_Shoulder")
        apply_limit_rotation(
            c_l_sh,
            min_x=JOINT_LIMITS["LEFT_SHOULDER_PITCH_MIN"], max_x=JOINT_LIMITS["LEFT_SHOULDER_PITCH_MAX"],
            min_y=JOINT_LIMITS["LEFT_SHOULDER_ROLL_MIN"], max_y=JOINT_LIMITS["LEFT_SHOULDER_ROLL_MAX"]
        )

    l_el = bpy.data.objects.get("left_elbow_link")
    c_l_el = bpy.data.objects.get("CTRL_LEFT_ELBOW")
    if l_el and c_l_el:
        add_or_update_copy_rotation(l_el, "CTRL_LEFT_ELBOW", "Follow_L_Elbow")
        apply_limit_rotation(c_l_el, min_x=JOINT_LIMITS["LEFT_ELBOW_MIN"], max_x=JOINT_LIMITS["LEFT_ELBOW_MAX"])

    l_wr = bpy.data.objects.get("left_wrist_link")
    c_l_wr = bpy.data.objects.get("CTRL_LEFT_WRIST")
    if l_wr and c_l_wr:
        add_or_update_copy_rotation(l_wr, "CTRL_LEFT_WRIST", "Follow_L_Wrist")
        apply_limit_rotation(c_l_wr, min_x=JOINT_LIMITS["LEFT_WRIST_MIN"], max_x=JOINT_LIMITS["LEFT_WRIST_MAX"])

    l_hd = bpy.data.objects.get("left_hand_link")
    c_l_hd = bpy.data.objects.get("CTRL_LEFT_HAND")
    if l_hd and c_l_hd:
        add_or_update_copy_rotation(l_hd, "CTRL_LEFT_HAND", "Follow_L_Hand")

    # -------------------------------------------------------------
    # 3. Right Arm Bindings
    # -------------------------------------------------------------
    r_sh = bpy.data.objects.get("right_shoulder_link")
    c_r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    if r_sh and c_r_sh:
        add_or_update_copy_rotation(r_sh, "CTRL_RIGHT_SHOULDER", "Follow_R_Shoulder")
        apply_limit_rotation(
            c_r_sh,
            min_x=JOINT_LIMITS["RIGHT_SHOULDER_PITCH_MIN"], max_x=JOINT_LIMITS["RIGHT_SHOULDER_PITCH_MAX"],
            min_y=JOINT_LIMITS["RIGHT_SHOULDER_ROLL_MIN"], max_y=JOINT_LIMITS["RIGHT_SHOULDER_ROLL_MAX"]
        )

    r_el = bpy.data.objects.get("right_elbow_link")
    c_r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    if r_el and c_r_el:
        add_or_update_copy_rotation(r_el, "CTRL_RIGHT_ELBOW", "Follow_R_Elbow")
        apply_limit_rotation(c_r_el, min_x=JOINT_LIMITS["RIGHT_ELBOW_MIN"], max_x=JOINT_LIMITS["RIGHT_ELBOW_MAX"])

    r_wr = bpy.data.objects.get("right_wrist_link")
    c_r_wr = bpy.data.objects.get("CTRL_RIGHT_WRIST")
    if r_wr and c_r_wr:
        add_or_update_copy_rotation(r_wr, "CTRL_RIGHT_WRIST", "Follow_R_Wrist")
        apply_limit_rotation(c_r_wr, min_x=JOINT_LIMITS["RIGHT_WRIST_MIN"], max_x=JOINT_LIMITS["RIGHT_WRIST_MAX"])

    r_hd = bpy.data.objects.get("right_hand_link")
    c_r_hd = bpy.data.objects.get("CTRL_RIGHT_HAND")
    if r_hd and c_r_hd:
        add_or_update_copy_rotation(r_hd, "CTRL_RIGHT_HAND", "Follow_R_Hand")

    # -------------------------------------------------------------
    # 4. Wheel Drive Axle Bindings
    # -------------------------------------------------------------
    for w_link, ctrl_name in [
        ("left_wheel", "CTRL_LEFT_WHEEL"),
        ("right_wheel", "CTRL_RIGHT_WHEEL"),
        ("left_front_wheel", "CTRL_LEFT_FRONT_WHEEL"),
        ("right_front_wheel", "CTRL_RIGHT_FRONT_WHEEL"),
    ]:
        obj_link = bpy.data.objects.get(w_link)
        if obj_link:
            add_or_update_copy_rotation(obj_link, ctrl_name, "Follow_Wheel_Axle")

    return True
