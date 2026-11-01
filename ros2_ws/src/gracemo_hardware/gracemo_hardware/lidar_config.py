"""
GRaCEmo ViRa — LiDAR Configuration Registry
=============================================
Defines expected ROS 2 interface for the LiDAR connected to the robot.

STATUS: LiDAR model is [PENDING CONFIRMATION].
Physical hardware must be inspected to determine the exact model.
Known information from existing URDF:
  - The simulation uses a 360° planar LiDAR
  - Range: 0.15m – 12.0m
  - 360 samples, 15 Hz update rate
  - Topic: /scan (sensor_msgs/LaserScan)
  - Frame: lidar_link

Common LiDAR candidates for this class of robot:
  - RPLiDAR A1/A2/A3 (Slamtec) — USB-UART, driver: ros-jazzy-rplidar-ros
  - YDLIDAR X4/G4 — USB, driver: ros-jazzy-ydlidar-ros2-driver
  - Hokuyo URG-04LX/UST-10LX — USB/Ethernet
  - LDRobot LD19 — USB
  - Unitree L1 — USB

The correct driver package, launch file, and parameters MUST be determined
after physical inspection of the hardware.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class LiDARConfig:
    """
    LiDAR configuration record.
    Fields marked [PENDING] require physical hardware confirmation.
    """
    model: str                            # [PENDING]
    ros_package: str                      # ROS 2 driver package name
    ros_executable: str                   # Node executable name
    topic: str = "/scan"                  # Standard topic
    frame_id: str = "lidar_link"          # TF frame — must match URDF lidar_link
    scan_type: str = "sensor_msgs/LaserScan"
    angle_min_rad: float = -3.14159      # Full 360°
    angle_max_rad: float = 3.14159
    range_min_m: float = 0.15
    range_max_m: float = 12.0
    scan_frequency_hz: float = 15.0
    samples_per_scan: int = 360
    usb_vid_pid: str = ""                 # [PENDING]
    default_port: str = "/dev/ttyUSB1"    # [PENDING: confirm port on Jetson]
    driver_params: Dict[str, Any] = field(default_factory=dict)
    install_command: str = ""
    notes: str = ""


# Known LiDAR profiles — select the correct one once hardware is identified
LIDAR_PROFILES: Dict[str, LiDARConfig] = {

    "rplidar_a1": LiDARConfig(
        model="RPLiDAR A1M8",
        ros_package="rplidar_ros",
        ros_executable="rplidar_composition",
        angle_min_rad=-3.14159,
        angle_max_rad=3.14159,
        range_min_m=0.15,
        range_max_m=12.0,
        scan_frequency_hz=7.5,
        samples_per_scan=360,
        usb_vid_pid="10C4:EA60",
        default_port="/dev/ttyUSB1",
        driver_params={"serial_port": "/dev/ttyUSB1", "serial_baudrate": 115200,
                       "frame_id": "lidar_link", "inverted": False, "angle_compensate": True},
        install_command="sudo apt install -y ros-jazzy-rplidar-ros",
        notes="Most common RPLiDAR. Check port with: ls -la /dev/ttyUSB*",
    ),

    "rplidar_a2": LiDARConfig(
        model="RPLiDAR A2M8",
        ros_package="rplidar_ros",
        ros_executable="rplidar_composition",
        range_min_m=0.15,
        range_max_m=18.0,
        scan_frequency_hz=10.0,
        samples_per_scan=720,
        usb_vid_pid="10C4:EA60",
        default_port="/dev/ttyUSB1",
        driver_params={"serial_port": "/dev/ttyUSB1", "serial_baudrate": 115200,
                       "frame_id": "lidar_link", "inverted": False, "angle_compensate": True},
        install_command="sudo apt install -y ros-jazzy-rplidar-ros",
    ),

    "ydlidar_x4": LiDARConfig(
        model="YDLIDAR X4",
        ros_package="ydlidar_ros2_driver",
        ros_executable="ydlidar_ros2_driver_node",
        range_min_m=0.12,
        range_max_m=10.0,
        scan_frequency_hz=6.0,
        samples_per_scan=720,
        usb_vid_pid="10C4:EA60",
        default_port="/dev/ttyUSB1",
        driver_params={"port": "/dev/ttyUSB1", "baudrate": 128000,
                       "frame_id": "lidar_link", "lidar_type": 1, "device_type": 6,
                       "sample_rate": 9, "abnormal_check_count": 4, "fixed_resolution": True,
                       "reversion": False, "inverted": False, "auto_reconnect": True,
                       "isSingleChannel": False, "intensity": False},
        install_command="sudo apt install -y ros-jazzy-ydlidar-ros2-driver",
    ),

    "ldrobot_ld19": LiDARConfig(
        model="LDRobot LD19",
        ros_package="ldlidar_stl_ros2",
        ros_executable="ldlidar_stl_ros2_node",
        range_min_m=0.02,
        range_max_m=12.0,
        scan_frequency_hz=10.0,
        samples_per_scan=450,
        usb_vid_pid="0483:5740",
        default_port="/dev/ttyUSB1",
        driver_params={"product_name": "LDLiDAR_LD19", "topic_name": "/scan",
                       "frame_id": "lidar_link", "port_name": "/dev/ttyUSB1",
                       "port_baudrate": 230400, "laser_scan_dir": True,
                       "enable_angle_crop_func": False},
        install_command="# Build from source: https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2",
    ),
}


# [PENDING] Set this to the actual LiDAR model key once hardware is identified
ACTIVE_LIDAR_PROFILE_KEY: str = "UNKNOWN"


def validate_lidar_profile(profile_key: str) -> tuple[bool, str]:
    """
    Check if a LiDAR profile key is known and valid.
    Returns (is_valid, message).
    """
    k = profile_key.lower().strip()
    if k in LIDAR_PROFILES:
        return True, f"LiDAR profile '{k}' is valid."
    return False, f"Unsupported LiDAR profile: '{profile_key}'. Available profiles: {list(LIDAR_PROFILES.keys())}"


def set_active_lidar_profile(profile_key: str) -> LiDARConfig:
    """
    Explicitly set and return the active LiDAR profile.
    Raises ValueError if the profile is unknown.
    """
    global ACTIVE_LIDAR_PROFILE_KEY
    k = profile_key.lower().strip()
    if k not in LIDAR_PROFILES:
        raise ValueError(
            f"Unsupported LiDAR profile '{profile_key}'. "
            f"Supported profiles are: {list(LIDAR_PROFILES.keys())}"
        )
    ACTIVE_LIDAR_PROFILE_KEY = k
    return LIDAR_PROFILES[k]


def get_active_lidar_config() -> Optional[LiDARConfig]:
    """Returns the active LiDAR configuration, or None if not yet confirmed."""
    if ACTIVE_LIDAR_PROFILE_KEY == "UNKNOWN":
        return None
    return LIDAR_PROFILES.get(ACTIVE_LIDAR_PROFILE_KEY)


def validate_lidar_scan_msg(
    angle_min: float,
    angle_max: float,
    range_min: float,
    range_max: float,
    ranges_count: int,
    frame_id: str,
) -> tuple[bool, str]:
    """
    Validate a received LaserScan message against expected LiDAR parameters.
    Returns (is_valid, reason_if_invalid).
    """
    cfg = get_active_lidar_config()
    if cfg is None:
        # Cannot validate without confirmed config — accept with warning
        return True, "LiDAR config not confirmed — scan accepted without validation"

    if frame_id != cfg.frame_id:
        return False, f"LiDAR frame_id mismatch: got '{frame_id}', expected '{cfg.frame_id}'"

    if range_min < 0.0 or range_min > 0.5:
        return False, f"Unexpected range_min: {range_min}"

    if range_max < 1.0:
        return False, f"Suspicious range_max: {range_max} (expected >= 1.0m)"

    if ranges_count < 90:
        return False, f"Too few scan rays: {ranges_count} (expected >= 90)"

    return True, "ok"
