import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = get_package_share_directory('gracemo_brain')
    config_file = os.path.join(pkg_dir, 'config', 'brain.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('direct_cmd_vel', default_value='true'),
        DeclareLaunchArgument('actuate_joints', default_value='true'),
        Node(
            package='gracemo_brain',
            executable='llm_node',
            output='screen',
            parameters=[config_file],
        ),
        Node(
            package='gracemo_brain',
            executable='planner_node',
            output='screen',
            parameters=[{
                'direct_cmd_vel': LaunchConfiguration('direct_cmd_vel'),
                'actuate_joints': LaunchConfiguration('actuate_joints'),
            }],
        ),
    ])
