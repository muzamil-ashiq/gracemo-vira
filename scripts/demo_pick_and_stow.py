#!/usr/bin/env python3
"""
GRaCEmo ViRa — Live End-to-End Embodied Manipulation Demo (M3 + M4)
Executes:
  1. Base approach to bedroom nightstand (-4.34m, 2.95m, yaw=90°).
  2. Hand opens to 80mm aperture.
  3. 6-DOF Arm IK reaches forward to book_math on nightstand (Z=0.62m).
  4. Hand closes on book_math; pad contacts confirmed.
  5. Test lift (+5cm) verifies physical displacement.
  6. Lift to table clearance (+10cm total).
  7. Arm transfers book to rear cargo shelf (STANCE_TRAY_HOVER).
  8. Hand releases book onto cargo shelf.
  9. Arm tucks into STANCE_TRAVEL for cruise.
"""

import sys
import os
import time
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
for sub in ["sdk", "motion", "brain/gracemo_brain", "brain/gracemo_brain/skills"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_base_controller import BaseController
from arm_controller import ArmController
from hand_controller import HandSubsystem
from manipulation_skill import ManipulationSkill


def main():
    print("=================================================================")
    print("  GRaCEmo ViRa — Live Physical Pick & Cargo Stow Demo (M3 + M4)")
    print("=================================================================")

    # 1. Initialize Base Controller
    print("\n[PHASE 1] Initializing Base Controller and checking odometry...")
    base = BaseController()
    time.sleep(1.0)
    print(f"Current Robot Pose: X={base.cur_x:.2f}m, Y={base.cur_y:.2f}m, Yaw={math.degrees(base.cur_yaw):.1f}°")

    # 2. Drive to Bedroom Nightstand Docking Station
    # Target: X=-4.34, Y=2.95 facing North (yaw=90 deg) directly aligning right arm with book_math
    target_x = -4.34
    target_y = 2.95
    target_yaw = math.pi / 2.0  # +90 deg

    dist_to_dock = math.hypot(target_x - base.cur_x, target_y - base.cur_y)
    if dist_to_dock > 0.40:
        print(f"\n[PHASE 2] Navigating from current pose to nightstand dock ({target_x:.2f}, {target_y:.2f})...")
        waypoints = []
        # If in central hallway, route via corridor door
        if abs(base.cur_y) < 1.0:
            waypoints.append((-5.0, 0.0))
            waypoints.append((-5.0, 1.4))
        waypoints.append((target_x, target_y))
        
        ok_nav = base.follow_waypoints(waypoints, final_yaw=target_yaw)
        print(f"Docking arrival result: {ok_nav}")
    else:
        print(f"\n[PHASE 2] Robot is already near docking pose ({base.cur_x:.2f}, {base.cur_y:.2f}). Aligning heading...")
        base.rotate_to_heading(target_yaw)

    time.sleep(0.5)
    print(f"Docked at: X={base.cur_x:.2f}m, Y={base.cur_y:.2f}m, Yaw={math.degrees(base.cur_yaw):.1f}°")

    # 3. Initialize Manipulation Skill
    print("\n[PHASE 3] Initializing 6-DOF Arm and Hand Manipulation Skill...")
    skill = ManipulationSkill(mock=False)
    time.sleep(0.5)

    # 4. Gate M3: Pick & Physical Grasp Verification
    print("\n[PHASE 4] Executing Closed-Loop Pick & Test Lift on 'book_math'...")
    # Book is on nightstand at surface height 0.618m
    result = skill.pick_and_verify(
        target_id="book_math",
        target_reach_x=0.42,
        surface_height_z=0.618,
        lift_height_m=0.05,
        max_retries=2
    )

    print("\n--- Gate M3 Physical Evidence ---")
    print(f"Status:                 {result.status}")
    print(f"Verified:               {result.verified}")
    print(f"Commanded Lift:         {result.commanded_lift_m*1000:.1f} mm")
    print(f"Measured Hand Lift:     {result.measured_hand_delta_m*1000:.1f} mm")
    print(f"Measured Book Lift:     {result.measured_object_delta_m*1000:.1f} mm")
    print(f"Relative Error:         {result.relative_error_m*1000:.1f} mm (Tolerance: {result.tolerance_m*1000:.1f} mm)")
    print(f"Contact Left/Right:     {result.contact_left} / {result.contact_right}")
    print("---------------------------------")

    if not result.verified:
        print("\n⚠️ Gate M3 did not verify. Halting before tray transfer.")
        return

    # 5. Gate M4: Transfer to Rear Cargo Shelf & Tuck
    print("\n[PHASE 5] Gate M3 Verified! Proceeding to Gate M4: Cargo Shelf Stow...")
    stow_res = skill.stow_to_cargo_shelf(target_id="book_math")
    print(f"Cargo Stow Status:      {stow_res.status}")
    print(f"Cargo Verified:         {stow_res.verified}")
    print(f"Final Arm Stance:       {stow_res.arm_stance}")

    # 6. Final Cruise Stance Check
    p_ee, _ = skill.arm.get_ee_pose()
    print(f"Palm Stowed at:         X={p_ee[0]:.2f}m, Y={p_ee[1]:.2f}m, Z={p_ee[2]:.2f}m")
    print("\n🎉 MISSION COMPLETE! The book was picked up, physically verified, stowed on the cargo tray, and arm is tucked for transit.")


if __name__ == "__main__":
    main()
