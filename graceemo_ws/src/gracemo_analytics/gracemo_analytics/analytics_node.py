#!/usr/bin/env python3
"""
GraceEMO — Analytics & Logging Node
Records mission metrics, navigation stats, collision counts, energy consumption,
server offload percentages, and provides structured logging + replay data.
"""

import json
import time
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class AnalyticsNode(Node):
    """
    Records and publishes simulation analytics, structured logs,
    and replay data for the LPU Digital Twin.
    """

    def __init__(self):
        super().__init__('analytics_node')
        self.get_logger().info('📊 Initializing Analytics Engine...')

        self.declare_parameter('log_directory', '/workspace/gracemo_data/logs')
        self.declare_parameter('replay_directory', '/workspace/gracemo_data/replays')

        self.log_dir = self.get_parameter('log_directory').value
        self.replay_dir = self.get_parameter('replay_directory').value

        # Create directories
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.replay_dir, exist_ok=True)

        # Analytics state
        self.metrics = {
            'session_start': time.time(),
            'mission_success_rate': 0.0,
            'missions_completed': 0,
            'missions_failed': 0,
            'missions_total': 0,
            'total_distance_traveled': 0.0,
            'total_navigation_time': 0.0,
            'collision_count': 0,
            'near_miss_count': 0,
            'energy_consumed': 0.0,
            'average_inference_latency_ms': 0.0,
            'server_offload_pct': 0.0,
            'edge_processing_pct': 100.0,
            'network_failures': 0,
            'recovery_success_count': 0,
            'sensor_failures': 0,
            'average_speed': 0.0,
            'max_speed': 0.0,
        }

        # Structured log buffer
        self.log_buffer: list[dict] = []
        self.max_buffer_size = 10000

        # Replay data
        self.replay_buffer: list[dict] = []
        self.replay_recording = True
        self.replay_session_id = f'session_{int(time.time())}'

        # Previous robot position for distance tracking
        self.prev_x = 0.0
        self.prev_y = 0.0
        self.speed_samples = []

        # Publishers
        self.analytics_pub = self.create_publisher(String, '/gracemo/analytics', 10)
        self.log_pub = self.create_publisher(String, '/gracemo/structured_log', 10)

        # Subscribers — listen to all subsystems
        self.create_subscription(String, '/gracemo/mission_state', self.on_mission_state, 10)
        self.create_subscription(String, '/gracemo/fault_events', self.on_fault_event, 10)
        self.create_subscription(String, '/gracemo/network_state', self.on_network_state, 10)
        self.create_subscription(String, '/gracemo/scenario_state', self.on_scenario_state, 10)

        # Timers
        self.create_timer(2.0, self.publish_analytics)
        self.create_timer(5.0, self.record_replay_frame)
        self.create_timer(60.0, self.flush_logs)

        self.get_logger().info('✅ Analytics Engine ready')

    def _log(self, robot_id: str, module: str, severity: str, message: str):
        """Add structured log entry."""
        entry = {
            'timestamp': time.time(),
            'time_str': time.strftime('%H:%M:%S'),
            'robot': robot_id,
            'module': module,
            'severity': severity,
            'message': message
        }
        self.log_buffer.append(entry)
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]

        # Publish structured log
        msg = String()
        msg.data = json.dumps(entry)
        self.log_pub.publish(msg)

    def on_mission_state(self, msg: String):
        """Track mission metrics."""
        try:
            data = json.loads(msg.data)
            active = data.get('active_mission')
            if active:
                state = active.get('state', '')
                if state == 'completed':
                    self.metrics['missions_completed'] += 1
                    self.metrics['missions_total'] += 1
                    metrics = active.get('metrics', {})
                    self.metrics['total_distance_traveled'] += metrics.get('distance_traveled', 0)
                    self.metrics['total_navigation_time'] += metrics.get('time_elapsed', 0)
                    self._log('ROBOT-01', 'MISSION', 'INFO', f'Mission completed: {active.get("id")}')
                elif state == 'failed':
                    self.metrics['missions_failed'] += 1
                    self.metrics['missions_total'] += 1
                    self._log('ROBOT-01', 'MISSION', 'WARNING', f'Mission failed: {active.get("id")}')

            # Update success rate
            total = self.metrics['missions_total']
            if total > 0:
                self.metrics['mission_success_rate'] = round(
                    self.metrics['missions_completed'] / total * 100, 1
                )
        except Exception:
            pass

    def on_fault_event(self, msg: String):
        """Track fault events."""
        try:
            data = json.loads(msg.data)
            event_type = data.get('event_type', '')
            fault = data.get('fault', {})

            if event_type == 'fault_injected':
                subsystem = fault.get('affected_subsystem', '')
                if subsystem == 'perception':
                    self.metrics['sensor_failures'] += 1
                elif subsystem == 'network':
                    self.metrics['network_failures'] += 1
                self._log('ROBOT-01', 'FAULT', 'CRITICAL',
                         f'Fault injected: {fault.get("type")} [{fault.get("severity")}]')

            elif event_type == 'fault_auto_recovered':
                self.metrics['recovery_success_count'] += 1
                self._log('ROBOT-01', 'FAULT', 'INFO',
                         f'Fault recovered: {fault.get("type")}')
        except Exception:
            pass

    def on_network_state(self, msg: String):
        """Track network metrics."""
        try:
            data = json.loads(msg.data)
            mode = data.get('mode', 'ONLINE')
            latency = data.get('actual_latency_ms', 0)

            # Update inference latency estimate
            if latency > 0:
                self.metrics['average_inference_latency_ms'] = round(
                    (self.metrics['average_inference_latency_ms'] * 0.9 + latency * 0.1), 1
                )

            # Update offload percentages
            if mode == 'ONLINE':
                self.metrics['server_offload_pct'] = 70.0
                self.metrics['edge_processing_pct'] = 30.0
            elif mode == 'PARTIAL':
                self.metrics['server_offload_pct'] = 30.0
                self.metrics['edge_processing_pct'] = 70.0
            else:
                self.metrics['server_offload_pct'] = 0.0
                self.metrics['edge_processing_pct'] = 100.0
        except Exception:
            pass

    def on_scenario_state(self, msg: String):
        """Log scenario changes."""
        try:
            data = json.loads(msg.data)
            self._log('SYSTEM', 'SCENARIO', 'INFO', f'Scenario: {data.get("name", "unknown")}')
        except Exception:
            pass

    def record_replay_frame(self):
        """Record a replay frame for later playback."""
        if not self.replay_recording:
            return

        frame = {
            'timestamp': time.time(),
            'session': self.replay_session_id,
            'metrics_snapshot': dict(self.metrics),
            'recent_logs': self.log_buffer[-10:] if self.log_buffer else []
        }
        self.replay_buffer.append(frame)

        # Keep replay buffer manageable
        if len(self.replay_buffer) > 5000:
            self.replay_buffer = self.replay_buffer[-5000:]

    def flush_logs(self):
        """Flush logs to disk periodically."""
        if not self.log_buffer:
            return

        try:
            log_file = os.path.join(self.log_dir, f'session_{self.replay_session_id}.jsonl')
            with open(log_file, 'a') as f:
                for entry in self.log_buffer[-100:]:
                    f.write(json.dumps(entry) + '\n')
        except Exception as e:
            self.get_logger().error(f'Failed to flush logs: {e}')

    def publish_analytics(self):
        """Publish current analytics."""
        self.metrics['session_uptime'] = round(time.time() - self.metrics['session_start'], 1)

        msg = String()
        msg.data = json.dumps(self.metrics)
        self.analytics_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = AnalyticsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
