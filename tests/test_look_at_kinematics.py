#!/usr/bin/env python3
"""
Unit and kinematic test suite for Phase 3 Step 4: 2-DOF Active Neck LookAt Kinematics.

Validates:
TEST 1:  Target directly ahead at neck height -> pan ≈ 0°, tilt ≈ 0°
TEST 2:  Target 45° left at same height -> pan ≈ +45°, tilt ≈ 0°
TEST 3:  Target 45° right at same height -> pan ≈ -45°, tilt ≈ 0°
TEST 4:  Target below robot at same horizontal direction -> tilt > 0° (positive tilt = downward)
TEST 5:  Target above robot -> tilt < 0° (negative tilt = upward)
TEST 6:  Target exactly at +120° -> accepted (workspace_exceeded = False)
TEST 7:  Target exactly at -120° -> accepted (workspace_exceeded = False)
TEST 8:  Target beyond +120° -> rejected (workspace_exceeded = True)
TEST 9:  Target beyond -120° -> rejected (workspace_exceeded = True)
TEST 10: Target requiring tilt > +45° -> rejected (workspace_exceeded = True)
TEST 11: Target requiring tilt < -45° -> rejected (workspace_exceeded = True)
TEST 12: Workspace rejection -> verify NO /cmd_vel command is generated, neck not commanded
TEST 13: Valid LookAt -> verify NO /cmd_vel command is generated, neck commanded

Additional tests:
- Robot at non-zero world pose and non-zero yaw heading
- Output structure schema compliance (required keys for success and failure)
"""

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = REPO_ROOT / "ros2_ws" / "src" / "gracemo_bridge"
if str(BRIDGE_PATH) not in sys.path:
    sys.path.insert(0, str(BRIDGE_PATH))

from gracemo_bridge.kernel_bridge import (
    compute_look_at,
    KernelBridgeNode,
    PAN_LIMIT_RAD,
    TILT_LIMIT_RAD,
    NECK_OFFSET_X,
    NECK_OFFSET_Y,
    NECK_OFFSET_Z,
)


class TestLookAtKinematics(unittest.TestCase):
    """Kinematic and limit enforcement unit tests for GRaCEmo active head."""

    def setUp(self):
        # Default robot neutral pose at origin
        self.rx = 0.0
        self.ry = 0.0
        self.rz = 0.0
        self.ryaw = 0.0

        # Neutral neck pivot world coordinates for robot at origin:
        # x_neck = 0 - 0.02 * cos(0) = -0.02
        # y_neck = 0 - 0.02 * sin(0) = 0.00
        # z_neck = 0 + 0.645 = 0.645
        self.neck_x = self.rx + NECK_OFFSET_X * math.cos(self.ryaw)
        self.neck_y = self.ry + NECK_OFFSET_X * math.sin(self.ryaw)
        self.neck_z = self.rz + NECK_OFFSET_Z

    # -------------------------------------------------------------------------
    # TEST 1: Target directly ahead at neck height
    # -------------------------------------------------------------------------
    def test_01_target_ahead_at_neck_height(self):
        """TEST 1: Target directly ahead at neck height -> pan ≈ 0°, tilt ≈ 0°."""
        tx = self.neck_x + 2.0
        ty = self.neck_y + 0.0
        tz = self.neck_z + 0.0

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Failed: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertAlmostEqual(res["pan_deg"], 0.0, delta=0.5)
        self.assertAlmostEqual(res["tilt_deg"], 0.0, delta=0.5)
        self.assertAlmostEqual(res["pan_rad"], 0.0, delta=0.01)
        self.assertAlmostEqual(res["tilt_rad"], 0.0, delta=0.01)

    # -------------------------------------------------------------------------
    # TEST 2: Target 45° left at same height
    # -------------------------------------------------------------------------
    def test_02_target_45_left_same_height(self):
        """TEST 2: Target 45° left at same height -> pan ≈ +45°, tilt ≈ 0°."""
        dist = 2.0
        angle_rad = math.radians(45.0)
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Failed: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertAlmostEqual(res["pan_deg"], 45.0, delta=0.5)
        self.assertAlmostEqual(res["tilt_deg"], 0.0, delta=0.5)
        self.assertAlmostEqual(res["pan_rad"], angle_rad, delta=0.01)

    # -------------------------------------------------------------------------
    # TEST 3: Target 45° right at same height
    # -------------------------------------------------------------------------
    def test_03_target_45_right_same_height(self):
        """TEST 3: Target 45° right at same height -> pan ≈ -45°, tilt ≈ 0°."""
        dist = 2.0
        angle_rad = math.radians(-45.0)
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Failed: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertAlmostEqual(res["pan_deg"], -45.0, delta=0.5)
        self.assertAlmostEqual(res["tilt_deg"], 0.0, delta=0.5)
        self.assertAlmostEqual(res["pan_rad"], angle_rad, delta=0.01)

    # -------------------------------------------------------------------------
    # TEST 4: Target below robot at same horizontal direction
    # -------------------------------------------------------------------------
    def test_04_target_below_robot(self):
        """TEST 4: Target below robot at same horizontal direction -> tilt > 0°."""
        tx = self.neck_x + 2.0
        ty = self.neck_y
        tz = self.neck_z - 0.5  # 0.5m below neck pivot

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Failed: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertGreater(res["tilt_rad"], 0.0, "Positive tilt must mean looking downward")
        self.assertGreater(res["tilt_deg"], 0.0, "Positive tilt must mean looking downward")
        self.assertAlmostEqual(res["pan_deg"], 0.0, delta=0.5)

    # -------------------------------------------------------------------------
    # TEST 5: Target above robot
    # -------------------------------------------------------------------------
    def test_05_target_above_robot(self):
        """TEST 5: Target above robot -> tilt < 0° (looking upward)."""
        tx = self.neck_x + 2.0
        ty = self.neck_y
        tz = self.neck_z + 0.5  # 0.5m above neck pivot

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Failed: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertLess(res["tilt_rad"], 0.0, "Negative tilt must mean looking upward")
        self.assertLess(res["tilt_deg"], 0.0, "Negative tilt must mean looking upward")
        self.assertAlmostEqual(res["pan_deg"], 0.0, delta=0.5)

    # -------------------------------------------------------------------------
    # TEST 6: Target exactly at +120°
    # -------------------------------------------------------------------------
    def test_06_target_exactly_at_plus_120(self):
        """TEST 6: Target exactly at +120° -> accepted."""
        dist = 2.0
        angle_rad = math.radians(120.0)
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Target at +120° must be accepted: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertAlmostEqual(res["pan_deg"], 120.0, delta=0.1)

    # -------------------------------------------------------------------------
    # TEST 7: Target exactly at -120°
    # -------------------------------------------------------------------------
    def test_07_target_exactly_at_minus_120(self):
        """TEST 7: Target exactly at -120° -> accepted."""
        dist = 2.0
        angle_rad = math.radians(-120.0)
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertTrue(res["success"], f"Target at -120° must be accepted: {res}")
        self.assertFalse(res["workspace_exceeded"])
        self.assertAlmostEqual(res["pan_deg"], -120.0, delta=0.1)

    # -------------------------------------------------------------------------
    # TEST 8: Target beyond +120°
    # -------------------------------------------------------------------------
    def test_08_target_beyond_plus_120(self):
        """TEST 8: Target beyond +120° -> rejected."""
        dist = 2.0
        angle_rad = math.radians(125.0)  # Beyond +120°
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertFalse(res["success"])
        self.assertTrue(res["workspace_exceeded"])
        self.assertIn("pan", res["reason"].lower())
        self.assertIn("pan_limit", res)
        self.assertIn("calculated_pan", res)

    # -------------------------------------------------------------------------
    # TEST 9: Target beyond -120°
    # -------------------------------------------------------------------------
    def test_09_target_beyond_minus_120(self):
        """TEST 9: Target beyond -120° -> rejected."""
        dist = 2.0
        angle_rad = math.radians(-125.0)  # Beyond -120°
        tx = self.neck_x + dist * math.cos(angle_rad)
        ty = self.neck_y + dist * math.sin(angle_rad)
        tz = self.neck_z

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertFalse(res["success"])
        self.assertTrue(res["workspace_exceeded"])
        self.assertIn("pan", res["reason"].lower())
        self.assertIn("pan_limit", res)
        self.assertIn("calculated_pan", res)

    # -------------------------------------------------------------------------
    # TEST 10: Target requiring tilt > +45°
    # -------------------------------------------------------------------------
    def test_10_target_tilt_exceeds_plus_45(self):
        """TEST 10: Target requiring tilt > +45° -> rejected (downward steep)."""
        # Horizontal dist = 0.5m, vertical drop = 1.0m -> tilt = atan2(1.0, 0.5) = 63.4° > 45°
        tx = self.neck_x + 0.5
        ty = self.neck_y
        tz = self.neck_z - 1.0

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertFalse(res["success"])
        self.assertTrue(res["workspace_exceeded"])
        self.assertIn("tilt", res["reason"].lower())
        self.assertIn("tilt_limit", res)
        self.assertIn("calculated_tilt", res)

    # -------------------------------------------------------------------------
    # TEST 11: Target requiring tilt < -45°
    # -------------------------------------------------------------------------
    def test_11_target_tilt_exceeds_minus_45(self):
        """TEST 11: Target requiring tilt < -45° -> rejected (upward steep)."""
        # Horizontal dist = 0.5m, vertical height = +1.0m -> tilt = atan2(-1.0, 0.5) = -63.4° < -45°
        tx = self.neck_x + 0.5
        ty = self.neck_y
        tz = self.neck_z + 1.0

        res = compute_look_at(tx, ty, tz, self.rx, self.ry, self.rz, self.ryaw)
        self.assertFalse(res["success"])
        self.assertTrue(res["workspace_exceeded"])
        self.assertIn("tilt", res["reason"].lower())
        self.assertIn("tilt_limit", res)
        self.assertIn("calculated_tilt", res)

    # -------------------------------------------------------------------------
    # TEST 12: Workspace rejection -> Verify NO /cmd_vel is generated
    # -------------------------------------------------------------------------
    def test_12_workspace_rejection_no_cmd_vel(self):
        """TEST 12: On workspace rejection, NO /cmd_vel or neck commands are published."""
        # Create a mock node object mirroring KernelBridgeNode methods
        mock_node = MagicMock()
        mock_node.current_x = 0.0
        mock_node.current_y = 0.0
        mock_node.current_z = 0.0
        mock_node.current_yaw_rad = 0.0

        # Bind the real compute_look_at and execute_look_at methods
        mock_node.compute_look_at = lambda tx, ty, tz: KernelBridgeNode.compute_look_at(mock_node, tx, ty, tz)
        mock_node.execute_look_at = lambda tx, ty, tz: KernelBridgeNode.execute_look_at(mock_node, tx, ty, tz)

        # Target far behind the robot (180° pan)
        target_x = -3.0
        target_y = 0.0
        target_z = 0.645

        result = mock_node.execute_look_at(target_x, target_y, target_z)

        self.assertFalse(result["success"])
        self.assertTrue(result["workspace_exceeded"])

        # Invariant: Neither neck command nor cmd_vel publisher must be called
        mock_node.publish_neck_command.assert_not_called()
        mock_node._publish_cmd_vel.assert_not_called()
        mock_node.ros_cmd_pub.publish.assert_not_called()
        mock_node.gz_cmd_pub.publish.assert_not_called()

    # -------------------------------------------------------------------------
    # TEST 13: Valid LookAt -> Verify NO /cmd_vel is generated
    # -------------------------------------------------------------------------
    def test_13_valid_lookat_no_cmd_vel(self):
        """TEST 13: On valid LookAt, neck commands are published, but NO /cmd_vel is generated."""
        mock_node = MagicMock()
        mock_node.current_x = 0.0
        mock_node.current_y = 0.0
        mock_node.current_z = 0.0
        mock_node.current_yaw_rad = 0.0

        # Bind the real compute_look_at and execute_look_at methods
        mock_node.compute_look_at = lambda tx, ty, tz: KernelBridgeNode.compute_look_at(mock_node, tx, ty, tz)
        mock_node.execute_look_at = lambda tx, ty, tz: KernelBridgeNode.execute_look_at(mock_node, tx, ty, tz)

        # Target 30° left, slightly downward (table level)
        target_x = 2.0
        target_y = 1.0
        target_z = 0.30

        result = mock_node.execute_look_at(target_x, target_y, target_z)

        self.assertTrue(result["success"])
        self.assertFalse(result["workspace_exceeded"])

        # Neck command MUST be called with valid pan and tilt
        mock_node.publish_neck_command.assert_called_once()
        called_pan, called_tilt = mock_node.publish_neck_command.call_args[0]
        self.assertAlmostEqual(called_pan, result["pan_rad"])
        self.assertAlmostEqual(called_tilt, result["tilt_rad"])

        # INVARIANT: cmd_vel must NEVER be called by LookAt!
        mock_node._publish_cmd_vel.assert_not_called()
        mock_node.ros_cmd_pub.publish.assert_not_called()
        mock_node.gz_cmd_pub.publish.assert_not_called()

    # -------------------------------------------------------------------------
    # Additional: Rotated and translated robot pose
    # -------------------------------------------------------------------------
    def test_14_lookat_with_rotated_and_translated_robot(self):
        """Test LookAt calculation when robot is translated and rotated by 90° (yaw = +pi/2)."""
        rx = 2.0
        ry = 3.0
        rz = 0.0
        ryaw = math.pi / 2.0  # Robot facing +Y (North)

        # Target is placed at (2.0, 5.0, 0.645) -> directly in front of the robot!
        tx = 2.0
        ty = 5.0
        tz = 0.645

        res = compute_look_at(tx, ty, tz, rx, ry, rz, ryaw)
        self.assertTrue(res["success"])
        self.assertFalse(res["workspace_exceeded"])
        # In robot heading frame, target is directly ahead:
        self.assertAlmostEqual(res["pan_deg"], 0.0, delta=0.5)
        self.assertAlmostEqual(res["tilt_deg"], 0.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
