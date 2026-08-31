import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_nav2_bringup = get_package_share_directory("nav2_bringup")
    pkg_slam_toolbox = get_package_share_directory("slam_toolbox")
    pkg_gracemo_nav2 = get_package_share_directory("gracemo_nav2")

    nav2_params_file = os.path.join(pkg_gracemo_nav2, "config", "nav2_params.yaml")
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation clock"),

        # 1. SLAM Toolbox (Live 2D Mapping from 360 LiDAR)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_slam_toolbox, "launch", "online_async_launch.py")
            ),
            launch_arguments={
                "use_sim_time": use_sim_time
            }.items()
        ),

        # 2. Nav2 Navigation Stack (Path Planning & DWB Obstacle Avoidance)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_nav2_bringup, "launch", "navigation_launch.py")
            ),
            launch_arguments={
                "use_sim_time": use_sim_time,
                "params_file": nav2_params_file,
                "autostart": "true"
            }.items()
        ),

        # 3. RViz2 Visualizer with Nav2 & 2D Goal Pose Tool
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2_nav2",
            output="screen",
            parameters=[{"use_sim_time": use_sim_time}],
            arguments=["-d", os.path.join(pkg_nav2_bringup, "rviz", "nav2_default_view.rviz")]
        )
    ])
