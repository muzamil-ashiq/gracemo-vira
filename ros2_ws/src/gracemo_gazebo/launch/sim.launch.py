import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    DeclareLaunchArgument,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_ros_gz_sim          = get_package_share_directory("ros_gz_sim")
    pkg_gracemo_description = get_package_share_directory("gracemo_description")
    pkg_gracemo_gazebo      = get_package_share_directory("gracemo_gazebo")

    world_file  = os.path.join(pkg_gracemo_gazebo, "worlds", "apartment_floor.world")
    xacro_file  = os.path.join(pkg_gracemo_description, "urdf", "gracemo_vira.urdf.xacro")
    models_path = os.path.join(pkg_gracemo_gazebo, "models")

    os.environ["GZ_SIM_RESOURCE_PATH"] = models_path

    robot_description = Command(["xacro ", xacro_file])
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    # Check if MNSE Kernel is online
    kernel_running = False
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:7780/health", timeout=0.5)
        kernel_running = True
    except Exception:
        pass

    nodes = [
        DeclareLaunchArgument("use_sim_time", default_value="true", description="Use simulation clock"),
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", models_path),

        # 1. Launch Gazebo Harmonic (gz sim 8) with world (contains embedded robot)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
            ),
            launch_arguments={
                "gz_args": f"-r {world_file}",
                "gz_version": "8"
            }.items()
        ),

        # 2. Robot State Publisher (publishes TF tree from robot_description)
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

        # 3. ROS 2 <-> Gazebo Harmonic Transport Bridge
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="ros_gz_bridge",
            output="screen",
            arguments=[
                "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
                "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
                "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
                "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
                "/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
                "/imu/data@sensor_msgs/msg/Imu[gz.msgs.IMU",
                "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
                "/left_arm/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/right_arm/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/left_arm/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/right_arm/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/head/pan_cmd@std_msgs/msg/Float64]gz.msgs.Double",
                "/head/tilt_cmd@std_msgs/msg/Float64]gz.msgs.Double"
            ],
            parameters=[{"use_sim_time": use_sim_time}]
        ),
    ]

    if kernel_running:
        nodes.append(Node(
            package="gracemo_bridge",
            executable="kernel_bridge",
            name="gracemo_kernel_bridge",
            output="screen",
            parameters=[{"kernel_url": "http://127.0.0.1:7780"}]
        ))
    else:
        print("[sim.launch.py] Kernel offline at :7780 — skipping gracemo_kernel_bridge")

    return LaunchDescription(nodes)
