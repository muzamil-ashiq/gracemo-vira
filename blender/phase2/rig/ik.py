"""
GRACEEMO-01 — Rigid Robot Inverse Kinematics (IK)
Implements natural two-bone rigid arm IK with elbow pole vector control.
"""

import math
import bpy
from mathutils import Vector

def setup_ik_system():
    """Setup IK targets, pole empties, and rigid IK solver armature."""
    col_debug = bpy.data.collections.get("15_DEBUG")
    col_joints = bpy.data.collections.get("13_JOINTS")
    torso = bpy.data.objects.get("torso_link")

    # 1. Create IK Controller Empties
    ik_ctrls = {}
    configs = [
        ("CTRL_LEFT_HAND_IK", (-0.32, -0.03, 0.55), "CUBE", 0.08),
        ("CTRL_LEFT_ELBOW_POLE", (-0.30, 0.35, 0.86), "SPHERE", 0.05),
        ("CTRL_RIGHT_HAND_IK", (0.32, -0.03, 0.55), "CUBE", 0.08),
        ("CTRL_RIGHT_ELBOW_POLE", (0.30, 0.35, 0.86), "SPHERE", 0.05),
    ]
    for name, loc, shape, sz in configs:
        o = bpy.data.objects.get(name)
        if not o:
            o = bpy.data.objects.new(name, None)
            col_debug.objects.link(o)
        o.location = loc
        o.empty_display_type = shape
        o.empty_display_size = sz
        if torso and o.parent is None:
            o.parent = torso
        ik_ctrls[name] = o

    # 2. Rigid IK Armature
    arm_data = bpy.data.armatures.get("GRACEEMO_Rigid_Arm_IK")
    arm_obj = bpy.data.objects.get("GRACEEMO_Rigid_Arm_IK")
    if not arm_obj:
        if not arm_data:
            arm_data = bpy.data.armatures.new("GRACEEMO_Rigid_Arm_IK")
        arm_obj = bpy.data.objects.new("GRACEEMO_Rigid_Arm_IK", arm_data)
        col_joints.objects.link(arm_obj)
        if torso:
            arm_obj.parent = torso
        arm_obj.show_in_front = True

    # Build / update bones in edit mode
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_data.edit_bones

    sides = [
        ("left", -1, (-0.22, 0.0, 1.08), (-0.30, -0.02, 0.86), (-0.32, -0.02, 0.66)),
        ("right", 1, (0.22, 0.0, 1.08), (0.30, -0.02, 0.86), (0.32, -0.02, 0.66))
    ]

    for prefix, sign, sh_loc, el_loc, wr_loc in sides:
        # Upper Arm Bone
        b_up = edit_bones.get(f"{prefix}_upper_arm_ik")
        if not b_up:
            b_up = edit_bones.new(f"{prefix}_upper_arm_ik")
        b_up.head = Vector(sh_loc)
        b_up.tail = Vector(el_loc)

        # Forearm Bone
        b_fore = edit_bones.get(f"{prefix}_forearm_ik")
        if not b_fore:
            b_fore = edit_bones.new(f"{prefix}_forearm_ik")
        b_fore.head = Vector(el_loc)
        b_fore.tail = Vector(wr_loc)
        b_fore.parent = b_up
        b_fore.use_connect = True

    bpy.ops.object.mode_set(mode='POSE')

    # Add IK Constraints in Pose Mode
    for prefix in ["left", "right"]:
        p_fore = arm_obj.pose.bones.get(f"{prefix}_forearm_ik")
        if p_fore:
            c_ik = p_fore.constraints.get("IK")
            if not c_ik:
                c_ik = p_fore.constraints.new('IK')
                c_ik.name = "IK"
            c_ik.target = ik_ctrls[f"CTRL_{prefix.upper()}_HAND_IK"]
            c_ik.pole_target = ik_ctrls[f"CTRL_{prefix.upper()}_ELBOW_POLE"]
            c_ik.chain_count = 2
            c_ik.pole_angle = 0.0 if prefix == "left" else math.pi

    bpy.ops.object.mode_set(mode='OBJECT')

    # Bind link empties to copy bone rotation (with influence slider support)
    for prefix in ["left", "right"]:
        l_up = bpy.data.objects.get(f"{prefix}_upper_arm_link")
        if l_up:
            c = l_up.constraints.get("IK_Follow_Upper")
            if not c:
                c = l_up.constraints.new('COPY_ROTATION')
                c.name = "IK_Follow_Upper"
            c.target = arm_obj
            c.subtarget = f"{prefix}_upper_arm_ik"
            c.influence = 0.0  # Default 0.0 allows direct FK; set 1.0 for active IK

        l_el = bpy.data.objects.get(f"{prefix}_elbow_link")
        if l_el:
            c = l_el.constraints.get("IK_Follow_Fore")
            if not c:
                c = l_el.constraints.new('COPY_ROTATION')
                c.name = "IK_Follow_Fore"
            c.target = arm_obj
            c.subtarget = f"{prefix}_forearm_ik"
            c.influence = 0.0

    return ik_ctrls

def set_ik_influence(prefix, influence):
    """Set IK influence between 0.0 (FK mode) and 1.0 (IK mode)."""
    for link_name, c_name in [
        (f"{prefix}_upper_arm_link", "IK_Follow_Upper"),
        (f"{prefix}_elbow_link", "IK_Follow_Fore"),
    ]:
        obj = bpy.data.objects.get(link_name)
        if obj:
            c = obj.constraints.get(c_name)
            if c:
                c.influence = influence
