import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (IncludeLaunchDescription, DeclareLaunchArgument,
                             SetEnvironmentVariable, TimerAction)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
import subprocess


def generate_launch_description():
    pkg_ros_gz_sim          = get_package_share_directory("ros_gz_sim")
    pkg_gracemo_description = get_package_share_directory("gracemo_description")
    pkg_gracemo_gazebo      = get_package_share_directory("gracemo_gazebo")

    world_file  = os.path.join(pkg_gracemo_gazebo, "worlds", "apartment_floor.world")
    xacro_file  = os.path.join(pkg_gracemo_description, "urdf", "gracemo_vira.urdf.xacro")
    urdf_file   = "/tmp/gracemo_vira_spawn.urdf"
    models_path = os.path.join(pkg_gracemo_gazebo, "models")

    # Pre-generate URDF from xacro to a temp file (avoids topic timing issues)
    subprocess.run(["xacro", xacro_file, "-o", urdf_file], check=True)

    os.environ["GZ_SIM_RESOURCE_PATH"] = models_path

    robot_description = Command(["xacro ", xacro_file])
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    # Only start kernel_bridge if kernel is actually reachable
    kernel_running = False
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:7780/health", timeout=1)
        kernel_running = True
    except Exception:
        pass

    nodes = [
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", models_path),

        # 1. Launch Gazebo Harmonic
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
            ),
            launch_arguments={
                "gz_args": f"-r {world_file}",
                "gz_version": "8"
            }.items()
        ),

        # 2. Robot State Publisher (TF tree)
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

        # 3. Spawn robot — 6s delay using pre-generated URDF file (most reliable)
        TimerAction(
            period=6.0,
            actions=[
                Node(
                    package="ros_gz_sim",
                    executable="create",
                    name="spawn_gracemo_vira",
                    output="screen",
                    arguments=[
                        "-world", "gracemo_home",
                        "-file",  urdf_file,
                        "-name",  "gracemo_vira",
                        "-x", "0.0",
                        "-y", "0.0",
                        "-z", "0.15"
                    ]
                )
            ]
        ),

        # 4. ROS <-> Gazebo Bridge (gz.msgs for Harmonic)
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
                "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V"
            ],
            parameters=[{"use_sim_time": use_sim_time}]
        ),
    ]

    # 5. Kernel bridge — only if kernel server is running (optional)
    if kernel_running:
        nodes.append(Node(
            package="gracemo_bridge",
            executable="kernel_bridge",
            name="gracemo_kernel_bridge",
            output="screen",
            parameters=[{"kernel_url": "http://127.0.0.1:7780"}]
        ))
    else:
        print("[sim.launch.py] Kernel not reachable at :7780 — skipping kernel_bridge")

    return LaunchDescription(nodes)
