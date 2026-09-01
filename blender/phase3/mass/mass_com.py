"""
GRACEEMO-01 — Mass Properties & Center of Mass (CoM) Estimation
Calculates system mass distribution from hardware manifest envelopes.
"""

import bpy
from mathutils import Vector

def calculate_mass_and_com():
    """Traverse all packaged components with mass properties and calculate Center of Mass."""
    total_mass = 0.0
    weighted_pos = Vector((0.0, 0.0, 0.0))
    category_masses = {}
    counted_objects = 0

    base_fp = bpy.data.objects.get("base_footprint") or bpy.data.objects.get("base_link")
    base_inv = base_fp.matrix_world.inverted() if base_fp else None

    for o in bpy.data.objects:
        if "mass_estimate_kg" in o:
            try:
                m = float(o["mass_estimate_kg"])
            except (ValueError, TypeError):
                continue

            if m > 0:
                total_mass += m
                world_pos = o.matrix_world.to_translation()
                weighted_pos += m * world_pos
                counted_objects += 1

                cat = o.get("category", "OTHER")
                category_masses[cat] = category_masses.get(cat, 0.0) + m

    if total_mass > 0:
        com_world = weighted_pos / total_mass
    else:
        com_world = Vector((0.0, 0.0, 0.5))

    com_base = (base_inv @ com_world) if base_inv else com_world

    # Tag properties on root object
    root = bpy.data.objects.get("GRACEEMO-01_ROOT")
    if root:
        root["total_mass_estimate_kg"] = round(total_mass, 3)
        root["com_x"] = round(com_base.x, 4)
        root["com_y"] = round(com_base.y, 4)
        root["com_z"] = round(com_base.z, 4)
        root["com_status"] = "PROVISIONAL_ESTIMATE"

    # Create/update visual Center of Mass indicator in 15_DEBUG
    col_debug = bpy.data.collections.get("15_DEBUG")
    if col_debug:
        com_obj = bpy.data.objects.get("INDICATOR_CENTER_OF_MASS")
        if not com_obj:
            com_obj = bpy.data.objects.new("INDICATOR_CENTER_OF_MASS", None)
            col_debug.objects.link(com_obj)
            com_obj.empty_display_type = 'SPHERE'
            com_obj.empty_display_size = 0.06
        com_obj.location = com_world

    report = {
        "total_mass_kg": round(total_mass, 3),
        "com_world": (round(com_world.x, 4), round(com_world.y, 4), round(com_world.z, 4)),
        "com_base_footprint": (round(com_base.x, 4), round(com_base.y, 4), round(com_base.z, 4)),
        "component_count": counted_objects,
        "category_breakdown": {k: round(v, 3) for k, v in category_masses.items()}
    }

    return report
