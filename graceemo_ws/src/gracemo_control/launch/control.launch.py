from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='gracemo_control',
            executable='safety_servo_node',
            output='screen',
        )
    ])
