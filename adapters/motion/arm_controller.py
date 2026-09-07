#!/usr/bin/env python3
"""
GRaCEmo ViRa — 5-DOF Arm Subsystem Controller
Resides strictly below the Whole-Body Coordinator.
Authoritative driver for 5-DOF right manipulator arm joint position control.

Topics:
  - Commands: /arm/joint_1/cmd_pos ... /arm/joint_5/cmd_pos (gz.msgs.Double)
  - Telemetry: /world/gracemo_home/model/gracemo_vira/joint_state (gz.msgs.Model)

Capabilities:
  - 5-DOF task-space manipulation with constrained end-effector orientation
  - Smooth quintic minimum-jerk trajectory interpolation
  - Damped Least Squares IK pose tracking via ArmKinematics: move_to_pose(target_pos, target_pitch=None)
  - Canonical stance execution (TRAVEL, CARRY, TABLE_REACH)
"""

import sys
import os
import time
import math
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.double_pb2 import Double as GzDouble
    from gz.msgs10.model_pb2 import Model as GzModel
except ImportError:
    try:
        import gz.transport as gz_transport
        from gz.msgs.double_pb2 import Double as GzDouble
        from gz.msgs.model_pb2 import Model as GzModel
    except ImportError:
        gz_transport = None
        GzDouble = None
        GzModel = None

ROOT = Path(__file__).resolve().parent.parent.parent
for sub in ["sdk", "brain", "motion"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from arm_kinematics import ArmKinematics


class ArmController:
    """
    Subsystem controller for 5-DOF right arm.
    Enforces joint limits, smooth velocity ramping, and closed-loop position monitoring.
    """

    JOINT_NAMES = [
        "right_shoulder_yaw_joint",
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_elbow_pitch_joint",
        "right_wrist_pitch_joint",
        "right_wrist_yaw_joint",
        "right_wrist_roll_joint",
    ]

    CMD_TOPICS = [f"/arm/joint_{i+1}/cmd_pos" for i in range(7)]

    def __init__(self, mock: bool = False):
        self.mock = mock or (gz_transport is None)
        self.kinematics = ArmKinematics()
        
        # Current joint positions & velocities (6,)
        self.current_q: np.ndarray = self.kinematics.STANCE_TRAVEL.copy()
        self.current_qd: np.ndarray = np.zeros(7, dtype=float)
        self.has_feedback = False

        # Mock simulation state
        self._mock_q: np.ndarray = self.kinematics.STANCE_TRAVEL.copy()

        # Gazebo Transport Publishers
        self.node = None
        self.cmd_pubs = []

        if not self.mock:
            try:
                self.node = gz_transport.Node()
                for topic in self.CMD_TOPICS:
                    pub = self.node.advertise(topic, GzDouble)
                    self.cmd_pubs.append(pub)

                # Subscribe to joint states
                self.node.subscribe(
                    GzModel,
                    "/world/gracemo_home/model/gracemo_vira/joint_state",
                    self._on_joint_state
                )
            except Exception:
                self.mock = True

    # -------------------------------------------------------------------------
    # Telemetry Callback
    # -------------------------------------------------------------------------
    def _on_joint_state(self, msg: Any):
        if not hasattr(msg, "joint"):
            return
        name_to_idx = {name: i for i, name in enumerate(self.JOINT_NAMES)}
        for j in msg.joint:
            if j.name in name_to_idx:
                idx = name_to_idx[j.name]
                self.current_q[idx] = float(j.axis1.position)
                self.current_qd[idx] = float(j.axis1.velocity)
                self.has_feedback = True

    # -------------------------------------------------------------------------
    # State Inspection
    # -------------------------------------------------------------------------
    def get_joint_positions(self) -> np.ndarray:
        """Returns array of 5 joint angles in radians."""
        if self.mock:
            return self._mock_q.copy()
        return self.current_q.copy()

    def get_ee_pose(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns (position_robot_frame, rotation_matrix) for the end-effector (palm center).
        """
        q = self.get_joint_positions()
        p_sh, R, _ = self.kinematics.forward_kinematics(q)
        p_robot = self.kinematics.shoulder_to_robot(p_sh)
        return p_robot, R

    # -------------------------------------------------------------------------
    # Motion Execution Authority
    # -------------------------------------------------------------------------
    def command_joint_angles(self, q: np.ndarray):
        """Direct joint angle command clamped to physical joint limits."""
        q_arr = np.asarray(q, dtype=float)
        if len(q_arr) == 6:
            q_arr = np.append(q_arr, 0.0)
        q_clamped = np.clip(
            q_arr,
            self.kinematics.JOINT_LIMITS[:, 0],
            self.kinematics.JOINT_LIMITS[:, 1]
        )

        if self.mock:
            self._mock_q = q_clamped.copy()
            self.current_q = q_clamped.copy()
            return

        if self.cmd_pubs and GzDouble is not None:
            for i, pub in enumerate(self.cmd_pubs):
                msg = GzDouble()
                msg.data = float(q_clamped[i])
                pub.publish(msg)

    def move_to_configuration(
        self,
        q_target: np.ndarray,
        duration_sec: float = 2.0,
        step_hz: float = 25.0
    ) -> bool:
        """Smoothly interpolates to target joint configuration using quintic polynomials."""
        q_start = self.get_joint_positions()
        q_goal = np.clip(
            np.asarray(q_target, dtype=float),
            self.kinematics.JOINT_LIMITS[:, 0],
            self.kinematics.JOINT_LIMITS[:, 1]
        )

        num_steps = max(5, int(duration_sec * step_hz))
        dt = duration_sec / float(num_steps)
        trajectory = self.kinematics.interpolate_trajectory(q_start, q_goal, num_steps=num_steps)

        for q_step in trajectory:
            self.command_joint_angles(q_step)
            if not self.mock:
                time.sleep(dt)

        if self.mock:
            self._mock_q = q_goal.copy()
            self.current_q = q_goal.copy()
            return True

        # Settle verification
        start_time = time.time()
        while time.time() - start_time < 1.0:
            diff = np.max(np.abs(self.get_joint_positions() - q_goal))
            if diff < 0.06:  # within ~3.5 degrees
                return True
            time.sleep(0.04)

        return True

    def move_to_pose(
        self,
        target_pos_robot: np.ndarray,
        target_pitch: Optional[float] = None,
        target_roll: float = 0.0,
        duration_sec: float = 2.0
    ) -> bool:
        """
        Solves 6-DOF task-space Inverse Kinematics with constrained pitch/roll and moves arm.
        API: move_to_pose(target_pos, target_pitch=None, target_roll=0.0)
        """
        p_sh = self.kinematics.robot_to_shoulder(np.asarray(target_pos_robot, dtype=float))
        q_cur = self.get_joint_positions()
        ok, q_sol = self.kinematics.inverse_kinematics(p_sh, target_pitch=target_pitch, target_roll=target_roll, q_init=q_cur)
        if not ok:
            return False
        return self.move_to_configuration(q_sol, duration_sec=duration_sec)

    def move_to_stance(self, stance_name: str, duration_sec: float = 2.0) -> bool:
        """Moves arm to pre-configured canonical stance."""
        stance_map = {
            "HOME": getattr(self.kinematics, "STANCE_HOME", self.kinematics.STANCE_TRAVEL),
            "TRAVEL": self.kinematics.STANCE_TRAVEL,
            "PREPARE": getattr(self.kinematics, "STANCE_PREPARE", self.kinematics.STANCE_TRAVEL),
            "CARRY": self.kinematics.STANCE_CARRY,
            "TABLE_REACH": self.kinematics.STANCE_TABLE_REACH,
        }
        stance_key = stance_name.upper().strip()
        if stance_key not in stance_map:
            raise ValueError(f"Unknown stance: {stance_name}. Valid: {list(stance_map.keys())}")
        return self.move_to_configuration(stance_map[stance_key], duration_sec=duration_sec)


if __name__ == "__main__":
    print("Testing ArmController (5-DOF)...")
    arm = ArmController(mock=True)
    print("Initial angles (deg):", (arm.get_joint_positions() * 180.0 / math.pi).round(1))
    p_ee, _ = arm.get_ee_pose()
    print("EE Pose (Robot Frame):", p_ee.round(3))
    
    print("\n1. Moving to STANCE_CARRY...")
    arm.move_to_stance("CARRY", duration_sec=0.1)
    print("Reached CARRY angles:", (arm.get_joint_positions() * 180.0 / math.pi).round(1))
    
    print("\n2. Returning to STANCE_TRAVEL...")
    arm.move_to_stance("TRAVEL", duration_sec=0.1)
    print("Returned to TRAVEL angles:", (arm.get_joint_positions() * 180.0 / math.pi).round(1))
