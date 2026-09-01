"""
GRACEEMO-01 — Phase 2 Motion & Interaction Automated Validation
"""

import math
import bpy
from mathutils import Vector, Euler
try:
    from phase2.rig.limits import JOINT_LIMITS
except ImportError:
    from rig.limits import JOINT_LIMITS

def validate_phase2_motion():
    """Perform comprehensive automated motion and rig validation."""
    results = {}

    # 1. Neck validation
    c_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
    c_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
    c_roll = bpy.data.objects.get("CTRL_NECK_ROLL")
    neck_yaw_link = bpy.data.objects.get("neck_yaw_link")
    head_link = bpy.data.objects.get("head_link")

    neck_ctrls_ok = all(o is not None for o in [c_yaw, c_pitch, c_roll, neck_yaw_link, head_link])
    neck_const_ok = False
    if neck_yaw_link and head_link:
        neck_const_ok = bool(neck_yaw_link.constraints.get("Follow_Yaw")) and bool(head_link.constraints.get("Follow_Pitch"))
    results["Neck"] = neck_ctrls_ok and neck_const_ok

    # 2. Left Arm validation
    l_sh = bpy.data.objects.get("CTRL_LEFT_SHOULDER")
    l_el = bpy.data.objects.get("CTRL_LEFT_ELBOW")
    l_wr = bpy.data.objects.get("CTRL_LEFT_WRIST")
    l_hd = bpy.data.objects.get("CTRL_LEFT_HAND")
    l_sh_link = bpy.data.objects.get("left_shoulder_link")
    l_el_link = bpy.data.objects.get("left_elbow_link")
    l_wr_link = bpy.data.objects.get("left_wrist_link")
    l_hd_link = bpy.data.objects.get("left_hand_link")

    l_arm_ctrls_ok = all(o is not None for o in [l_sh, l_el, l_wr, l_hd, l_sh_link, l_el_link, l_wr_link, l_hd_link])
    l_arm_const_ok = bool(l_sh_link and l_sh_link.constraints.get("Follow_L_Shoulder"))
    results["Left Arm"] = l_arm_ctrls_ok and l_arm_const_ok

    # 3. Right Arm validation
    r_sh = bpy.data.objects.get("CTRL_RIGHT_SHOULDER")
    r_el = bpy.data.objects.get("CTRL_RIGHT_ELBOW")
    r_wr = bpy.data.objects.get("CTRL_RIGHT_WRIST")
    r_hd = bpy.data.objects.get("CTRL_RIGHT_HAND")
    r_sh_link = bpy.data.objects.get("right_shoulder_link")
    r_el_link = bpy.data.objects.get("right_elbow_link")
    r_wr_link = bpy.data.objects.get("right_wrist_link")
    r_hd_link = bpy.data.objects.get("right_hand_link")

    r_arm_ctrls_ok = all(o is not None for o in [r_sh, r_el, r_wr, r_hd, r_sh_link, r_el_link, r_wr_link, r_hd_link])
    r_arm_const_ok = bool(r_sh_link and r_sh_link.constraints.get("Follow_R_Shoulder"))
    results["Right Arm"] = r_arm_ctrls_ok and r_arm_const_ok

    # 4. Hands validation (Knuckles and thumbs on both sides)
    hands_ok = True
    for side in ["LEFT", "RIGHT"]:
        palm = bpy.data.objects.get(f"HAND_{side}_Palm")
        thumb = bpy.data.objects.get(f"HAND_{side}_Thumb")
        if not palm or not thumb:
            hands_ok = False
        for i in range(1, 5):
            kn = bpy.data.objects.get(f"HAND_{side}_Knuckle_{i}")
            fg = bpy.data.objects.get(f"HAND_{side}_Finger_{i}")
            if not kn or not fg:
                hands_ok = False
    results["Hands"] = hands_ok

    # 5. Wheels validation
    wheels_ok = True
    for w_name in ["CTRL_LEFT_WHEEL", "CTRL_RIGHT_WHEEL", "CTRL_LEFT_FRONT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL"]:
        if bpy.data.objects.get(w_name) is None:
            wheels_ok = False
    for wl_name in ["left_wheel", "right_wheel", "left_front_wheel", "right_front_wheel"]:
        wl = bpy.data.objects.get(wl_name)
        if not wl or not wl.constraints.get("Follow_Wheel_Axle"):
            wheels_ok = False
    results["Wheels"] = wheels_ok

    # 6. IK validation
    ik_targets_ok = all(
        bpy.data.objects.get(name) is not None for name in [
            "CTRL_LEFT_HAND_IK", "CTRL_LEFT_ELBOW_POLE",
            "CTRL_RIGHT_HAND_IK", "CTRL_RIGHT_ELBOW_POLE",
            "GRACEEMO_Rigid_Arm_IK"
        ]
    )
    results["IK"] = ik_targets_ok

    # 7. Joint Limits validation
    limits_ok = False
    if c_yaw and c_yaw.constraints.get("Limit_Rotation"):
        limits_ok = True
    results["Joint Limits"] = limits_ok

    # 8. Reset validation (can return to neutral)
    reset_ok = True
    try:
        try:
            from phase2.animation.poses import reset_robot_pose
        except ImportError:
            from animation.poses import reset_robot_pose
        reset_robot_pose()
    except Exception:
        reset_ok = False
    results["Reset"] = reset_ok

    # 9. Pose System validation
    pose_ok = True
    try:
        try:
            from phase2.animation.poses import pose_greeting, pose_namaste, pose_idle
        except ImportError:
            from animation.poses import pose_greeting, pose_namaste, pose_idle
        pose_greeting()
        pose_idle()
    except Exception:
        pose_ok = False
    results["Pose System"] = pose_ok

    # 10. UI validation
    ui_ok = hasattr(bpy.types, "GRACEEMO_PT_control_panel")
    results["UI"] = ui_ok

    # Print Validation Report
    print("\n" + "=" * 50)
    print("   GRACEEMO-01 PHASE 2 MOTION VALIDATION")
    print("=" * 50)
    for k in ["Neck", "Left Arm", "Right Arm", "Hands", "Wheels", "IK", "Joint Limits", "Reset", "Pose System", "UI"]:
        v = results.get(k, False)
        print(f"{k + ':':<20} {'PASS' if v else 'FAIL'}")
    print("=" * 50 + "\n")

    return all(results.values())
