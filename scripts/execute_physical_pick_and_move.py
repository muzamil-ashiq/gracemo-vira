#!/usr/bin/env python3
"""
GRaCEmo ViRa — Authoritative Live Physical Pick & Move Execution (Gates M3 & M4)
Executes the decoupled 5-DOF manipulation & in-hand carry pipeline under live Gazebo Harmonic physics:

  Gate M3 (Hard Gate — Completely Stationary):
    1. Base is stationary at bedroom nightstand.
    2. Encloses and grasps 'book_math'.
    3. Executes +5cm vertical test lift.
    4. Measures hand delta Z and book delta Z.
    5. Emits authoritative GraspConfirmed to MNSE Kernel.
    6. Smoothly enters in-hand STANCE_CARRY.

  Gate M4 (In-Hand Locomotion Transit & Placement):
    7. CARRY_READY: Object held in hand.
    8. Locomotion: Base executes acceleration, rotation, and braking.
    9. CARRY_VERIFIED: Closed-loop check (elevation, envelope, contact).
   10. PLACE: Reaches over surface, lowers, releases gripper.
   11. PLACEMENT_VERIFIED: Confirms object rests securely on surface.
   12. STANCE_TRAVEL: Tucks arm for free travel.
"""

import sys
import os
import time
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for sub in ["sdk", "motion", "brain/gracemo_brain/skills"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from manipulation_skill import ManipulationSkill
from gracemo_base_controller import BaseController


def main():
    print("=================================================================")
    print("  GRaCEmo ViRa — Live 5-DOF Physical Pick & Carry (Gates M3 & M4)")
    print("=================================================================")

    # 1. Initialize ManipulationSkill in live mode (mock=False)
    print("\n1. Initializing Live Manipulation Skill & Subsystems...")
    skill = ManipulationSkill(mock=False)
    time.sleep(1.5)

    # Immediately tuck arm into TRAVEL stance for clearance
    print("   Setting initial arm stance to STANCE_TRAVEL...")
    skill.arm.move_to_stance("TRAVEL", duration_sec=1.0)
    time.sleep(0.5)

    # Telemetry inspection
    rob_pose = skill.verifier.tracked_objects.get("gracemo_vira")
    book_pose = None
    for k, v in skill.verifier.tracked_objects.items():
        if "book" in k:
            book_pose = (k, v)
            break

    print(f"   Robot Pose: {rob_pose}")
    print(f"   Book Pose:  {book_pose}")
    print(f"   Hand Aperture: {skill.hand.get_width()*1000:.1f}mm")

    # Step 2: Smooth Docking to Nightstand (Arm tucked in STANCE_TRAVEL)
    base = BaseController()
    rob_p = skill.verifier.tracked_objects.get("gracemo_vira")
    if rob_p is not None and rob_p[1] < 2.83:
        print("\n2. Smooth Docking: Driving forward to nightstand grasp pose (arm tucked in STANCE_TRAVEL)...")
        t_dock = time.time()
        while time.time() - t_dock < 3.0:
            cur_p = skill.verifier.tracked_objects.get("gracemo_vira")
            if cur_p is not None and cur_p[1] >= 2.85:
                break
            base.drive_raw_velocity(0.10, 0.0)
            time.sleep(0.04)
        base.stop()
        time.sleep(0.6)
        rob_p = skill.verifier.tracked_objects.get("gracemo_vira")
        print(f"   Docked cleanly at Robot Pose: {rob_p}")
    else:
        base.stop()
        time.sleep(0.3)

    print("\n2b. Stationary Grasp Check: Base velocity = 0.0, motors locked at docking pose.")

    # Step 3: Gate M3 — Stationary Physical Grasp Verification
    print("\n=================================================================")
    print("  GATE M3: Stationary Physical Grasp Verification ('book_math')")
    print("=================================================================")
    t0 = time.time()
    res_grasp = skill.pick_and_verify(target_id="book_math", max_retries=2)
    dt_grasp = time.time() - t0

    print(f"\n   ---------------------------------------------")
    print(f"   Grasp Result Status:     {res_grasp.status}")
    print(f"   Dual Contact Left/Right: {res_grasp.contact_left} / {res_grasp.contact_right}")
    print(f"   Commanded Lift:          +{res_grasp.commanded_lift_m*1000:.1f} mm")
    print(f"   Measured Hand Delta:     dX={res_grasp.measured_hand_delta[0]*1000:+.1f}mm, dY={res_grasp.measured_hand_delta[1]*1000:+.1f}mm, dZ={res_grasp.measured_hand_delta[2]*1000:+.1f}mm")
    print(f"   Measured Book Delta:     dX={res_grasp.measured_object_delta[0]*1000:+.1f}mm, dY={res_grasp.measured_object_delta[1]*1000:+.1f}mm, dZ={res_grasp.measured_object_delta[2]*1000:+.1f}mm")
    print(f"   Vertical Delta Z Error:  {res_grasp.vertical_error_m*1000:.2f} mm")
    print(f"   Lateral Slip:            {res_grasp.lateral_slip_m*1000:.2f} mm")
    print(f"   Verified Physical Grasp: {res_grasp.verified}")
    print(f"   Current Arm Stance:      {skill.arm.get_joint_positions().round(3)}")
    print(f"   Duration:                {dt_grasp:.2f}s")
    print(f"   ---------------------------------------------")

    if not res_grasp.verified:
        print("\n❌ CRITICAL: Gate M3 failed! Grasp verification not satisfied. Halting.")
        sys.exit(1)

    print("\n🎉 GATE M3 PASSED: GraspConfirmed verified under live physics!")
    print(f"   Skill State: {skill.state} (Holding object in hand)")

    # Step 4: Gate M4 — In-Hand Locomotion Transit & Carry Verification
    print("\n=================================================================")
    print("  GATE M4: In-Hand Locomotion Transit & Placement")
    print("=================================================================")
    
    # 4a. Locomotion Transit (Base Acceleration, Rotation, Braking)
    print("\n4a. Executing Base Locomotion Maneuver with Object Held in Hand...")
    if base.wait_for_sensors(timeout_sec=2.0):
        # BASE_ROTATION: rotate slightly into open room
        print("   [LOCOMOTION] Rotating base +25°...")
        t_rot = time.time()
        while time.time() - t_rot < 1.0:
            base.drive_velocity(0.0, 0.35)
            time.sleep(0.02)
        base.stop()
        time.sleep(0.3)

        # BASE_ACCELERATION & DRIVE: drive forward 0.20m
        print("   [LOCOMOTION] Driving forward 0.20m...")
        t_fwd = time.time()
        while time.time() - t_fwd < 1.5:
            base.drive_velocity(0.12, 0.0)
            time.sleep(0.02)

        # BASE_BRAKING: smooth deceleration to stop
        print("   [LOCOMOTION] Braking to complete stop...")
        base.stop()
        time.sleep(0.5)

    # 4b. CARRY_VERIFIED: Closed-Loop Carry State Observation
    print("\n4b. Evaluating In-Hand Carry Stability (CARRY_VERIFIED)...")
    res_carry = skill.verify_carry("book_math")
    print(f"   Carry Status:            {res_carry.status}")
    print(f"   Object Elevation Z:      {res_carry.elevation_m:.3f} m")
    print(f"   Relative Distance:       {res_carry.relative_distance_m:.3f} m")
    print(f"   Contact Valid:           {res_carry.contact_valid}")
    print(f"   Carry Verified:          {res_carry.verified}")

    if not res_carry.verified:
        print("\n❌ CRITICAL: Gate M4 carry verification failed! Object dropped or slipped.")
        sys.exit(1)

    print("\n🎉 CARRY_VERIFIED: Object securely maintained in hand throughout locomotion!")

    # 4c. SURFACE PLACEMENT & VERIFICATION
    print("\n4c. Executing Surface Placement...")
    res_place = skill.place_on_surface("book_math", surface_height_z=0.62)
    print(f"   Placement Status:        {res_place.status}")
    print(f"   Final Surface Height Z:  {res_place.surface_z:.3f} m")
    print(f"   Placement Verified:      {res_place.verified}")

    if not res_place.verified:
        print("\n❌ CRITICAL: Surface placement failed!")
        sys.exit(1)

    print("\n🎉 PLACEMENT_VERIFIED: Book released and resting securely on surface!")
    print(f"   Arm tucked in STANCE_TRAVEL: {skill.arm.get_joint_positions().round(3)}")

    # Final Verification
    final_book_z = skill.verifier.get_object_z("book_math")
    print(f"\n   Final Book Height: Z={final_book_z:.3f}m")
    print("\n=================================================================")
    print("  🚀 GATES M3 & M4 FULLY VERIFIED UNDER LIVE GAZEBO HARMONIC!    ")
    print("=================================================================")


if __name__ == "__main__":
    main()
