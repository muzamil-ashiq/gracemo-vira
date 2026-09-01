"""
GraceEMO — generate GraceEMO_LPU.blend (Blender 4.x / 5.x)

Creates:
  • LPU 200 m × 200 m campus from campus_metadata.json (Z-up, meters = ROS ENU XY)
  • GRACEEMO-01 placeholder matching gracemo.urdf.xacro links/joints
  • Sensor empties (lidar_link, camera_link, imu_link, base_footprint)
  • Collections you can sculpt, then export glTF/DAE into meshes/

Run:
  /path/to/Blender --background --python blender/scripts/build_graceemo_lpu.py
or open Blender and Scripting → Run Script.
"""
from __future__ import annotations

import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
META = os.path.join(ROOT, 'graceemo_ws', 'src', 'gracemo_gazebo', 'config', 'campus_metadata.json')
OUT = os.path.join(ROOT, 'blender', 'GraceEMO_LPU.blend')
MESH_DIR = os.path.join(ROOT, 'graceemo_ws', 'src', 'gracemo_description', 'meshes')
MESH_DIR_ROS2 = os.path.join(ROOT, 'ros2_ws', 'src', 'gracemo_description', 'meshes')

TYPE_COLOR = {
    'academic': (0.79, 0.64, 0.48, 1),
    'academic_library': (0.85, 0.77, 0.63, 1),
    'academic_research': (0.66, 0.53, 0.44, 1),
    'academic_labs': (0.60, 0.48, 0.38, 1),
    'commercial': (0.78, 0.71, 0.61, 1),
    'commercial_social': (0.75, 0.66, 0.53, 1),
    'healthcare': (0.78, 0.83, 0.87, 1),
    'residential': (0.54, 0.67, 0.52, 1),
    'sports': (0.31, 0.54, 0.27, 1),
}


def reset_scene():
    # Do not use read_homefile here — it aborts --python in background.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        if col is not bpy.context.scene.collection:
            try:
                bpy.data.collections.remove(col)
            except Exception:
                pass
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    try:
        scene.unit_settings.length_unit = 'METERS'
    except Exception:
        pass
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception:
        try:
            scene.render.engine = 'BLENDER_EEVEE'
        except Exception:
            pass
    world = bpy.data.worlds.new('LPU_World')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = next((n for n in nt.nodes if n.type == 'BACKGROUND'), None)
    if bg and bg.inputs:
        bg.inputs[0].default_value = (0.72, 0.83, 0.92, 1)
        if len(bg.inputs) > 1:
            bg.inputs[1].default_value = 0.85


def collection(name, parent=None):
    col = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(col)
    else:
        parent.children.link(col)
    return col


def mat(name, rgba, rough=0.7, metal=0.04):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = rgba
        if 'Roughness' in bsdf.inputs:
            bsdf.inputs['Roughness'].default_value = rough
        if 'Metallic' in bsdf.inputs:
            bsdf.inputs['Metallic'].default_value = metal
    return m


def link_obj(obj, col):
    col.objects.link(obj)
    obj['gracemo_asset'] = True


def add_cube(name, size, loc, col, material, origin_bottom=True):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = Vector(size)
    z = loc[2] + (size[2] / 2.0 if origin_bottom else 0.0)
    obj.location = Vector((loc[0], loc[1], z))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if obj.data.users == 1:
        obj.data.name = name + '_mesh'
    if material:
        obj.data.materials.append(material)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    link_obj(obj, col)
    return obj


def add_cylinder(name, radius, depth, loc, col, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot, vertices=24)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    link_obj(obj, col)
    return obj


def add_sphere(name, radius, loc, col, material):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=16, ring_count=8)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    link_obj(obj, col)
    return obj


def add_empty(name, loc, col, size=0.15):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = size
    e.location = loc
    link_obj(e, col)
    return e


def parent(child, parent_obj):
    child.parent = parent_obj
    child.matrix_parent_inverse = parent_obj.matrix_world.inverted()


def build_campus(data):
    campus = collection('01_Campus')
    bcol = collection('Buildings', campus)
    rcol = collection('Roads_Ground', campus)
    ecol = collection('Entrances_Empties', campus)
    scol = collection('Sports_Landscape', campus)

    grass = mat('M_Grass', (0.35, 0.52, 0.28, 1), 0.95)
    asphalt = mat('M_Asphalt', (0.22, 0.23, 0.25, 1), 0.92)
    walk = mat('M_Walk', (0.72, 0.68, 0.60, 1), 0.9)
    field = mat('M_Field', (0.28, 0.48, 0.22, 1), 0.95)
    roof = mat('M_Roof', (0.28, 0.32, 0.36, 1), 0.45, 0.12)
    plinth = mat('M_Plinth', (0.45, 0.44, 0.42, 1), 0.85)

    ground = add_cube('Ground_240m', (240, 240, 0.08), (0, 0, -0.04), rcol, grass, origin_bottom=True)
    ground.lock_scale = (True, True, True)

    for road in data.get('roads', []):
        segs = road.get('segments') or []
        w = float(road.get('width', 8))
        for i, seg in enumerate(segs):
            a, b = seg['from'], seg['to']
            dx, dy = b['x'] - a['x'], b['y'] - a['y']
            length = math.hypot(dx, dy) or 1
            ang = math.atan2(dy, dx)
            cx, cy = (a['x'] + b['x']) / 2, (a['y'] + b['y']) / 2
            obj = add_cube(f"{road['id']}_{i}", (length, w, 0.06), (cx, cy, 0.02), rcol, asphalt)
            obj.rotation_euler[2] = ang

    for path in data.get('pedestrian_paths', []):
        wps = path.get('waypoints') or []
        if len(wps) < 2:
            continue
        a, b = wps[0], wps[-1]
        dx, dy = b['x'] - a['x'], b['y'] - a['y']
        length = math.hypot(dx, dy) or 1
        ang = math.atan2(dy, dx)
        cx, cy = (a['x'] + b['x']) / 2, (a['y'] + b['y']) / 2
        w = float(path.get('width', 3))
        obj = add_cube(path['id'], (length, w, 0.04), (cx, cy, 0.03), rcol, walk)
        obj.rotation_euler[2] = ang

    field_obj = add_cube('Sports_Field', (60, 40, 0.04), (0, -70, 0.04), scol, field)
    field_obj['geometry_source'] = 'approximate'

    for b in data.get('buildings', []):
        dim = b['dimensions']
        pos = b['position']
        h = float(dim['height'])
        if h < 0.5:
            continue
        t = b.get('type', 'academic')
        m = mat(f"M_{t}", TYPE_COLOR.get(t, TYPE_COLOR['academic']))
        body = add_cube(b['id'], (float(dim['length']), float(dim['width']), h),
                        (pos['x'], pos['y'], 0.25), bcol, m)
        body['lpu_name'] = b.get('name', b['id'])
        body['lpu_type'] = t
        body['geometry_source'] = b.get('geometry_source', 'approximate')
        body['floors'] = int(b.get('floors', 1))
        add_cube(b['id'] + '_plinth', (float(dim['length']) + 0.8, float(dim['width']) + 0.8, 0.5),
                 (pos['x'], pos['y'], 0), bcol, plinth)
        add_cube(b['id'] + '_roof', (float(dim['length']) + 0.5, float(dim['width']) + 0.5, 0.4),
                 (pos['x'], pos['y'], 0.25 + h), bcol, roof)
        tag = add_empty(b.get('name', b['id']), (pos['x'], pos['y'], 0.25 + h + 2.2), ecol, 1.2)
        tag['label'] = b.get('name', b['id'])
        for ent in b.get('entrances') or []:
            ep = ent['position']
            door = add_cube(ent['id'], (2.2, 0.25, 3.0), (ep['x'], ep['y'], 0), ecol, mat('M_Door', (0.29, 0.22, 0.16, 1)))
            door['facing'] = ent.get('facing', '')


def build_robot():
    """URDF-faithful GRACEEMO-01 (white/black/cyan product design). Keep ROS empties."""
    robot = collection('02_GRACEEMO_01')
    vis = collection('Robot_Visual', robot)
    frames = collection('ROS_Frames', robot)

    dark = mat('M_RobotDark', (0.04, 0.045, 0.05, 1), 0.28, 0.55)
    white = mat('M_RobotWhite', (0.92, 0.93, 0.95, 1), 0.22, 0.08)
    cyan = mat('M_RobotCyan', (0.08, 0.78, 0.95, 1), 0.18, 0.1)
    face = mat('M_Faceplate', (0.02, 0.03, 0.04, 1), 0.12, 0.35)
    tyre = mat('M_Tyre', (0.03, 0.03, 0.03, 1), 0.72, 0.02)
    metal = mat('M_Metal', (0.35, 0.37, 0.40, 1), 0.24, 0.8)

    L, W = 0.38, 0.36
    wr, ww, wsep = 0.12, 0.08, 0.42
    caster_r = 0.045

    footprint = add_empty('base_footprint', (0, 0, 0), frames, 0.25)
    footprint['ros_link'] = 'base_footprint'

    base = add_empty('base_link', (0, 0, wr), frames, 0.2)
    base['ros_link'] = 'base_link'
    parent(base, footprint)

    lower = add_cube('chassis_lower', (L, W, 0.16), (0, 0, wr + 0.02), vis, dark, origin_bottom=False)
    parent(lower, base)
    lower.location = (0, 0, 0.02)
    mid = add_cube('chassis_mid', (0.36, 0.32, 0.12), (0, 0, wr + 0.16), vis, white, origin_bottom=False)
    parent(mid, base)
    mid.location = (0, 0, 0.16)
    bay = add_cube('chassis_sensor_bay', (0.34, 0.30, 0.12), (0, 0, wr + 0.28), vis, dark, origin_bottom=False)
    parent(bay, base)
    bay.location = (0, 0, 0.28)
    cap = add_cube('chassis_cap', (0.32, 0.28, 0.08), (0, 0, wr + 0.38), vis, white, origin_bottom=False)
    parent(cap, base)
    cap.location = (0, 0, 0.38)

    lw = add_cylinder('left_wheel', wr, ww, (0, wsep / 2, wr), vis, tyre, rot=(math.pi / 2, 0, 0))
    rw = add_cylinder('right_wheel', wr, ww, (0, -wsep / 2, wr), vis, tyre, rot=(math.pi / 2, 0, 0))
    parent(lw, base)
    parent(rw, base)
    lw['ros_joint'] = 'left_wheel_joint'
    rw['ros_joint'] = 'right_wheel_joint'

    caster = add_sphere('caster_wheel', caster_r, (-L / 2 + 0.06, 0, caster_r), vis, tyre)
    parent(caster, base)

    for name, y in (('left', 0.10), ('right', -0.10)):
        hip = add_cube(f'hip_{name}', (0.11, 0.10, 0.22), (0, y, wr + 0.50), vis, white, origin_bottom=False)
        parent(hip, base)
        hip.location = (0, y, 0.50)

    torso_e = add_empty('torso_link', (0, 0, wr + 0.84), frames, 0.1)
    torso_e['ros_link'] = 'torso_link'
    parent(torso_e, base)
    torso = add_cube('torso_visual', (0.36, 0.22, 0.36), (0, 0, wr + 0.84), vis, white, origin_bottom=False)
    parent(torso, torso_e)
    torso.location = (0, 0, 0)
    screen = add_cube('chest_display', (0.012, 0.20, 0.14), (0.116, 0, wr + 0.88), vis, mat('M_Screen', (0.06, 0.10, 0.12, 1), 0.16, 0.25), origin_bottom=False)
    parent(screen, torso_e)
    screen.location = (0.116, 0, 0.04)

    lidar_e = add_empty('lidar_link', (0.14, 0, wr + 0.42), frames, 0.08)
    lidar_e['ros_link'] = 'lidar_link'
    lidar_e['sensor'] = 'gpu_lidar'
    parent(lidar_e, base)
    lidar_m = add_cylinder('lidar_visual', 0.04, 0.035, (0.14, 0, wr + 0.42), vis, metal)
    parent(lidar_m, lidar_e)
    lidar_m.location = (0, 0, 0)

    neck = add_empty('neck_yaw_link', (0, 0, wr + 1.04), frames, 0.08)
    neck['ros_joint'] = 'neck_yaw'
    parent(neck, torso_e)
    neck.location = (0, 0, 0.20)
    neck_m = add_cylinder('neck_visual', 0.05, 0.09, (0, 0, wr + 1.085), vis, dark)
    parent(neck_m, neck)
    neck_m.location = (0, 0, 0.045)

    head = add_empty('head_link', (0, 0, wr + 1.13), frames, 0.1)
    head['ros_joint'] = 'neck_pitch'
    parent(head, neck)
    head.location = (0, 0, 0.09)
    head_m = add_sphere('head_visual', 0.13, (0, 0, wr + 1.21), vis, white)
    parent(head_m, head)
    head_m.location = (0, 0, 0.08)
    visor = add_cube('face_display', (0.012, 0.18, 0.14), (0.12, 0, wr + 1.21), vis, face, origin_bottom=False)
    parent(visor, head)
    visor.location = (0.12, 0, 0.08)
    for y in (0.045, -0.045):
        eye = add_sphere('face_eye', 0.028, (0.128, y, wr + 1.23), vis, cyan)
        parent(eye, head)
        eye.location = (0.128, y, 0.10)

    cam = add_empty('camera_link', (0.13, 0, wr + 1.27), frames, 0.06)
    cam['ros_link'] = 'camera_link'
    cam['sensor'] = 'rgb_camera'
    parent(cam, head)
    cam.location = (0.13, 0, 0.14)

    imu = add_empty('imu_link', (0, 0, wr + 0.84), frames, 0.05)
    imu['ros_link'] = 'imu_link'
    parent(imu, torso_e)
    imu.location = (0, 0, 0)

    for prefix, y in (('left', 1), ('right', -1)):
        e = add_empty(f'{prefix}_hand_link', (0, y * 0.22, wr + 0.96), frames, 0.08)
        e['ros_joint'] = f'{prefix}_hand'
        parent(e, torso_e)
        e.location = (0, y * 0.22, 0.12)
        upper = add_cylinder(f'{prefix}_upper_arm', 0.042, 0.22, (0, y * 0.22, wr + 0.84), vis, white)
        parent(upper, e)
        upper.location = (0, 0, -0.12)
        palm = add_cube(f'{prefix}_hand_visual', (0.075, 0.055, 0.09), (0, y * 0.22, wr + 0.46), vis, white, origin_bottom=False)
        parent(palm, e)
        palm.location = (0, 0, -0.50)


def build_lights_camera():
    col = collection('03_Studio')
    bpy.ops.object.light_add(type='SUN', location=(40, 50, 80))
    sun = bpy.context.active_object
    sun.name = 'Sun'
    sun.data.energy = 4.0
    sun.rotation_euler = (0.7, 0.2, 0.4)
    for c in list(sun.users_collection):
        c.objects.unlink(sun)
    link_obj(sun, col)

    bpy.ops.object.camera_add(location=(18, -22, 8), rotation=(math.radians(68), 0, math.radians(18)))
    cam = bpy.context.active_object
    cam.name = 'LookDev_Camera'
    cam.data.lens = 35
    bpy.context.scene.camera = cam
    for c in list(cam.users_collection):
        c.objects.unlink(cam)
    link_obj(cam, col)

    bpy.ops.object.camera_add(location=(0.18, 0, 0.32), rotation=(math.radians(90), 0, math.radians(90)))
    rcam = bpy.context.active_object
    rcam.name = 'Robot_HeadCam_Preview'
    rcam.data.lens = 22
    rcam.data.sensor_width = 36
    for c in list(rcam.users_collection):
        c.objects.unlink(rcam)
    link_obj(rcam, col)
    head = bpy.data.objects.get('head_link')
    if head:
        parent(rcam, head)
        rcam.location = (0.08, 0, 0.06)


def write_readme_text():
    body = """GraceEMO_LPU.blend — how to create the real assets
================================================

UNITS: meters. XY = ROS ENU (x east, y north). Z up.

CAMPUS
  Buildings are LOD0 boxes from campus_metadata.json (geometry_source=approximate).
  Sculpt facades, windows, roofs as children of each building id (block_34, …).
  Keep object origin at footprint center, Z=0 at ground.
  Do not treat sizes as surveyed GIS.

ROBOT (URDF)
  Keep ROS_Frames empties. Replace *_visual meshes only.
  Product look: white shells, black actuators, cyan LEDs, chest status display.
  Height ~1.37 m. Wheels: radius 0.12 m, separation 0.42 m.
  Joints: left_wheel_joint, right_wheel_joint, neck_yaw, neck_pitch, left_hand, right_hand.
  Export visual meshes to:
    graceemo_ws/src/gracemo_description/meshes/
  Suggested: glTF (robot.glb) + collision convex hulls as *_collision.stl

HERO GUIDE
  Wire cubes in Robot_HeroSculpt_Optional are a larger VC-style proportion sketch.
  Do not export those as Gazebo collision unless you update the URDF.

EXPORT
  File → Export → glTF 2.0 (selected visual meshes).
  For Gazebo: DAE or STL per link, then set <mesh filename=\"package://gracemo_description/meshes/...\"/> in xacro.
"""
    txt = bpy.data.texts.new('README_GraceEMO')
    txt.write(body)


def export_gltf_preview():
    os.makedirs(MESH_DIR, exist_ok=True)
    os.makedirs(MESH_DIR_ROS2, exist_ok=True)
    preview = os.path.join(os.path.dirname(OUT), 'GraceEMO_LPU_preview.glb')
    bpy.ops.export_scene.gltf(filepath=preview, export_format='GLB', export_apply=True)
    print('Campus GLB:', preview)


def export_robot_glb():
    robot_col = bpy.data.collections.get('02_GRACEEMO_01')
    if not robot_col:
        print('Robot GLB skipped: 02_GRACEEMO_01 missing')
        return
    bpy.ops.object.select_all(action='DESELECT')
    for obj in robot_col.all_objects:
        if obj.type == 'MESH':
            obj.select_set(True)
    if not bpy.context.selected_objects:
        print('Robot GLB skipped: no mesh objects')
        return
    glb_name = 'GRACEEMO-01_campus_robot.glb'
    for mesh_dir in (MESH_DIR, MESH_DIR_ROS2):
        os.makedirs(mesh_dir, exist_ok=True)
        path = os.path.join(mesh_dir, glb_name)
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format='GLB',
            use_selection=True,
            export_apply=True,
            export_yup=True,
        )
        print('Robot GLB:', path)
    bpy.ops.object.select_all(action='DESELECT')


def render_campus_preview():
    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.file_format = 'PNG'
    png = os.path.join(os.path.dirname(OUT), 'GraceEMO_LPU_preview.png')
    scene.render.filepath = png
    bpy.ops.render.render(write_still=True)
    print('Campus preview:', png)


def write_artifact_manifest():
    manifest_path = os.path.join(os.path.dirname(OUT), 'ARTIFACTS.json')
    existing = {}
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding='utf-8') as f:
            existing = json.load(f)
    existing.setdefault('robot_id', 'GRACEEMO-01')
    existing['campus_generated_utc'] = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat().replace('+00:00', 'Z')
    existing.setdefault('campus_artifacts', {})
    existing['campus_artifacts'].update({
        'campus_blend': 'blender/GraceEMO_LPU.blend',
        'campus_glb': 'blender/GraceEMO_LPU_preview.glb',
        'campus_preview_png': 'blender/GraceEMO_LPU_preview.png',
        'campus_robot_glb': [
            'graceemo_ws/src/gracemo_description/meshes/GRACEEMO-01_campus_robot.glb',
            'ros2_ws/src/gracemo_description/meshes/GRACEEMO-01_campus_robot.glb',
        ],
    })
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2)
    print('Manifest updated:', manifest_path)


def main():
    if not os.path.isfile(META):
        print('Missing campus_metadata.json', META, file=sys.stderr)
        sys.exit(1)
    with open(META, encoding='utf-8') as f:
        data = json.load(f)

    reset_scene()
    build_campus(data)
    build_robot()
    build_lights_camera()
    write_readme_text()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    try:
        export_gltf_preview()
    except Exception as e:
        print('glTF preview skipped:', e)
    try:
        export_robot_glb()
    except Exception as e:
        print('Robot GLB skipped:', e)
    try:
        render_campus_preview()
    except Exception as e:
        print('Campus preview skipped:', e)
    try:
        write_artifact_manifest()
    except Exception as e:
        print('Manifest skipped:', e)
    print('Wrote', OUT)


if __name__ == '__main__':
    main()
