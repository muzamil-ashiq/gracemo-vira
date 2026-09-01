"""Gazebo Harmonic campus world + GraceEMO spawn + ROS–GZ bridges."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_gazebo = get_package_share_directory('gracemo_gazebo')
    pkg_desc = get_package_share_directory('gracemo_description')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world = os.path.join(pkg_gazebo, 'worlds', 'campus.sdf')
    bridge = os.path.join(pkg_gazebo, 'config', 'ros_gz_bridge.yaml')
    xacro_file = os.path.join(pkg_desc, 'urdf', 'gracemo.urdf.xacro')

    robot_description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)

    gui = LaunchConfiguration('gui')
    gz_args_gui = f'-r -v 2 {world}'
    gz_args_headless = f'-s -r -v 2 {world}'

    gz_sim_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': gz_args_gui,
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(gui),
    )

    gz_sim_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': gz_args_headless,
            'on_exit_shutdown': 'true',
        }.items(),
        condition=UnlessCondition(gui),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    spawn = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ros_gz_sim',
                executable='create',
                output='screen',
                arguments=[
                    '-name', 'gracemo',
                    '-topic', 'robot_description',
                    '-x', '0', '-y', '0', '-z', '0.08',
                    '-allow_renaming', 'true',
                ],
            )
        ],
    )

    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge,
            'use_sim_time': True,
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true',
                              description='Launch Gazebo GUI (set false for server-only on Mac Docker)'),
        gz_sim_gui,
        gz_sim_headless,
        robot_state_publisher,
        spawn,
        gz_bridge,
    ])
