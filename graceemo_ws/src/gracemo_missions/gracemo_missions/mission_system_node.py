#!/usr/bin/env python3
"""
GraceEMO — Mission System Node
Provides a complete mission planning, execution, and monitoring system.
Supports natural-language mission creation via LLM, structured mission graphs,
and multiple mission types (navigate, deliver, patrol, guide, inspect, escort, emergency).
"""

import json
import time
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Mission:
    """Represents a structured robot mission."""

    TYPES = ['navigate', 'deliver', 'patrol', 'guide', 'inspect', 'escort', 'emergency', 'return_home', 'search']
    STATES = ['created', 'queued', 'running', 'paused', 'completed', 'failed', 'aborted']

    def __init__(self, mission_id: str, mission_type: str, description: str):
        self.id = mission_id
        self.type = mission_type
        self.description = description
        self.state = 'created'
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.start_location = None
        self.destination = None
        self.waypoints = []
        self.constraints = []
        self.actions = []
        self.return_condition = None
        self.progress = 0.0
        self.current_waypoint_idx = 0
        self.error_message = ''
        self.metrics = {
            'distance_traveled': 0.0,
            'time_elapsed': 0.0,
            'obstacles_avoided': 0,
            'replanning_count': 0,
            'energy_consumed': 0.0
        }

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'state': self.state,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'start_location': self.start_location,
            'destination': self.destination,
            'waypoints': self.waypoints,
            'constraints': self.constraints,
            'actions': self.actions,
            'return_condition': self.return_condition,
            'progress': round(self.progress, 2),
            'current_waypoint_idx': self.current_waypoint_idx,
            'error_message': self.error_message,
            'metrics': self.metrics
        }


class MissionSystemNode(Node):
    """
    Mission planning and execution system for the GraceEMO robot.
    Accepts natural language commands and structured mission definitions.
    """

    def __init__(self):
        super().__init__('mission_system_node')
        self.get_logger().info('🎯 Initializing Mission System...')

        self.declare_parameter('campus_metadata_path', '')
        self.declare_parameter('max_concurrent_missions', 1)

        # Load campus metadata for semantic resolution
        self.campus_metadata = {}
        self.nav_nodes = {}
        metadata_path = self.get_parameter('campus_metadata_path').value
        if metadata_path:
            try:
                import os
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        self.campus_metadata = json.load(f)
                    nav_graph = self.campus_metadata.get('navigation_graph', {})
                    for node in nav_graph.get('nodes', []):
                        self.nav_nodes[node['id']] = node
                    self.get_logger().info(f'Loaded {len(self.nav_nodes)} navigation nodes')
            except Exception as e:
                self.get_logger().error(f'Failed to load campus metadata: {e}')

        # Mission storage
        self.missions: dict[str, Mission] = {}
        self.active_mission: Mission | None = None
        self.mission_history: list[dict] = []
        self.mission_counter = 0

        # Robot state
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = 0.0

        # Publishers
        self.mission_state_pub = self.create_publisher(String, '/gracemo/mission_state', 10)
        self.mission_command_pub = self.create_publisher(String, '/gracemo/mission_command', 10)
        self.nav_goal_pub = self.create_publisher(String, '/gracemo/nav_goal', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/create_mission', self.on_create_mission, 10)
        self.create_subscription(String, '/gracemo/create_mission_nl', self.on_create_mission_nl, 10)
        self.create_subscription(String, '/gracemo/mission_control', self.on_mission_control, 10)
        self.create_subscription(String, '/gracemo/robot_pose', self.on_robot_pose, 10)

        # Mission update timer
        self.create_timer(0.5, self.update_missions)
        self.create_timer(1.0, self.publish_mission_state)

        self.get_logger().info('✅ Mission System ready')

    def resolve_semantic_location(self, query: str) -> dict | None:
        """Resolve a natural language location to navigation coordinates."""
        query_lower = query.lower().strip()

        for node_id, node in self.nav_nodes.items():
            labels = node.get('semantic_labels', [])
            for label in labels:
                if label.lower() in query_lower or query_lower in label.lower():
                    return {
                        'node_id': node_id,
                        'x': node['position']['x'],
                        'y': node['position']['y'],
                        'building': node.get('building', ''),
                        'matched_label': label
                    }

        return None

    def _parse_nl_mission(self, text: str) -> Mission:
        """Parse natural language mission description into structured mission."""
        self.mission_counter += 1
        mission_id = f'mission_{self.mission_counter:04d}'

        # Simple keyword-based parsing (LLM integration can enhance this)
        text_lower = text.lower()

        # Determine mission type
        mission_type = 'navigate'
        if any(w in text_lower for w in ['deliver', 'bring', 'carry', 'take']):
            mission_type = 'deliver'
        elif any(w in text_lower for w in ['patrol', 'survey', 'monitor']):
            mission_type = 'patrol'
        elif any(w in text_lower for w in ['guide', 'show', 'lead', 'escort']):
            mission_type = 'escort'
        elif any(w in text_lower for w in ['inspect', 'check', 'examine']):
            mission_type = 'inspect'
        elif any(w in text_lower for w in ['emergency', 'urgent', 'alert']):
            mission_type = 'emergency'
        elif any(w in text_lower for w in ['search', 'find', 'look for']):
            mission_type = 'search'
        elif any(w in text_lower for w in ['return', 'come back', 'go home', 'home']):
            mission_type = 'return_home'

        mission = Mission(mission_id, mission_type, text)

        # Try to resolve destination
        # Look for "to <location>" or "from <location>"
        for node_id, node in self.nav_nodes.items():
            for label in node.get('semantic_labels', []):
                if label.lower() in text_lower:
                    if mission.destination is None:
                        mission.destination = {
                            'node_id': node_id,
                            'x': node['position']['x'],
                            'y': node['position']['y'],
                            'label': label
                        }
                    elif mission.start_location is None:
                        mission.start_location = {
                            'node_id': node_id,
                            'x': node['position']['x'],
                            'y': node['position']['y'],
                            'label': label
                        }

        # Extract constraints
        if 'avoid crowd' in text_lower or 'avoid crowded' in text_lower:
            mission.constraints.append('avoid_crowds')
        if 'fast' in text_lower or 'quick' in text_lower:
            mission.constraints.append('minimize_time')
        if 'safe' in text_lower or 'careful' in text_lower:
            mission.constraints.append('maximize_safety')

        # Check for return condition
        if 'return' in text_lower or 'come back' in text_lower:
            mission.return_condition = 'return_to_start'

        # Set start location from robot's current position if not specified
        if mission.start_location is None:
            mission.start_location = {
                'node_id': 'current',
                'x': self.robot_x,
                'y': self.robot_y,
                'label': 'current position'
            }

        return mission

    def on_create_mission_nl(self, msg: String):
        """Create mission from natural language command."""
        text = msg.data.strip()
        if not text:
            return

        mission = self._parse_nl_mission(text)
        self.missions[mission.id] = mission

        self.get_logger().info(f'📋 Mission created: {mission.id} — {mission.type} — "{text}"')
        if mission.destination:
            self.get_logger().info(f'   Destination: {mission.destination.get("label", "unknown")} @ ({mission.destination["x"]}, {mission.destination["y"]})')

        # Auto-start if no active mission
        if self.active_mission is None:
            self._start_mission(mission)

    def on_create_mission(self, msg: String):
        """Create mission from structured JSON."""
        try:
            data = json.loads(msg.data)
            self.mission_counter += 1
            mission_id = f'mission_{self.mission_counter:04d}'
            mission = Mission(mission_id, data.get('type', 'navigate'), data.get('description', ''))
            mission.destination = data.get('destination')
            mission.start_location = data.get('start_location', {
                'x': self.robot_x, 'y': self.robot_y, 'label': 'current'
            })
            mission.waypoints = data.get('waypoints', [])
            mission.constraints = data.get('constraints', [])
            mission.actions = data.get('actions', [])
            mission.return_condition = data.get('return_condition')

            self.missions[mission.id] = mission
            self.get_logger().info(f'📋 Structured mission created: {mission.id}')

            if self.active_mission is None:
                self._start_mission(mission)
        except Exception as e:
            self.get_logger().error(f'Failed to create mission: {e}')

    def on_mission_control(self, msg: String):
        """Handle mission control commands: pause, resume, abort, return_home."""
        command = msg.data.strip().lower()

        if command == 'pause' and self.active_mission:
            self.active_mission.state = 'paused'
            self.get_logger().info(f'⏸️  Mission paused: {self.active_mission.id}')

        elif command == 'resume' and self.active_mission and self.active_mission.state == 'paused':
            self.active_mission.state = 'running'
            self.get_logger().info(f'▶️  Mission resumed: {self.active_mission.id}')

        elif command == 'abort' and self.active_mission:
            self.active_mission.state = 'aborted'
            self.active_mission.completed_at = time.time()
            self.mission_history.append(self.active_mission.to_dict())
            self.get_logger().info(f'🛑 Mission aborted: {self.active_mission.id}')
            self.active_mission = None

        elif command == 'return_home':
            # Create return-to-home mission
            self.mission_counter += 1
            m = Mission(f'mission_{self.mission_counter:04d}', 'return_home', 'Return to home position')
            m.destination = {'x': 0.0, 'y': 0.0, 'label': 'home'}
            self.missions[m.id] = m
            if self.active_mission:
                self.active_mission.state = 'aborted'
                self.active_mission.completed_at = time.time()
                self.mission_history.append(self.active_mission.to_dict())
            self._start_mission(m)

    def on_robot_pose(self, msg: String):
        """Update robot position from pose topic."""
        try:
            data = json.loads(msg.data)
            self.robot_x = data.get('x', self.robot_x)
            self.robot_y = data.get('y', self.robot_y)
            self.robot_yaw = data.get('yaw', self.robot_yaw)
        except Exception:
            pass

    def _start_mission(self, mission: Mission):
        """Start executing a mission."""
        mission.state = 'running'
        mission.started_at = time.time()
        self.active_mission = mission

        # Publish navigation goal
        if mission.destination:
            goal = String()
            goal.data = json.dumps({
                'action': 'navigate_to',
                'x': mission.destination['x'],
                'y': mission.destination['y'],
                'mission_id': mission.id,
                'constraints': mission.constraints
            })
            self.nav_goal_pub.publish(goal)

        self.get_logger().info(f'🚀 Mission started: {mission.id} ({mission.type})')

    def update_missions(self):
        """Update active mission progress."""
        if self.active_mission is None or self.active_mission.state != 'running':
            return

        m = self.active_mission

        # Update metrics
        if m.started_at:
            m.metrics['time_elapsed'] = time.time() - m.started_at

        # Check if destination reached
        if m.destination:
            dx = m.destination['x'] - self.robot_x
            dy = m.destination['y'] - self.robot_y
            dist = math.hypot(dx, dy)

            # Calculate progress (distance-based)
            if m.start_location:
                total_dist = math.hypot(
                    m.destination['x'] - m.start_location['x'],
                    m.destination['y'] - m.start_location['y']
                )
                if total_dist > 0.1:
                    m.progress = max(0, min(1.0, 1.0 - (dist / total_dist)))

            # Mission complete check
            if dist < 2.0:
                if m.return_condition == 'return_to_start' and m.start_location:
                    # Need to return
                    m.destination = m.start_location
                    m.return_condition = None  # Don't loop
                    m.progress = 0.5
                    self.get_logger().info(f'↩️  Returning to start for mission {m.id}')
                else:
                    m.state = 'completed'
                    m.completed_at = time.time()
                    m.progress = 1.0
                    self.mission_history.append(m.to_dict())
                    self.get_logger().info(f'✅ Mission completed: {m.id}')
                    self.active_mission = None

    def publish_mission_state(self):
        """Publish current mission system state."""
        state = {
            'active_mission': self.active_mission.to_dict() if self.active_mission else None,
            'queued_missions': [m.to_dict() for m in self.missions.values() if m.state == 'created'],
            'mission_history_count': len(self.mission_history),
            'total_missions': len(self.missions),
            'robot_position': {'x': self.robot_x, 'y': self.robot_y, 'yaw': self.robot_yaw}
        }
        msg = String()
        msg.data = json.dumps(state)
        self.mission_state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MissionSystemNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
