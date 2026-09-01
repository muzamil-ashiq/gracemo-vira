"""
GRACEEMO-01 — Simplified Collision Envelopes
Packages physics/simulation collision shapes inside 14_COLLISION.
"""

import bpy
from .base_power_compute import create_box_envelope, get_or_create_material
from .mobility_wheels import create_cylinder_envelope

def setup_collision_envelopes():
    """Build simplified collision proxy meshes."""
    col_collision = bpy.data.collections.get("14_COLLISION")

    mat_col = get_or_create_material("MAT_ENG_CollisionProxy", (1.0, 0.4, 0.0, 0.2), 0.0, 0.5)

    base_link = bpy.data.objects.get("base_link")
    torso_link = bpy.data.objects.get("torso_link")
    head_link = bpy.data.objects.get("head_link")
    lidar_link = bpy.data.objects.get("lidar_link")
    camera_link = bpy.data.objects.get("camera_link")

    created = []

    # 1. Base Collision Box
    if base_link:
        o = create_box_envelope("COL_BASE_PROXY", (0, 0, 0.12), (0.48, 0.40, 0.28), col_collision, mat_col, base_link)
        o.display_type = 'BOUNDS'
        created.append(o)

    # 2. Torso Collision Box
    if torso_link:
        o = create_box_envelope("COL_TORSO_PROXY", (0, 0, 0.10), (0.36, 0.26, 0.46), col_collision, mat_col, torso_link)
        o.display_type = 'BOUNDS'
        created.append(o)

    # 3. Head Collision Box
    if head_link:
        o = create_box_envelope("COL_HEAD_PROXY", (0, -0.02, 0.06), (0.24, 0.22, 0.24), col_collision, mat_col, head_link)
        o.display_type = 'BOUNDS'
        created.append(o)

    # 4. Arm & Hand Collision Capsules
    for side in ["left", "right"]:
        sh = bpy.data.objects.get(f"{side}_shoulder_link")
        el = bpy.data.objects.get(f"{side}_elbow_link")
        hd = bpy.data.objects.get(f"{side}_hand_link")

        if sh:
            o = create_cylinder_envelope(f"COL_ARM_{side.upper()}_UPPER", (0, 0, -0.08), 0.055, 0.22, col_collision, parent_obj=sh)
            o.display_type = 'BOUNDS'
            created.append(o)
        if el:
            o = create_cylinder_envelope(f"COL_ARM_{side.upper()}_FORE", (0, 0, -0.07), 0.048, 0.20, col_collision, parent_obj=el)
            o.display_type = 'BOUNDS'
            created.append(o)
        if hd:
            o = create_box_envelope(f"COL_HAND_{side.upper()}", (0, 0, -0.03), (0.075, 0.055, 0.11), col_collision, mat_col, hd)
            o.display_type = 'BOUNDS'
            created.append(o)

    # 5. Drive Wheels Collision Cylinders
    for w_name, code in [("left_wheel", "RL"), ("right_wheel", "RR"), ("left_front_wheel", "FL"), ("right_front_wheel", "FR")]:
        wl = bpy.data.objects.get(w_name)
        if wl:
            o = create_cylinder_envelope(f"COL_WHEEL_{code}", (0, 0, 0), radius=0.12, depth=0.08, collection=col_collision, rot=(0, 1.5708, 0), parent_obj=wl)
            o.display_type = 'BOUNDS'
            created.append(o)

    # 6. Sensor Housings Collision
    if lidar_link:
        o = create_cylinder_envelope("COL_LIDAR_HOUSING", (0, 0, 0), radius=0.06, depth=0.08, collection=col_collision, parent_obj=lidar_link)
        o.display_type = 'BOUNDS'
        created.append(o)

    if camera_link:
        o = create_box_envelope("COL_CAMERA_HOUSING", (0, 0, 0), (0.11, 0.04, 0.04), col_collision, mat_col, camera_link)
        o.display_type = 'BOUNDS'
        created.append(o)

    return created
