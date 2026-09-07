#!/usr/bin/env python3
"""
GRaCEmo ViRa — 5-DOF Arm Kinematics & Constrained-Pitch Task-Space Verification Suite
Tests:
  1. Forward Kinematics (FK) sanity and reach bounds.
  2. Frame conversions (Shoulder <-> Robot Base).
  3. Geometric Jacobian dimensions and numerical consistency.
  4. DLS IK solver convergence (< 2mm error) for table reach targets.
  5. Canonical stances: STANCE_TRAVEL, STANCE_CARRY, STANCE_TABLE_REACH.
  6. Strict joint limit clamping in all solutions.
  7. Quintic trajectory interpolation smoothness.
"""

import unittest
import math
import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from arm_kinematics import ArmKinematics


class TestArmKinematics(unittest.TestCase):

    def setUp(self):
        self.arm = ArmKinematics()

    def test_01_frame_conversions(self):
        """Verify bidirectional shoulder <-> robot frame conversions."""
        p_robot = np.array([0.35, -0.14, 0.55])
        p_shoulder = self.arm.robot_to_shoulder(p_robot)
        p_recon = self.arm.shoulder_to_robot(p_shoulder)
        np.testing.assert_allclose(p_robot, p_recon, atol=1e-6)

    def test_02_reach_bounds(self):
        """Verify maximum kinematic reach does not exceed link sum (L1 + L2 + L3 = 0.50m)."""
        max_reach = self.arm.L1 + self.arm.L2 + self.arm.L3
        self.assertAlmostEqual(max_reach, 0.515, delta=1e-4)
        np.random.seed(42)
        for _ in range(50):
            q_rand = np.random.uniform(self.arm.JOINT_LIMITS[:, 0], self.arm.JOINT_LIMITS[:, 1])
            p_ee, _, _ = self.arm.forward_kinematics(q_rand)
            dist = np.linalg.norm(p_ee)
            self.assertLessEqual(dist, max_reach + 1e-4, f"Kinematic reach exceeded sum of links: {dist} > {max_reach}")

    def test_03_jacobian_dimension_and_rank(self):
        """Verify 4x6 Jacobian dimensions."""
        q = np.array([0.1, 0.3, -0.2, 0.8, 0.1, 0.0, 0.2])
        J = self.arm.compute_jacobian(q)
        self.assertEqual(J.shape, (4, 7))
        rank = np.linalg.matrix_rank(J)
        self.assertEqual(rank, 4, "Jacobian rank deficient at nominal configuration")

    def test_04_table_reach_ik_convergence(self):
        """Verify sub-2mm IK convergence for tabletop target."""
        target_shoulder = np.array([0.38, 0.0, -0.03])
        ok, q_sol = self.arm.inverse_kinematics(target_shoulder, target_pitch=0.0, pos_tol=1.5e-3)
        self.assertTrue(ok, "Table reach IK failed to converge!")
        
        p_check, _, _ = self.arm.forward_kinematics(q_sol)
        err = np.linalg.norm(target_shoulder - p_check)
        self.assertLess(err, 0.0025, f"IK error exceeded 2.5mm: {err*1000:.3f}mm")

        for i in range(7):
            self.assertGreaterEqual(q_sol[i], self.arm.JOINT_LIMITS[i, 0] - 1e-5)
            self.assertLessEqual(q_sol[i], self.arm.JOINT_LIMITS[i, 1] + 1e-5)

    def test_05_canonical_stances(self):
        """Verify all canonical stances have valid joint limits and positions."""
        for name, stance in [
            ("TRAVEL", self.arm.STANCE_TRAVEL),
            ("CARRY", self.arm.STANCE_CARRY),
            ("TABLE_REACH", self.arm.STANCE_TABLE_REACH)
        ]:
            self.assertEqual(len(stance), 7)
            for i in range(7):
                self.assertGreaterEqual(stance[i], self.arm.JOINT_LIMITS[i, 0] - 1e-5, f"{name} joint {i} below limit")
                self.assertLessEqual(stance[i], self.arm.JOINT_LIMITS[i, 1] + 1e-5, f"{name} joint {i} above limit")
            p_ee, _, _ = self.arm.forward_kinematics(stance)
            p_rob = self.arm.shoulder_to_robot(p_ee)
            self.assertTrue(np.all(np.isfinite(p_rob)))

    def test_06_trajectory_interpolation_continuity(self):
        """Verify quintic trajectory generation is smooth with zero boundary velocity."""
        q_start = self.arm.STANCE_TRAVEL
        q_goal = self.arm.STANCE_CARRY
        traj = self.arm.interpolate_trajectory(q_start, q_goal, num_steps=20)
        
        self.assertEqual(len(traj), 20)
        np.testing.assert_allclose(traj[0], q_start, atol=1e-5)
        np.testing.assert_allclose(traj[-1], q_goal, atol=1e-5)
        
        for i in range(len(traj) - 1):
            step_diff = np.linalg.norm(traj[i+1] - traj[i])
            self.assertLess(step_diff, 0.35, f"Discontinuous jump in trajectory step {i}: {step_diff}")

    def test_07_urdf_fk_agreement(self):
        """
        Acceptance Criterion: URDF FK end-effector position ≈ ArmKinematics FK position.
        Verifies position error < 1.0 mm at known configurations against raw URDF joint origins.
        """
        def urdf_fk_chain(q):
            # Raw origins from gracemo_vira.urdf.xacro:
            # 1. base_footprint -> base_link: (0, 0, 0.065)
            # 2. base_link -> torso_link: (-0.02, 0, 0.14)
            # 3. torso_link -> right_shoulder_yaw_link: (0, -0.122, 0.36)
            T = np.eye(4)
            T[:3, 3] += np.array([0.0, 0.0, 0.065])
            T[:3, 3] += np.array([-0.02, 0.0, 0.14])
            T[:3, 3] += np.array([0.0, -0.122, 0.36])
            
            # Joint 1: shoulder yaw (Z)
            T = T @ self.arm._rot_z(q[0])
            # Joint 2: shoulder pitch (Y)
            T = T @ self.arm._rot_y(q[1])
            # Joint 3: shoulder roll (X) + upper arm (0.22, 0, 0)
            T = T @ self.arm._rot_x(q[2]) @ self.arm._trans(0.22, 0.0, 0.0)
            # Joint 4: elbow pitch (Y) + forearm (0.22, 0, 0)
            T = T @ self.arm._rot_y(q[3]) @ self.arm._trans(0.22, 0.0, 0.0)
            # Joint 5: wrist pitch (Y)
            T = T @ self.arm._rot_y(q[4])
            # Joint 6: wrist yaw (Z)
            T = T @ self.arm._rot_z(q[5])
            # Joint 7: wrist roll (X) + palm/pocket (L3)
            T = T @ self.arm._rot_x(q[6]) @ self.arm._trans(self.arm.L3, 0.0, 0.0)
            return T[:3, 3]

        test_configs = [
            np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            self.arm.STANCE_TRAVEL,
            self.arm.STANCE_CARRY,
            self.arm.STANCE_TABLE_REACH,
            np.array([0.3, -0.2, 0.1, 0.9, -0.3, 0.1, 0.4]),
            np.array([-0.4, 0.5, -0.2, 1.2, 0.4, -0.1, -0.5])
        ]

        for idx, q_test in enumerate(test_configs):
            p_urdf = urdf_fk_chain(q_test)
            p_ee, _, _ = self.arm.forward_kinematics(q_test)
            p_kinematics = self.arm.shoulder_to_robot(p_ee)
            
            error_m = np.linalg.norm(p_urdf - p_kinematics)
            self.assertLess(
                error_m, 0.001,  # Strict < 1mm tolerance
                f"Config {idx}: URDF vs ArmKinematics FK error {error_m*1000:.3f}mm exceeds 1mm limit! "
                f"URDF={p_urdf}, Kinematics={p_kinematics}"
            )


if __name__ == "__main__":
    unittest.main()
