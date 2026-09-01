#!/usr/bin/env python3
"""
GraceEMO — LPU Digital Twin Virtual Space Simulation Engine & Web Studio
Provides 200m x 200m campus physics, kinematic updates, 360-deg LiDAR raycasting,
first-person camera rendering, IMU generation, TF2 broadcasting,
and a full-duplex Web Studio WebSocket Server bridging all Digital Twin subsystems.
"""

import os
import sys
import math
import time
import json
import base64
import threading
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from geometry_msgs.msg import Twist, TransformStamped, Pose, Point, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Imu, Image, JointState, Range
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster

import tornado.ioloop
import tornado.web
import tornado.websocket

# Try to import custom interfaces if available
try:
    from gracemo_interfaces.msg import RobotState, Detection
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False


def euler_to_quaternion(roll, pitch, yaw):
    """Convert roll, pitch, yaw to quaternion (x, y, z, w)"""
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return x, y, z, w


def line_intersection(p1, p2, p3, p4):
    """Compute intersection point of segment p1-p2 and p3-p4, returns (t, (x,y)) or None"""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t, (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


class VirtualSpaceNode(Node):
    def __init__(self):
        super().__init__('virtual_space_node')
        self.get_logger().info('🏛️ Initializing GraceEMO LPU Digital Twin Simulation Engine...')

        # Declare parameters
        self.declare_parameter('web_port', 8888)
        self.declare_parameter('update_rate_hz', 50.0)
        self.declare_parameter('scan_rate_hz', 10.0)
        self.declare_parameter('camera_rate_hz', 15.0)
        self.declare_parameter('campus_metadata_path', '')

        self.web_port = self.get_parameter('web_port').value
        self.update_rate = self.get_parameter('update_rate_hz').value

        # Robot kinematic state in meters / radians (Campus center origin)
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.linear_v = 0.0
        self.angular_w = 0.0
        self.target_linear_v = 0.0
        self.target_angular_w = 0.0
        self.robot_radius = 0.30
        self.nav_goal = None
        self.last_teleop_time = 0.0
        self.prev_linear_v = 0.0
        self.imu_ax = 0.0
        self.bumper_hit = False
        self.bumper_until = 0.0
        self.heard_nodes = {}

        # Telemetry & Joint state
        self.battery = 98.5
        self.status = 'READY'
        self.current_task = 'IDLE'
        self.last_speech = ''
        self.neck_yaw = 0.0
        self.neck_pitch = 0.0
        self.left_hand = 0.0
        self.right_hand = 0.0

        # Subsystem States forwarded to Web Studio
        self.scenario_state = {'name': 'normal_campus', 'weather': 'clear_day', 'crowd_density': 'medium'}
        self.mission_state = {'active_mission': None}
        self.server_state = {'status': 'online', 'gpu_utilization': 55.0, 'cpu_utilization': 40.0}
        self.network_state = {'mode': 'ONLINE', 'latency_ms': 12, 'packet_loss_pct': 0.0}
        self.fault_state = {'active_faults': {}, 'active_count': 0}
        self.analytics_metrics = {'mission_success_rate': 100.0, 'collision_count': 0}
        self.recent_logs = []

        # Sensor failure flags (updated from fault_state)
        self.lidar_failed = False
        self.camera_failed = False
        self.sensor_noise_factor = 1.0

        # 200m x 200m LPU Campus Boundary Walls
        self.campus_bounds = 100.0
        self.walls = [
            ((-100.0, -100.0), (100.0, -100.0), 'South Boundary'),
            ((100.0, -100.0), (100.0, 100.0), 'East Boundary'),
            ((100.0, 100.0), (-100.0, 100.0), 'North Boundary'),
            ((-100.0, 100.0), (-100.0, -100.0), 'West Boundary'),
        ]

        # Buildings footprint boxes for collision and lidar raycasting
        self.buildings = []
        self.nav_nodes = []
        self._load_campus_metadata()

        # Dynamic obstacles (pedestrians, vehicles, obstacles)
        self.dynamic_agents = []
        self.static_obstacles = [
            {'id': 'bench_1', 'type': 'bench', 'x': -12.0, 'y': 0.0, 'radius': 0.8, 'name': 'Campus Bench', 'color': [50, 90, 140]},
            {'id': 'bench_2', 'type': 'bench', 'x': 12.0, 'y': 0.0, 'radius': 0.8, 'name': 'Campus Bench', 'color': [50, 90, 140]},
            {'id': 'tree_1', 'type': 'tree', 'x': -15.0, 'y': -20.0, 'radius': 0.6, 'name': 'Garden Tree', 'color': [40, 140, 50]},
            {'id': 'tree_2', 'type': 'tree', 'x': 15.0, 'y': -20.0, 'radius': 0.6, 'name': 'Garden Tree', 'color': [40, 140, 50]},
            {'id': 'sec_booth', 'type': 'booth', 'x': 0.0, 'y': -96.0, 'radius': 1.5, 'name': 'Security Gate 1', 'color': [180, 180, 200]},
        ]

        # Cached sensor outputs
        self.current_scan_ranges = [30.0] * 360
        self.current_camera_jpeg = None
        self.current_camera_left_jpeg = None
        self.current_camera_right_jpeg = None
        self.current_depth_jpeg = None
        self.current_det_jpeg = None
        self.active_websockets = set()

        # ROS 2 Publishers
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        self.camera_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        self.prox_pub = self.create_publisher(Range, '/gracemo/proximity_front', 10)
        self.sensors_json_pub = self.create_publisher(String, '/gracemo/sensors', 10)
        self.robot_pose_pub = self.create_publisher(String, '/gracemo/robot_pose', 10)
        self.speech_in_pub = self.create_publisher(String, '/gracemo/speech_input', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Bridge Publishers (Web UI -> ROS)
        self.create_mission_pub = self.create_publisher(String, '/gracemo/create_mission_nl', 10)
        self.mission_ctrl_pub = self.create_publisher(String, '/gracemo/mission_control', 10)
        self.set_scenario_pub = self.create_publisher(String, '/gracemo/set_scenario', 10)
        self.set_weather_pub = self.create_publisher(String, '/gracemo/set_weather', 10)
        self.set_crowd_pub = self.create_publisher(String, '/gracemo/set_crowd', 10)
        self.inject_fault_pub = self.create_publisher(String, '/gracemo/inject_fault', 10)
        self.clear_fault_pub = self.create_publisher(String, '/gracemo/clear_fault', 10)
        self.set_network_pub = self.create_publisher(String, '/gracemo/set_network', 10)
        self.set_server_pub = self.create_publisher(String, '/gracemo/set_server', 10)

        if HAVE_INTERFACES:
            self.state_pub = self.create_publisher(RobotState, '/gracemo/robot_state', 10)
            self.gt_det_pub = self.create_publisher(Detection, '/gracemo/detections', 10)

        # ROS 2 Subscribers
        self.cmd_vel_sub = self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 10)
        self.create_subscription(String, '/gracemo/nav_goal', self.on_nav_goal, 10)
        self.joint_sub = self.create_subscription(JointState, '/joint_states', self.on_joint_states, 10)
        self.speech_sub = self.create_subscription(String, '/gracemo/spoken_text', self.on_spoken, 10)
        self.say_sub = self.create_subscription(String, '/gracemo/say', self.on_spoken, 10)

        # Telemetry from other Digital Twin packages
        self.create_subscription(String, '/gracemo/dynamic_agents', self.on_dynamic_agents, 10)
        self.create_subscription(String, '/gracemo/scenario_state', self.on_scenario_state, 10)
        self.create_subscription(String, '/gracemo/mission_state', self.on_mission_state, 10)
        self.create_subscription(String, '/gracemo/server_state', self.on_server_state, 10)
        self.create_subscription(String, '/gracemo/network_state', self.on_network_state, 10)
        self.create_subscription(String, '/gracemo/fault_state', self.on_fault_state, 10)
        self.create_subscription(String, '/gracemo/analytics', self.on_analytics, 10)
        self.create_subscription(String, '/gracemo/structured_log', self.on_structured_log, 10)

        # Timers
        self.physics_timer = self.create_timer(1.0 / self.update_rate, self.update_physics)
        self.scan_timer = self.create_timer(1.0 / self.get_parameter('scan_rate_hz').value, self.update_lidar)
        self.camera_timer = self.create_timer(1.0 / self.get_parameter('camera_rate_hz').value, self.update_camera)
        self.pose_pub_timer = self.create_timer(0.2, self.publish_robot_pose)

        # Start Web Studio Server in background
        self.server_thread = threading.Thread(target=self.start_web_server, daemon=True)
        self.server_thread.start()

        self.get_logger().info(f'🌟 LPU Digital Twin Web Studio ready at: http://localhost:{self.web_port}')

    def _heard(self, name: str):
        self.heard_nodes[name] = time.time()

    def _live_nodes(self):
        now = time.time()
        names = ['virtual_space_node']
        for name, ts in self.heard_nodes.items():
            if now - ts < 5.0:
                names.append(name)
        return names

    def _scan_min_in_sector(self, center=0.0, half=0.4):
        n = max(1, len(self.current_scan_ranges))
        best = 30.0
        for i, d in enumerate(self.current_scan_ranges):
            if not math.isfinite(d):
                continue
            ang = -math.pi + (i * 2.0 * math.pi / n)
            err = (ang - center + math.pi) % (2 * math.pi) - math.pi
            if abs(err) <= half:
                best = min(best, float(d))
        return best

    def _finite_scan(self, step=2):
        out = []
        for r in self.current_scan_ranges[::step]:
            out.append(round(float(r), 3) if math.isfinite(r) else 30.0)
        return out

    def _sensor_snapshot(self, front_m=None):
        if front_m is None:
            front_m = self._scan_min_in_sector(0.0, 0.35)
        finite = [r for r in self.current_scan_ranges if math.isfinite(r)]
        lidar_min = min(finite) if finite else 30.0
        return {
            'source': 'virtual_space_raycast',
            'not_gazebo': True,
            'front_range_m': round(float(front_m), 3),
            'lidar_min_m': round(float(lidar_min), 3),
            'bumper': bool(self.bumper_hit),
            'imu': {
                'yaw': round(self.yaw, 4),
                'wz': round(self.angular_w, 4),
                'ax': round(self.imu_ax, 4),
                'az': 9.81,
            },
            'lidar_failed': bool(self.lidar_failed),
            'camera_failed': bool(self.camera_failed),
            'heard_nodes': self._live_nodes(),
            'ros_topics': ['/scan', '/imu/data', '/camera/image_raw', '/odom', '/gracemo/proximity_front'],
        }

    def _load_campus_metadata(self):
        """Load building footprints and navigation graph from campus_metadata.json"""
        candidate_paths = [
            self.get_parameter('campus_metadata_path').value,
            '/workspace/graceemo_ws/src/gracemo_gazebo/config/campus_metadata.json',
            '/Users/samdavi/projects/GraceEMO-Final/graceemo_ws/src/gracemo_gazebo/config/campus_metadata.json',
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'campus_metadata.json'))
        ]
        meta_file = next((p for p in candidate_paths if p and os.path.exists(p)), None)
        if not meta_file:
            self.get_logger().warn('No campus_metadata.json found, using default building geometries.')
            return

        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.buildings = data.get('buildings', [])
            self.nav_nodes = data.get('navigation_graph', {}).get('nodes', [])

            # Convert building footprints into 4 bounding wall segments each
            for b in self.buildings:
                if b.get('dimensions', {}).get('height', 10) < 0.5:
                    continue
                bx = b['position']['x']
                by = b['position']['y']
                bw = b['dimensions']['length'] / 2.0
                bh = b['dimensions']['width'] / 2.0
                bname = b.get('name', b['id'])

                # 4 edges of building box
                self.walls.append(((bx - bw, by - bh), (bx + bw, by - bh), f'{bname} S'))
                self.walls.append(((bx + bw, by - bh), (bx + bw, by + bh), f'{bname} E'))
                self.walls.append(((bx + bw, by + bh), (bx - bw, by + bh), f'{bname} N'))
                self.walls.append(((bx - bw, by + bh), (bx - bw, by - bh), f'{bname} W'))

            self.get_logger().info(f'✅ Loaded {len(self.buildings)} buildings ({len(self.walls)} wall segments) from campus metadata.')
        except Exception as e:
            self.get_logger().error(f'Error loading campus metadata: {e}')

    def on_cmd_vel(self, msg: Twist):
        self.last_teleop_time = time.time()
        self.target_linear_v = float(msg.linear.x)
        self.target_angular_w = float(msg.angular.z)

    def on_nav_goal(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.nav_goal = {'x': float(data['x']), 'y': float(data['y'])}
            self.get_logger().info(
                f'Nav goal (kinematic pursuit, not Nav2): ({self.nav_goal["x"]:.1f}, {self.nav_goal["y"]:.1f})'
            )
        except Exception as e:
            self.get_logger().warn(f'Invalid /gracemo/nav_goal: {e}')

    def on_joint_states(self, msg: JointState):
        for name, pos in zip(msg.name, msg.position):
            if name == 'neck_yaw': self.neck_yaw = float(pos)
            elif name == 'neck_pitch': self.neck_pitch = float(pos)
            elif name == 'left_hand': self.left_hand = float(pos)
            elif name == 'right_hand': self.right_hand = float(pos)

    def on_spoken(self, msg: String):
        if msg.data.strip():
            self.last_speech = msg.data.strip()

    def on_dynamic_agents(self, msg: String):
        self._heard('gracemo_pedestrians')
        try:
            data = json.loads(msg.data)
            peds = data.get('pedestrians', [])
            vehs = data.get('vehicles', [])
            self.dynamic_agents = peds + vehs
        except Exception:
            pass

    def on_scenario_state(self, msg: String):
        self._heard('gracemo_scenarios')
        try:
            self.scenario_state = json.loads(msg.data)
            self.sensor_noise_factor = self.scenario_state.get('sensor_noise_factor', 1.0)
        except Exception:
            pass

    def on_mission_state(self, msg: String):
        self._heard('gracemo_missions')
        try:
            self.mission_state = json.loads(msg.data)
            active = self.mission_state.get('active_mission')
            if active:
                self.current_task = active.get('type', 'MISSION').upper()
                if active.get('state') in ('aborted', 'completed'):
                    self.nav_goal = None
                    self.target_linear_v = 0.0
                    self.target_angular_w = 0.0
            else:
                self.current_task = 'IDLE'
        except Exception:
            pass

    def on_server_state(self, msg: String):
        self._heard('gracemo_server')
        try: self.server_state = json.loads(msg.data)
        except Exception: pass

    def on_network_state(self, msg: String):
        self._heard('gracemo_network_sim')
        try: self.network_state = json.loads(msg.data)
        except Exception: pass

    def on_fault_state(self, msg: String):
        self._heard('gracemo_fault_injection')
        try:
            self.fault_state = json.loads(msg.data)
            active = self.fault_state.get('active_faults', {})
            types = [f.get('type') for f in active.values()]
            self.lidar_failed = 'lidar_failure' in types
            self.camera_failed = 'camera_failure' in types
        except Exception:
            pass

    def on_analytics(self, msg: String):
        self._heard('gracemo_analytics')
        try: self.analytics_metrics = json.loads(msg.data)
        except Exception: pass

    def on_structured_log(self, msg: String):
        try:
            entry = json.loads(msg.data)
            self.recent_logs.append(entry)
            if len(self.recent_logs) > 50:
                self.recent_logs = self.recent_logs[-50:]
        except Exception:
            pass

    def publish_robot_pose(self):
        pose_msg = String()
        pose_msg.data = json.dumps({'x': round(self.x, 3), 'y': round(self.y, 3), 'yaw': round(self.yaw, 3)})
        self.robot_pose_pub.publish(pose_msg)

    def _apply_nav_pursuit(self):
        """Follow /gracemo/nav_goal when teleop is idle. Not Nav2 — differential heading pursuit."""
        if not self.nav_goal:
            return
        active = self.mission_state.get('active_mission') if isinstance(self.mission_state, dict) else None
        if active and active.get('state') == 'paused':
            self.target_linear_v = 0.0
            self.target_angular_w = 0.0
            return
        if active and active.get('state') not in (None, 'running'):
            return
        if time.time() - self.last_teleop_time < 0.8:
            return
        dx = self.nav_goal['x'] - self.x
        dy = self.nav_goal['y'] - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.9:
            self.target_linear_v = 0.0
            self.target_angular_w = 0.0
            return
        desired = math.atan2(dy, dx)
        err = (desired - self.yaw + math.pi) % (2 * math.pi) - math.pi
        self.target_angular_w = max(-1.2, min(1.2, err * 1.8))
        if abs(err) > 0.55:
            self.target_linear_v = 0.12
        else:
            self.target_linear_v = min(0.95, 0.4 + dist * 0.05)
        front = self._scan_min_in_sector(0.0, 0.42)
        if front < 0.85:
            self.target_linear_v = 0.0
            self.target_angular_w = 0.85 if err >= 0 else -0.85
        elif front < 2.0:
            self.target_linear_v = min(self.target_linear_v, 0.22)

    def update_physics(self):
        """Kinematics update and collision resolution against campus bounds and buildings"""
        dt = 1.0 / self.update_rate
        acc_lin = 2.5 * dt
        acc_ang = 5.0 * dt
        self._apply_nav_pursuit()

        if self.linear_v < self.target_linear_v:
            self.linear_v = min(self.linear_v + acc_lin, self.target_linear_v)
        elif self.linear_v > self.target_linear_v:
            self.linear_v = max(self.linear_v - acc_lin, self.target_linear_v)

        if self.angular_w < self.target_angular_w:
            self.angular_w = min(self.angular_w + acc_ang, self.target_angular_w)
        elif self.angular_w > self.target_angular_w:
            self.angular_w = max(self.angular_w - acc_ang, self.target_angular_w)

        new_yaw = (self.yaw + self.angular_w * dt + math.pi) % (2 * math.pi) - math.pi
        new_x = self.x + self.linear_v * math.cos(new_yaw) * dt
        new_y = self.y + self.linear_v * math.sin(new_yaw) * dt

        collided = False
        # Outer campus bounds
        limit = self.campus_bounds - self.robot_radius
        if abs(new_x) > limit or abs(new_y) > limit:
            collided = True

        # Check building bounding boxes
        if not collided:
            for b in self.buildings:
                if b.get('dimensions', {}).get('height', 10) < 0.5:
                    continue
                bx = b['position']['x']
                by = b['position']['y']
                half_l = b['dimensions']['length'] / 2.0 + self.robot_radius
                half_w = b['dimensions']['width'] / 2.0 + self.robot_radius
                if abs(new_x - bx) < half_l and abs(new_y - by) < half_w:
                    collided = True
                    break

        if not collided:
            self.x = new_x
            self.y = new_y
            self.yaw = new_yaw
        else:
            self.linear_v = 0.0
            self.yaw = new_yaw
            self.bumper_hit = True
            self.bumper_until = time.time() + 0.45

        if time.time() > self.bumper_until:
            self.bumper_hit = False

        self.imu_ax = (self.linear_v - self.prev_linear_v) / max(1e-3, dt)
        self.prev_linear_v = self.linear_v

        if abs(self.linear_v) > 0.01:
            self.battery = max(5.0, self.battery - 0.0005)

        now = self.get_clock().now().to_msg()
        qx, qy, qz, qw = euler_to_quaternion(0.0, 0.0, self.yaw)

        # Broadcast TF: odom -> base_footprint
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(t)

        # Publish Odometry
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
        odom.twist.twist.linear.x = self.linear_v
        odom.twist.twist.angular.z = self.angular_w
        self.odom_pub.publish(odom)

        # Publish IMU
        imu = Imu()
        imu.header.stamp = now
        imu.header.frame_id = 'imu_link'
        imu.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
        imu.angular_velocity.z = self.angular_w
        imu.linear_acceleration.x = self.imu_ax
        imu.linear_acceleration.z = 9.81
        self.imu_pub.publish(imu)

        front_m = self._scan_min_in_sector(0.0, 0.35)
        prox = Range()
        prox.header.stamp = now
        prox.header.frame_id = 'base_footprint'
        prox.radiation_type = Range.INFRARED
        prox.field_of_view = 0.7
        prox.min_range = 0.15
        prox.max_range = 30.0
        prox.range = float(front_m)
        self.prox_pub.publish(prox)
        self.sensors_json_pub.publish(String(data=json.dumps(self._sensor_snapshot(front_m))))

        # Publish RobotState interface
        if HAVE_INTERFACES:
            state = RobotState()
            state.status = 'AUTONOMOUS' if abs(self.linear_v) > 0.01 else 'IDLE'
            state.battery_voltage = float(12.0 + (self.battery / 100.0) * 0.6)
            state.cpu_temperature = 44.0
            state.current_task = self.current_task
            state.current_pose.position.x = self.x
            state.current_pose.position.y = self.y
            state.current_pose.orientation = Quaternion(x=qx, y=qy, z=qz, w=qw)
            state.active_nodes = self._live_nodes()
            self.state_pub.publish(state)

        self.notify_websockets()

    def update_lidar(self):
        """Simulate 360-degree LiDAR raycasting against all campus walls, buildings & dynamic agents"""
        now = self.get_clock().now().to_msg()
        num_readings = 360
        max_range = 30.0
        min_range = 0.15

        if self.lidar_failed:
            ranges = [float('inf')] * num_readings
        else:
            ranges = [max_range] * num_readings
            all_obstacles = self.static_obstacles + self.dynamic_agents

            for i in range(0, num_readings, 2):  # Raycast every 2 deg for performance
                angle_rel = -math.pi + (i * 2.0 * math.pi / num_readings)
                angle_global = self.yaw + angle_rel

                ray_end_x = self.x + max_range * math.cos(angle_global)
                ray_end_y = self.y + max_range * math.sin(angle_global)
                p1 = (self.x, self.y)
                p2 = (ray_end_x, ray_end_y)
                closest_dist = max_range

                # Intersect with all campus walls & buildings
                for (w1, w2, _) in self.walls:
                    hit = line_intersection(p1, p2, w1, w2)
                    if hit is not None:
                        d = hit[0] * max_range
                        if min_range <= d < closest_dist:
                            closest_dist = d

                # Intersect with obstacles & dynamic agents
                for obs in all_obstacles:
                    ox, oy = obs['x'], obs['y']
                    orad = obs.get('radius', 0.4)
                    dx = ox - self.x
                    dy = oy - self.y
                    proj = dx * math.cos(angle_global) + dy * math.sin(angle_global)
                    if proj > 0:
                        perp_sq = (dx*dx + dy*dy) - (proj * proj)
                        if perp_sq < (orad * orad):
                            d_hit = proj - math.sqrt(max(0.0, orad*orad - perp_sq))
                            if min_range <= d_hit < closest_dist:
                                closest_dist = d_hit

                # Apply sensor noise
                noise = np.random.normal(0, 0.01 * self.sensor_noise_factor)
                if closest_dist < max_range:
                    closest_dist = max(min_range, min(max_range, closest_dist + float(noise)))

                ranges[i] = closest_dist
                ranges[i+1] = closest_dist

        self.current_scan_ranges = ranges

        scan = LaserScan()
        scan.header.stamp = now
        scan.header.frame_id = 'lidar_link'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = (2.0 * math.pi) / num_readings
        scan.time_increment = 0.0
        scan.scan_time = 0.1
        scan.range_min = min_range
        scan.range_max = max_range
        scan.ranges = [float(r) for r in ranges]
        self.scan_pub.publish(scan)

    def _encode_jpeg(self, img, quality=72):
        _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer).decode('utf-8')

    def _perception_agents(self):
        return list(self.dynamic_agents or [])

    def _publish_detections(self):
        if not HAVE_INTERFACES:
            return
        people = {'student', 'faculty', 'security', 'visitor', 'person', 'pedestrian'}
        fov = math.radians(72)
        for i, it in enumerate(self._collect_camera_items(self.yaw + self.neck_yaw, 20.0)):
            if it['kind'] not in people or abs(it['ang']) > fov / 2:
                continue
            det = Detection()
            det.track_id = i
            det.label = 'person'
            det.confidence = 0.82
            det.center_x = 0.5 + it['ang'] / fov
            det.center_y = 0.55
            det.width = 0.08
            det.height = 0.18
            det.distance_meters = float(it['dist'])
            self.gt_det_pub.publish(det)

    def _collect_camera_items(self, cam_yaw, max_dist=40.0):
        items = []
        for b in self.buildings or []:
            pos = b.get('position') or {}
            dim = b.get('dimensions') or {}
            bx = pos.get('x', b.get('x', 0))
            by = pos.get('y', b.get('y', 0))
            dx, dy = bx - self.x, by - self.y
            dist = math.hypot(dx, dy)
            if dist < 1.0 or dist > max_dist:
                continue
            ang = math.atan2(dy, dx) - cam_yaw
            ang = (ang + math.pi) % (2 * math.pi) - math.pi
            items.append({
                'kind': 'building',
                'dist': dist,
                'ang': ang,
                'h': dim.get('height', b.get('h', 12)),
                'w': dim.get('length', b.get('l', 20)),
                'name': b.get('name', b.get('id', 'Block')),
                'color': [90, 140, 190],
            })
        for obs in (self.static_obstacles + self._perception_agents()):
            dx = obs['x'] - self.x
            dy = obs['y'] - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.25 or dist > 32.0:
                continue
            ang = math.atan2(dy, dx) - cam_yaw
            ang = (ang + math.pi) % (2 * math.pi) - math.pi
            items.append({
                'kind': str(obs.get('type', 'obj')).lower(),
                'dist': dist,
                'ang': ang,
                'h': obs.get('radius', 0.35) * 4.2,
                'w': obs.get('radius', 0.35) * 1.6,
                'name': obs.get('name', obs.get('type', 'obj')),
                'color': obs.get('color', [80, 90, 160]),
            })
        items.sort(key=lambda it: it['dist'], reverse=True)
        return items

    def _render_camera_frame(self, yaw_offset=0.0, width=640, height=480, with_hud=True, detections_only=False):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        if self.camera_failed:
            cv2.putText(img, "CAMERA SENSOR FAILURE", (max(12, width // 8), height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
            return img

        weather = self.scenario_state.get('weather', 'clear_day')
        if weather == 'night':
            sky_color, ground_color = [48, 32, 22], [46, 52, 42]
        elif weather == 'rain':
            sky_color, ground_color = [150, 138, 128], [88, 108, 92]
        elif weather == 'fog':
            sky_color, ground_color = [186, 180, 174], [148, 158, 146]
        else:
            sky_color, ground_color = [234, 212, 184], [106, 168, 125]

        img[0:height // 2, :] = sky_color
        img[height // 2:height, :] = ground_color
        cv2.line(img, (0, height // 2), (width, height // 2), (150, 170, 150), 1)

        fov = math.radians(72)
        cam_yaw = self.yaw + self.neck_yaw + yaw_offset
        focal = (width / 2.0) / math.tan(fov / 2.0)
        people = {'student', 'faculty', 'security', 'visitor', 'person', 'pedestrian'}

        for it in self._collect_camera_items(cam_yaw):
            if abs(it['ang']) > fov / 2.0 + 0.25:
                continue
            screen_x = int(width / 2.0 + math.tan(it['ang']) * focal)
            obj_h = int(max(8, (it['h'] * focal) / max(0.4, it['dist'])))
            obj_w = int(max(6, (it['w'] * 0.35 * focal) / max(0.4, it['dist'])))
            y_bot = min(height - 4, height // 2 + obj_h // 6)
            y_top = max(4, y_bot - obj_h)
            x_left = max(2, screen_x - obj_w // 2)
            x_right = min(width - 2, screen_x + obj_w // 2)
            if x_right <= x_left or y_bot <= y_top:
                continue
            kind = it['kind']
            if detections_only and kind not in people:
                continue
            if kind == 'building':
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), it['color'], -1)
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), (220, 230, 240), 1)
                cv2.putText(img, str(it.get('name', ''))[:16], (x_left, max(12, y_top - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)
            elif kind in people:
                body = (it['color'][0], it['color'][1], it['color'][2])
                head_r = max(3, obj_w // 4)
                cv2.circle(img, ((x_left + x_right) // 2, y_top + head_r), head_r, body, -1)
                cv2.rectangle(img, (x_left + 2, y_top + head_r * 2), (x_right - 2, y_bot), body, -1)
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), (60, 220, 80), 2)
                cv2.putText(img, f"person {it['dist']:.1f}m", (x_left, max(14, y_top - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.36, (60, 220, 80), 1, cv2.LINE_AA)
            else:
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), it['color'], -1)

        if weather == 'rain':
            rng = np.random.RandomState(int(time.time() * 12) % 10000)
            for _ in range(70):
                x0 = int(rng.randint(0, width))
                y0 = int(rng.randint(0, height))
                cv2.line(img, (x0, y0), (x0 - 2, y0 + 12), (210, 210, 210), 1)

        if with_hud and not detections_only:
            cv2.putText(img, f'LPU Campus | ({self.x:.1f}, {self.y:.1f})m | {math.degrees(self.yaw):.0f}deg',
                        (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 160, 255), 1, cv2.LINE_AA)
            cv2.putText(img, f'Weather: {weather.upper()} | Agents: {len(self._perception_agents())} | Task: {self.current_task}',
                        (12, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (40, 160, 255), 1, cv2.LINE_AA)
        return img

    def _render_depth_frame(self, width=160, height=84):
        img = np.zeros((height, width), dtype=np.uint8)
        n = max(1, len(self.current_scan_ranges))
        for x in range(width):
            i = int((x / width) * n)
            d = float(self.current_scan_ranges[i % n])
            shade = int(np.clip(255 - (min(d, 20.0) / 20.0) * 220, 18, 255))
            img[:, x] = shade
        cam_yaw = self.yaw + self.neck_yaw
        fov = math.radians(70)
        for it in self._collect_camera_items(cam_yaw, 20.0):
            if it['kind'] not in {'student', 'faculty', 'security', 'visitor', 'person', 'pedestrian'}:
                continue
            if abs(it['ang']) > fov / 2:
                continue
            sx = int((0.5 + it['ang'] / fov) * width)
            h = int(np.clip(28 / max(0.6, it['dist']) * 10, 8, height - 4))
            x0, x1 = max(0, sx - 4), min(width, sx + 4)
            y1 = height - 4
            y0 = max(2, y1 - h)
            img[y0:y1, x0:x1] = int(np.clip(40 + it['dist'] * 8, 40, 180))
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def update_camera(self):
        width, height = 480, 270
        front = self._render_camera_frame(0.0, width, height, True)
        left = self._render_camera_frame(math.radians(65), 320, 180, False)
        right = self._render_camera_frame(-math.radians(65), 320, 180, False)
        det = self._render_camera_frame(0.0, 240, 140, False, detections_only=True)
        depth = self._render_depth_frame(160, 84)
        self.current_camera_jpeg = self._encode_jpeg(front, 70)
        self.current_camera_left_jpeg = self._encode_jpeg(left, 60)
        self.current_camera_right_jpeg = self._encode_jpeg(right, 60)
        self.current_det_jpeg = self._encode_jpeg(det, 58)
        self.current_depth_jpeg = self._encode_jpeg(depth, 55)

        now = self.get_clock().now().to_msg()
        img_msg = Image()
        img_msg.header.stamp = now
        img_msg.header.frame_id = 'camera_optical_frame'
        img_msg.height = height
        img_msg.width = width
        img_msg.encoding = 'bgr8'
        img_msg.is_bigendian = False
        img_msg.step = width * 3
        img_msg.data = front.tobytes()
        self.camera_pub.publish(img_msg)
        self._publish_detections()

    def notify_websockets(self):
        """Send complete digital twin state snapshot to web dashboard"""
        if not self.active_websockets:
            return

        # Compute 4-wheel simulated RPM and health
        wheel_r = 0.12
        wheel_sep = 0.42
        v_l = self.linear_v - (self.angular_w * wheel_sep / 2.0)
        v_r = self.linear_v + (self.angular_w * wheel_sep / 2.0)
        rpm_l = round((v_l / (2.0 * math.pi * wheel_r)) * 60.0, 1)
        rpm_r = round((v_r / (2.0 * math.pi * wheel_r)) * 60.0, 1)

        # Dynamic battery consumption
        if abs(self.linear_v) > 0.01 or abs(self.angular_w) > 0.01:
            self.battery = max(5.0, self.battery - 0.002)

        active_faults = self.fault_state.get('active_faults', {}) if isinstance(self.fault_state, dict) else {}
        fl_ok = 'wheel_fl_failure' not in active_faults
        fr_ok = 'wheel_fr_failure' not in active_faults

        payload = json.dumps({
            'type': 'digital_twin_state',
            'robot': {
                'x': self.x,
                'y': self.y,
                'yaw': self.yaw,
                'linear_v': self.linear_v,
                'angular_w': self.angular_w,
                'battery': round(self.battery, 1),
                'status': self.status,
                'task': self.current_task,
                'neck_yaw': self.neck_yaw,
                'neck_pitch': self.neck_pitch,
                'left_hand': self.left_hand,
                'right_hand': self.right_hand,
                'speech': self.last_speech,
                'wheels': {
                    'fl': {'rpm': rpm_l if fl_ok else 0.0, 'status': 'OK' if fl_ok else 'FAULT'},
                    'fr': {'rpm': rpm_r if fr_ok else 0.0, 'status': 'OK' if fr_ok else 'FAULT'},
                    'rl': {'rpm': rpm_l, 'status': 'OK'},
                    'rr': {'rpm': rpm_r, 'status': 'OK'},
                },
            },
            'buildings': self.buildings,
            'dynamic_agents': self.dynamic_agents or [],
            'static_obstacles': self.static_obstacles,
            'scan': self._finite_scan(2),
            'sensors': self._sensor_snapshot(),
            'camera_jpeg': self.current_camera_jpeg,
            'camera_left_jpeg': self.current_camera_left_jpeg,
            'camera_right_jpeg': self.current_camera_right_jpeg,
            'camera_depth_jpeg': self.current_depth_jpeg,
            'camera_det_jpeg': self.current_det_jpeg,
            'scenario': self.scenario_state,
            'mission': self.mission_state,
            'server': self.server_state,
            'network': self.network_state,
            'faults': self.fault_state,
            'analytics': self.analytics_metrics,
            'recent_logs': self.recent_logs[-10:] if self.recent_logs else []
        })

        for ws in list(self.active_websockets):
            try:
                ws.write_message(payload)
            except Exception:
                self.active_websockets.discard(ws)

    def start_web_server(self):
        """Run Tornado Web & WebSocket Server bridging ROS 2 to Web Studio"""
        node_ref = self
        web_dirs = [
            '/workspace/GraceEMO-Final/graceemo_ws/src/gracemo_gazebo/web',
            '/workspace/graceemo_ws/src/gracemo_gazebo/web',
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')),
        ]
        try:
            from ament_index_python.packages import get_package_share_directory
            web_dirs.append(os.path.join(get_package_share_directory('gracemo_gazebo'), 'web'))
        except Exception:
            pass

        web_dir = next((d for d in web_dirs if os.path.isdir(d) and os.path.exists(os.path.join(d, 'index.html'))), web_dirs[0])

        class IndexHandler(tornado.web.RequestHandler):
            def get(self):
                for candidate in web_dirs:
                    fpath = os.path.join(candidate, 'index.html')
                    if os.path.exists(fpath):
                        with open(fpath, 'r', encoding='utf-8') as f:
                            self.set_header("Content-Type", "text/html; charset=UTF-8")
                            self.write(f.read())
                            return
                self.set_status(404)
                self.write("<h1>GraceEMO: index.html not found</h1>")

        class WSHandler(tornado.websocket.WebSocketHandler):
            def check_origin(self, origin):
                return True

            def open(self):
                node_ref.active_websockets.add(self)

            def on_close(self):
                node_ref.active_websockets.discard(self)

            def on_message(self, message):
                try:
                    data = json.loads(message)
                    action = data.get('action')

                    # 1. Teleop
                    if action == 'teleop':
                        cmd = Twist()
                        cmd.linear.x = float(data.get('v', 0.0))
                        cmd.angular.z = float(data.get('w', 0.0))
                        node_ref.on_cmd_vel(cmd)

                    # 2. Reset pose
                    elif action == 'reset_pose':
                        node_ref.x = 0.0
                        node_ref.y = 0.0
                        node_ref.yaw = 0.0
                        node_ref.linear_v = 0.0
                        node_ref.angular_w = 0.0

                    # 2b. Emergency Stop (E-STOP)
                    elif action == 'estop':
                        node_ref.target_linear_v = 0.0
                        node_ref.target_angular_w = 0.0
                        node_ref.linear_v = 0.0
                        node_ref.angular_w = 0.0
                        node_ref.nav_goal = None
                        node_ref.status = 'EMERGENCY_STOP'
                        node_ref.on_cmd_vel(Twist())
                        m = String()
                        m.data = 'abort'
                        node_ref.mission_ctrl_pub.publish(m)
                        sp = String()
                        sp.data = 'stop'
                        node_ref.speech_in_pub.publish(sp)

                    elif action == 'estop_clear':
                        node_ref.status = 'READY'

                    # 3. Missions (Natural language or control)
                    elif action == 'create_mission_nl':
                        text = str(data.get('text', '')).strip()
                        if text:
                            m = String()
                            m.data = text
                            node_ref.create_mission_pub.publish(m)

                    elif action == 'mission_control':
                        cmd = str(data.get('command', '')).strip()
                        if cmd:
                            m = String()
                            m.data = cmd
                            node_ref.mission_ctrl_pub.publish(m)

                    # 4. Scenarios & Weather
                    elif action == 'set_scenario':
                        m = String()
                        m.data = str(data.get('scenario', 'normal_campus'))
                        node_ref.set_scenario_pub.publish(m)

                    elif action == 'set_weather':
                        m = String()
                        m.data = str(data.get('weather', 'clear_day'))
                        node_ref.set_weather_pub.publish(m)

                    elif action == 'set_crowd':
                        m = String()
                        m.data = str(data.get('crowd', 'medium'))
                        node_ref.set_crowd_pub.publish(m)

                    # 5. Fault Injection
                    elif action == 'inject_fault':
                        m = String()
                        m.data = json.dumps(data.get('fault', {}))
                        node_ref.inject_fault_pub.publish(m)

                    elif action == 'clear_fault':
                        m = String()
                        m.data = str(data.get('target', 'all'))
                        node_ref.clear_fault_pub.publish(m)

                    # 6. Network Simulation
                    elif action == 'set_network':
                        m = String()
                        m.data = json.dumps(data.get('network', {}))
                        node_ref.set_network_pub.publish(m)

                    elif action == 'set_server':
                        m = String()
                        m.data = str(data.get('available', True))
                        node_ref.set_server_pub.publish(m)

                    # 7. Voice / Speech
                    elif action == 'voice':
                        text = str(data.get('text', '')).strip()
                        if text:
                            m = String()
                            m.data = text
                            node_ref.speech_in_pub.publish(m)

                except Exception as e:
                    node_ref.get_logger().error(f'WebSocket error: {e}')

        class FaviconHandler(tornado.web.RequestHandler):
            def get(self):
                for candidate in web_dirs:
                    fpath = os.path.join(candidate, 'favicon.svg')
                    if os.path.exists(fpath):
                        self.set_header('Content-Type', 'image/svg+xml')
                        with open(fpath, 'rb') as f:
                            self.write(f.read())
                        return
                self.set_status(204)

        app = tornado.web.Application([
            (r'/', IndexHandler),
            (r'/ws', WSHandler),
            (r'/favicon.ico', FaviconHandler),
            (r'/(.*)', tornado.web.StaticFileHandler, {'path': web_dir}),
        ])

        async_loop = tornado.ioloop.IOLoop()
        async_loop.make_current()
        app.listen(self.web_port)
        async_loop.start()


def main(args=None):
    rclpy.init(args=args)
    node = VirtualSpaceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
