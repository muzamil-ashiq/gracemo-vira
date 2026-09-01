import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_dir = get_package_share_directory('gracemo_perception')
    config_file = os.path.join(pkg_dir, 'config', 'perception.yaml')

    detector_node = Node(
        package='gracemo_perception',
        executable='detector_node',
        output='screen',
        parameters=[config_file]
    )

    return LaunchDescription([
        detector_node
    ])
