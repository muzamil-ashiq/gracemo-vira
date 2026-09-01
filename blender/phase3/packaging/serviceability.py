"""
GRACEEMO-01 — Serviceability & Maintenance Access Panels
Creates maintenance access covers and tags serviceability metadata.
"""

import bpy
from .base_power_compute import create_box_envelope, get_or_create_material
from .mobility_wheels import create_cylinder_envelope

def setup_service_panels():
    """Build marked service panels for battery, compute, wheels, and sensors."""
    col_chassis = bpy.data.collections.get("01_CHASSIS") or bpy.context.scene.collection
    col_torso = bpy.data.collections.get("05_TORSO") or bpy.data.collections.get("03_TORSO") or bpy.context.scene.collection
    col_head = bpy.data.collections.get("06_HEAD") or bpy.data.collections.get("07_HEAD") or bpy.context.scene.collection

    mat_panel = get_or_create_material("MAT_ENG_ServicePanelMarked", (0.2, 0.22, 0.25, 1.0), 0.8, 0.3)
    mat_latch = get_or_create_material("MAT_ENG_QuickReleaseLatch", (0.9, 0.8, 0.1, 1.0), 0.85, 0.2)

    base_link = bpy.data.objects.get("base_link")
    torso_link = bpy.data.objects.get("torso_link")
    head_link = bpy.data.objects.get("head_link")

    created = []

    # 1. Battery Service Panel (Rear chassis quick-release)
    if base_link:
        o_bat = create_box_envelope(
            "PANEL_SERVICE_BATTERY_REAR", (0.0, 0.19, 0.02), (0.34, 0.005, 0.18),
            col_chassis, mat_panel, base_link
        )
        o_bat["service_target"] = "PWR-01 24V LiFePO4 Battery Pack"
        o_bat["access_type"] = "Slide-out quick release with captive thumb screws"
        created.append(o_bat)

    # 2. Compute Bay Spine Door (Torso rear)
    if torso_link:
        o_cmp = create_box_envelope(
            "PANEL_SERVICE_COMPUTE_TORSO", (0.0, 0.135, 0.02), (0.25, 0.005, 0.32),
            col_torso, mat_panel, torso_link
        )
        o_cmp["service_target"] = "Jetson Orin AI Computer, STM32 MCU, Ethernet Switch"
        o_cmp["access_type"] = "Hinged maintenance door with magnetic latch"
        created.append(o_cmp)

    # 3. Head Electronics Access Cover (Rear cranium)
    if head_link:
        o_head = create_box_envelope(
            "PANEL_SERVICE_HEAD_ACCESS", (0.0, 0.095, 0.04), (0.16, 0.005, 0.14),
            col_head, mat_panel, head_link
        )
        o_head["service_target"] = "RealSense Depth Camera board & Neck Pitch Actuator"
        o_head["access_type"] = "Removable rear visor cowl"
        created.append(o_head)

    # 4. Wheel Motor Hub Service Caps
    for w_name, code, sign in [("left_wheel", "RL", -1), ("right_wheel", "RR", 1), ("left_front_wheel", "FL", -1), ("right_front_wheel", "FR", 1)]:
        wl = bpy.data.objects.get(w_name)
        if wl:
            o_w = create_cylinder_envelope(
                f"PANEL_SERVICE_MOTOR_{code}", (sign * 0.045, 0, 0),
                radius=0.035, depth=0.005, collection=col_chassis,
                rot=(0, 1.5708, 0), mat=mat_latch, parent_obj=wl
            )
            o_w["service_target"] = f"Wheel {code} BLDC Motor & Optical Encoder"
            o_w["access_type"] = "Threaded hub dust cap"
            created.append(o_w)

    return created
