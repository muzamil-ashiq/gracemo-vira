import os
import math
import json
import bpy
from mathutils import Vector

# ================================================================
# GRACEEMO-01 — parametric Blender model matching the product
# reference (white polymer shells, black actuators, cyan LEDs,
# chest status display, differential two-wheel base).
#
# Run with Blender 4.0+ (5.2 recommended), not system Python:
#   Blender --background --python GraceEMO_Blender_Generator.py
# ================================================================

if bpy.app.version < (4, 0, 0):
    raise RuntimeError("GraceEMO generator requires Blender 4.0+; Blender 5.2+ is recommended.")

# Master height 4.5 ft. All values in meters, ROS Z-up.
P = {
    "height": 1.372,
    "wheel_r": 0.12,
    "wheel_w": 0.080,
    "wheel_sep": 0.42,
    "base_l": 0.38,
    "base_w": 0.36,
    "torso_w": 0.36,
    "torso_d": 0.22,
    "torso_h": 0.36,
    "head_w": 0.26,
    "head_d": 0.20,
    "head_h": 0.24,
}

def mat(name, color, metallic=0.0, rough=0.4, emit=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if emit > 0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*color, 1)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emit
    return m

MAT = {
    "body": mat("GRACEEMO Shell White", (0.92, 0.93, 0.95), 0.08, 0.22),
    "dark": mat("GRACEEMO Actuator Black", (0.02, 0.025, 0.03), 0.55, 0.28),
    "rubber": mat("GRACEEMO Tyre", (0.02, 0.02, 0.02), 0.02, 0.72),
    "metal": mat("GRACEEMO Machined", (0.28, 0.30, 0.33), 0.82, 0.24),
    "cyan": mat("GRACEEMO LED Cyan", (0.05, 0.75, 0.95), 0.1, 0.18, emit=8.0),
    "glass": mat("GRACEEMO Sensor Glass", (0.02, 0.04, 0.06), 0.6, 0.08),
    "screen": mat("GRACEEMO Chest Screen", (0.04, 0.07, 0.09), 0.25, 0.16),
    "face": mat("GRACEEMO Faceplate", (0.01, 0.015, 0.02), 0.35, 0.12),
    "accent": mat("GRACEEMO Emblem Orange", (0.92, 0.32, 0.08), 0.12, 0.32, emit=1.5),
}

def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c

def move_to(obj, coll):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)

def cube(name, loc, size, material, coll, bevel=0.012):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new("Edge_Rounding", "BEVEL")
        mod.width = bevel
        mod.segments = 3
    o.data.materials.append(material)
    move_to(o, coll)
    return o

def cyl(name, loc, radius, depth, material, coll, rot=(0, 0, 0), verts=32):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot
    )
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    move_to(o, coll)
    return o

def uv(name, loc, scale, material, coll):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    move_to(o, coll)
    return o

def torus(name, loc, major, minor, material, coll, rot=(math.pi / 2, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor,
        major_segments=36, minor_segments=10, location=loc, rotation=rot,
    )
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    move_to(o, coll)
    return o

def beam_between(name, a, b, radius, material, coll):
    a, b = Vector(a), Vector(b)
    d = b - a
    mid = (a + b) / 2
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=d.length, location=mid)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    move_to(o, coll)
    return o

def empty(name, loc, coll, display="ARROWS", size=0.08):
    o = bpy.data.objects.new(name, None)
    coll.objects.link(o)
    o.location = loc
    o.empty_display_type = display
    o.empty_display_size = size
    return o

def label(text, loc, coll, size=0.028, material=None):
    bpy.ops.object.text_add(location=loc)
    o = bpy.context.object
    o.name = "LABEL_" + text.replace(" ", "_")[:40]
    o.data.body = text
    o.data.align_x = "CENTER"
    o.data.size = size
    o.data.extrude = 0.0015
    o.data.materials.append(material or MAT["dark"])
    move_to(o, coll)
    o.rotation_euler = (math.pi / 2, 0, 0)
    return o

def parent(obj, p):
    obj.parent = p

# ----------------------------
# Clean previous generated data FIRST
# ----------------------------
_generated_prefixes = (
    "GRACEEMO", "LIDAR_", "CAM_", "JOINT_", "LABEL_", "COMP_",
    "CABLE_", "HAND_", "ARM_", "WHEEL_", "BUMP_", "CASTER_",
    "SENSOR_", "PATIENT_", "POWER_", "TORSO_", "HEAD_", "FACE_",
    "MIC_", "TF_", "COLLISION_", "CHASSIS_", "ACT_", "CAMERA_",
    "LIGHT_", "PRESENTATION_", "HRI_", "HIP_", "WAIST_",
)
for obj in list(bpy.data.objects):
    if obj.name.startswith(_generated_prefixes):
        bpy.data.objects.remove(obj, do_unlink=True)

_old_root = bpy.data.collections.get("GRACEEMO-01")
if _old_root:
    for child in list(_old_root.children):
        _old_root.children.unlink(child)
        try:
            bpy.data.collections.remove(child)
        except RuntimeError:
            pass
    try:
        bpy.context.scene.collection.children.unlink(_old_root)
    except RuntimeError:
        pass
    try:
        bpy.data.collections.remove(_old_root)
    except RuntimeError:
        pass

ROOT = collection("GRACEEMO-01")
COL = {}
for n in [
    "00_REFERENCE", "01_CHASSIS", "02_POWER", "03_COMPUTE", "04_CONTROL",
    "05_TORSO", "06_HEAD", "07_LEFT_ARM", "08_RIGHT_ARM", "09_HANDS",
    "10_PATIENT_SUPPORT", "11_SENSORS", "12_CABLE_ROUTING", "13_JOINTS",
    "14_COLLISION", "15_DEBUG",
]:
    COL[n] = collection(n, ROOT)

robot = empty("GRACEEMO-01_ROOT", (0, 0, 0), ROOT, "CUBE", 0.12)
base_link = empty("base_link", (0, 0, P["wheel_r"]), COL["01_CHASSIS"], "ARROWS", 0.10)
parent(base_link, robot)

wr, ww, sep = P["wheel_r"], P["wheel_w"], P["wheel_sep"]

# ----------------------------
# CHASSIS — stacked white/black modules + large drive wheels
# ----------------------------
lower = cube("CHASSIS_Lower_Module", (0, 0, 0.14), (P["base_l"], P["base_w"], 0.16), MAT["dark"], COL["01_CHASSIS"], 0.02)
parent(lower, robot)
mid = cube("CHASSIS_Mid_Deck", (0, 0, 0.28), (0.36, 0.32, 0.12), MAT["body"], COL["01_CHASSIS"], 0.02)
parent(mid, robot)
upper = cube("CHASSIS_Sensor_Bay", (0, 0, 0.40), (0.34, 0.30, 0.12), MAT["dark"], COL["01_CHASSIS"], 0.018)
parent(upper, robot)
cap = cube("CHASSIS_Upper_Cap", (0, 0, 0.50), (0.32, 0.28, 0.08), MAT["body"], COL["01_CHASSIS"], 0.016)
parent(cap, robot)

for sign, name in ((-1, "LEFT"), (1, "RIGHT")):
    y = sign * sep / 2
    wheel = cyl(f"WHEEL_{name}_Drive", (0, y, wr), wr, ww, MAT["rubber"], COL["01_CHASSIS"], rot=(math.pi / 2, 0, 0))
    parent(wheel, robot)
    rim = cyl(f"WHEEL_{name}_Rim", (0, y * 0.98, wr), wr * 0.62, ww * 0.45, MAT["metal"], COL["01_CHASSIS"], rot=(math.pi / 2, 0, 0))
    parent(rim, robot)
    hub = cyl(f"WHEEL_{name}_Hub", (0, y * 0.97, wr), 0.035, ww * 0.7, MAT["dark"], COL["01_CHASSIS"], rot=(math.pi / 2, 0, 0))
    parent(hub, robot)

for x, name in ((-0.13, "FRONT"), (0.13, "REAR")):
    caster = cyl(f"CASTER_{name}", (x, 0, 0.05), 0.045, 0.05, MAT["rubber"], COL["01_CHASSIS"], rot=(math.pi / 2, 0, 0))
    parent(caster, robot)

# Front sensor array (cameras / ToF with cyan LEDs)
for i, (x, y, z) in enumerate([
    (-0.16, -0.17, 0.36), (0.0, -0.18, 0.36), (0.16, -0.17, 0.36),
    (-0.10, -0.16, 0.44), (0.10, -0.16, 0.44),
]):
    cam = cyl(f"CAM_Base_{i+1}", (x, y, z), 0.018, 0.016, MAT["glass"], COL["11_SENSORS"], rot=(math.pi / 2, 0, 0))
    parent(cam, robot)
    led = uv(f"SENSOR_LED_{i+1}", (x + 0.022, y, z + 0.012), (0.006, 0.004, 0.006), MAT["cyan"], COL["11_SENSORS"])
    parent(led, robot)

lidar = cyl("LIDAR_Base_Forward", (0.12, -0.02, 0.52), 0.04, 0.035, MAT["metal"], COL["11_SENSORS"])
parent(lidar, robot)

# Hip / thigh columns (white, image: two posts from waist into base)
for sign, name in ((-1, "LEFT"), (1, "RIGHT")):
    hip = cube(f"HIP_{name}_Column", (0, sign * 0.10, 0.62), (0.11, 0.10, 0.22), MAT["body"], COL["05_TORSO"], 0.02)
    parent(hip, robot)
    joint = cyl(f"JOINT_{name}_Hip", (0, sign * 0.10, 0.72), 0.045, 0.08, MAT["dark"], COL["13_JOINTS"], rot=(math.pi / 2, 0, 0))
    parent(joint, robot)

# ----------------------------
# POWER / COMPUTE (internal envelopes)
# ----------------------------
battery = cube("COMP_Battery_Pack", (0, 0.02, 0.22), (0.24, 0.20, 0.10), MAT["metal"], COL["02_POWER"], 0.01)
parent(battery, robot)
jetson = cube("COMP_Edge_AI_Computer", (0, 0.02, 0.34), (0.18, 0.14, 0.04), MAT["metal"], COL["03_COMPUTE"], 0.006)
parent(jetson, robot)

# ----------------------------
# TORSO + chest SYSTEM STATUS
# ----------------------------
waist = cube("WAIST_Actuator_Band", (0, 0, 0.76), (0.28, 0.18, 0.08), MAT["dark"], COL["13_JOINTS"], 0.012)
parent(waist, robot)
torso = cube("TORSO_Outer_Shell", (0, 0, 0.96), (P["torso_w"], P["torso_d"], P["torso_h"]), MAT["body"], COL["05_TORSO"], 0.04)
parent(torso, robot)
screen = cube("TORSO_Status_Display", (0, -0.118, 1.02), (0.20, 0.012, 0.14), MAT["screen"], COL["05_TORSO"], 0.008)
parent(screen, robot)
label("SYSTEM STATUS", (0, -0.126, 1.07), COL["05_TORSO"], 0.012, MAT["cyan"]).parent = robot
label("GRACEEMO-01", (0, -0.124, 0.90), COL["05_TORSO"], 0.018, MAT["dark"]).parent = robot
emblem = uv("TORSO_Emblem", (0, -0.122, 0.84), (0.028, 0.008, 0.028), MAT["accent"], COL["05_TORSO"])
parent(emblem, robot)
ring = torus("TORSO_Emblem_Ring", (0, -0.122, 0.84), 0.022, 0.003, MAT["cyan"], COL["05_TORSO"], rot=(math.pi / 2, 0, 0))
parent(ring, robot)

# ----------------------------
# NECK + HEAD (pill shell, digital face, ear rings)
# ----------------------------
neck = cyl("JOINT_Neck_Yaw", (0, 0, 1.16), 0.05, 0.09, MAT["dark"], COL["13_JOINTS"])
parent(neck, robot)
neck_p = cyl("JOINT_Neck_Pitch", (0, 0, 1.21), 0.038, 0.07, MAT["metal"], COL["13_JOINTS"], rot=(0, math.pi / 2, 0))
parent(neck_p, robot)

head = uv("HEAD_Shell", (0, -0.01, 1.30), (0.13, 0.10, 0.125), MAT["body"], COL["06_HEAD"])
parent(head, robot)
face = cube("HEAD_Expressive_Face", (0, -0.105, 1.30), (0.18, 0.012, 0.14), MAT["face"], COL["06_HEAD"], 0.02)
parent(face, robot)
for x in (-0.045, 0.045):
    eye = uv("FACE_Eye", (x, -0.114, 1.325), (0.028, 0.008, 0.028), MAT["cyan"], COL["06_HEAD"])
    parent(eye, robot)
mouth = cube("FACE_Mouth", (0, -0.114, 1.255), (0.07, 0.006, 0.008), MAT["cyan"], COL["06_HEAD"], 0.004)
parent(mouth, robot)
for sign, name in ((-1, "LEFT"), (1, "RIGHT")):
    ear = torus(f"HEAD_Ear_Ring_{name}", (sign * 0.125, 0.0, 1.30), 0.028, 0.006, MAT["cyan"], COL["06_HEAD"], rot=(0, math.pi / 2, 0))
    parent(ear, robot)
    camh = cyl(f"CAM_{name}_Head", (sign * 0.08, -0.10, 1.36), 0.014, 0.012, MAT["glass"], COL["11_SENSORS"], rot=(math.pi / 2, 0, 0))
    parent(camh, robot)

rgb = cyl("CAM_RGB_Front", (0, -0.112, 1.36), 0.016, 0.012, MAT["glass"], COL["11_SENSORS"], rot=(math.pi / 2, 0, 0))
parent(rgb, robot)

# ----------------------------
# ARMS — white plating, black actuator housings, 5-finger hands
# ----------------------------
def build_hand(side, sign, wrist):
    palm = cube(f"HAND_{side}_Palm", (wrist.x, wrist.y - 0.01, wrist.z - 0.055), (0.075, 0.055, 0.09), MAT["body"], COL["09_HANDS"], 0.012)
    parent(palm, robot)
    xs = [-0.028, -0.010, 0.008, 0.026]
    for i, dx in enumerate(xs, 1):
        f = beam_between(
            f"HAND_{side}_Finger_{i}",
            (wrist.x + dx, wrist.y - 0.015, wrist.z - 0.10),
            (wrist.x + dx, wrist.y - 0.02, wrist.z - 0.155),
            0.008, MAT["body"], COL["09_HANDS"],
        )
        parent(f, robot)
        kn = uv(f"HAND_{side}_Knuckle_{i}", (wrist.x + dx, wrist.y - 0.017, wrist.z - 0.10), (0.009, 0.009, 0.009), MAT["dark"], COL["09_HANDS"])
        parent(kn, robot)
    thumb = beam_between(
        f"HAND_{side}_Thumb",
        (wrist.x - sign * 0.038, wrist.y - 0.01, wrist.z - 0.05),
        (wrist.x - sign * 0.058, wrist.y - 0.02, wrist.z - 0.09),
        0.009, MAT["body"], COL["09_HANDS"],
    )
    parent(thumb, robot)
    return palm

def build_arm(side, sign, coll_name):
    x0 = sign * 0.22
    z_sh = 1.08
    shoulder = empty(f"JOINT_{side}_Shoulder", (x0, 0, z_sh), COL["13_JOINTS"], "SPHERE", 0.05)
    parent(shoulder, robot)
    act = cyl(f"ACT_{side}_Shoulder", (x0, 0, z_sh), 0.048, 0.085, MAT["dark"], COL[coll_name], rot=(0, math.pi / 2, 0))
    parent(act, robot)
    led = uv(f"SENSOR_{side}_Shoulder_LED", (x0, -0.048, z_sh), (0.01, 0.008, 0.01), MAT["cyan"], COL["11_SENSORS"])
    parent(led, robot)
    cam_s = cyl(f"CAM_{side}_Shoulder", (x0, -0.055, z_sh - 0.02), 0.012, 0.01, MAT["glass"], COL["11_SENSORS"], rot=(math.pi / 2, 0, 0))
    parent(cam_s, robot)

    elbow = Vector((sign * 0.30, -0.02, 0.86))
    wrist = Vector((sign * 0.32, -0.02, 0.66))
    upper = beam_between(f"ARM_{side}_UpperArm", (x0, 0, z_sh), elbow, 0.042, MAT["body"], COL[coll_name])
    parent(upper, robot)
    ej = cyl(f"JOINT_{side}_Elbow", elbow, 0.042, 0.07, MAT["dark"], COL["13_JOINTS"], rot=(0, math.pi / 2, 0))
    parent(ej, robot)
    eled = uv(f"SENSOR_{side}_Elbow_LED", elbow + Vector((0, -0.04, 0)), (0.008, 0.006, 0.008), MAT["cyan"], COL["11_SENSORS"])
    parent(eled, robot)
    fore = beam_between(f"ARM_{side}_Forearm", elbow, wrist, 0.036, MAT["body"], COL[coll_name])
    parent(fore, robot)
    wj = cyl(f"JOINT_{side}_Wrist", wrist, 0.032, 0.05, MAT["dark"], COL["13_JOINTS"], rot=(0, math.pi / 2, 0))
    parent(wj, robot)
    return build_hand(side, sign, wrist)

build_arm("LEFT", -1, "07_LEFT_ARM")
build_arm("RIGHT", 1, "08_RIGHT_ARM")

# ----------------------------
# Collision envelopes (hidden)
# ----------------------------
cb = cube("COLLISION_Base", (0, 0, 0.28), (0.40, 0.44, 0.40), MAT["cyan"], COL["14_COLLISION"], 0.01)
cb.display_type = "WIRE"
cb.hide_render = True
parent(cb, robot)
ct = cube("COLLISION_Torso", (0, 0, 0.96), (0.38, 0.24, 0.40), MAT["cyan"], COL["14_COLLISION"], 0.01)
ct.display_type = "WIRE"
ct.hide_render = True
parent(ct, robot)

for n, l in (
    ("JOINT_base_link", (0, 0, wr)),
    ("JOINT_neck_yaw", (0, 0, 1.16)),
    ("JOINT_head", (0, 0, 1.30)),
    ("JOINT_left_shoulder", (-0.22, 0, 1.08)),
    ("JOINT_right_shoulder", (0.22, 0, 1.08)),
):
    parent(empty(n, l, COL["13_JOINTS"], "ARROWS", 0.06), robot)

label("GRACEEMO-01", (0, 0, 1.52), COL["00_REFERENCE"], 0.04, MAT["cyan"]).parent = robot
ground = cube("PRESENTATION_Ground", (0, 0, -0.02), (2.2, 2.2, 0.04), MAT["dark"], COL["00_REFERENCE"], 0)

bpy.ops.object.camera_add(location=(2.2, -2.4, 1.45))
cam = bpy.context.object
cam.name = "CAMERA_Presentation"
move_to(cam, COL["00_REFERENCE"])
bpy.context.scene.camera = cam

def point_camera(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

point_camera(cam, (0, 0, 0.85))
cam.data.lens = 55

for name, loc, energy, size in (
    ("LIGHT_Key", (1.4, -1.2, 2.4), 1100, 1.5),
    ("LIGHT_Fill", (-1.4, -0.6, 1.5), 700, 1.2),
    ("LIGHT_Rim", (0, 1.0, 2.0), 900, 1.0),
):
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.size = size
    point_camera(light, (0, 0, 0.9))
    move_to(light, COL["00_REFERENCE"])

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 900
scene.render.resolution_y = 1100
scene.render.image_settings.file_format = "PNG"

try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _here = bpy.path.abspath("//") or os.getcwd()
_out_dir = os.path.join(_here, "blender")
os.makedirs(_out_dir, exist_ok=True)
preview = os.path.join(_out_dir, "GRACEEMO_preview.png")
blend = os.path.join(_out_dir, "GRACEEMO-01_Engineering_Prototype.blend")
scene.render.filepath = preview

if scene.world is None:
    scene.world = bpy.data.worlds.new("GRACEEMO World")
scene.world.use_nodes = True
_bg = scene.world.node_tree.nodes.get("Background")
if _bg:
    _bg.inputs["Color"].default_value = (0.01, 0.012, 0.018, 1.0)
    _bg.inputs["Strength"].default_value = 0.22

robot["robot_id"] = "GRACEEMO-01"
robot["role"] = "LPU campus service humanoid on a differential wheeled base"
robot["mobility"] = "Differential two-wheel drive + casters"
robot["simulation_target"] = "Gazebo / ROS 2 / digital twin"
robot["design_reference"] = "blender/reference/GRACEEMO-01.jpg"
robot["height_m"] = P["height"]

COL["14_COLLISION"].hide_viewport = True
COL["15_DEBUG"].hide_viewport = True
COL["12_CABLE_ROUTING"].hide_viewport = True

bpy.ops.wm.save_as_mainfile(filepath=blend)

def _render_preview(path, res_x, res_y):
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("Preview:", path)

def _select_robot_hierarchy(root_name="GRACEEMO-01_ROOT"):
    bpy.ops.object.select_all(action="DESELECT")
    root = bpy.data.objects.get(root_name)
    if not root:
        return False

    def walk(obj):
        obj.select_set(True)
        for ch in obj.children:
            walk(ch)

    walk(root)
    return True

def _export_robot_glb(paths):
    hide_restore = []
    for obj in bpy.data.objects:
        if obj.name.startswith(("COLLISION_", "PRESENTATION_Ground", "LABEL_")):
            hide_restore.append((obj, obj.hide_render))
            obj.hide_render = True
    if not _select_robot_hierarchy():
        print("GLB export skipped: robot root missing")
        return
    for path in paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_yup=True,
        )
        print("GLB:", path)
    for obj, was_hidden in hide_restore:
        obj.hide_render = was_hidden
    bpy.ops.object.select_all(action="DESELECT")

def _save_professional_variant():
    """Higher-res hero render + dedicated blend for marketing / docs."""
    prof_blend = os.path.join(_out_dir, "GRACEEMO-01_PROFESSIONAL_v3.blend")
    prof_preview = os.path.join(_out_dir, "GRACEEMO-01_v3_preview.png")

    cam = bpy.data.objects.get("CAMERA_Presentation")
    if cam:
        cam.data.lens = 48
        cam.location = (1.95, -2.15, 1.38)
        point_camera(cam, (0, 0, 0.88))

    for name, boost in (("LIGHT_Key", 1400), ("LIGHT_Fill", 850), ("LIGHT_Rim", 1100)):
        light = bpy.data.objects.get(name)
        if light:
            light.data.energy = boost

    if _bg:
        _bg.inputs["Strength"].default_value = 0.28

    bpy.ops.wm.save_as_mainfile(filepath=prof_blend)
    _render_preview(prof_preview, 1600, 2000)
    print("Professional blend:", prof_blend)

try:
    _render_preview(preview, 900, 1100)
except Exception as e:
    print("Preview render skipped:", e)

_mesh_dirs = [
    os.path.join(_here, "graceemo_ws", "src", "gracemo_description", "meshes"),
    os.path.join(_here, "ros2_ws", "src", "gracemo_description", "meshes"),
]
_glb_name = "GRACEEMO-01_robot.glb"
try:
    _export_robot_glb([os.path.join(d, _glb_name) for d in _mesh_dirs])
except Exception as e:
    print("GLB export skipped:", e)

try:
    _save_professional_variant()
except Exception as e:
    print("Professional variant skipped:", e)

_manifest = {
    "robot_id": "GRACEEMO-01",
    "generated_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z"),
    "height_m": P["height"],
    "wheel_radius_m": wr,
    "wheel_separation_m": sep,
    "design_reference": "blender/reference/GRACEEMO-01.jpg",
    "artifacts": {
        "engineering_blend": "blender/GRACEEMO-01_Engineering_Prototype.blend",
        "engineering_preview": "blender/GRACEEMO_preview.png",
        "professional_blend": "blender/GRACEEMO-01_PROFESSIONAL_v3.blend",
        "professional_preview": "blender/GRACEEMO-01_v3_preview.png",
        "robot_glb": [
            "graceemo_ws/src/gracemo_description/meshes/GRACEEMO-01_robot.glb",
            "ros2_ws/src/gracemo_description/meshes/GRACEEMO-01_robot.glb",
        ],
    },
}
with open(os.path.join(_out_dir, "ARTIFACTS.json"), "w", encoding="utf-8") as _mf:
    json.dump(_manifest, _mf, indent=2)
print("Manifest:", os.path.join(_out_dir, "ARTIFACTS.json"))

print("=" * 60)
print("GRACEEMO-01 generated (product-design match)")
print("Saved:", blend)
print("Height m:", P["height"], "wheel_r:", wr, "wheel_sep:", sep)
print("=" * 60)
