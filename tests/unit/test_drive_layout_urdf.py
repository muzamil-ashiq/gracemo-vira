"""
Unit tests for URDF Drive Topology Parameterization.
Verifies Phase 6 requirements:
1. 'differential' generates 2 continuous wheel joints (left, right) and 2 casters (front, rear).
2. 'four_wheel_skid_steer' generates 4 continuous wheel joints (front_left, front_right, rear_left, rear_right) and 0 casters.
"""

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
XACRO_PATH = ROOT / "ros2_ws" / "src" / "gracemo_description" / "urdf" / "gracemo_vira_parameterized.urdf.xacro"


def generate_urdf(drive_layout: str) -> ET.Element:
    """Executes xacro with specified drive_layout argument and returns parsed XML root."""
    cmd = [
        "xacro",
        str(XACRO_PATH),
        f"drive_layout:={drive_layout}"
    ]
    env = os.environ.copy()
    install_prefix = ROOT / "ros2_ws" / "install"
    desc_install = install_prefix / "gracemo_description"
    if desc_install.exists():
        existing = env.get("AMENT_PREFIX_PATH", "")
        if str(desc_install) not in existing:
            env["AMENT_PREFIX_PATH"] = f"{desc_install}:{existing}" if existing else str(desc_install)

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, env=env)
    return ET.fromstring(res.stdout)


def test_urdf_differential_layout_generation():
    """Verify 2WD differential drive generation with casters."""
    root = generate_urdf("differential")

    joints = {j.get("name"): j.get("type") for j in root.findall(".//joint")}
    assert "left_wheel_joint" in joints
    assert "right_wheel_joint" in joints
    assert joints["left_wheel_joint"] == "continuous"
    assert joints["right_wheel_joint"] == "continuous"

    assert "front_caster_joint" in joints
    assert "rear_caster_joint" in joints
    assert joints["front_caster_joint"] == "fixed"
    assert joints["rear_caster_joint"] == "fixed"

    # Ensure 4WD joints are not present
    assert "front_left_wheel_joint" not in joints
    assert "front_right_wheel_joint" not in joints
    assert "rear_left_wheel_joint" not in joints
    assert "rear_right_wheel_joint" not in joints


def test_urdf_four_wheel_skid_steer_generation():
    """Verify 4WD skid-steer generation without casters."""
    root = generate_urdf("four_wheel_skid_steer")

    joints = {j.get("name"): j.get("type") for j in root.findall(".//joint")}
    assert "front_left_wheel_joint" in joints
    assert "front_right_wheel_joint" in joints
    assert "rear_left_wheel_joint" in joints
    assert "rear_right_wheel_joint" in joints
    assert joints["front_left_wheel_joint"] == "continuous"
    assert joints["front_right_wheel_joint"] == "continuous"
    assert joints["rear_left_wheel_joint"] == "continuous"
    assert joints["rear_right_wheel_joint"] == "continuous"

    # Ensure casters are not present
    assert "front_caster_joint" not in joints
    assert "rear_caster_joint" not in joints

    # Ensure 2WD center wheel joints are not present
    assert "left_wheel_joint" not in joints
    assert "right_wheel_joint" not in joints
