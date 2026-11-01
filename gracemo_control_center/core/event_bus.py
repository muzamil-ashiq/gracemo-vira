"""
Central Event Bus for GRaCEmo ViRa UARCC.
Provides thread-safe Qt Signal dispatch between background ROS workers,
sensor pipelines, and GUI views.
"""

from PySide6.QtCore import QObject, Signal
import time


class EventBus(QObject):
    """Singleton event bus routing signals across UARCC modules."""

    _instance = None

    # Connection & Lifecycle Signals
    ros_connected = Signal(bool)
    gazebo_connected = Signal(bool)
    sim_clock_updated = Signal(float)  # current sim_time in seconds
    subsystem_health_updated = Signal(dict) # dict of subsystem health states

    # Sensor Signals
    rgb_frame_ready = Signal(object, float, str, float)  # (QImage, fps, resolution_str, timestamp)
    depth_frame_ready = Signal(object, float, float, float)  # (QImage, min_m, max_m, timestamp)
    lidar_scan_ready = Signal(object)  # dict containing cartesian (xs, ys), min_r, max_r, timestamp
    imu_data_ready = Signal(object)    # dict containing roll, pitch, yaw, ax, ay, az, gx, gy, gz
    odom_data_ready = Signal(object)   # dict containing x, y, yaw, vx, vy, wz, timestamp

    # Localization & TF
    amcl_pose_ready = Signal(float, float, float, float, float, float) # (x, y, yaw, var_x, var_y, var_yaw)
    map_ready = Signal(object)         # dict containing width, height, resolution, origin, grid
    global_path_ready = Signal(list)   # list of (x, y) waypoints
    tf_status_ready = Signal(dict)     # dict of frame pair statuses (e.g. map->odom: True)

    # Navigation & Coordinator
    coordinator_feedback_ready = Signal(str, str, dict, float) # (state, speech, details, timestamp)
    navigation_goal_dispatched = Signal(str, float, float, float) # (name, x, y, yaw)
    navigation_cancel_requested = Signal() # user/UI requested goal cancellation
    navigation_arrival_confirmed = Signal(str, float, float) # (destination, error_m, duration_s)

    # Voice & Interaction
    user_input_received = Signal(str, str) # (text, source: TEXT/VOICE)
    voice_recognized = Signal(str)        # recognized speech transcript
    spoken_feedback_received = Signal(str, str) # (text, status)

    # Cognitive & MNSE
    mnse_kernel_status = Signal(dict)     # dict containing online, rest_ok, sock_ok, latency_ms
    cognitive_task_updated = Signal(dict) # dict containing task_id, status, approval_state

    # Safety & Watchdogs
    terrain_status_ready = Signal(dict)   # dict with slope_state, roll, pitch, speed_factor
    emergency_stop_state = Signal(bool, str) # (is_active, source)
    collision_warning = Signal(bool, float) # (breached, min_dist)

    # Diagnostics & System Logs
    system_metrics_ready = Signal(dict)   # dict containing cpu, ram, gpu_util, gpu_mem, temp
    ros_diagnostics_ready = Signal(dict)  # dict of active nodes, topics, frequencies
    log_event_emitted = Signal(dict)      # dict with timestamp, level, source, message

    # Navigation routing between views
    request_page_navigation = Signal(str) # page name to switch to

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
        return cls._instance


# Global singleton instance
bus = EventBus()
