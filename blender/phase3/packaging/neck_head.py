"""
GRACEEMO-01 — Neck Actuators, Head Packaging & Sensor FOV Visualization
Packages neck yaw/pitch actuators, brackets, microphones, speaker, and sensor FOV cones.
"""

import math
import bpy
from mathutils import Vector, Euler
try:
    from phase3.manifest.hardware_manifest import get_component
except ImportError:
    from manifest.hardware_manifest import get_component
from .base_power_compute import create_box_envelope, get_or_create_material
from .mobility_wheels import create_cylinder_envelope

def create_fov_cone(name, loc, rot, h_fov_deg, v_fov_deg, distance, collection, parent_obj=None):
    """Create a transparent/wireframe pyramid visualizing sensor Field of View."""
    obj = bpy.data.objects.get(name)
    if not obj:
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)

        h_rad = math.radians(h_fov_deg / 2.0)
        v_rad = math.radians(v_fov_deg / 2.0)
        w = distance * math.tan(h_rad)
        h = distance * math.tan(v_rad)

        # In camera frame: apex is at (0, 0, 0), projecting forward along -Y (or +Z)
        apex = (0, 0, 0)
        p1 = (-w, -distance, -h)
        p2 = (w, -distance, -h)
        p3 = (w, -distance, h)
        p4 = (-w, -distance, h)

        verts = [apex, p1, p2, p3, p4]
        faces = [
            (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
            (1, 2, 3, 4)
        ]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
    else:
        if collection not in obj.users_collection:
            for c in list(obj.users_collection): c.objects.unlink(obj)
            collection.objects.link(obj)

    obj.location = loc
    obj.rotation_euler = rot

    # Transparent wireframe FOV material
    mat_fov = bpy.data.materials.get(f"MAT_FOV_{name}")
    if not mat_fov:
        mat_fov = bpy.data.materials.new(f"MAT_FOV_{name}")
        mat_fov.use_nodes = True
        bsdf = mat_fov.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.2, 0.8, 1.0, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.1
        mat_fov.blend_method = 'BLEND' if hasattr(mat_fov, 'blend_method') else 'OPAQUE'

    if not obj.data.materials:
        obj.data.materials.append(mat_fov)
    obj.display_type = 'WIRE'

    if parent_obj and obj.parent != parent_obj:
        m = obj.matrix_world.copy()
        obj.parent = parent_obj
        obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
        obj.matrix_world = m

    return obj

def setup_neck_head_and_sensors(manifest):
    """Package neck actuation, sensors, and FOV visualization."""
    col_neck = bpy.data.collections.get("06_HEAD") or bpy.data.collections.get("05_TORSO") or bpy.context.scene.collection
    col_head = bpy.data.collections.get("06_HEAD") or bpy.context.scene.collection
    col_sensors = bpy.data.collections.get("11_SENSORS") or bpy.context.scene.collection
    col_debug = bpy.data.collections.get("15_DEBUG") or bpy.context.scene.collection
    col_torso = bpy.data.collections.get("05_TORSO") or bpy.context.scene.collection

    neck_yaw_link = bpy.data.objects.get("neck_yaw_link")
    head_link = bpy.data.objects.get("head_link")
    torso_link = bpy.data.objects.get("torso_link")
    camera_link = bpy.data.objects.get("camera_link")
    lidar_link = bpy.data.objects.get("lidar_link")

    mat_servo = get_or_create_material("MAT_ENG_DynamixelServo", (0.15, 0.15, 0.18, 1.0), 0.7, 0.3)
    mat_plate = get_or_create_material("MAT_ENG_AnodizedBlackPlate", (0.1, 0.1, 0.12, 1.0), 0.8, 0.25)
    mat_sensor_glass = get_or_create_material("MAT_ENG_SensorOptics", (0.05, 0.05, 0.08, 1.0), 0.95, 0.1)

    c_servo = get_component("ACT-01", manifest)
    dim_servo = (c_servo["length"], c_servo["width"], c_servo["height"]) if c_servo else (0.046, 0.034, 0.028)

    created = []

    # --------------------------------------------------------------------------
    # 1. Neck Actuators
    # --------------------------------------------------------------------------
    # Yaw Actuator (at neck_yaw_link, rotates Z)
    if neck_yaw_link:
        o_yaw_act = create_box_envelope(
            "ACTUATOR_NECK_YAW_ENVELOPE", (0, 0, -0.02), dim_servo,
            col_neck, mat_servo, neck_yaw_link, c_servo
        )
        o_yaw_plate = create_cylinder_envelope(
            "NECK_YAW_MOUNTING_PLATE", (0, 0, -0.04),
            radius=0.045, depth=0.006, collection=col_neck,
            rot=(0, 0, 0), mat=mat_plate, parent_obj=neck_yaw_link
        )
        created.extend([o_yaw_act, o_yaw_plate])

    # Pitch Actuator (at head_link base, rotates X)
    if head_link:
        o_pitch_act = create_box_envelope(
            "ACTUATOR_NECK_PITCH_ENVELOPE", (0, 0, -0.05), dim_servo,
            col_head, mat_servo, head_link, c_servo
        )
        # Roll Actuator (provisional/auxiliary envelope)
        o_roll_act = create_box_envelope(
            "ACTUATOR_NECK_ROLL_PROVISIONAL", (0, 0.025, -0.05), (0.035, 0.025, 0.020),
            col_head, mat_servo, head_link, c_servo
        )
        o_roll_act["provisional_auxiliary_dof"] = True
        created.extend([o_pitch_act, o_roll_act])

    # --------------------------------------------------------------------------
    # 2. Perception & Sensor Envelopes
    # --------------------------------------------------------------------------
    # RGB-D Camera Envelope & Mounting Bracket
    c_cam = get_component("SEN-02", manifest)
    dim_cam = (c_cam["length"], c_cam["width"], c_cam["height"]) if c_cam else (0.090, 0.025, 0.025)
    if camera_link:
        o_cam = create_box_envelope(
            "COMP_CAMERA_ENVELOPE", (0, 0, 0), dim_cam,
            col_sensors, mat_sensor_glass, camera_link, c_cam
        )
        o_cam_bkt = create_box_envelope(
            "BRACKET_CAMERA_MOUNT", (0, 0.015, -0.015), (0.095, 0.015, 0.020),
            col_sensors, mat_plate, camera_link
        )
        created.extend([o_cam, o_cam_bkt])

        # Camera FOV Cone in 15_DEBUG (Intel D435i: ~87 deg H x 58 deg V, 1.2m range)
        o_cam_fov = create_fov_cone(
            "DEBUG_FOV_CAMERA_CONE", (0, 0, 0), (0, 0, 0),
            h_fov_deg=87.0, v_fov_deg=58.0, distance=1.0,
            collection=col_debug, parent_obj=camera_link
        )
        created.append(o_cam_fov)

    # LiDAR Envelope & Mounting Bracket
    c_lidar = get_component("SEN-01", manifest)
    dim_lidar = (c_lidar["length"], c_lidar["width"], c_lidar["height"]) if c_lidar else (0.098, 0.098, 0.065)
    if lidar_link:
        o_lidar = create_cylinder_envelope(
            "COMP_LIDAR_ENVELOPE", (0, 0, 0),
            radius=0.049, depth=0.065, collection=col_sensors,
            rot=(0, 0, 0), mat=mat_sensor_glass, parent_obj=lidar_link, comp_data=c_lidar
        )
        o_lidar_bkt = create_cylinder_envelope(
            "BRACKET_LIDAR_MOUNT", (0, 0, -0.035),
            radius=0.055, depth=0.008, collection=col_sensors,
            rot=(0, 0, 0), mat=mat_plate, parent_obj=lidar_link
        )
        created.extend([o_lidar, o_lidar_bkt])

        # LiDAR Scan Plane FOV in 15_DEBUG (Horizontal 270 deg scan disc)
        o_lidar_fov = create_cylinder_envelope(
            "DEBUG_FOV_LIDAR_PLANE", (0, 0, 0.025),
            radius=1.50, depth=0.005, collection=col_debug,
            rot=(0, 0, 0), parent_obj=lidar_link
        )
        o_lidar_fov.display_type = 'WIRE'
        created.append(o_lidar_fov)

    # --------------------------------------------------------------------------
    # 3. Audio Hardware (Forehead Mic Array & Chest Speaker)
    # --------------------------------------------------------------------------
    c_mic = get_component("AUD-01", manifest)
    dim_mic = (c_mic["length"], c_mic["width"], c_mic["height"]) if c_mic else (0.065, 0.015, 0.008)
    if head_link:
        o_mic = create_box_envelope(
            "COMP_AUDIO_MIC_ARRAY_ENVELOPE", (0, -0.115, 0.12), dim_mic,
            col_head, mat_plate, head_link, c_mic
        )
        created.append(o_mic)

    c_spk = get_component("AUD-02", manifest)
    dim_spk = (c_spk["length"], c_spk["width"], c_spk["height"]) if c_spk else (0.085, 0.085, 0.040)
    if torso_link:
        o_spk = create_cylinder_envelope(
            "COMP_AUDIO_SPEAKER_ENVELOPE", (0, -0.11, 0.05),
            radius=0.042, depth=0.040, collection=col_torso,
            rot=(1.5708, 0, 0), mat=mat_plate, parent_obj=torso_link, comp_data=c_spk
        )
        created.append(o_spk)

    return created
