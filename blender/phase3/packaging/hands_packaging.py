"""
GRACEEMO-01 — Hand Internal Packaging & Actuation Envelopes
Packages hand actuators, finger linkages, and service access.
"""

import bpy
from mathutils import Vector, Euler
try:
    from phase3.manifest.hardware_manifest import get_component
except ImportError:
    from manifest.hardware_manifest import get_component
from .base_power_compute import create_box_envelope, get_or_create_material

def setup_hands_packaging(manifest):
    """Package internal hand actuator mechanisms and service access plates."""
    col_hands = bpy.data.collections.get("09_HANDS") or bpy.data.collections.get("10_HANDS") or bpy.context.scene.collection
    mat_mech = get_or_create_material("MAT_ENG_PrecisionMechanism", (0.25, 0.26, 0.28, 1.0), 0.7, 0.3)
    mat_access = get_or_create_material("MAT_ENG_ServicePlate", (0.55, 0.58, 0.60, 1.0), 0.8, 0.35)

    c_hand_act = get_component("ACT-05", manifest)
    dim_act = (c_hand_act["length"], c_hand_act["width"], c_hand_act["height"]) if c_hand_act else (0.055, 0.045, 0.025)

    created = []

    for side in ["LEFT", "RIGHT"]:
        prefix = side.lower()
        hd_link = bpy.data.objects.get(f"{prefix}_hand_link")
        if not hd_link:
            continue

        # Hand Actuator Area Envelope (internal to palm)
        o_act = create_box_envelope(
            f"COMP_HAND_ACTUATOR_ENVELOPE_{side}", (0, 0, 0), dim_act,
            col_hands, mat_mech, hd_link, c_hand_act
        )

        # Finger Linkage Transmission Area
        o_linkage = create_box_envelope(
            f"FINGER_LINKAGE_AREA_{side}", (0, -0.015, -0.035), (0.050, 0.035, 0.018),
            col_hands, mat_mech, hd_link
        )

        # Hand Service Access Cover (back of hand)
        o_serv = create_box_envelope(
            f"HAND_SERVICE_ACCESS_{side}", (0, 0.022, 0.0), (0.045, 0.003, 0.035),
            col_hands, mat_access, hd_link
        )

        created.extend([o_act, o_linkage, o_serv])

    return created
