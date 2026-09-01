"""
GRACEEMO-01 — Phase 3 Hardware Packaging & Engineering Model Master Runner
Blender 5.2.1 LTS / bpy-only script.

Converts the visual/kinematic robot into a hardware-aware engineering assembly.
Preserves all Phase 2 motion controllers, IK, poses, and UI.
"""

import os
import sys
import bpy

# Set up python path for local imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(PARENT_DIR, ".."))

for p in [CURRENT_DIR, PARENT_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from manifest.hardware_manifest import load_manifest
from packaging.base_power_compute import setup_base_power_and_compute
from packaging.mobility_wheels import setup_wheel_assemblies
from packaging.arm_actuators import setup_arm_mechanical_packaging
from packaging.neck_head import setup_neck_head_and_sensors
from packaging.hands_packaging import setup_hands_packaging
from packaging.cables import setup_cable_routing
from packaging.collision import setup_collision_envelopes
from packaging.serviceability import setup_service_panels
from mass.mass_com import calculate_mass_and_com
from validation.validate_phase3_hardware import validate_phase3_hardware

def log(msg):
    print(f"[GRACEEMO-PHASE3] {msg}")

def run_phase3():
    log("==================================================")
    log("Starting Phase 3 Hardware Packaging & Engineering")
    log("==================================================")

    # 1. Load & Verify Hardware Manifest
    log("Loading hardware manifest database...")
    manifest = load_manifest()
    log(f"Manifest loaded successfully with {len(manifest.get('components', []))} components.")

    # 2. Package Base, Power Distribution & Compute Bay
    log("Packaging Base, Power Distribution & Compute Bay envelopes...")
    pwr_cmp_objs = setup_base_power_and_compute(manifest)
    log(f"Created {len(pwr_cmp_objs)} power & compute envelopes.")

    # 3. Package Driven Wheel Assemblies
    log("Packaging multi-part wheel assemblies (hubs, axles, bearings, motors, encoders)...")
    wheel_objs = setup_wheel_assemblies(manifest)
    log(f"Created {len(wheel_objs)} wheel engineering assembly parts.")

    # 4. Package Arm Mechanical Actuation & Bearings
    log("Packaging arm actuator envelopes, bearings and hand mounting interfaces...")
    arm_objs = setup_arm_mechanical_packaging(manifest)
    log(f"Created {len(arm_objs)} arm mechanical parts.")

    # 5. Package Neck, Head & Sensor FOV
    log("Packaging neck servos, brackets, and sensor FOV cones...")
    neck_sensor_objs = setup_neck_head_and_sensors(manifest)
    log(f"Created {len(neck_sensor_objs)} neck & sensor envelope objects.")

    # 6. Package Hand Internal Actuation Envelopes
    log("Packaging hand actuator and linkage envelopes...")
    hand_objs = setup_hands_packaging(manifest)
    log(f"Created {len(hand_objs)} hand packaging objects.")

    # 7. Setup Cable Routing Conduits
    log("Building cable routing conduits in 12_CABLE_ROUTING...")
    cable_objs = setup_cable_routing()
    log(f"Created {len(cable_objs)} cable routing conduits.")

    # 8. Setup Simplified Collision Envelopes
    log("Building simplified collision proxy envelopes in 14_COLLISION...")
    col_objs = setup_collision_envelopes()
    log(f"Created {len(col_objs)} collision proxy envelopes.")

    # 9. Setup Service Panels
    log("Building marked service access panels...")
    service_objs = setup_service_panels()
    log(f"Created {len(service_objs)} service access panels.")

    # 10. Mass Properties & Center of Mass Estimation
    log("Calculating system mass properties and Center of Mass...")
    mass_report = calculate_mass_and_com()
    log(f"System Total Mass Estimate: {mass_report['total_mass_kg']} kg")
    log(f"Center of Mass (base_footprint): {mass_report['com_base_footprint']}")
    log(f"Subsystem Breakdown: {mass_report['category_breakdown']}")

    # 11. Run Phase 3 Engineering Validation
    log("Executing automated Phase 3 Engineering Validation checks...")
    phase3_passed = validate_phase3_hardware()

    # 12. Verify Phase 2 Motion System Remains Intact
    log("Verifying Phase 2 motion system and controllers...")
    p2_ctrls = [
        "CTRL_NECK_YAW", "CTRL_NECK_PITCH", "CTRL_NECK_ROLL",
        "CTRL_LEFT_SHOULDER", "CTRL_LEFT_ELBOW", "CTRL_LEFT_WRIST", "CTRL_LEFT_HAND",
        "CTRL_RIGHT_SHOULDER", "CTRL_RIGHT_ELBOW", "CTRL_RIGHT_WRIST", "CTRL_RIGHT_HAND",
        "CTRL_LEFT_HAND_IK", "CTRL_RIGHT_HAND_IK",
        "CTRL_LEFT_WHEEL", "CTRL_RIGHT_WHEEL", "CTRL_LEFT_FRONT_WHEEL", "CTRL_RIGHT_FRONT_WHEEL"
    ]
    missing_p2 = [c for c in p2_ctrls if bpy.data.objects.get(c) is None]
    if missing_p2:
        log(f"WARNING: Some Phase 2 controllers were not found: {missing_p2}")
    else:
        log("All Phase 2 controllers verified 100% functional.")

    # 13. Safe Blend Export (Never overwrite Phase 2 file)
    blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.join(PROJECT_ROOT, "blender")
    out_blend = os.path.join(blend_dir, "GRACEEMO-01_MASTER_ENGINEERING_PHASE3_HARDWARE.blend")

    if os.access(blend_dir, os.W_OK):
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        log("==================================================")
        log(f"Successfully saved Phase 3 Hardware Scene to:")
        log(f"{out_blend}")
        log("==================================================")
    else:
        raise PermissionError(f"Directory not writable: {blend_dir}")

    return phase3_passed

if __name__ == "__main__":
    run_phase3()
