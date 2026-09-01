"""Full Phase 1 stack on Gazebo Harmonic (no Virtual Space — topics would clash)."""

import os

from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    gazebo_dir = get_package_share_directory('gracemo_gazebo')
    perception_dir = get_package_share_directory('gracemo_perception')
    voice_dir = get_package_share_directory('gracemo_voice')
    memory_dir = get_package_share_directory('gracemo_memory')
    brain_dir = get_package_share_directory('gracemo_brain')

    has_cpp = True
    try:
        control_dir = get_package_share_directory('gracemo_control')
    except PackageNotFoundError:
        has_cpp = False
        control_dir = ''

    brain_args = {
        'direct_cmd_vel': 'false' if has_cpp else 'true',
        'actuate_joints': 'false' if has_cpp else 'true',
    }

    actions = [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(gazebo_dir, 'launch', 'gazebo.launch.py')
            )
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(perception_dir, 'launch', 'perception.launch.py')
            )
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(voice_dir, 'launch', 'voice.launch.py')
            )
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(memory_dir, 'launch', 'memory.launch.py')
            )
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(brain_dir, 'launch', 'brain.launch.py')
            ),
            launch_arguments=brain_args.items(),
        ),
    ]

    if has_cpp:
        actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(control_dir, 'launch', 'control.launch.py')
                )
            )
        )

    return LaunchDescription(actions)
