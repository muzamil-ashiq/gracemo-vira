"""
GRACEEMO-01 — Wheel Mechanical Assembly Packaging
Transforms each drive wheel into a realistic multi-part engineering assembly.
"""

import bpy
from mathutils import Vector, Euler
try:
    from phase3.manifest.hardware_manifest import get_component
except ImportError:
    from manifest.hardware_manifest import get_component

def create_cylinder_envelope(name, loc, radius, depth, collection, rot=(0, 0, 0), mat=None, parent_obj=None, comp_data=None):
    """Create a dimensionally accurate cylinder envelope."""
    obj = bpy.data.objects.get(name)
    if not obj:
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        # Create cylinder pydata
        import math
        segments = 16
        half_d = depth / 2.0
        verts = []
        for z in [-half_d, half_d]:
            for i in range(segments):
                theta = 2.0 * math.pi * i / segments
                verts.append((radius * math.cos(theta), radius * math.sin(theta), z))
        faces = []
        # Side faces
        for i in range(segments):
            i_next = (i + 1) % segments
            faces.append((i, i_next, segments + i_next, segments + i))
        # End caps
        faces.append(tuple(reversed(range(segments))))
        faces.append(tuple(range(segments, segments * 2)))
        mesh.from_pydata(verts, [], faces)
        mesh.update()
    else:
        if collection not in obj.users_collection:
            for c in list(obj.users_collection): c.objects.unlink(obj)
            collection.objects.link(obj)

    obj.location = loc
    obj.rotation_euler = rot

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

    if comp_data:
        obj["component_id"] = comp_data.get("component_id", "UNKNOWN")
        obj["component_name"] = comp_data.get("component_name", "UNKNOWN")
        obj["category"] = comp_data.get("category", "UNKNOWN")
        obj["mass_estimate_kg"] = float(comp_data.get("mass", 0.0))
        obj["status"] = comp_data.get("status", "UNKNOWN")

    return obj

def setup_wheel_assemblies(manifest):
    """Build multi-component wheel assemblies for all 4 drive wheels."""
    col_wheels = bpy.data.collections.get("01_CHASSIS") or bpy.data.collections.get("04_WHEELS") or bpy.context.scene.collection

    # Materials
    mat_steel = bpy.data.materials.get("MAT_ENG_SteelShaft")
    if not mat_steel:
        mat_steel = bpy.data.materials.new("MAT_ENG_SteelShaft")
        mat_steel.use_nodes = True
        bsdf = mat_steel.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.75, 0.77, 0.80, 1.0)
            bsdf.inputs["Metallic"].default_value = 0.95
            bsdf.inputs["Roughness"].default_value = 0.20

    mat_brass = bpy.data.materials.get("MAT_ENG_BearingBrass")
    if not mat_brass:
        mat_brass = bpy.data.materials.new("MAT_ENG_BearingBrass")
        mat_brass.use_nodes = True
        bsdf = mat_brass.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.85, 0.65, 0.25, 1.0)
            bsdf.inputs["Metallic"].default_value = 0.90
            bsdf.inputs["Roughness"].default_value = 0.25

    mat_motor = bpy.data.materials.get("MAT_ENG_MotorBlack")
    if not mat_motor:
        mat_motor = bpy.data.materials.new("MAT_ENG_MotorBlack")
        mat_motor.use_nodes = True
        bsdf = mat_motor.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.10, 0.10, 0.12, 1.0)
            bsdf.inputs["Metallic"].default_value = 0.85
            bsdf.inputs["Roughness"].default_value = 0.30

    mat_encoder = bpy.data.materials.get("MAT_ENG_EncoderGold")
    if not mat_encoder:
        mat_encoder = bpy.data.materials.new("MAT_ENG_EncoderGold")
        mat_encoder.use_nodes = True
        bsdf = mat_encoder.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.90, 0.75, 0.30, 1.0)
            bsdf.inputs["Metallic"].default_value = 0.80

    c_motor = get_component("MOB-06", manifest)
    c_encoder = get_component("MOB-07", manifest)
    c_bearing = get_component("MOB-08", manifest)

    wheel_links = [
        ("left_wheel", -1, "RL"),
        ("right_wheel", 1, "RR"),
        ("left_front_wheel", -1, "FL"),
        ("right_front_wheel", 1, "FR"),
    ]

    created = []

    for w_link_name, sign, code in wheel_links:
        w_link = bpy.data.objects.get(w_link_name)
        if not w_link:
            continue

        # In wheel_link frame, axle is along local Y (or X depending on wheel orientation)
        # Hub flange
        o_hub = create_cylinder_envelope(
            f"WHEEL_HUB_{code}", (0, 0, 0),
            radius=0.055, depth=0.030, collection=col_wheels,
            rot=(0, 1.5708, 0), mat=mat_steel, parent_obj=w_link
        )
        # Axle drive shaft (passing through hub)
        o_axle = create_cylinder_envelope(
            f"WHEEL_AXLE_{code}", (0, 0, 0),
            radius=0.010, depth=0.090, collection=col_wheels,
            rot=(0, 1.5708, 0), mat=mat_steel, parent_obj=w_link
        )
        # Deep groove ball bearing (6004-2RS: OD 0.042, width 0.012)
        o_brg = create_cylinder_envelope(
            f"WHEEL_BEARING_{code}", (sign * 0.035, 0, 0),
            radius=0.021, depth=0.012, collection=col_wheels,
            rot=(0, 1.5708, 0), mat=mat_brass, parent_obj=w_link, comp_data=c_bearing
        )
        # In-wheel BLDC gearmotor envelope
        o_mot = create_cylinder_envelope(
            f"WHEEL_MOTOR_{code}", (sign * -0.025, 0, 0),
            radius=0.045, depth=0.075, collection=col_wheels,
            rot=(0, 1.5708, 0), mat=mat_motor, parent_obj=w_link, comp_data=c_motor
        )
        # Optical encoder envelope (mounted at inner shaft tail)
        o_enc = create_cylinder_envelope(
            f"WHEEL_ENCODER_{code}", (sign * -0.065, 0, 0),
            radius=0.020, depth=0.025, collection=col_wheels,
            rot=(0, 1.5708, 0), mat=mat_encoder, parent_obj=w_link, comp_data=c_encoder
        )

        created.extend([o_hub, o_axle, o_brg, o_mot, o_enc])

    return created
