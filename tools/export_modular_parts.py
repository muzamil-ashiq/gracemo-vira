"""
GRACEEMO-01 — Export Modular Subassemblies & Individual Parts
Exports separate .blend, .glb, and .obj files for each robot subassembly and component.
"""

import os
import sys
import bpy

def log(msg):
    print(f"[EXPORT-PARTS] {msg}")

def export_selection_as_blend(out_path, object_names):
    """Save only the selected objects into a standalone .blend file."""
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')
    objs = [bpy.data.objects.get(n) for n in object_names if bpy.data.objects.get(n)]
    for o in objs:
        o.select_set(True)
    
    # Export copy of scene with selected objects or copy data
    # In Blender, write_empty or clean duplication:
    # Safest way: duplicate into new temporary blend
    pass

def run_export():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "blender", "modular_parts"))
    blend_dir = os.path.join(base_dir, "blend")
    glb_dir = os.path.join(base_dir, "glb")
    obj_dir = os.path.join(base_dir, "obj")

    os.makedirs(blend_dir, exist_ok=True)
    os.makedirs(glb_dir, exist_ok=True)
    os.makedirs(obj_dir, exist_ok=True)

    # Define subassemblies with member objects (exact names or prefixes)
    subassemblies = {
        "01_Head_and_Sensors": [
            "HEAD_Outer_Shell", "HEAD_Face_Visor", "HEAD_Expressive_Face",
            "FACE_Eye_Left", "FACE_Eye_Right", "FACE_Mouth",
            "CAM_RGB_Front", "CAM_Stereo_Left", "CAM_Stereo_Right",
            "COMP_CAMERA_ENVELOPE", "BRACKET_CAMERA_MOUNT",
            "ACTUATOR_NECK_PITCH_ENVELOPE", "COMP_AUDIO_MIC_ARRAY_ENVELOPE",
            "PANEL_SERVICE_HEAD_ACCESS", "head_link"
        ],
        "02_Neck_Mechanism": [
            "ACTUATOR_NECK_YAW_ENVELOPE", "NECK_YAW_MOUNTING_PLATE",
            "neck_yaw_link", "neck_yaw_visual"
        ],
        "03_Torso_and_Compute_Bay": [
            "TORSO_Main_Shell", "TORSO_Mid_Waist_Band", "TORSO_Lower_Pelvis",
            "DISP_Chest_Screen_Housing", "DISP_Chest_Active_Display", "EMBLEM_Heart_Logo",
            "COMP_AI_COMPUTER_ENVELOPE", "COMP_MCU_ENVELOPE",
            "COMP_MOTOR_CONTROLLER_ENVELOPE_L", "COMP_MOTOR_CONTROLLER_ENVELOPE_R",
            "COMP_ETH_SWITCH_ENVELOPE", "COMP_SERIAL_BUS_HUB_ENVELOPE",
            "COMP_IMU_ENVELOPE", "COMP_AUDIO_SPEAKER_ENVELOPE",
            "PANEL_SERVICE_COMPUTE_TORSO", "EMERGENCY_STOP", "torso_link"
        ],
        "04_Base_Chassis_and_Power": [
            "CHASSIS_Lower_Module", "CHASSIS_Mid_Deck", "CHASSIS_Sensor_Bay",
            "COMP_BATTERY_ENVELOPE", "BATTERY_MOUNT_LEFT", "BATTERY_MOUNT_RIGHT",
            "BATTERY_SERVICE_ACCESS", "PANEL_SERVICE_BATTERY_REAR",
            "MAIN_FUSE", "POWER_DISTRIBUTION", "DC_DC_CONVERTER",
            "CHARGING_PORT", "MAIN_SWITCH", "base_link", "base_footprint"
        ],
        "05_Drive_Wheel_Assembly": [
            "WHEEL_Drive_Left", "WHEEL_Drive_Right", "WHEEL_Front_Left", "WHEEL_Front_Right",
            "WHEEL_HUB_FL", "WHEEL_AXLE_FL", "WHEEL_BEARING_FL", "WHEEL_MOTOR_FL", "WHEEL_ENCODER_FL",
            "WHEEL_HUB_FR", "WHEEL_AXLE_FR", "WHEEL_BEARING_FR", "WHEEL_MOTOR_FR", "WHEEL_ENCODER_FR",
            "WHEEL_HUB_RL", "WHEEL_AXLE_RL", "WHEEL_BEARING_RL", "WHEEL_MOTOR_RL", "WHEEL_ENCODER_RL",
            "WHEEL_HUB_RR", "WHEEL_AXLE_RR", "WHEEL_BEARING_RR", "WHEEL_MOTOR_RR", "WHEEL_ENCODER_RR",
            "left_wheel", "right_wheel", "left_front_wheel", "right_front_wheel"
        ],
        "06_Left_Arm_Assembly": [
            "ACT_LEFT_Shoulder", "ARM_LEFT_UpperArm", "ARM_LEFT_Forearm",
            "left_elbow_joint_housing", "left_wrist_joint_housing",
            "ACTUATOR_SHOULDER_ENVELOPE_LEFT", "BEARING_SHOULDER_LEFT",
            "ACTUATOR_ELBOW_ENVELOPE_LEFT", "BEARING_ELBOW_LEFT",
            "ACTUATOR_WRIST_ENVELOPE_LEFT", "BEARING_WRIST_LEFT",
            "HAND_MOUNTING_INTERFACE_LEFT",
            "left_shoulder_link", "left_upper_arm_link", "left_elbow_link",
            "left_forearm_link", "left_wrist_link"
        ],
        "07_Right_Arm_Assembly": [
            "ACT_RIGHT_Shoulder", "ARM_RIGHT_UpperArm", "ARM_RIGHT_Forearm",
            "right_elbow_joint_housing", "right_wrist_joint_housing",
            "ACTUATOR_SHOULDER_ENVELOPE_RIGHT", "BEARING_SHOULDER_RIGHT",
            "ACTUATOR_ELBOW_ENVELOPE_RIGHT", "BEARING_ELBOW_RIGHT",
            "ACTUATOR_WRIST_ENVELOPE_RIGHT", "BEARING_WRIST_RIGHT",
            "HAND_MOUNTING_INTERFACE_RIGHT",
            "right_shoulder_link", "right_upper_arm_link", "right_elbow_link",
            "right_forearm_link", "right_wrist_link"
        ],
        "08_Left_Hand_Assembly": [
            "HAND_LEFT_Palm", "HAND_LEFT_Thumb",
            "HAND_LEFT_Knuckle_1", "HAND_LEFT_Knuckle_2", "HAND_LEFT_Knuckle_3", "HAND_LEFT_Knuckle_4",
            "HAND_LEFT_Finger_1", "HAND_LEFT_Finger_2", "HAND_LEFT_Finger_3", "HAND_LEFT_Finger_4",
            "COMP_HAND_ACTUATOR_ENVELOPE_LEFT", "FINGER_LINKAGE_AREA_LEFT", "HAND_SERVICE_ACCESS_LEFT",
            "left_hand_link"
        ],
        "09_Right_Hand_Assembly": [
            "HAND_RIGHT_Palm", "HAND_RIGHT_Thumb",
            "HAND_RIGHT_Knuckle_1", "HAND_RIGHT_Knuckle_2", "HAND_RIGHT_Knuckle_3", "HAND_RIGHT_Knuckle_4",
            "HAND_RIGHT_Finger_1", "HAND_RIGHT_Finger_2", "HAND_RIGHT_Finger_3", "HAND_RIGHT_Finger_4",
            "COMP_HAND_ACTUATOR_ENVELOPE_RIGHT", "FINGER_LINKAGE_AREA_RIGHT", "HAND_SERVICE_ACCESS_RIGHT",
            "right_hand_link"
        ],
        "10_Sensors_and_LiDAR_Unit": [
            "LIDAR_Base_Forward", "COMP_LIDAR_ENVELOPE", "BRACKET_LIDAR_MOUNT",
            "CAM_Base_1", "CAM_Base_2", "CAM_Base_3", "CAM_Base_4", "CAM_Base_5",
            "SENSOR_LED_1", "SENSOR_LED_2", "SENSOR_LED_3", "SENSOR_LED_4", "SENSOR_LED_5",
            "lidar_link"
        ],
    }

    # 1. Export each Subassembly to GLB
    for sub_name, obj_names in subassemblies.items():
        bpy.ops.object.select_all(action='DESELECT')
        valid_objs = []
        for name in obj_names:
            o = bpy.data.objects.get(name)
            if o and o.type == 'MESH':
                o.select_set(True)
                valid_objs.append(o)
        
        if valid_objs:
            bpy.context.view_layer.objects.active = valid_objs[0]
            glb_path = os.path.join(glb_dir, f"{sub_name}.glb")
            bpy.ops.export_scene.gltf(
                filepath=glb_path,
                export_format='GLB',
                use_selection=True
            )
            log(f"Exported Subassembly GLB: {os.path.basename(glb_path)} ({len(valid_objs)} parts)")

    # 2. Export individual key parts to GLB and OBJ
    individual_parts = {
        "Head_Shell": "HEAD_Outer_Shell",
        "Face_Visor": "HEAD_Face_Visor",
        "Camera_RealSense_D435i": "COMP_CAMERA_ENVELOPE",
        "LiDAR_Scanner": "COMP_LIDAR_ENVELOPE",
        "Torso_Chassis": "TORSO_Main_Shell",
        "Chest_Screen": "DISP_Chest_Active_Display",
        "Battery_Pack_24V": "COMP_BATTERY_ENVELOPE",
        "AI_Computer_Jetson": "COMP_AI_COMPUTER_ENVELOPE",
        "Base_Chassis": "CHASSIS_Lower_Module",
        "Drive_Wheel": "WHEEL_Drive_Right",
        "Wheel_Motor_BLDC": "WHEEL_MOTOR_FR",
        "Shoulder_Actuator": "ACTUATOR_SHOULDER_ENVELOPE_RIGHT",
        "Upper_Arm": "ARM_RIGHT_UpperArm",
        "Elbow_Actuator": "ACTUATOR_ELBOW_ENVELOPE_RIGHT",
        "Forearm": "ARM_RIGHT_Forearm",
        "Wrist_Actuator": "ACTUATOR_WRIST_ENVELOPE_RIGHT",
        "Hand_Palm": "HAND_RIGHT_Palm",
        "Emergency_Stop": "EMERGENCY_STOP",
    }

    for part_name, obj_name in individual_parts.items():
        o = bpy.data.objects.get(obj_name)
        if o and o.type == 'MESH':
            bpy.ops.object.select_all(action='DESELECT')
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            
            # Export GLB
            part_glb = os.path.join(glb_dir, f"Part_{part_name}.glb")
            bpy.ops.export_scene.gltf(
                filepath=part_glb,
                export_format='GLB',
                use_selection=True
            )

            # Export OBJ (Wavefront OBJ for CAD/SolidWorks/3D printing)
            part_obj = os.path.join(obj_dir, f"Part_{part_name}.obj")
            try:
                bpy.ops.wm.obj_export(filepath=part_obj, export_selected_objects=True)
            except AttributeError:
                bpy.ops.export_scene.obj(filepath=part_obj, use_selection=True)

            log(f"Exported Part: {part_name} (.glb & .obj)")

    # 3. Create standalone .blend files for each subassembly
    # We do this by loading the master file and keeping only the relevant objects
    orig_blend = bpy.data.filepath
    for sub_name, obj_names in subassemblies.items():
        blend_path = os.path.join(blend_dir, f"{sub_name}.blend")
        # Load fresh copy of master
        bpy.ops.wm.open_mainfile(filepath=orig_blend)
        
        # Keep only objects in obj_names + world lighting
        keep_names = set(obj_names)
        for o in list(bpy.data.objects):
            if o.name not in keep_names:
                bpy.data.objects.remove(o, do_unlink=True)
        
        # Save standalone subassembly blend
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        log(f"Exported Standalone Blend: {os.path.basename(blend_path)}")

    log("==================================================")
    log("All modular subassemblies & individual parts exported successfully!")
    log(f"Location: {base_dir}")
    log("==================================================")

if __name__ == "__main__":
    run_export()
