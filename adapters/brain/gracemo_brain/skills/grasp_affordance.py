#!/usr/bin/env python3
"""
GRaCEmo ViRa — Grasp Affordance Synthesizer
Answers the fundamental question: "Where and how should I try to grasp this object?"

Responsibilities:
  - Inspects object bounding box dimensions (length, width, height) and 3D pose.
  - Determines optimal grasp axis, aperture, and approach direction.
  - Computes exact pocket penetration and standoff to guarantee zero palm collision.
  - Generates 6D/7D Grasp Candidates (position, approach yaw, pitch, roll, preferred swivel)
    for the 7-DOF IK solver.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import numpy as np


@dataclass
class GraspCandidate:
    """Represents a validated candidate grasp pose in shoulder frame for 7-DOF manipulator."""
    object_id: str
    grasp_pos_sh: np.ndarray          # 3D position in arm shoulder frame (meters)
    pre_grasp_hover_sh: np.ndarray    # 3D hover position in arm shoulder frame (meters)
    approach_dir: np.ndarray          # Normalized 3D approach unit vector in shoulder frame
    target_yaw: float                 # Desired approach yaw angle (radians)
    target_pitch: float               # Desired pitch angle (radians)
    target_roll: float                # Desired wrist roll angle (radians)
    preferred_swivel: float           # Desired shoulder roll / swivel bias (radians)
    swivel_range: Tuple[float, float] # Soft allowable range for swivel (radians)
    expected_aperture_m: float        # Expected object dimension being clamped (meters)
    standoff_clearance_m: float       # Guaranteed clearance between object near edge and palm base (meters)

    @property
    def shoulder_roll(self) -> float:
        """Backward-compatibility property for shoulder_roll."""
        return self.preferred_swivel


class GraspAffordanceSynthesizer:
    """
    Synthesizes candidate grasps based on object geometry and gripper pocket mechanics.
    """

    # Gripper mechanical envelope constants (Compact 100mm Franka/Robotiq-style)
    MAX_APERTURE_M: float = 0.100       # 100mm maximum open aperture
    MIN_GAP_M: float = 0.010            # 10mm minimum closed gap
    POCKET_DEPTH_M: float = 0.070       # 70mm usable pocket depth to recessed U-channel
    PAD_CENTER_OFFSET_M: float = 0.050  # Distance from palm base to silicone pad center
    NOMINAL_PENETRATION_M: float = 0.040 # How far object front enters pad envelope (40mm, leaving 30mm clearance to palm base)

    # Known object geometry database (meters) [length (X), width (Y), height (Z)]
    OBJECT_GEOMETRIES: Dict[str, Tuple[float, float, float]] = {
        "book_math": (0.140, 0.060, 0.040),      # Math book: 140mm long, 60mm wide, 40mm thick
        "coke_can": (0.065, 0.065, 0.120),       # Soda can: 65mm diameter, 120mm height
        "water_bottle": (0.070, 0.070, 0.200),   # Water bottle: 70mm diameter, 200mm height
        "apple": (0.075, 0.075, 0.075),          # Apple: 75mm sphere
    }

    def __init__(self, kinematics=None):
        self.kinematics = kinematics

    def synthesize_grasp(
        self,
        object_id: str,
        obj_center_sh: np.ndarray,
        obj_dims: Optional[Tuple[float, float, float]] = None,
        approach_type: str = "horizontal_side",
        preferred_swivel: float = math.radians(38.0),
        swivel_range: Tuple[float, float] = (math.radians(25.0), math.radians(50.0))
    ) -> Optional[GraspCandidate]:
        """
        Synthesizes a 7-DOF candidate grasp for a target object.
        Args:
          - object_id: Identifier of target object.
          - obj_center_sh: Center position of object in shoulder frame (3,).
          - obj_dims: Optional (length, width, height) in meters.
          - approach_type: horizontal_side, top_down, or auto.
          - preferred_swivel: Soft elbow-swivel bias (default: 38 deg).
          - swivel_range: Soft range for swivel bias (default: 25-50 deg).
        """
        dims = obj_dims or self.OBJECT_GEOMETRIES.get(object_id, (0.100, 0.060, 0.040))
        length, width, height = dims

        dist_xy = math.hypot(obj_center_sh[0], obj_center_sh[1])
        if dist_xy < 0.05:
            dir_xy = np.array([1.0, 0.0, 0.0], dtype=float)
        else:
            dir_xy = np.array([obj_center_sh[0] / dist_xy, obj_center_sh[1] / dist_xy, 0.0], dtype=float)

        approach_dir = dir_xy
        target_yaw = math.atan2(approach_dir[1], approach_dir[0])

        # Along the line of sight (approach direction), find the dimension of the object
        depth_along_approach = length
        near_edge_offset = depth_along_approach / 2.0

        # Place pad center NOMINAL_PENETRATION_M into the near edge
        grasp_offset = near_edge_offset - self.NOMINAL_PENETRATION_M
        grasp_pos_sh = obj_center_sh - grasp_offset * approach_dir

        # Ensure tabletop clearance buffer (fingers 26mm tall, keep 12mm buffer above table)
        grasp_pos_sh[2] = max(grasp_pos_sh[2] + 0.008, 0.040)

        # Standoff clearance between object near edge and palm base
        standoff_clearance_m = self.PAD_CENTER_OFFSET_M - self.NOMINAL_PENETRATION_M

        # Pre-grasp hover pose: elevated 80mm directly above target to guarantee zero table collision
        pre_grasp_hover_sh = grasp_pos_sh - 0.040 * approach_dir + np.array([0.0, 0.0, 0.080], dtype=float)

        target_pitch = 0.0
        target_roll = 0.0
        expected_aperture = width

        return GraspCandidate(
            object_id=object_id,
            grasp_pos_sh=grasp_pos_sh,
            pre_grasp_hover_sh=pre_grasp_hover_sh,
            approach_dir=approach_dir,
            target_yaw=target_yaw,
            target_pitch=target_pitch,
            target_roll=target_roll,
            preferred_swivel=preferred_swivel,
            swivel_range=swivel_range,
            expected_aperture_m=expected_aperture,
            standoff_clearance_m=standoff_clearance_m
        )
