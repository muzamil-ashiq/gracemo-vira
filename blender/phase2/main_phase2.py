"""
GRACEEMO-01 — Phase 2 Interactive Articulation & Motion Rigging Master Runner
Blender 5.2.1 LTS / bpy-only script.
"""

import os
import sys
import math
import bpy
from mathutils import Vector, Euler

# Add parent directory to sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from rig.limits import JOINT_LIMITS
from rig.controllers import setup_controllers
from rig.joints import bind_joints_to_controllers
from rig.ik import setup_ik_system
from animation.poses import reset_robot_pose, pose_idle, pose_greeting
from animation.test_animation import build_test_animation
from ui.control_panel import register_ui
from validation.validate_phase2 import validate_phase2_motion

def log(msg):
    print(f"[GRACEEMO-PHASE2] {msg}")

def safe_parent(child_obj, parent_obj):
    """Parent child to parent strictly preserving world transform with correct parent inverse."""
    if not child_obj or not parent_obj or child_obj == parent_obj:
        return
    world_matrix = child_obj.matrix_world.copy()
    child_obj.parent = parent_obj
    child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    child_obj.matrix_world = world_matrix

def align_arm_pivots_and_hierarchy():
    """Ensure arm link frames have true physical joint pivot locations and continuous parent chains."""
    torso = bpy.data.objects.get("torso_link")
    
    for side, sign in [("left", -1), ("right", 1)]:
        sh_loc = Vector((sign * 0.22, 0.0, 1.08))
        el_loc = Vector((sign * 0.30, -0.02, 0.86))
        wr_loc = Vector((sign * 0.32, -0.02, 0.66))
        hd_loc = Vector((sign * 0.32, -0.03, 0.605))

        sh = bpy.data.objects.get(f"{side}_shoulder_link")
        up = bpy.data.objects.get(f"{side}_upper_arm_link")
        el = bpy.data.objects.get(f"{side}_elbow_link")
        fo = bpy.data.objects.get(f"{side}_forearm_link")
        wr = bpy.data.objects.get(f"{side}_wrist_link")
        hd = bpy.data.objects.get(f"{side}_hand_link")

        # Set physical pivot locations and establish parent chain
        if sh and torso:
            sh.matrix_world.translation = sh_loc
            safe_parent(sh, torso)

        if up and sh:
            up.matrix_world.translation = sh_loc
            safe_parent(up, sh)

        if el and sh:
            el.matrix_world.translation = el_loc
            safe_parent(el, sh)

        if fo and el:
            fo.matrix_world.translation = el_loc
            safe_parent(fo, el)

        if wr and el:
            wr.matrix_world.translation = wr_loc
            safe_parent(wr, el)

        if hd and wr:
            hd.matrix_world.translation = hd_loc
            safe_parent(hd, wr)

        # Re-parent meshes to their respective link frames with matrix_world preservation
        side_upper = side.upper()
        act_sh = bpy.data.objects.get(f"ACT_{side_upper}_Shoulder")
        arm_up = bpy.data.objects.get(f"ARM_{side_upper}_UpperArm")
        cam_sh = bpy.data.objects.get(f"CAM_{side_upper}_Shoulder")
        led_sh = bpy.data.objects.get(f"SENSOR_{side_upper}_Shoulder_LED")

        elb_j = bpy.data.objects.get(f"{side}_elbow_joint_housing")
        arm_fo = bpy.data.objects.get(f"ARM_{side_upper}_Forearm")
        led_el = bpy.data.objects.get(f"SENSOR_{side_upper}_Elbow_LED")

        wri_j = bpy.data.objects.get(f"{side}_wrist_joint_housing")
        palm = bpy.data.objects.get(f"HAND_{side_upper}_Palm")

        # Upper arm assembly attached to shoulder link
        if act_sh and sh: safe_parent(act_sh, sh)
        if arm_up and sh: safe_parent(arm_up, sh)
        if cam_sh and sh: safe_parent(cam_sh, sh)
        if led_sh and sh: safe_parent(led_sh, sh)

        # Forearm assembly attached to elbow link
        if elb_j and el: safe_parent(elb_j, el)
        if arm_fo and el: safe_parent(arm_fo, el)
        if led_el and el: safe_parent(led_el, el)

        # Wrist housing attached to wrist link
        if wri_j and wr: safe_parent(wri_j, wr)

        # Hand palm attached to hand link
        if palm and hd:
            safe_parent(palm, hd)
            th = bpy.data.objects.get(f"HAND_{side_upper}_Thumb")
            if th: safe_parent(th, palm)
            for i in range(1, 5):
                kn = bpy.data.objects.get(f"HAND_{side_upper}_Knuckle_{i}")
                fg = bpy.data.objects.get(f"HAND_{side_upper}_Finger_{i}")
                if kn:
                    safe_parent(kn, palm)
                    if fg: safe_parent(fg, kn)

    bpy.context.view_layer.update()

def run_phase2():
    log("==================================================")
    log("Starting Phase 2 Interactive Robotics Motion Setup")
    log("==================================================")

    # 1. Align arm joint pivots and parent hierarchy
    log("Aligning physical joint pivot locations and arm chain...")
    align_arm_pivots_and_hierarchy()

    # 2. Setup Dedicated Robotics Controllers in 15_DEBUG
    log("Setting up dedicated controllers in 15_DEBUG...")
    ctrls = setup_controllers()
    log(f"Created {len(ctrls)} dedicated motion controllers.")

    # 3. Setup Joint Constraint Bindings & Limits
    log("Binding joint links to controllers with mechanical rotation axes...")
    bind_joints_to_controllers()
    log("Joint constraints and limit rotation bounds established.")

    # 4. Setup Arm IK System (Rigid Two-Bone Inverse Kinematics)
    log("Setting up rigid arm IK with pole targets...")
    ik_ctrls = setup_ik_system()
    log(f"IK system established with {len(ik_ctrls)} targets and pole empties.")

    # 5. Register UI Panel
    log("Registering 3D Viewport Control Panel (GRACEEMO CONTROL)...")
    register_ui()

    # 6. Embed UI Autoload Script in Blend File
    ui_script_text = bpy.data.texts.get("GraceEMO_UI_Runner.py")
    if not ui_script_text:
        ui_script_text = bpy.data.texts.new("GraceEMO_UI_Runner.py")
    ui_script_text.clear()
    ui_script_text.write("""# GraceEMO Interactive Sidebar Control Panel Loader
import os, sys, bpy
here = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
p2_dir = os.path.join(here, "phase2")
if p2_dir not in sys.path:
    sys.path.insert(0, p2_dir)
try:
    from ui.control_panel import register_ui
    register_ui()
    print("GRACEEMO CONTROL panel registered in 3D View -> Sidebar (N) -> GRACEEMO")
except Exception as e:
    print("Could not auto-register GRACEEMO panel:", e)
""")
    ui_script_text.use_module = True

    # 7. Build Motion Validation Timeline (Frames 1-240)
    log("Generating 240-frame motion validation animation sequence...")
    build_test_animation()
    log("Animation sequence keyframed (IDLE -> LOOK -> ARMS -> GREETING -> IDLE).")

    # 8. Reset Robot to Neutral
    log("Resetting robot to neutral rest pose...")
    reset_robot_pose()

    # 9. Run Phase 2 Motion Validation
    log("Running Phase 2 Motion Validation System...")
    passed = validate_phase2_motion()

    # 10. Safe Export (Never overwrite Phase 1 file)
    blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.join(os.getcwd(), "blender")
    os.makedirs(blend_dir, exist_ok=True)
    out_blend = os.path.join(blend_dir, "GRACEEMO-01_MASTER_ENGINEERING_PHASE2_MOTION.blend")

    if os.access(blend_dir, os.W_OK):
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        log("==================================================")
        log(f"Successfully saved Phase 2 Motion Scene to:")
        log(f"{out_blend}")
        log("==================================================")
    else:
        raise PermissionError(f"Directory not writable: {blend_dir}")

    return passed

if __name__ == "__main__":
    run_phase2()
