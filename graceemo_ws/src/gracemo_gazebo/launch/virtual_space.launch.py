import os
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    desc_dir = get_package_share_directory('gracemo_description')
    xacro_file = os.path.join(desc_dir, 'urdf', 'gracemo.urdf.xacro')

    robot_description = ParameterValue(Command(['xacro ', xacro_file]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}],
    )

    virtual_space_node = Node(
        package='gracemo_gazebo',
        executable='virtual_space_node',
        output='screen',
        parameters=[{'web_port': 8888}]
    )

    return LaunchDescription([
        robot_state_publisher,
        virtual_space_node
    ])
