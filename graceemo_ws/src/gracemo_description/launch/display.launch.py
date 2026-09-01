"""
GraceEMO — Robot Description Display Launch
Starts robot_state_publisher to broadcast TF2 frames from the URDF.
"""
import os
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Path to the xacro file
    urdf_dir = os.path.join(
        get_package_share_directory('gracemo_description'), 'urdf'
    )
    xacro_file = os.path.join(urdf_dir, 'gracemo.urdf.xacro')

    # Process xacro → URDF XML string
    robot_description = Command(['xacro ', xacro_file])

    # robot_state_publisher: publishes TF2 transforms from URDF
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}],
    )

    # joint_state_publisher_gui: GUI sliders for movable joints
    joint_state_publisher_gui = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        output='screen',
    )

    return LaunchDescription([
        robot_state_publisher,
        joint_state_publisher_gui,
    ])
