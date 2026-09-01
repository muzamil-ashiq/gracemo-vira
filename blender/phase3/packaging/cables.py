"""
GRACEEMO-01 — Cable Routing Channels & Service Loops
Packages realistic routing channels in 12_CABLE_ROUTING.
"""

import bpy
from mathutils import Vector
from .base_power_compute import get_or_create_material

def create_cable_curve(name, points, radius, collection, mat=None, parent_obj=None):
    """Create a 3D bevelled curve path representing an engineering cable conduit."""
    obj = bpy.data.objects.get(name)
    if not obj:
        curve_data = bpy.data.curves.new(name=f"{name}_Curve", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = radius
        curve_data.bevel_resolution = 4
        
        spline = curve_data.splines.new('POLY')
        spline.points.add(len(points) - 1)
        for i, pt in enumerate(points):
            spline.points[i].co = (pt[0], pt[1], pt[2], 1.0)

        obj = bpy.data.objects.new(name, curve_data)
        collection.objects.link(obj)
    else:
        if collection not in obj.users_collection:
            for c in list(obj.users_collection): c.objects.unlink(obj)
            collection.objects.link(obj)

    if mat:
        if not obj.data.materials:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat

    if parent_obj and obj.parent != parent_obj:
        m = obj.matrix_world.copy()
        obj.parent = parent_obj
        obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
        obj.matrix_world = m

    return obj

def setup_cable_routing():
    """Setup realistic cable conduits and service loops."""
    col_cables = bpy.data.collections.get("12_CABLE_ROUTING")
    base_link = bpy.data.objects.get("base_link")
    torso_link = bpy.data.objects.get("torso_link")

    # Cable materials by engineering standard colors
    mat_pwr_main = get_or_create_material("MAT_CABLE_PowerMainOrange", (0.90, 0.40, 0.05, 1.0), 0.1, 0.5)
    mat_pwr_low = get_or_create_material("MAT_CABLE_LowVoltageYellow", (0.85, 0.80, 0.10, 1.0), 0.1, 0.5)
    mat_mot_pwr = get_or_create_material("MAT_CABLE_MotorPowerBlack", (0.12, 0.12, 0.14, 1.0), 0.1, 0.6)
    mat_mot_sig = get_or_create_material("MAT_CABLE_MotorSignalBlue", (0.10, 0.35, 0.85, 1.0), 0.1, 0.5)
    mat_cam = get_or_create_material("MAT_CABLE_CameraDataCyan", (0.05, 0.75, 0.85, 1.0), 0.1, 0.4)
    mat_net = get_or_create_material("MAT_CABLE_NetworkGreen", (0.15, 0.75, 0.25, 1.0), 0.1, 0.5)
    mat_aud = get_or_create_material("MAT_CABLE_AudioPurple", (0.60, 0.15, 0.80, 1.0), 0.1, 0.5)

    created = []

    # 1. POWER_MAIN: Battery -> Fuse -> Distribution Contactor -> DC-DC
    pts_pwr_main = [
        (0.0, -0.05, 0.08),
        (-0.08, -0.08, 0.10),
        (-0.15, -0.10, 0.14),
        (-0.15, 0.02, 0.14),
        (0.0, 0.06, 0.15),
        (0.12, 0.02, 0.15),
        (0.15, -0.05, 0.14),
    ]
    c_pwr = create_cable_curve("CABLE_POWER_MAIN", pts_pwr_main, 0.008, col_cables, mat_pwr_main, base_link)
    created.append(c_pwr)

    # 2. POWER_LOW_VOLTAGE: DC-DC -> Spine Vertical Duct -> Compute Bay
    pts_pwr_low = [
        (0.12, 0.02, 0.14),
        (0.06, 0.05, 0.22),
        (0.03, 0.05, 0.50),
        (0.02, 0.03, 0.78),
        (0.0, 0.02, 0.86),
    ]
    c_low = create_cable_curve("CABLE_POWER_LOW_VOLTAGE", pts_pwr_low, 0.006, col_cables, mat_pwr_low, base_link)
    created.append(c_low)

    # 3. MOTOR_POWER: Dual Controllers -> 4 Wheel Hubs
    pts_mot_pwr = [
        (-0.11, 0.01, 0.76),
        (-0.11, 0.04, 0.45),
        (-0.10, 0.02, 0.20),
        (-0.18, -0.15, 0.12),
        (-0.21, -0.18, 0.12),
    ]
    c_mp = create_cable_curve("CABLE_MOTOR_POWER", pts_mot_pwr, 0.007, col_cables, mat_mot_pwr, base_link)
    created.append(c_mp)

    # 4. MOTOR_SIGNAL: Encoders & Hall sensors -> MCU
    pts_mot_sig = [
        (-0.21, -0.22, 0.12),
        (-0.14, -0.12, 0.18),
        (-0.06, 0.01, 0.42),
        (0.0, 0.02, 0.74),
    ]
    c_ms = create_cable_curve("CABLE_MOTOR_SIGNAL", pts_mot_sig, 0.005, col_cables, mat_mot_sig, base_link)
    created.append(c_ms)

    # 5. CAMERA_DATA: Head RealSense -> Neck Swivel Service Loop -> Jetson
    pts_cam = [
        (0.0, -0.10, 1.36),
        (0.0, -0.05, 1.34),
        (0.0, 0.03, 1.25),   # Neck service loop with gentle radius
        (0.02, 0.04, 1.16),
        (0.02, 0.03, 0.96),
        (0.0, 0.02, 0.90),
    ]
    c_cam = create_cable_curve("CABLE_CAMERA_DATA", pts_cam, 0.004, col_cables, mat_cam, torso_link)
    created.append(c_cam)

    # 6. NETWORK: Industrial Switch -> LiDAR & Jetson
    pts_net = [
        (0.0, -0.05, 0.74),
        (0.05, -0.04, 0.60),
        (0.10, -0.03, 0.54),
        (0.12, -0.02, 0.52),
    ]
    c_net = create_cable_curve("CABLE_NETWORK", pts_net, 0.005, col_cables, mat_net, torso_link)
    created.append(c_net)

    # 7. AUDIO: Forehead Mic & Chest Speaker -> Audio Codec
    pts_aud = [
        (0.0, -0.11, 1.34),
        (0.0, -0.07, 1.26),
        (0.0, -0.08, 1.05),
        (0.0, -0.09, 0.88),
    ]
    c_aud = create_cable_curve("CABLE_AUDIO", pts_aud, 0.004, col_cables, mat_aud, torso_link)
    created.append(c_aud)

    return created
