import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_ros_gz_sim       = get_package_share_directory("ros_gz_sim")
    pkg_gracemo_description = get_package_share_directory("gracemo_description")
    pkg_gracemo_gazebo   = get_package_share_directory("gracemo_gazebo")

    world_file  = os.path.join(pkg_gracemo_gazebo, "worlds", "apartment_floor.world")
    xacro_file  = os.path.join(pkg_gracemo_description, "urdf", "gracemo_vira.urdf.xacro")
    models_path = os.path.join(pkg_gracemo_gazebo, "models")

    # Gazebo Harmonic uses GZ_SIM_RESOURCE_PATH (no longer IGN_GAZEBO_RESOURCE_PATH)
    os.environ["GZ_SIM_RESOURCE_PATH"] = models_path

    robot_description = Command(["xacro ", xacro_file])
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation clock"),
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", models_path),

        # 1. Gazebo Harmonic (gz sim) with auto-run physics
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
            ),
            launch_arguments={
                "gz_args": f"-r {world_file}"
            }.items()
        ),

        # 2. Robot State Publisher / TF Tree
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{
                "robot_description": robot_description,
                "use_sim_time": use_sim_time
            }]
        ),

        # 3. Spawn GRaCEmo ViRa robot in Gazebo
        Node(
            package="ros_gz_sim",
            executable="create",
            name="spawn_gracemo_vira",
            output="screen",
            arguments=[
                "-topic", "robot_description",
                "-name", "gracemo_vira",
                "-x", "0.0",
                "-y", "0.0",
                "-z", "0.10"
            ]
        ),

        # 4. ROS <-> Gazebo Transport Bridge
        # Harmonic uses gz.msgs.* instead of ignition.msgs.*
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="ros_gz_bridge",
            output="screen",
            arguments=[
                "/left_arm/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/right_arm/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/left_arm/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/right_arm/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/head/pan_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/head/tilt_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
                "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
                "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
                "/imu/data@sensor_msgs/msg/Imu[gz.msgs.IMU",
                "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V"
            ],
            parameters=[{
                "use_sim_time": use_sim_time
            }]
        ),

        # 5. GRaCEmo Kernel Bridge
        Node(
            package="gracemo_bridge",
            executable="kernel_bridge",
            name="gracemo_kernel_bridge",
            output="screen",
            parameters=[{
                "kernel_url": "http://127.0.0.1:7780"
            }]
        )
    ])
