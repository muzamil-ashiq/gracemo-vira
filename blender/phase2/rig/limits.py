"""
GRACEEMO-01 — Central Joint Limits Configuration
All values in radians unless specified. Easy to tune and configure.
"""

import math
import bpy

JOINT_LIMITS = {
    # -------------------------------------------------------------
    # Neck Limits (Degrees of Freedom: Yaw, Pitch, Roll)
    # -------------------------------------------------------------
    "NECK_YAW_MIN": -1.2,        # -68.75 deg (Turn Left)
    "NECK_YAW_MAX": 1.2,         # +68.75 deg (Turn Right)
    "NECK_PITCH_MIN": -0.5,      # -28.6 deg (Pitch Down)
    "NECK_PITCH_MAX": 0.6,       # +34.4 deg (Pitch Up)
    "NECK_ROLL_MIN": -0.35,      # -20.0 deg (Tilt Left)
    "NECK_ROLL_MAX": 0.35,       # +20.0 deg (Tilt Right)

    # -------------------------------------------------------------
    # Left Arm Limits (Shoulder Pitch/Roll, Elbow, Wrist)
    # -------------------------------------------------------------
    "LEFT_SHOULDER_PITCH_MIN": -1.6,   # Forward raised swing (~91 deg)
    "LEFT_SHOULDER_PITCH_MAX": 0.6,    # Backward swing (~34 deg)
    "LEFT_SHOULDER_ROLL_MIN": -0.2,    # Inward
    "LEFT_SHOULDER_ROLL_MAX": 1.5708,  # Outward lateral raise (~90 deg)
    "LEFT_ELBOW_MIN": -2.0944,         # Bent forward (~120 deg)
    "LEFT_ELBOW_MAX": 0.2,             # Straight / extension
    "LEFT_WRIST_MIN": -0.7854,         # -45 deg
    "LEFT_WRIST_MAX": 0.7854,          # +45 deg

    # -------------------------------------------------------------
    # Right Arm Limits (Mirrored)
    # -------------------------------------------------------------
    "RIGHT_SHOULDER_PITCH_MIN": -1.6,  # Forward raised swing (~91 deg)
    "RIGHT_SHOULDER_PITCH_MAX": 0.6,   # Backward swing (~34 deg)
    "RIGHT_SHOULDER_ROLL_MIN": -1.5708,# Outward lateral raise (~90 deg)
    "RIGHT_SHOULDER_ROLL_MAX": 0.2,    # Inward
    "RIGHT_ELBOW_MIN": -2.0944,        # Bent forward (~120 deg)
    "RIGHT_ELBOW_MAX": 0.2,            # Straight / extension
    "RIGHT_WRIST_MIN": -0.7854,        # -45 deg
    "RIGHT_WRIST_MAX": 0.7854,         # +45 deg

    # -------------------------------------------------------------
    # Hand Limits (Finger Flexion)
    # -------------------------------------------------------------
    "FINGER_CURL_MIN": 0.0,            # Extended flat
    "FINGER_CURL_MAX": 1.45,           # Curled closed (~83 deg)
    "THUMB_CURL_MIN": 0.0,
    "THUMB_CURL_MAX": 1.15,
}

def clamp_value(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def apply_limit_rotation(obj, min_x=None, max_x=None, min_y=None, max_y=None, min_z=None, max_z=None, space='LOCAL'):
    """Add or update LIMIT_ROTATION constraint on object."""
    c = obj.constraints.get("Limit_Rotation")
    if not c:
        c = obj.constraints.new('LIMIT_ROTATION')
        c.name = "Limit_Rotation"
    c.owner_space = space

    if min_x is not None or max_x is not None:
        c.use_limit_x = True
        c.min_x = min_x if min_x is not None else -math.pi
        c.max_x = max_x if max_x is not None else math.pi
    else:
        c.use_limit_x = False

    if min_y is not None or max_y is not None:
        c.use_limit_y = True
        c.min_y = min_y if min_y is not None else -math.pi
        c.max_y = max_y if max_y is not None else math.pi
    else:
        c.use_limit_y = False

    if min_z is not None or max_z is not None:
        c.use_limit_z = True
        c.min_z = min_z if min_z is not None else -math.pi
        c.max_z = max_z if max_z is not None else math.pi
    else:
        c.use_limit_z = False
    return c
