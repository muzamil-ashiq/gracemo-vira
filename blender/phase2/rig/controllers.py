"""
GRACEEMO-01 — Dedicated Robotics Controller Empties
Creates and organizes intuitive visual controllers inside 15_DEBUG.
"""

import bpy
from mathutils import Vector, Euler

def get_or_create_empty(name, loc, collection, shape="CIRCLE", size=0.10, rot=(0, 0, 0)):
    """Idempotently fetch or create an empty controller."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = rot
        obj.empty_display_type = shape
        obj.empty_display_size = size
    else:
        # Move to collection if not present
        if collection not in obj.users_collection:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            collection.objects.link(obj)
        obj.location = loc
        obj.empty_display_type = shape
        obj.empty_display_size = size
    return obj

def setup_controllers():
    """Create all Phase 2 motion controllers inside 15_DEBUG."""
    col_debug = bpy.data.collections.get("15_DEBUG")
    if not col_debug:
        root_col = bpy.data.collections.get("GRACEEMO-01") or bpy.context.scene.collection
        col_debug = bpy.data.collections.new("15_DEBUG")
        root_col.children.link(col_debug)

    # Clean legacy Phase 1 coarse controllers if present
    for old_name in ["CTRL_HEAD", "CTRL_LEFT_ARM", "CTRL_RIGHT_ARM", "CTRL_WHEELS"]:
        old_o = bpy.data.objects.get(old_name)
        if old_o:
            bpy.data.objects.remove(old_o, do_unlink=True)

    torso = bpy.data.objects.get("torso_link")
    base = bpy.data.objects.get("base_link")

    ctrls = {}

    # -------------------------------------------------------------
    # 1. Neck & Head Controllers
    # -------------------------------------------------------------
    # CTRL_NECK_YAW: Above head, rotates Z (Left/Right)
    ctrls["CTRL_NECK_YAW"] = get_or_create_empty(
        "CTRL_NECK_YAW", (0.0, 0.0, 1.48), col_debug, "CIRCLE", 0.18
    )
    if torso and ctrls["CTRL_NECK_YAW"].parent != torso:
        ctrls["CTRL_NECK_YAW"].parent = torso

    # CTRL_NECK_PITCH: Above Yaw, single arrow / circle for up/down pitch
    ctrls["CTRL_NECK_PITCH"] = get_or_create_empty(
        "CTRL_NECK_PITCH", (0.0, 0.0, 1.56), col_debug, "SINGLE_ARROW", 0.15
    )
    if ctrls["CTRL_NECK_PITCH"].parent != ctrls["CTRL_NECK_YAW"]:
        ctrls["CTRL_NECK_PITCH"].parent = ctrls["CTRL_NECK_YAW"]

    # CTRL_NECK_ROLL: Side tilt
    ctrls["CTRL_NECK_ROLL"] = get_or_create_empty(
        "CTRL_NECK_ROLL", (0.0, 0.0, 1.64), col_debug, "ARROWS", 0.12
    )
    if ctrls["CTRL_NECK_ROLL"].parent != ctrls["CTRL_NECK_PITCH"]:
        ctrls["CTRL_NECK_ROLL"].parent = ctrls["CTRL_NECK_PITCH"]

    # -------------------------------------------------------------
    # 2. Left Arm Controllers
    # -------------------------------------------------------------
    ctrls["CTRL_LEFT_SHOULDER"] = get_or_create_empty(
        "CTRL_LEFT_SHOULDER", (-0.32, 0.0, 1.08), col_debug, "CIRCLE", 0.14
    )
    if torso and ctrls["CTRL_LEFT_SHOULDER"].parent != torso:
        ctrls["CTRL_LEFT_SHOULDER"].parent = torso

    ctrls["CTRL_LEFT_ELBOW"] = get_or_create_empty(
        "CTRL_LEFT_ELBOW", (-0.38, -0.02, 0.86), col_debug, "CIRCLE", 0.11
    )
    if ctrls["CTRL_LEFT_ELBOW"].parent != ctrls["CTRL_LEFT_SHOULDER"]:
        ctrls["CTRL_LEFT_ELBOW"].parent = ctrls["CTRL_LEFT_SHOULDER"]

    ctrls["CTRL_LEFT_WRIST"] = get_or_create_empty(
        "CTRL_LEFT_WRIST", (-0.40, -0.02, 0.66), col_debug, "CIRCLE", 0.09
    )
    if ctrls["CTRL_LEFT_WRIST"].parent != ctrls["CTRL_LEFT_ELBOW"]:
        ctrls["CTRL_LEFT_WRIST"].parent = ctrls["CTRL_LEFT_ELBOW"]

    ctrls["CTRL_LEFT_HAND"] = get_or_create_empty(
        "CTRL_LEFT_HAND", (-0.40, -0.03, 0.55), col_debug, "SPHERE", 0.08
    )
    if ctrls["CTRL_LEFT_HAND"].parent != ctrls["CTRL_LEFT_WRIST"]:
        ctrls["CTRL_LEFT_HAND"].parent = ctrls["CTRL_LEFT_WRIST"]

    # -------------------------------------------------------------
    # 3. Right Arm Controllers
    # -------------------------------------------------------------
    ctrls["CTRL_RIGHT_SHOULDER"] = get_or_create_empty(
        "CTRL_RIGHT_SHOULDER", (0.32, 0.0, 1.08), col_debug, "CIRCLE", 0.14
    )
    if torso and ctrls["CTRL_RIGHT_SHOULDER"].parent != torso:
        ctrls["CTRL_RIGHT_SHOULDER"].parent = torso

    ctrls["CTRL_RIGHT_ELBOW"] = get_or_create_empty(
        "CTRL_RIGHT_ELBOW", (0.38, -0.02, 0.86), col_debug, "CIRCLE", 0.11
    )
    if ctrls["CTRL_RIGHT_ELBOW"].parent != ctrls["CTRL_RIGHT_SHOULDER"]:
        ctrls["CTRL_RIGHT_ELBOW"].parent = ctrls["CTRL_RIGHT_SHOULDER"]

    ctrls["CTRL_RIGHT_WRIST"] = get_or_create_empty(
        "CTRL_RIGHT_WRIST", (0.40, -0.02, 0.66), col_debug, "CIRCLE", 0.09
    )
    if ctrls["CTRL_RIGHT_WRIST"].parent != ctrls["CTRL_RIGHT_ELBOW"]:
        ctrls["CTRL_RIGHT_WRIST"].parent = ctrls["CTRL_RIGHT_ELBOW"]

    ctrls["CTRL_RIGHT_HAND"] = get_or_create_empty(
        "CTRL_RIGHT_HAND", (0.40, -0.03, 0.55), col_debug, "SPHERE", 0.08
    )
    if ctrls["CTRL_RIGHT_HAND"].parent != ctrls["CTRL_RIGHT_WRIST"]:
        ctrls["CTRL_RIGHT_HAND"].parent = ctrls["CTRL_RIGHT_WRIST"]

    # -------------------------------------------------------------
    # 4. Wheel Controllers (External to tire for easy selection)
    # -------------------------------------------------------------
    wheel_ctrl_configs = [
        ("CTRL_LEFT_WHEEL", (0.0, -0.28, 0.12)),
        ("CTRL_RIGHT_WHEEL", (0.0, 0.28, 0.12)),
        ("CTRL_LEFT_FRONT_WHEEL", (0.14, -0.28, 0.12)),
        ("CTRL_RIGHT_FRONT_WHEEL", (0.14, 0.28, 0.12)),
    ]
    for w_name, w_loc in wheel_ctrl_configs:
        ctrls[w_name] = get_or_create_empty(w_name, w_loc, col_debug, "CIRCLE", 0.13)
        if base and ctrls[w_name].parent != base:
            ctrls[w_name].parent = base

    return ctrls
