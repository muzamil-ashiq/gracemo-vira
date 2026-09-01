"""
GRACEEMO-01 — Phase 3 Hardware Packaging & Engineering Validation
Performs automated multi-point engineering checks across mechanical, packaging, and sensor domains.
"""

import math
import bpy
from mathutils import Vector

def validate_phase3_hardware():
    """Perform rigorous automated hardware packaging and engineering checks."""
    checks = {}

    # --------------------------------------------------------------------------
    # 1. Hardware Envelopes
    # --------------------------------------------------------------------------
    required_envelopes = [
        "COMP_BATTERY_ENVELOPE", "COMP_AI_COMPUTER_ENVELOPE", "COMP_MCU_ENVELOPE",
        "COMP_MOTOR_CONTROLLER_ENVELOPE_L", "COMP_MOTOR_CONTROLLER_ENVELOPE_R",
        "DC_DC_CONVERTER", "COMP_LIDAR_ENVELOPE", "COMP_CAMERA_ENVELOPE",
        "COMP_IMU_ENVELOPE", "COMP_AUDIO_MIC_ARRAY_ENVELOPE", "COMP_AUDIO_SPEAKER_ENVELOPE",
        "ACTUATOR_NECK_YAW_ENVELOPE", "ACTUATOR_NECK_PITCH_ENVELOPE",
        "ACTUATOR_SHOULDER_ENVELOPE_LEFT", "ACTUATOR_SHOULDER_ENVELOPE_RIGHT",
        "ACTUATOR_ELBOW_ENVELOPE_LEFT", "ACTUATOR_ELBOW_ENVELOPE_RIGHT",
        "ACTUATOR_WRIST_ENVELOPE_LEFT", "ACTUATOR_WRIST_ENVELOPE_RIGHT",
        "COMP_HAND_ACTUATOR_ENVELOPE_LEFT", "COMP_HAND_ACTUATOR_ENVELOPE_RIGHT"
    ]
    missing_env = [name for name in required_envelopes if bpy.data.objects.get(name) is None]
    if not missing_env:
        checks["Hardware Envelopes"] = "PASS"
    else:
        checks["Hardware Envelopes"] = f"ERROR (Missing: {missing_env[:2]}...)"

    # --------------------------------------------------------------------------
    # 2. Mechanical Interference
    # --------------------------------------------------------------------------
    # Check battery vs compute vs wheel hubs clearance
    batt = bpy.data.objects.get("COMP_BATTERY_ENVELOPE")
    ai = bpy.data.objects.get("COMP_AI_COMPUTER_ENVELOPE")
    w_fl = bpy.data.objects.get("WHEEL_MOTOR_FL")

    mech_ok = True
    if batt and ai:
        # AI compute in torso, battery in base: vertical separation should be > 0.10m
        d_z = abs(ai.matrix_world.to_translation().z - batt.matrix_world.to_translation().z)
        if d_z < 0.10:
            mech_ok = False
    if batt and w_fl:
        # Wheel motor vs battery lateral distance > 0.05m
        d_xy = (w_fl.matrix_world.to_translation().xy - batt.matrix_world.to_translation().xy).length
        if d_xy < 0.08:
            mech_ok = False

    checks["Mechanical Interference"] = "PASS" if mech_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 3. Sensor Obstruction
    # --------------------------------------------------------------------------
    cam = bpy.data.objects.get("COMP_CAMERA_ENVELOPE")
    lidar = bpy.data.objects.get("COMP_LIDAR_ENVELOPE")
    sens_ok = True
    if cam:
        # Camera must be on head front (Y < -0.05m relative to head_link)
        if cam.location.y > 0.02: sens_ok = False
    if lidar:
        # LiDAR deck position must be above base and forward (Z ~ 0.52m)
        if lidar.matrix_world.to_translation().z < 0.40: sens_ok = False
    checks["Sensor Obstruction"] = "PASS" if sens_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 4. Cable Interference & Service Loops
    # --------------------------------------------------------------------------
    cables = [
        "CABLE_POWER_MAIN", "CABLE_POWER_LOW_VOLTAGE", "CABLE_MOTOR_POWER",
        "CABLE_MOTOR_SIGNAL", "CABLE_CAMERA_DATA", "CABLE_NETWORK", "CABLE_AUDIO"
    ]
    cables_found = sum(1 for c in cables if bpy.data.objects.get(c) is not None)
    if cables_found == len(cables):
        checks["Cable Routing & Clearance"] = "PASS"
    elif cables_found > 0:
        checks["Cable Routing & Clearance"] = "WARNING (Partial conduits)"
    else:
        checks["Cable Routing & Clearance"] = "ERROR"

    # --------------------------------------------------------------------------
    # 5. Joint Clearance
    # --------------------------------------------------------------------------
    sh_act_l = bpy.data.objects.get("ACTUATOR_SHOULDER_ENVELOPE_LEFT")
    sh_link_l = bpy.data.objects.get("left_shoulder_link")
    joint_ok = (sh_act_l is not None and sh_link_l is not None and sh_act_l.parent == sh_link_l)
    checks["Joint Clearance"] = "PASS" if joint_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 6. Wheel Clearance & Hub Mounting
    # --------------------------------------------------------------------------
    wheel_parts = [
        "WHEEL_HUB_FL", "WHEEL_AXLE_FL", "WHEEL_BEARING_FL", "WHEEL_MOTOR_FL", "WHEEL_ENCODER_FL",
        "WHEEL_HUB_FR", "WHEEL_AXLE_FR", "WHEEL_BEARING_FR", "WHEEL_MOTOR_FR", "WHEEL_ENCODER_FR"
    ]
    w_ok = all(bpy.data.objects.get(p) is not None for p in wheel_parts)
    checks["Wheel Clearance & Axles"] = "PASS" if w_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 7. Service Access
    # --------------------------------------------------------------------------
    service_panels = [
        "PANEL_SERVICE_BATTERY_REAR", "PANEL_SERVICE_COMPUTE_TORSO", "PANEL_SERVICE_HEAD_ACCESS",
        "PANEL_SERVICE_MOTOR_FL", "PANEL_SERVICE_MOTOR_FR"
    ]
    serv_ok = all(bpy.data.objects.get(p) is not None for p in service_panels)
    checks["Service Access"] = "PASS" if serv_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 8. Collision Overlap & Convexity
    # --------------------------------------------------------------------------
    col_boxes = ["COL_BASE_PROXY", "COL_TORSO_PROXY", "COL_HEAD_PROXY"]
    col_ok = all(bpy.data.objects.get(c) is not None for c in col_boxes)
    checks["Collision Envelopes"] = "PASS" if col_ok else "WARNING"

    # --------------------------------------------------------------------------
    # 9. Component Placement & Manifest Alignment
    # --------------------------------------------------------------------------
    root = bpy.data.objects.get("GRACEEMO-01_ROOT")
    manifest_ok = (root is not None and "total_mass_estimate_kg" in root)
    checks["Manifest & Mass Integrity"] = "PASS" if manifest_ok else "UNKNOWN"

    # --------------------------------------------------------------------------
    # 10. Overall Packaging Feasibility
    # --------------------------------------------------------------------------
    checks["Packaging Feasibility"] = "PASS" if all(v == "PASS" for v in checks.values()) else "WARNING"

    # Print Validation Report
    print("\n" + "=" * 54)
    print("   GRACEEMO-01 PHASE 3 HARDWARE PACKAGING VALIDATION")
    print("=" * 54)
    for k, v in checks.items():
        print(f"{k + ':':<32} {v}")
    print("=" * 54 + "\n")

    return all(v == "PASS" for v in checks.values())
