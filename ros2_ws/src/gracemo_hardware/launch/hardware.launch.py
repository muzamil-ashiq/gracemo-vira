"""
GRaCEmo ViRa — Hardware Mode Launch File
==========================================
Launches the robot stack for PHYSICAL hardware deployment.
Mutually exclusive with simulation.launch.py — do NOT run both.

Requires on Jetson Orin Nano:
  - ROS 2 Jazzy installed
  - MCU connected and serial port confirmed
  - LiDAR driver installed and port confirmed
  - URDF built and accessible via gracemo_robot_description package

Launch modes:
  hardware.launch.py                         # Full hardware stack with AMCL
  hardware.launch.py transport_type:=mock    # Hardware stack with mock MCU (testing)
  hardware.launch.py use_rviz:=true          # With RViz visualization
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_hardware = get_package_share_directory("gracemo_hardware")
    pkg_nav = get_package_share_directory("gracemo_nav2")
    pkg_robot_desc = get_package_share_directory("gracemo_description")

    transport_type = LaunchConfiguration("transport_type")
    mcu_port = LaunchConfiguration("mcu_port")
    mcu_baud_rate = LaunchConfiguration("mcu_baud_rate")
    use_rviz = LaunchConfiguration("use_rviz")
    map_yaml = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")

    xacro_file = os.path.join(pkg_robot_desc, "urdf", "gracemo_vira.urdf.xacro")
    robot_description = ParameterValue(Command(["xacro ", xacro_file]), value_type=str)

    default_map = os.path.join(pkg_nav, "maps", "physical_lab_map.yaml")
    default_params = os.path.join(pkg_nav, "config", "nav2_physical_params.yaml")
    hw_params = os.path.join(pkg_hardware, "config", "hardware_params.yaml")
    pkg_nav2_bringup = get_package_share_directory("nav2_bringup")
    rviz_config = os.path.join(pkg_nav2_bringup, "rviz", "nav2_default_view.rviz")

    lidar_port = LaunchConfiguration("lidar_port")
    lidar_profile = LaunchConfiguration("lidar_profile")
    launch_nav2 = LaunchConfiguration("launch_nav2")

    return LaunchDescription([
        # ── Arguments ──────────────────────────────────────────────────────
        DeclareLaunchArgument(
            "transport_type", default_value="mock",
            description="MCU transport: 'mock' (testing) or 'serial' (real STM32 - requires protocol confirmation)"
        ),
        DeclareLaunchArgument(
            "mcu_port", default_value="/dev/ttyUSB0",
            description="[PENDING] Dedicated serial port for STM32 MCU on Jetson Orin Nano"
        ),
        DeclareLaunchArgument(
            "mcu_baud_rate", default_value="115200",
            description="[PENDING] Baud rate - confirm with STM32 firmware"
        ),
        DeclareLaunchArgument(
            "lidar_port", default_value="/dev/ttyUSB1",
            description="[PENDING] Dedicated serial port for LiDAR (MUST be distinct from mcu_port)"
        ),
        DeclareLaunchArgument(
            "lidar_profile", default_value="unconfirmed",
            description="LiDAR model profile: unconfirmed, rplidar_a1, rplidar_a2, ydlidar_x4, ldrobot_ld19"
        ),
        DeclareLaunchArgument(
            "use_rviz", default_value="false",
            description="Launch RViz2 for visualization"
        ),
        DeclareLaunchArgument(
            "map", default_value=default_map,
            description="[PENDING PHYSICAL MAP] Map YAML file for AMCL. Note: sim_apartment_map represents Gazebo apartment, NOT physical room."
        ),
        DeclareLaunchArgument(
            "params_file", default_value=default_params,
            description="Nav2 parameters file (defaults to nav2_params_hardware.yaml)"
        ),
        DeclareLaunchArgument(
            "launch_nav2", default_value="true",
            description="Launch Nav2 navigation stack (requires map, odometry, and scan)"
        ),

        LogInfo(msg="[GRaCEmo ViRa] Starting HARDWARE mode (use_sim_time=false)."),
        LogInfo(msg="[GRaCEmo ViRa] NOTICE: In hardware mode, verify MCU port, LiDAR port, and real room map."),
        LogInfo(msg="[GRaCEmo ViRa] CAUTION: If transport_type:=mock, kinematics are simulated and physical motors will NOT move."),

        # ── 1. Robot State Publisher (TF tree from URDF) ────────────────────
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{
                "robot_description": robot_description,
                "use_sim_time": False,
            }]
        ),

        # ── 2. MCU Bridge (HAL: cmd_vel ↔ STM32, odometry publisher) ───────
        Node(
            package="gracemo_hardware",
            executable="mcu_bridge_node",
            name="gracemo_mcu_bridge",
            output="screen",
            parameters=[{
                "hardware_mode": "hardware",
                "transport_type": transport_type,
                "mcu_port": mcu_port,
                "mcu_baud_rate": mcu_baud_rate,
                "wheel_separation_m": 0.34,
                "wheel_radius_m": 0.065,
                "cmd_vel_watchdog_sec": 0.5,
                "publish_odom_tf": True,
                "odom_frame_id": "odom",
                "base_frame_id": "base_footprint",
            }]
        ),

        # ── 3. Hardware Status Monitor ──────────────────────────────────────
        Node(
            package="gracemo_hardware",
            executable="hardware_status_node",
            name="gracemo_hardware_status",
            output="screen",
            parameters=[{"hardware_mode": "hardware"}]
        ),

        # ── 4. LiDAR Driver (PENDING CONFIRMATION of physical LiDAR model) ──
        # Dedicated port: lidar_port (default /dev/ttyUSB1, separate from mcu_port /dev/ttyUSB0).
        # Driver launch remains disabled until physical model is inspected.
        # Example when RPLiDAR is confirmed:
        # Node(
        #     package="rplidar_ros",
        #     executable="rplidar_composition",
        #     name="rplidar",
        #     output="screen",
        #     parameters=[{
        #         "serial_port": lidar_port,   # Dedicated LiDAR port (separate from mcu_port)
        #         "serial_baudrate": 115200,
        #         "frame_id": "lidar_link",
        #         "inverted": False,
        #         "angle_compensate": True,
        #     }]
        # ),
        LogInfo(msg="[GRaCEmo ViRa] LiDAR driver is pending physical model confirmation. Physical driver node not launched."),

        # ── 5. Nav2 Stack (wait for MCU/LiDAR/transforms to initialize) ─────
        TimerAction(
            period=3.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_nav2_bringup, "launch", "bringup_launch.py")
                    ),
                    condition=IfCondition(launch_nav2),
                    launch_arguments={
                        "map": map_yaml,
                        "use_sim_time": "false",
                        "params_file": params_file,
                        "autostart": "true",
                        "slam": "False",
                    }.items()
                )
            ]
        ),

        # ── 6. Command Coordinator ──────────────────────────────────────────
        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package="gracemo_nav2",
                    executable="coordinator_node.py",
                    name="gracemo_command_coordinator",
                    output="screen",
                    parameters=[{"use_sim_time": False}]
                )
            ]
        ),

        # ── 7. Interaction Node ─────────────────────────────────────────────
        TimerAction(
            period=5.5,
            actions=[
                Node(
                    package="gracemo_interaction",
                    executable="interaction_node",
                    name="gracemo_interaction_node",
                    output="screen",
                    parameters=[{"use_sim_time": False}]
                )
            ]
        ),

        # ── 8. RViz2 (optional) ─────────────────────────────────────────────
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            output="screen",
            condition=IfCondition(use_rviz),
            parameters=[{"use_sim_time": False}],
            arguments=["-d", rviz_config],
        ),
    ])
