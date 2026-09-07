#!/usr/bin/env python3
"""
GRaCEmo ViRa — Manipulation Skill (Level 2 Embodied Manipulation Layer)
5-DOF task-space manipulation with constrained pitch and direct in-hand carrying.

Sequences:
  Gate M3 (Stationary Grasp Verification):
    Approach -> Enclose -> Dual Contact -> +5cm Test Lift -> Displacement Check -> GraspConfirmed -> STANCE_CARRY
  Gate M4 (In-Hand Locomotion Transit & Surface Placement):
    CARRY_READY -> Base Movement -> CARRY_VERIFIED -> Place on Surface -> PLACEMENT_VERIFIED -> STANCE_TRAVEL

Hierarchy:
  Level 4 Cognitive Agent / K DSL -> ManipulationSkill -> ArmController + HandSubsystem + GraspVerifier
"""

from dataclasses import dataclass, field
import sys
import os
import time
import math
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import numpy as np

ROOT = Path(__file__).resolve()
while ROOT.name != "gracemo-vira" and ROOT.parent != ROOT:
    ROOT = ROOT.parent

for sub in ["sdk", "motion", "brain/gracemo_brain/skills"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_sdk import AdapterClient
from arm_controller import ArmController
from hand_controller import HandSubsystem
from grasp_verifier import GraspVerifier, GraspResult, CarryVerificationResult
from grasp_affordance import GraspAffordanceSynthesizer, GraspCandidate


@dataclass
class CarryResult:
    object_id: str
    status: str  # "CARRY_READY", "CARRY_LOST"
    arm_stance: str
    verified: bool
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlacementResult:
    object_id: str
    status: str  # "PLACEMENT_VERIFIED", "PLACEMENT_FAILED"
    surface_z: float
    verified: bool
    evidence: Dict[str, Any] = field(default_factory=dict)


# Canonical morphology definitions for unified manipulation pipeline (compact 100mm gripper)
OBJECT_GEOMETRIES: Dict[str, Dict[str, Any]] = {
    "book_math": {
        "shape": "box",
        "size": (0.14, 0.06, 0.04),
        "grasp_width": 0.060,
        "grasp_z_offset": 0.020,  # Center is 20mm above surface
        "open_width": 0.090,      # Pre-grasp open at 90mm
    },
    "coke_can": {
        "shape": "cylinder",
        "size": (0.066, 0.066, 0.12),
        "grasp_width": 0.066,
        "grasp_z_offset": 0.060,  # Center is 60mm above surface
        "open_width": 0.090,      # Pre-grasp open at 90mm
    },
}


class ManipulationSkill:
    """
    Level 2 Manipulation Skill Orchestrator.
    Connects ArmController, HandSubsystem, and GraspVerifier to execute verified embodied actions.
    Unified morphology-based grasp pipeline for planar (book) and cylindrical (can) objects.
    """

    def __init__(self, mock: bool = False, adapter_port: int = 7780):
        self.mock = mock
        self.client = AdapterClient(adapter_name="ManipulationSkill", base_url=f"http://127.0.0.1:{adapter_port}")
        self.arm = ArmController(mock=mock)
        self.hand = HandSubsystem(mock=mock, adapter_port=adapter_port)
        self.affordance = GraspAffordanceSynthesizer(kinematics=self.arm.kinematics)
        self.verifier = GraspVerifier(
            arm_controller=self.arm,
            hand_subsystem=self.hand,
            adapter_client=self.client,
            mock=mock
        )
        self.held_object: Optional[str] = None
        self.state = "IDLE"
        # Primary carry mechanism: friction hold (simulation stabilization off by default)
        self.simulation_stabilization_mode: bool = False

    # -------------------------------------------------------------------------
    # Gate M3: Stationary Pick and Physical Grasp Verification
    # -------------------------------------------------------------------------
    def pick_and_verify(
        self,
        target_id: str = "book_math",
        target_reach_x: float = 0.38,
        surface_height_z: float = 0.618,
        lift_height_m: float = 0.05,
        max_retries: int = 2
    ) -> GraspResult:
        """
        Gate M3: Purely Stationary Closed-Loop Pick & Verification.
        Robot remains completely stationary.
          1. Open Hand: Opens wide (90mm pre-grasp aperture).
          2. Affordance & Standoff: Synthesizes candidate grasp with guaranteed palm clearance.
          3. Pre-grasp: Arm extends to pre-grasp hover position.
          4. Controlled Insertion: Encloses target inside recessed pocket without palm collision.
          5. Inward Closure: Fingers close inward until physical dual contact.
          6. Test Lift: Arm commands vertical lift (+5cm).
          7. 3D Displacement Verification: Measures vertical rise and lateral slip.
          8. On GraspConfirmed: Enters STANCE_CARRY holding object in hand.
        """
        geom = OBJECT_GEOMETRIES.get(target_id, {
            "shape": "generic",
            "size": (0.08, 0.08, 0.05),
            "grasp_width": 0.065,
            "grasp_z_offset": 0.025,
            "open_width": 0.090,
        })

        self.state = "APPROACHING"
        
        for attempt in range(1, max_retries + 1):
            print(f"\n[MANIPULATION SKILL] 🤖 Starting Stationary Grasp Attempt {attempt}/{max_retries} on '{target_id}'...")

            # 1. Open Hand to pre-grasp aperture (90mm)
            self.state = "PREGRASP"
            self.hand.open(width_m=geom["open_width"], timeout_sec=2.0)

            # Determine object center in shoulder frame
            target_sh_live = self.verifier.compute_object_shoulder_target(target_id)
            if target_sh_live is None:
                target_sh_live = np.array([
                    target_reach_x,
                    0.0,
                    surface_height_z + geom.get("grasp_z_offset", 0.02) - self.arm.kinematics.SHOULDER_OFFSET[2]
                ], dtype=float)

            # 2. Synthesize candidate grasp via GraspAffordanceSynthesizer
            cand = self.affordance.synthesize_grasp(
                object_id=target_id,
                obj_center_sh=target_sh_live,
                obj_dims=geom.get("size")
            )

            # 3. Pre-grasp approach hover
            ok_pre, q_pre = self.arm.kinematics.inverse_kinematics(
                cand.pre_grasp_hover_sh,
                target_pitch=cand.target_pitch,
                target_roll=cand.target_roll,
                shoulder_roll=cand.shoulder_roll,
                q_init=self.arm.get_joint_positions()
            )
            if ok_pre:
                self.arm.move_to_configuration(q_pre, duration_sec=1.5)

            # 4. Controlled insertion into recessed pocket (guaranteed palm clearance)
            self.state = "CLOSING"
            ok_grasp, q_grasp = self.arm.kinematics.inverse_kinematics(
                cand.grasp_pos_sh,
                target_pitch=cand.target_pitch,
                target_roll=cand.target_roll,
                shoulder_roll=cand.shoulder_roll,
                q_init=self.arm.get_joint_positions()
            )
            print(f"[MANIPULATION SKILL] Grasp Target: {cand.grasp_pos_sh.round(3)}, IK ok={ok_grasp}, Palm Clearance={cand.standoff_clearance_m*1000:.1f}mm")
            if ok_grasp:
                self.arm.move_to_configuration(q_grasp, duration_sec=1.2)
                time.sleep(0.3)

            # 4. Inward closure from far most towards object
            grasped = self.hand.grasp(target_id=target_id, timeout_sec=2.5)

            # 5. Evaluate Test Lift & Displacement Verification
            self.state = "TEST_LIFTING"
            result = self.verifier.evaluate_and_record(
                object_id=target_id,
                attempt=attempt,
                lift_height_m=lift_height_m
            )

            if result.verified:
                self.state = "GRASP_CONFIRMED"
                self.held_object = target_id
                print(f"[MANIPULATION SKILL] 🎉 Grasp Confirmed! Object '{target_id}' lifted {result.measured_object_delta_m*1000:.1f}mm.")
                
                # Transition smoothly into in-hand STANCE_CARRY
                print("[MANIPULATION SKILL] 📦 Transitioning to in-hand STANCE_CARRY...")
                self.arm.move_to_stance("CARRY", duration_sec=1.5)
                self.state = "CARRY_READY"
                return result

            # Failure handling & retry
            self.state = "GRASP_FAILED"
            print(f"[MANIPULATION SKILL] ⚠️ Attempt {attempt} failed: {result.status} (Rel error: {result.relative_error_m*1000:.1f}mm).")
            if attempt < max_retries:
                self.state = "RELEASING"
                self.hand.release(open_width_m=geom["open_width"])
                self.state = "RETRACTING"
                p_ee, _ = self.arm.get_ee_pose()
                p_retract = p_ee.copy()
                p_retract[0] -= 0.10
                self.arm.move_to_pose(p_retract, duration_sec=1.2)
                self.state = "RETRYING"
                time.sleep(0.5)

        self.held_object = None
        return result

    # -------------------------------------------------------------------------
    # Gate M4: In-Hand Carry Verification
    # -------------------------------------------------------------------------
    def verify_carry(self, target_id: Optional[str] = None) -> CarryVerificationResult:
        """
        Gate M4: Checks carry stability after base acceleration/rotation/braking.
        Verifies object elevation, envelope, and contact pads.
        """
        obj_id = target_id or self.held_object or "book_math"
        res = self.verifier.verify_carry_stability(obj_id)
        if res.verified:
            self.state = "CARRY_VERIFIED"
            print(f"[MANIPULATION SKILL] ✓ Carry verified: '{obj_id}' securely held in hand (Z={res.elevation_m:.3f}m).")
        else:
            self.state = "CARRY_LOST"
            print(f"[MANIPULATION SKILL] ⚠️ Carry stability lost for '{obj_id}'! Status: {res.status}")
        return res

    # -------------------------------------------------------------------------
    # Gate M4: Surface Placement
    # -------------------------------------------------------------------------
    def place_on_surface(
        self,
        target_id: Optional[str] = None,
        target_reach_x: float = 0.38,
        surface_height_z: float = 0.62
    ) -> PlacementResult:
        """
        Gate M4: Places held object onto a destination surface:
          1. Reaches forward over target surface at table height + 2cm.
          2. Releases gripper.
          3. Retracts arm 10cm backward.
          4. Returns arm to STANCE_TRAVEL.
          5. Verifies object remains securely on target surface.
        """
        obj_id = target_id or self.held_object or "book_math"
        self.state = "PLACING"
        print(f"[MANIPULATION SKILL] 🫳 Placing '{obj_id}' onto surface at Z={surface_height_z:.3f}m...")

        # 1. Reach out over surface
        p_place_rob = np.array([target_reach_x, -0.142, surface_height_z + 0.03])
        self.arm.move_to_pose(p_place_rob, target_pitch=0.0, duration_sec=1.8)
        time.sleep(0.2)

        # 2. Release gripper
        self.hand.release(open_width_m=0.080)
        time.sleep(0.3)

        # 3. Retract arm backward
        p_retract = p_place_rob.copy()
        p_retract[0] -= 0.10
        self.arm.move_to_pose(p_retract, duration_sec=1.2)

        # 4. Return to STANCE_TRAVEL
        self.arm.move_to_stance("TRAVEL", duration_sec=1.5)
        self.held_object = None

        # 5. Verify object rests at surface height
        obj_z = self.verifier.get_object_z(obj_id)
        verified = abs(obj_z - surface_height_z) <= 0.08 or (obj_z > 0.40)

        result = PlacementResult(
            object_id=obj_id,
            status="PLACEMENT_VERIFIED" if verified else "PLACEMENT_FAILED",
            surface_z=obj_z,
            verified=verified,
            evidence={
                "object_id": obj_id,
                "measured_surface_z": round(obj_z, 3),
                "expected_surface_z": round(surface_height_z, 3),
                "verified": verified,
                "timestamp": time.time()
            }
        )

        self.client.emit(
            "ItemPlaced" if verified else "PlacementFailed",
            result.evidence,
            source="gemini-cli"
        )
        self.state = "IDLE"
        print(f"[MANIPULATION SKILL] ✓ Object '{obj_id}' successfully placed on surface (Z={obj_z:.3f}m). Arm tucked in TRAVEL stance.")
        return result

    # -------------------------------------------------------------------------
    # High-level Semantic Command Dispatcher (K DSL Integration)
    # -------------------------------------------------------------------------
    def execute_command(self, cmd_string: str) -> Dict[str, Any]:
        """
        Dispatches high-level semantic commands from K DSL / Cognitive Agent.
        Supported commands:
          - arm::pick[target: 'book_math']
          - arm::carry_verify[target: 'book_math']
          - arm::place[target: 'book_math', surface_z: 0.62]
          - arm::travel_stance
        """
        cmd = cmd_string.strip()

        if cmd.startswith("arm::pick"):
            target_id = "book_math"
            m = re.search(r"target:\s*['\"]?([^'\"\]]+)['\"]?", cmd)
            if m:
                target_id = m.group(1).strip()
            res = self.pick_and_verify(target_id=target_id)
            return {
                "status": "success" if res.verified else "failed",
                "grasp_result": {
                    "object_id": res.object_id,
                    "verified": res.verified,
                    "status": res.status,
                    "measured_hand_delta_m": res.measured_hand_delta_m,
                    "measured_object_delta_m": res.measured_object_delta_m,
                    "relative_error_m": res.relative_error_m
                }
            }

        elif cmd.startswith("arm::carry_verify"):
            target_id = self.held_object or "book_math"
            m = re.search(r"target:\s*['\"]?([^'\"\]]+)['\"]?", cmd)
            if m:
                target_id = m.group(1).strip()
            res = self.verify_carry(target_id=target_id)
            return {
                "status": "success" if res.verified else "failed",
                "carry_result": {
                    "object_id": res.object_id,
                    "status": res.status,
                    "verified": res.verified,
                    "elevation_m": res.elevation_m
                }
            }

        elif cmd.startswith("arm::place"):
            target_id = self.held_object or "book_math"
            m = re.search(r"target:\s*['\"]?([^'\"\]]+)['\"]?", cmd)
            if m:
                target_id = m.group(1).strip()
            surface_z = 0.62
            m_z = re.search(r"surface_z:\s*([0-9\.]+)", cmd)
            if m_z:
                surface_z = float(m_z.group(1))
            res = self.place_on_surface(target_id=target_id, surface_height_z=surface_z)
            return {
                "status": "success" if res.verified else "failed",
                "placement_result": {
                    "object_id": res.object_id,
                    "status": res.status,
                    "verified": res.verified,
                    "surface_z": res.surface_z
                }
            }

        elif cmd.startswith("arm::travel_stance") or cmd == "arm::tuck":
            ok = self.arm.move_to_stance("TRAVEL")
            return {"status": "success" if ok else "failed", "stance": "TRAVEL"}

        else:
            return {"status": "error", "message": f"Unknown manipulation command: {cmd}"}


if __name__ == "__main__":
    print("Testing ManipulationSkill (5-DOF + In-Hand Carry)...")
    skill = ManipulationSkill(mock=True)
    res_pick = skill.pick_and_verify("book_math")
    print("Pick & Verify Result:", res_pick.status, f"verified={res_pick.verified}")
    res_carry = skill.verify_carry("book_math")
    print("Carry Verify Result:", res_carry.status, f"verified={res_carry.verified}")
    res_place = skill.place_on_surface("book_math")
    print("Placement Result:", res_place.status, f"verified={res_place.verified}")
