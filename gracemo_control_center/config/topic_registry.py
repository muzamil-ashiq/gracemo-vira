"""
Authoritative Topic, Service, Action, and Frame Registry for GRaCEmo ViRa.
All communication names originate from verified ROS 2 graph and launch files.
"""

# Core Sensor Topics
TOPIC_CLOCK = "/clock"
TOPIC_SCAN = "/scan"
TOPIC_ODOM = "/odom"
TOPIC_IMU = "/imu/data"
TOPIC_CAMERA_RGB = "/camera/image_raw"
TOPIC_CAMERA_INFO = "/camera/camera_info"
TOPIC_CAMERA_DEPTH = "/camera/depth_image"
TOPIC_JOINT_STATES = "/joint_states"

# Localization & TF
TOPIC_AMCL_POSE = "/amcl_pose"
TOPIC_PARTICLES = "/particle_cloud"
TOPIC_INITIAL_POSE = "/initialpose"
TOPIC_MAP = "/map"
TOPIC_TF = "/tf"
TOPIC_TF_STATIC = "/tf_static"

# Navigation & Costmaps
TOPIC_GLOBAL_PATH = "/plan"
TOPIC_GLOBAL_COSTMAP = "/global_costmap/costmap"
TOPIC_LOCAL_COSTMAP = "/local_costmap/costmap"

# Command Velocity Pipeline
TOPIC_CMD_VEL_NAV = "/cmd_vel_nav"
TOPIC_CMD_VEL_SMOOTHED = "/cmd_vel_smoothed"
TOPIC_CMD_VEL_SAFE = "/cmd_vel_safe"
TOPIC_CMD_VEL_FINAL = "/cmd_vel"

# Safety & Terrain Subsystem
TOPIC_TERRAIN_EMERGENCY_STOP = "/terrain/emergency_stop"
TOPIC_TERRAIN_SAFETY_STOP = "/terrain/safety_stop"
TOPIC_TERRAIN_STATUS = "/terrain/status"
TOPIC_WAIST_PITCH_CMD = "/waist_pitch_cmd"

# Command Coordinator Subsystem
TOPIC_COORDINATOR_COMMAND = "/coordinator/command"
TOPIC_COORDINATOR_FEEDBACK = "/coordinator/feedback"

# Interaction & Voice Subsystem
TOPIC_USER_INPUT = "/interaction/user_input"
TOPIC_SPOKEN_FEEDBACK = "/interaction/spoken_feedback"
TOPIC_VOICE_RECOGNIZED = "/interaction/voice_recognized"

# Head and Arm Position Commands (Gz)
TOPIC_HEAD_PAN_CMD = "/head/pan/cmd_pos"
TOPIC_HEAD_TILT_CMD = "/head/tilt/cmd_pos"

# Action Servers
ACTION_NAVIGATE_TO_POSE = "navigate_to_pose"

# Service Clients
SERVICE_NOMOTION_UPDATE = "/request_nomotion_update"
SERVICE_CLEAR_GLOBAL_COSTMAP = "/global_costmap/clear_entirely_global_costmap"
SERVICE_CLEAR_LOCAL_COSTMAP = "/local_costmap/clear_entirely_local_costmap"

# Coordinate Frames
FRAME_MAP = "map"
FRAME_ODOM = "odom"
FRAME_BASE_FOOTPRINT = "base_footprint"
FRAME_BASE_LINK = "base_link"
FRAME_LIDAR = "lidar_link"
FRAME_CAMERA = "camera_link"
FRAME_IMU = "imu_link"

# Authoritative Coordinate Chain
TF_CHAIN = [FRAME_MAP, FRAME_ODOM, FRAME_BASE_FOOTPRINT, FRAME_LIDAR]

# Nav2 Lifecycle Nodes
NAV2_LIFECYCLE_NODES = [
    "map_server",
    "amcl",
    "controller_server",
    "smoother_server",
    "planner_server",
    "route_server",
    "behavior_server",
    "bt_navigator",
    "waypoint_follower",
    "velocity_smoother",
    "collision_monitor",
    "docking_server"
]

# Hardware Invariant Constraints
SAFETY_HARDWARE_PROTOCOL_CONFIRMED = False
SAFETY_MOTOR_OUTPUT_ENABLED = 0
SAFETY_BANNER_TEXT = "SIMULATION ONLY — PHYSICAL ACTUATION DISABLED"
