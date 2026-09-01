import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_dir = get_package_share_directory('gracemo_navigation')
    nav_params = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')

    patrol_node = Node(
        package='gracemo_navigation',
        executable='patrol_node',
        name='patrol_node',
        output='screen'
    )

    return LaunchDescription([
        patrol_node
    ])
