"""
GRACEEMO-01 — Arm Mechanical Actuation & Bearing Packaging
Creates realistic actuator envelopes, bearings, and mounting interfaces.
Maintains Phase 2 FK/IK kinematic hierarchy.
"""

import bpy
from mathutils import Vector, Euler
try:
    from phase3.manifest.hardware_manifest import get_component
except ImportError:
    from manifest.hardware_manifest import get_component
from .base_power_compute import create_box_envelope, get_or_create_material
from .mobility_wheels import create_cylinder_envelope

def setup_arm_mechanical_packaging(manifest):
    """Package internal actuators and bearings for both arms."""
    col_l_arm = bpy.data.collections.get("07_LEFT_ARM") or bpy.data.collections.get("08_LEFT_ARM") or bpy.context.scene.collection
    col_r_arm = bpy.data.collections.get("08_RIGHT_ARM") or bpy.data.collections.get("09_RIGHT_ARM") or bpy.context.scene.collection

    mat_actuator = get_or_create_material("MAT_ENG_HarmonicActuator", (0.12, 0.13, 0.15, 1.0), 0.9, 0.2)
    mat_bearing = get_or_create_material("MAT_ENG_BearingSteel", (0.80, 0.82, 0.85, 1.0), 0.95, 0.15)
    mat_flange = get_or_create_material("MAT_ENG_MountingFlange", (0.65, 0.67, 0.70, 1.0), 0.85, 0.3)

    c_sh_act = get_component("ACT-02", manifest)
    c_el_act = get_component("ACT-03", manifest)
    c_wr_act = get_component("ACT-04", manifest)

    dim_sh = (c_sh_act["length"], c_sh_act["width"], c_sh_act["height"]) if c_sh_act else (0.085, 0.085, 0.065)
    dim_el = (c_el_act["length"], c_el_act["width"], c_el_act["height"]) if c_el_act else (0.065, 0.055, 0.045)
    dim_wr = (c_wr_act["length"], c_wr_act["width"], c_wr_act["height"]) if c_wr_act else (0.048, 0.038, 0.032)

    created = []

    for side, sign in [("LEFT", -1), ("RIGHT", 1)]:
        prefix = side.lower()
        col = col_l_arm if side == "LEFT" else col_r_arm

        sh_link = bpy.data.objects.get(f"{prefix}_shoulder_link")
        el_link = bpy.data.objects.get(f"{prefix}_elbow_link")
        wr_link = bpy.data.objects.get(f"{prefix}_wrist_link")

        # 1. Shoulder Actuator Envelope & Bearing (parented to shoulder link)
        if sh_link:
            o_sh_act = create_box_envelope(
                f"ACTUATOR_SHOULDER_ENVELOPE_{side}", (0, 0, 0), dim_sh,
                col, mat_actuator, sh_link, c_sh_act
            )
            o_sh_brg = create_cylinder_envelope(
                f"BEARING_SHOULDER_{side}", (sign * 0.040, 0, 0),
                radius=0.045, depth=0.015, collection=col,
                rot=(0, 1.5708, 0), mat=mat_bearing, parent_obj=sh_link
            )
            created.extend([o_sh_act, o_sh_brg])

        # 2. Elbow Actuator Envelope & Bearing (parented to elbow link)
        if el_link:
            o_el_act = create_box_envelope(
                f"ACTUATOR_ELBOW_ENVELOPE_{side}", (0, 0, 0), dim_el,
                col, mat_actuator, el_link, c_el_act
            )
            o_el_brg = create_cylinder_envelope(
                f"BEARING_ELBOW_{side}", (sign * 0.030, 0, 0),
                radius=0.032, depth=0.012, collection=col,
                rot=(0, 1.5708, 0), mat=mat_bearing, parent_obj=el_link
            )
            created.extend([o_el_act, o_el_brg])

        # 3. Wrist Actuator Envelope, Bearing & Hand Mounting Interface (parented to wrist link)
        if wr_link:
            o_wr_act = create_box_envelope(
                f"ACTUATOR_WRIST_ENVELOPE_{side}", (0, 0, 0), dim_wr,
                col, mat_actuator, wr_link, c_wr_act
            )
            o_wr_brg = create_cylinder_envelope(
                f"BEARING_WRIST_{side}", (0, 0, 0.020),
                radius=0.022, depth=0.010, collection=col,
                rot=(0, 0, 0), mat=mat_bearing, parent_obj=wr_link
            )
            o_hand_flg = create_cylinder_envelope(
                f"HAND_MOUNTING_INTERFACE_{side}", (0, -0.01, -0.045),
                radius=0.028, depth=0.008, collection=col,
                rot=(0, 0, 0), mat=mat_flange, parent_obj=wr_link
            )
            created.extend([o_wr_act, o_wr_brg, o_hand_flg])

    return created
