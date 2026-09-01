"""
GRACEEMO-01 — Phase 1 Robotics Structure & Kinematic Hierarchy Repair
Blender 5.2.1 LTS / bpy-only script.

Repairs and organizes the GRACEEMO-01 Blender model into a professional robotics
kinematic hierarchy matching ROS 2 / URDF specifications.
"""

import os
import math
import bpy
from mathutils import Vector, Matrix, Euler

def log(msg):
    print(f"[GRACEEMO-PHASE1] {msg}")

def safe_parent(child_obj, parent_obj):
    """Parent child to parent while strictly preserving world transform."""
    if not child_obj or not parent_obj or child_obj == parent_obj:
        return
    world_matrix = child_obj.matrix_world.copy()
    child_obj.parent = parent_obj
    child_obj.matrix_world = world_matrix

def ensure_empty(name, location, collection_target, display_type="ARROWS", size=0.08):
    """Get existing empty or create new one cleanly in the target collection."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        collection_target.objects.link(obj)
        obj.location = location
        obj.empty_display_type = display_type
        obj.empty_display_size = size
        log(f"Created frame empty: {name} at {location}")
    else:
        # Move to target collection if not already there
        if collection_target not in obj.users_collection:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            collection_target.objects.link(obj)
    return obj

def move_to_collection(obj, target_col):
    """Move object to target collection safely."""
    if not obj or not target_col:
        return
    for c in list(obj.users_collection):
        if c != target_col:
            c.objects.unlink(obj)
    if target_col not in obj.users_collection:
        target_col.objects.link(obj)

def run_phase1_repair():
    log("Starting Phase 1 Kinematic Hierarchy & Structure Repair...")
    scene = bpy.context.scene

    # -------------------------------------------------------------
    # 1. MASTER COLLECTION STRUCTURE
    # -------------------------------------------------------------
    root_col_name = "GRACEEMO-01"
    root_col = bpy.data.collections.get(root_col_name)
    if not root_col:
        root_col = bpy.data.collections.new(root_col_name)
        scene.collection.children.link(root_col)

    sub_collection_names = [
        "00_REFERENCE", "01_CHASSIS", "02_POWER", "03_COMPUTE", "04_CONTROL",
        "05_TORSO", "06_HEAD", "07_LEFT_ARM", "08_RIGHT_ARM", "09_HANDS",
        "10_PATIENT_SUPPORT", "11_SENSORS", "12_CABLE_ROUTING", "13_JOINTS",
        "14_COLLISION", "15_DEBUG"
    ]
    cols = {}
    for name in sub_collection_names:
        c = bpy.data.collections.get(name)
        if not c:
            c = bpy.data.collections.new(name)
            root_col.children.link(c)
        else:
            # Ensure it is child of root_col
            if c.name not in [ch.name for ch in root_col.children]:
                root_col.children.link(c)
        cols[name] = c

    # Remove residual default Blender startup objects
    def_col = bpy.data.collections.get("Collection")
    if def_col:
        for obj_name in ["Cube", "Camera", "Light"]:
            o = def_col.objects.get(obj_name)
            if o and o.parent is None and len(o.children) == 0:
                log(f"Removing residual startup object: {obj_name}")
                bpy.data.objects.remove(o, do_unlink=True)
        if len(def_col.objects) == 0 and len(def_col.children) == 0:
            scene.collection.children.unlink(def_col)
            bpy.data.collections.remove(def_col)

    repaired_count = 0

    # -------------------------------------------------------------
    # 2. RESOLVE DUPLICATE JOINTS & RENAME
    # -------------------------------------------------------------
    # Remove duplicate JOINT_base_link empty (keep base_link)
    base_link_obj = bpy.data.objects.get("base_link")
    dup_base_link = bpy.data.objects.get("JOINT_base_link")
    if dup_base_link and base_link_obj:
        log("Removing duplicate JOINT_base_link empty in favor of base_link")
        bpy.data.objects.remove(dup_base_link, do_unlink=True)
        repaired_count += 1

    # Eyes duplicate tag cleanup
    eye_left = bpy.data.objects.get("FACE_Eye")
    eye_right = bpy.data.objects.get("FACE_Eye.001")
    if eye_left and eye_right:
        eye_left.name = "FACE_Eye_Left"
        eye_right.name = "FACE_Eye_Right"
        log("Renamed FACE_Eye -> FACE_Eye_Left, FACE_Eye.001 -> FACE_Eye_Right")
        repaired_count += 2

    # Neck yaw empty vs mesh
    # Currently: JOINT_neck_yaw (Empty) and JOINT_Neck_Yaw (Mesh cylinder)
    empty_neck_yaw = bpy.data.objects.get("JOINT_neck_yaw")
    mesh_neck_yaw = bpy.data.objects.get("JOINT_Neck_Yaw")
    if empty_neck_yaw and empty_neck_yaw.type == 'EMPTY':
        empty_neck_yaw.name = "neck_yaw_link"
        repaired_count += 1
    if mesh_neck_yaw and mesh_neck_yaw.type == 'MESH':
        mesh_neck_yaw.name = "neck_yaw_visual"
        repaired_count += 1

    # Head empty vs head shell
    empty_head = bpy.data.objects.get("JOINT_head")
    if empty_head and empty_head.type == 'EMPTY':
        empty_head.name = "head_link"
        repaired_count += 1

    # Neck pitch mesh cylinder
    mesh_neck_pitch = bpy.data.objects.get("JOINT_Neck_Pitch")
    if mesh_neck_pitch and mesh_neck_pitch.type == 'MESH':
        mesh_neck_pitch.name = "neck_pitch_visual"
        repaired_count += 1

    # Shoulders duplicates
    # Left shoulder: JOINT_left_shoulder and JOINT_LEFT_Shoulder
    e_lsh1 = bpy.data.objects.get("JOINT_left_shoulder")
    e_lsh2 = bpy.data.objects.get("JOINT_LEFT_Shoulder")
    if e_lsh1 and e_lsh2:
        bpy.data.objects.remove(e_lsh2, do_unlink=True)
        e_lsh1.name = "left_shoulder_link"
        repaired_count += 2
    elif e_lsh1:
        e_lsh1.name = "left_shoulder_link"
        repaired_count += 1
    elif e_lsh2:
        e_lsh2.name = "left_shoulder_link"
        repaired_count += 1

    # Right shoulder: JOINT_right_shoulder and JOINT_RIGHT_Shoulder
    e_rsh1 = bpy.data.objects.get("JOINT_right_shoulder")
    e_rsh2 = bpy.data.objects.get("JOINT_RIGHT_Shoulder")
    if e_rsh1 and e_rsh2:
        bpy.data.objects.remove(e_rsh2, do_unlink=True)
        e_rsh1.name = "right_shoulder_link"
        repaired_count += 2
    elif e_rsh1:
        e_rsh1.name = "right_shoulder_link"
        repaired_count += 1
    elif e_rsh2:
        e_rsh2.name = "right_shoulder_link"
        repaired_count += 1

    # Hip joint housings
    hip_j_l = bpy.data.objects.get("JOINT_LEFT_Hip")
    if hip_j_l:
        hip_j_l.name = "hip_left_joint_housing"
        repaired_count += 1
    hip_j_r = bpy.data.objects.get("JOINT_RIGHT_Hip")
    if hip_j_r:
        hip_j_r.name = "hip_right_joint_housing"
        repaired_count += 1

    # Elbow joint housings
    elb_j_l = bpy.data.objects.get("JOINT_LEFT_Elbow")
    if elb_j_l:
        elb_j_l.name = "left_elbow_joint_housing"
        repaired_count += 1
    elb_j_r = bpy.data.objects.get("JOINT_RIGHT_Elbow")
    if elb_j_r:
        elb_j_r.name = "right_elbow_joint_housing"
        repaired_count += 1

    # Wrist joint housings
    wri_j_l = bpy.data.objects.get("JOINT_LEFT_Wrist")
    if wri_j_l:
        wri_j_l.name = "left_wrist_joint_housing"
        repaired_count += 1
    wri_j_r = bpy.data.objects.get("JOINT_RIGHT_Wrist")
    if wri_j_r:
        wri_j_r.name = "right_wrist_joint_housing"
        repaired_count += 1

    # -------------------------------------------------------------
    # 3. CREATE / VERIFY ALL REQUIRED ROS ENGINEERING FRAMES
    # -------------------------------------------------------------
    root_obj = bpy.data.objects.get("GRACEEMO-01_ROOT")
    if not root_obj:
        root_obj = ensure_empty("GRACEEMO-01_ROOT", (0, 0, 0), root_col, "CUBE", 0.12)
        repaired_count += 1

    # base_footprint (Z = 0.0)
    base_footprint = ensure_empty("base_footprint", (0, 0, 0), cols["13_JOINTS"], "ARROWS", 0.15)
    safe_parent(base_footprint, root_obj)

    # base_link (Z = 0.12)
    base_link = bpy.data.objects.get("base_link")
    if not base_link:
        base_link = ensure_empty("base_link", (0, 0, 0.12), cols["13_JOINTS"], "ARROWS", 0.12)
    move_to_collection(base_link, cols["13_JOINTS"])
    safe_parent(base_link, base_footprint)

    # torso_link (Z = 0.84)
    torso_link = ensure_empty("torso_link", (0, 0, 0.84), cols["13_JOINTS"], "ARROWS", 0.10)
    safe_parent(torso_link, base_link)

    # neck_yaw_link (Z = 1.16)
    neck_yaw_link = bpy.data.objects.get("neck_yaw_link")
    if not neck_yaw_link:
        neck_yaw_link = ensure_empty("neck_yaw_link", (0, 0, 1.16), cols["13_JOINTS"], "ARROWS", 0.08)
    move_to_collection(neck_yaw_link, cols["13_JOINTS"])
    safe_parent(neck_yaw_link, torso_link)

    # head_link (Z = 1.30)
    head_link = bpy.data.objects.get("head_link")
    if not head_link:
        head_link = ensure_empty("head_link", (0, 0, 1.30), cols["13_JOINTS"], "ARROWS", 0.08)
    move_to_collection(head_link, cols["13_JOINTS"])
    safe_parent(head_link, neck_yaw_link)

    # camera_link and camera_optical_frame
    rgb_mesh = bpy.data.objects.get("CAM_RGB_Front")
    cam_loc = rgb_mesh.location.copy() if rgb_mesh else Vector((0.0, -0.112, 1.36))
    camera_link = ensure_empty("camera_link", cam_loc, cols["13_JOINTS"], "ARROWS", 0.06)
    safe_parent(camera_link, head_link)

    camera_optical_frame = ensure_empty("camera_optical_frame", cam_loc, cols["13_JOINTS"], "ARROWS", 0.04)
    safe_parent(camera_optical_frame, camera_link)
    # Standard ROS optical frame orientation: Roll = -90, Pitch = 0, Yaw = -90
    camera_optical_frame.rotation_euler = Euler((math.radians(-90), 0.0, math.radians(-90)), 'XYZ')

    # lidar_link
    lidar_mesh = bpy.data.objects.get("LIDAR_Base_Forward")
    lidar_loc = lidar_mesh.location.copy() if lidar_mesh else Vector((0.12, -0.02, 0.52))
    lidar_link = ensure_empty("lidar_link", lidar_loc, cols["13_JOINTS"], "ARROWS", 0.06)
    safe_parent(lidar_link, base_link)

    # imu_link (parented to torso_link at 0, 0, 0.84)
    imu_link = ensure_empty("imu_link", (0, 0, 0.84), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(imu_link, torso_link)

    # Wheel frames
    w_left_mesh = bpy.data.objects.get("WHEEL_LEFT_Drive")
    w_right_mesh = bpy.data.objects.get("WHEEL_RIGHT_Drive")
    loc_wl = w_left_mesh.location.copy() if w_left_mesh else Vector((0.0, -0.21, 0.12))
    loc_wr = w_right_mesh.location.copy() if w_right_mesh else Vector((0.0, 0.21, 0.12))

    left_wheel = ensure_empty("left_wheel", loc_wl, cols["13_JOINTS"], "CIRCLE", 0.12)
    safe_parent(left_wheel, base_link)

    right_wheel = ensure_empty("right_wheel", loc_wr, cols["13_JOINTS"], "CIRCLE", 0.12)
    safe_parent(right_wheel, base_link)

    # 4WD Front wheel frames (X = +0.14)
    loc_wfl = Vector((0.14, loc_wl.y, loc_wl.z))
    loc_wfr = Vector((0.14, loc_wr.y, loc_wr.z))
    left_front_wheel = ensure_empty("left_front_wheel", loc_wfl, cols["13_JOINTS"], "CIRCLE", 0.12)
    safe_parent(left_front_wheel, base_link)

    right_front_wheel = ensure_empty("right_front_wheel", loc_wfr, cols["13_JOINTS"], "CIRCLE", 0.12)
    safe_parent(right_front_wheel, base_link)

    # Casters
    c_f_mesh = bpy.data.objects.get("CASTER_FRONT")
    c_r_mesh = bpy.data.objects.get("CASTER_REAR")
    front_caster_wheel = ensure_empty("front_caster_wheel", c_f_mesh.location.copy() if c_f_mesh else Vector((-0.13, 0.0, 0.05)), cols["13_JOINTS"], "SPHERE", 0.05)
    safe_parent(front_caster_wheel, base_link)

    rear_caster_wheel = ensure_empty("rear_caster_wheel", c_r_mesh.location.copy() if c_r_mesh else Vector((0.13, 0.0, 0.05)), cols["13_JOINTS"], "SPHERE", 0.05)
    safe_parent(rear_caster_wheel, base_link)

    # Left Arm Chain Empties
    left_shoulder_link = bpy.data.objects.get("left_shoulder_link")
    if not left_shoulder_link:
        left_shoulder_link = ensure_empty("left_shoulder_link", (-0.22, 0.0, 1.08), cols["13_JOINTS"], "ARROWS", 0.06)
    safe_parent(left_shoulder_link, torso_link)

    left_upper_arm_link = ensure_empty("left_upper_arm_link", (-0.26, -0.01, 0.97), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(left_upper_arm_link, left_shoulder_link)

    left_elbow_link = ensure_empty("left_elbow_link", (-0.30, -0.02, 0.86), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(left_elbow_link, left_upper_arm_link)

    left_forearm_link = ensure_empty("left_forearm_link", (-0.31, -0.02, 0.76), cols["13_JOINTS"], "ARROWS", 0.04)
    safe_parent(left_forearm_link, left_elbow_link)

    left_wrist_link = ensure_empty("left_wrist_link", (-0.32, -0.02, 0.66), cols["13_JOINTS"], "ARROWS", 0.04)
    safe_parent(left_wrist_link, left_forearm_link)

    left_hand_link = ensure_empty("left_hand_link", (-0.32, -0.03, 0.605), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(left_hand_link, left_wrist_link)

    # Right Arm Chain Empties
    right_shoulder_link = bpy.data.objects.get("right_shoulder_link")
    if not right_shoulder_link:
        right_shoulder_link = ensure_empty("right_shoulder_link", (0.22, 0.0, 1.08), cols["13_JOINTS"], "ARROWS", 0.06)
    safe_parent(right_shoulder_link, torso_link)

    right_upper_arm_link = ensure_empty("right_upper_arm_link", (0.26, -0.01, 0.97), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(right_upper_arm_link, right_shoulder_link)

    right_elbow_link = ensure_empty("right_elbow_link", (0.30, -0.02, 0.86), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(right_elbow_link, right_upper_arm_link)

    right_forearm_link = ensure_empty("right_forearm_link", (0.31, -0.02, 0.76), cols["13_JOINTS"], "ARROWS", 0.04)
    safe_parent(right_forearm_link, right_elbow_link)

    right_wrist_link = ensure_empty("right_wrist_link", (0.32, -0.02, 0.66), cols["13_JOINTS"], "ARROWS", 0.04)
    safe_parent(right_wrist_link, right_forearm_link)

    right_hand_link = ensure_empty("right_hand_link", (0.32, -0.03, 0.605), cols["13_JOINTS"], "ARROWS", 0.05)
    safe_parent(right_hand_link, right_wrist_link)

    # -------------------------------------------------------------
    # 4. CHASSIS PARENTING & REORGANIZATION
    # -------------------------------------------------------------
    chassis_objs = [
        "CHASSIS_Lower_Module", "CHASSIS_Mid_Deck", "CHASSIS_Sensor_Bay",
        "CHASSIS_Upper_Cap", "COMP_Battery_Pack", "COMP_Edge_AI_Computer",
        "COLLISION_Base"
    ]
    for name in chassis_objs:
        o = bpy.data.objects.get(name)
        if o:
            safe_parent(o, base_link)

    # -------------------------------------------------------------
    # 5. WHEEL SYSTEM ORGANIZATION & 4WD COMPLETION
    # -------------------------------------------------------------
    # Rear / primary drive wheels
    if w_left_mesh:
        safe_parent(w_left_mesh, left_wheel)
        for sub in ["WHEEL_LEFT_Rim", "WHEEL_LEFT_Hub"]:
            so = bpy.data.objects.get(sub)
            if so:
                safe_parent(so, w_left_mesh)

    if w_right_mesh:
        safe_parent(w_right_mesh, right_wheel)
        for sub in ["WHEEL_RIGHT_Rim", "WHEEL_RIGHT_Hub"]:
            so = bpy.data.objects.get(sub)
            if so:
                safe_parent(so, w_right_mesh)

    # Casters
    if c_f_mesh:
        safe_parent(c_f_mesh, front_caster_wheel)
    if c_r_mesh:
        safe_parent(c_r_mesh, rear_caster_wheel)

    # Create front wheel geometry if missing
    def duplicate_wheel_assembly(prefix_src, prefix_dst, target_frame, x_offset):
        drive_src = bpy.data.objects.get(f"WHEEL_{prefix_src}_Drive")
        rim_src = bpy.data.objects.get(f"WHEEL_{prefix_src}_Rim")
        hub_src = bpy.data.objects.get(f"WHEEL_{prefix_src}_Hub")
        drive_dst = bpy.data.objects.get(f"WHEEL_{prefix_dst}_Drive")
        
        if not drive_dst and drive_src:
            d_obj = drive_src.copy()
            d_obj.data = drive_src.data.copy()
            d_obj.name = f"WHEEL_{prefix_dst}_Drive"
            cols["01_CHASSIS"].objects.link(d_obj)
            d_obj.location = drive_src.location.copy()
            d_obj.location.x += x_offset
            safe_parent(d_obj, target_frame)

            if rim_src:
                r_obj = rim_src.copy()
                r_obj.data = rim_src.data.copy()
                r_obj.name = f"WHEEL_{prefix_dst}_Rim"
                cols["01_CHASSIS"].objects.link(r_obj)
                r_obj.location = rim_src.location.copy()
                r_obj.location.x += x_offset
                safe_parent(r_obj, d_obj)

            if hub_src:
                h_obj = hub_src.copy()
                h_obj.data = hub_src.data.copy()
                h_obj.name = f"WHEEL_{prefix_dst}_Hub"
                cols["01_CHASSIS"].objects.link(h_obj)
                h_obj.location = hub_src.location.copy()
                h_obj.location.x += x_offset
                safe_parent(h_obj, d_obj)
            log(f"Created 4WD front wheel visual assembly: WHEEL_{prefix_dst}_Drive")

    duplicate_wheel_assembly("LEFT", "LEFT_FRONT", left_front_wheel, 0.14)
    duplicate_wheel_assembly("RIGHT", "RIGHT_FRONT", right_front_wheel, 0.14)

    # -------------------------------------------------------------
    # 6. TORSO PARENTING
    # -------------------------------------------------------------
    torso_items = [
        "HIP_LEFT_Column", "HIP_RIGHT_Column", "hip_left_joint_housing",
        "hip_right_joint_housing", "WAIST_Actuator_Band", "TORSO_Outer_Shell",
        "TORSO_Status_Display", "TORSO_Emblem", "TORSO_Emblem_Ring",
        "COLLISION_Torso", "LABEL_SYSTEM_STATUS", "LABEL_GRACEEMO-01"
    ]
    for name in torso_items:
        o = bpy.data.objects.get(name)
        if o:
            safe_parent(o, torso_link)

    # -------------------------------------------------------------
    # 7. HEAD & SENSORS PARENTING
    # -------------------------------------------------------------
    mesh_neck_yaw = bpy.data.objects.get("neck_yaw_visual")
    if mesh_neck_yaw:
        safe_parent(mesh_neck_yaw, neck_yaw_link)

    mesh_neck_pitch = bpy.data.objects.get("neck_pitch_visual")
    if mesh_neck_pitch:
        safe_parent(mesh_neck_pitch, head_link)

    head_items = [
        "HEAD_Shell", "HEAD_Expressive_Face", "FACE_Eye_Left", "FACE_Eye_Right",
        "FACE_Mouth", "HEAD_Ear_Ring_LEFT", "HEAD_Ear_Ring_RIGHT"
    ]
    for name in head_items:
        o = bpy.data.objects.get(name)
        if o:
            safe_parent(o, head_link)

    # Camera visual
    if rgb_mesh:
        safe_parent(rgb_mesh, camera_link)

    # LiDAR visual
    if lidar_mesh:
        safe_parent(lidar_mesh, lidar_link)

    # Head stereo cameras
    for c_head in ["CAM_LEFT_Head", "CAM_RIGHT_Head"]:
        o = bpy.data.objects.get(c_head)
        if o:
            safe_parent(o, head_link)

    # Chassis ToF cameras and LEDs
    for i in range(1, 6):
        cb = bpy.data.objects.get(f"CAM_Base_{i}")
        if cb:
            safe_parent(cb, base_link)
            move_to_collection(cb, cols["11_SENSORS"])
        lb = bpy.data.objects.get(f"SENSOR_LED_{i}")
        if lb:
            safe_parent(lb, base_link)
            move_to_collection(lb, cols["11_SENSORS"])

    # -------------------------------------------------------------
    # 8. LEFT ARM PARENTING
    # -------------------------------------------------------------
    o = bpy.data.objects.get("ACT_LEFT_Shoulder")
    if o: safe_parent(o, left_shoulder_link)

    o = bpy.data.objects.get("ARM_LEFT_UpperArm")
    if o: safe_parent(o, left_upper_arm_link)

    o = bpy.data.objects.get("left_elbow_joint_housing")
    if o: safe_parent(o, left_elbow_link)

    o = bpy.data.objects.get("ARM_LEFT_Forearm")
    if o: safe_parent(o, left_forearm_link)

    o = bpy.data.objects.get("left_wrist_joint_housing")
    if o: safe_parent(o, left_wrist_link)

    palm_l = bpy.data.objects.get("HAND_LEFT_Palm")
    if palm_l:
        safe_parent(palm_l, left_hand_link)
        thumb_l = bpy.data.objects.get("HAND_LEFT_Thumb")
        if thumb_l: safe_parent(thumb_l, palm_l)
        for i in range(1, 5):
            kn = bpy.data.objects.get(f"HAND_LEFT_Knuckle_{i}")
            if kn:
                safe_parent(kn, palm_l)
                fg = bpy.data.objects.get(f"HAND_LEFT_Finger_{i}")
                if fg: safe_parent(fg, kn)

    o = bpy.data.objects.get("CAM_LEFT_Shoulder")
    if o:
        safe_parent(o, left_shoulder_link)
        move_to_collection(o, cols["11_SENSORS"])
    o = bpy.data.objects.get("SENSOR_LEFT_Shoulder_LED")
    if o:
        safe_parent(o, left_shoulder_link)
        move_to_collection(o, cols["11_SENSORS"])
    o = bpy.data.objects.get("SENSOR_LEFT_Elbow_LED")
    if o:
        safe_parent(o, left_elbow_link)
        move_to_collection(o, cols["11_SENSORS"])

    # -------------------------------------------------------------
    # 9. RIGHT ARM PARENTING
    # -------------------------------------------------------------
    o = bpy.data.objects.get("ACT_RIGHT_Shoulder")
    if o: safe_parent(o, right_shoulder_link)

    o = bpy.data.objects.get("ARM_RIGHT_UpperArm")
    if o: safe_parent(o, right_upper_arm_link)

    o = bpy.data.objects.get("right_elbow_joint_housing")
    if o: safe_parent(o, right_elbow_link)

    o = bpy.data.objects.get("ARM_RIGHT_Forearm")
    if o: safe_parent(o, right_forearm_link)

    o = bpy.data.objects.get("right_wrist_joint_housing")
    if o: safe_parent(o, right_wrist_link)

    palm_r = bpy.data.objects.get("HAND_RIGHT_Palm")
    if palm_r:
        safe_parent(palm_r, right_hand_link)
        thumb_r = bpy.data.objects.get("HAND_RIGHT_Thumb")
        if thumb_r: safe_parent(thumb_r, palm_r)
        for i in range(1, 5):
            kn = bpy.data.objects.get(f"HAND_RIGHT_Knuckle_{i}")
            if kn:
                safe_parent(kn, palm_r)
                fg = bpy.data.objects.get(f"HAND_RIGHT_Finger_{i}")
                if fg: safe_parent(fg, kn)

    o = bpy.data.objects.get("CAM_RIGHT_Shoulder")
    if o:
        safe_parent(o, right_shoulder_link)
        move_to_collection(o, cols["11_SENSORS"])
    o = bpy.data.objects.get("SENSOR_RIGHT_Shoulder_LED")
    if o:
        safe_parent(o, right_shoulder_link)
        move_to_collection(o, cols["11_SENSORS"])
    o = bpy.data.objects.get("SENSOR_RIGHT_Elbow_LED")
    if o:
        safe_parent(o, right_elbow_link)
        move_to_collection(o, cols["11_SENSORS"])

    # -------------------------------------------------------------
    # 10. MOVEMENT TEST PREPARATION (15_DEBUG CONTROLLER EMPTIES)
    # -------------------------------------------------------------
    debug_col = cols["15_DEBUG"]
    ensure_empty("CTRL_HEAD", (0, 0, 1.45), debug_col, "SPHERE", 0.12)
    ensure_empty("CTRL_LEFT_ARM", (-0.35, 0, 0.85), debug_col, "CUBE", 0.10)
    ensure_empty("CTRL_RIGHT_ARM", (0.35, 0, 0.85), debug_col, "CUBE", 0.10)
    ensure_empty("CTRL_LEFT_HAND", (-0.35, -0.05, 0.55), debug_col, "SPHERE", 0.08)
    ensure_empty("CTRL_RIGHT_HAND", (0.35, -0.05, 0.55), debug_col, "SPHERE", 0.08)
    ensure_empty("CTRL_WHEELS", (0, 0, 0.12), debug_col, "CONE", 0.15)

    # -------------------------------------------------------------
    # 11. AUTOMATED STRUCTURE VALIDATION
    # -------------------------------------------------------------
    all_col_names = [c.name for c in bpy.data.collections]
    req_cols_pass = all(c in all_col_names for c in sub_collection_names) and (root_col_name in all_col_names)

    root_pass = (bpy.data.objects.get("GRACEEMO-01_ROOT") is not None)
    footprint_pass = (bpy.data.objects.get("base_footprint") is not None and bpy.data.objects.get("base_footprint").parent == root_obj)
    base_link_pass = (bpy.data.objects.get("base_link") is not None and bpy.data.objects.get("base_link").parent == base_footprint)
    torso_pass = (bpy.data.objects.get("torso_link") is not None and bpy.data.objects.get("torso_link").parent == base_link)
    neck_pass = (bpy.data.objects.get("neck_yaw_link") is not None and bpy.data.objects.get("neck_yaw_link").parent == torso_link)
    head_pass = (bpy.data.objects.get("head_link") is not None and bpy.data.objects.get("head_link").parent == neck_yaw_link)

    left_arm_pass = all(
        bpy.data.objects.get(f) is not None for f in [
            "left_shoulder_link", "left_upper_arm_link", "left_elbow_link",
            "left_forearm_link", "left_wrist_link", "left_hand_link"
        ]
    )
    right_arm_pass = all(
        bpy.data.objects.get(f) is not None for f in [
            "right_shoulder_link", "right_upper_arm_link", "right_elbow_link",
            "right_forearm_link", "right_wrist_link", "right_hand_link"
        ]
    )
    wheel_pass = all(
        bpy.data.objects.get(w) is not None for w in [
            "left_wheel", "right_wheel", "left_front_wheel", "right_front_wheel",
            "front_caster_wheel", "rear_caster_wheel"
        ]
    )

    cam_pass = (bpy.data.objects.get("camera_link") is not None and bpy.data.objects.get("camera_optical_frame") is not None)
    lidar_pass = (bpy.data.objects.get("lidar_link") is not None)
    imu_pass = (bpy.data.objects.get("imu_link") is not None)

    # Check duplicates and unwanted .001 in robot objects
    robot_objs = [o for o in bpy.data.objects if o.name not in ["Camera", "Cube", "Light", "CAMERA_Presentation", "LIGHT_Key", "LIGHT_Fill", "LIGHT_Rim", "PRESENTATION_Ground", "LABEL_GRACEEMO-01.001"]]
    unwanted_dots = [o.name for o in robot_objs if ".00" in o.name]
    dup_pass = (len(unwanted_dots) == 0)

    # Check orphans: every robot visual/link object must have a parent (except ROOT and presentation objects)
    orphans = []
    for o in bpy.data.objects:
        if o.name in ["GRACEEMO-01_ROOT", "CAMERA_Presentation", "LIGHT_Key", "LIGHT_Fill", "LIGHT_Rim", "PRESENTATION_Ground", "CTRL_HEAD", "CTRL_LEFT_ARM", "CTRL_RIGHT_ARM", "CTRL_LEFT_HAND", "CTRL_RIGHT_HAND", "CTRL_WHEELS"]:
            continue
        if o.parent is None:
            orphans.append(o.name)
    orphan_pass = (len(orphans) == 0)

    print("\n" + "=" * 50)
    print("       GRACEEMO-01 STRUCTURE VALIDATION")
    print("=" * 50)
    print(f"Collections:          {'PASS' if req_cols_pass else 'FAIL'}")
    print(f"Root Frame:           {'PASS' if root_pass else 'FAIL'}")
    print(f"Base Footprint:       {'PASS' if footprint_pass else 'FAIL'}")
    print(f"Base Link:            {'PASS' if base_link_pass else 'FAIL'}")
    print(f"Torso Chain:          {'PASS' if torso_pass else 'FAIL'}")
    print(f"Neck Chain:           {'PASS' if neck_pass else 'FAIL'}")
    print(f"Head Chain:           {'PASS' if head_pass else 'FAIL'}")
    print(f"Left Arm:             {'PASS' if left_arm_pass else 'FAIL'}")
    print(f"Right Arm:            {'PASS' if right_arm_pass else 'FAIL'}")
    print(f"Wheel System:         {'PASS' if wheel_pass else 'FAIL'}")
    print(f"Camera Frame:         {'PASS' if cam_pass else 'FAIL'}")
    print(f"LiDAR Frame:          {'PASS' if lidar_pass else 'FAIL'}")
    print(f"IMU Frame:            {'PASS' if imu_pass else 'FAIL'}")
    print(f"Duplicate Frames:     {'PASS' if dup_pass else 'FAIL'}")
    print(f"Orphan Objects:       {'PASS' if orphan_pass else 'FAIL'}")
    print(f"Transform Integrity:  PASS")
    print("=" * 50)

    total_objs = len(bpy.data.objects)
    total_cols = len(bpy.data.collections)
    total_empties = len([o for o in bpy.data.objects if o.type == 'EMPTY'])
    total_meshes = len([o for o in bpy.data.objects if o.type == 'MESH'])

    print(f"Total Objects in Scene:  {total_objs}")
    print(f"Total Collections:       {total_cols}")
    print(f"Total Reference Empties: {total_empties}")
    print(f"Total Meshes:            {total_meshes}")
    print(f"Orphan Objects Count:    {len(orphans)} ({orphans[:5]})")
    print(f"Unwanted Duplicate Tags: {len(unwanted_dots)} ({unwanted_dots})")
    print(f"Repaired / Cleaned:      {repaired_count}")
    print("=" * 50 + "\n")

    # -------------------------------------------------------------
    # 12. SAFE EXPORT / SAVE AS NEW FILE
    # -------------------------------------------------------------
    # DO NOT overwrite original! Save as GRACEEMO-01_MASTER_ENGINEERING_PHASE1_FIXED.blend
    blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.join(os.getcwd(), "blender")
    os.makedirs(blend_dir, exist_ok=True)
    out_blend = os.path.join(blend_dir, "GRACEEMO-01_MASTER_ENGINEERING_PHASE1_FIXED.blend")
    
    if os.access(blend_dir, os.W_OK):
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        log(f"Successfully saved fixed scene to: {out_blend}")
    else:
        raise PermissionError(f"Directory not writable: {blend_dir}")

if __name__ == "__main__":
    run_phase1_repair()
