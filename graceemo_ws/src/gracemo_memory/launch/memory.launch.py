import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_dir = get_package_share_directory('gracemo_memory')
    config_file = os.path.join(pkg_dir, 'config', 'memory.yaml')

    memory_node = Node(
        package='gracemo_memory',
        executable='memory_node',
        output='screen',
        parameters=[config_file]
    )

    return LaunchDescription([
        memory_node
    ])
