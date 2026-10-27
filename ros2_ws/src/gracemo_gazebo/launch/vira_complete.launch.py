import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    DeclareLaunchArgument,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_gracemo_gazebo = get_package_share_directory("gracemo_gazebo")
    pkg_gracemo_nav2 = get_package_share_directory("gracemo_nav2")

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    launch_nav2 = LaunchConfiguration("launch_nav2", default="true")
    launch_interaction = LaunchConfiguration("launch_interaction", default="true")
    kernel_url = LaunchConfiguration("kernel_url", default="http://127.0.0.1:7780")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation clock"),
        DeclareLaunchArgument("launch_nav2", default_value="true", description="Launch Nav2 and SLAM Toolbox"),
        DeclareLaunchArgument("launch_interaction", default_value="true", description="Launch Interaction & Navigation Bridge"),
        DeclareLaunchArgument("kernel_url", default_value="http://127.0.0.1:7780", description="VIRA Kernel EventBus URL"),

        # 1. Base Simulation: Gazebo Harmonic + URDF Robot Description + Physical Sensor Bridge + Kernel Bridge
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gracemo_gazebo, "launch", "sim.launch.py")
            ),
            launch_arguments={
                "use_sim_time": use_sim_time,
            }.items()
        ),

        # 2. Autonomous Navigation Stack: SLAM Toolbox + Nav2 Planner/Controller (Optional / Configurable)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gracemo_nav2, "launch", "nav2.launch.py")
            ),
            condition=IfCondition(launch_nav2),
            launch_arguments={
                "use_sim_time": use_sim_time,
            }.items()
        ),

        # 3. Interaction & Voice/Text Navigation Bridge
        Node(
            package="gracemo_bridge",
            executable="interaction_bridge",
            name="gracemo_interaction_bridge",
            output="screen",
            condition=IfCondition(launch_interaction),
            parameters=[{
                "kernel_url": kernel_url,
            }]
        ),
    ])
