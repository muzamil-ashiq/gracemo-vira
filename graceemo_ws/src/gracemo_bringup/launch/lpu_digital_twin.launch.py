import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory


def generate_launch_description():
    """
    Launch the full LPU Autonomous Robotics Digital Twin Platform.
    Includes:
      - Virtual Space Simulator & Web Studio (200m x 200m LPU Campus)
      - Scenario & Weather Manager
      - Dynamic Pedestrian & Vehicle Agent System
      - Natural Language Mission System
      - Central AI GPU Server (FastAPI / Tornado)
      - Network Simulation & Failover Engine
      - Fault Injection Testing Engine
      - Analytics & Structured Replay System
      - Research Experimentation Framework
    """
    actions = [
        LogInfo(msg="🚀 Starting GraceEMO LPU Autonomous Robotics Digital Twin...")
    ]

    # Helper to add node safely
    def add_node(package_name, executable_name, name=None, parameters=None):
        actions.append(
            Node(
                package=package_name,
                executable=executable_name,
                name=name or executable_name,
                parameters=parameters or [],
                output='screen'
            )
        )

    # 1. Virtual Space Simulation & Web Studio (port 8888)
    add_node(
        'gracemo_gazebo',
        'virtual_space_node',
        parameters=[{
            'web_port': 8888,
            'update_rate_hz': 50.0,
            'scan_rate_hz': 10.0,
            'camera_rate_hz': 15.0,
            'campus_metadata_path': '/workspace/graceemo_ws/src/gracemo_gazebo/config/campus_metadata.json'
        }]
    )

    # 2. Dynamic Scenarios & Weather Manager
    add_node(
        'gracemo_scenarios',
        'scenario_manager_node',
        parameters=[{
            'active_scenario': 'normal_campus',
            'campus_metadata_path': '/workspace/graceemo_ws/src/gracemo_gazebo/config/campus_metadata.json'
        }]
    )

    # 3. Dynamic Pedestrians & Vehicle Agents
    add_node(
        'gracemo_pedestrians',
        'pedestrian_manager_node',
        parameters=[{
            'initial_crowd_density': 'medium',
            'initial_traffic_density': 'low',
            'update_rate_hz': 10.0
        }]
    )

    # 4. Mission System & Natural Language Dispatcher
    add_node(
        'gracemo_missions',
        'mission_system_node',
        parameters=[{
            'campus_metadata_path': '/workspace/graceemo_ws/src/gracemo_gazebo/config/campus_metadata.json'
        }]
    )

    # 5. Central AI Server (port 8090)
    add_node(
        'gracemo_server',
        'central_server_node',
        parameters=[{
            'server_port': 8090,
            'gpu_utilization_sim': 55.0,
            'cpu_utilization_sim': 40.0
        }]
    )

    # 6. Network Simulation Engine
    add_node(
        'gracemo_network_sim',
        'network_sim_node',
        parameters=[{
            'latency_ms': 12,
            'jitter_ms': 2,
            'packet_loss_pct': 0.0,
            'server_available': True
        }]
    )

    # 7. Fault Injection Testing Engine
    add_node('gracemo_fault_injection', 'fault_injection_node')

    # 8. Analytics & Structured Event Logger
    add_node(
        'gracemo_analytics',
        'analytics_node',
        parameters=[{
            'log_directory': '/workspace/gracemo_data/logs',
            'replay_directory': '/workspace/gracemo_data/replays'
        }]
    )

    # 9. Research Experiment Framework
    add_node('gracemo_research', 'research_node')

    # 10. Cortex Brain & Autonomous Planner
    add_node('gracemo_brain', 'llm_node')
    add_node(
        'gracemo_brain',
        'planner_node',
        parameters=[{
            'direct_cmd_vel': True,
            'actuate_joints': True,
        }]
    )

    # 11. Persistent Memory Engine
    add_node('gracemo_memory', 'memory_node')

    return LaunchDescription(actions)
