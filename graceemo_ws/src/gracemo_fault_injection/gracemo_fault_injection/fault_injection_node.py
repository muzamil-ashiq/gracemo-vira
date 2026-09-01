#!/usr/bin/env python3
"""
GraceEMO — Fault Injection Engine
Injects configurable sensor, actuator, network, and system faults
into the simulation for testing robot resilience.
"""

import json
import time
import random
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class Fault:
    """Represents an active fault in the system."""

    TYPES = [
        'camera_failure', 'depth_sensor_failure', 'lidar_failure',
        'imu_failure', 'encoder_failure', 'motor_failure',
        'overheating', 'low_battery', 'network_outage',
        'server_outage', 'localization_degradation',
        'motor_left_failure', 'motor_right_failure',
        'camera_obstruction', 'lidar_noise'
    ]

    SEVERITIES = ['warning', 'critical', 'fatal']

    def __init__(self, fault_type: str, severity: str = 'critical', duration: float = -1):
        self.id = f'fault_{int(time.time()*1000)}_{random.randint(100,999)}'
        self.type = fault_type
        self.severity = severity
        self.active = True
        self.injected_at = time.time()
        self.duration = duration  # -1 = permanent until cleared
        self.affected_subsystem = self._get_subsystem()
        self.recovery_state = 'not_started'
        self.detected = False

    def _get_subsystem(self) -> str:
        mapping = {
            'camera_failure': 'perception', 'depth_sensor_failure': 'perception',
            'lidar_failure': 'perception', 'imu_failure': 'perception',
            'encoder_failure': 'control', 'motor_failure': 'control',
            'motor_left_failure': 'control', 'motor_right_failure': 'control',
            'overheating': 'system', 'low_battery': 'power',
            'network_outage': 'network', 'server_outage': 'network',
            'localization_degradation': 'navigation',
            'camera_obstruction': 'perception', 'lidar_noise': 'perception'
        }
        return mapping.get(self.type, 'unknown')

    def check_expired(self) -> bool:
        if self.duration > 0 and (time.time() - self.injected_at) > self.duration:
            self.active = False
            self.recovery_state = 'auto_recovered'
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'active': self.active,
            'injected_at': self.injected_at,
            'duration': self.duration,
            'elapsed': round(time.time() - self.injected_at, 1),
            'affected_subsystem': self.affected_subsystem,
            'recovery_state': self.recovery_state,
            'detected': self.detected
        }


class FaultInjectionNode(Node):
    """
    Fault injection engine for testing robot resilience.
    Supports injecting, clearing, and randomizing faults.
    Publishes fault events for the robot to detect and handle.
    """

    def __init__(self):
        super().__init__('fault_injection_node')
        self.get_logger().info('⚠️  Initializing Fault Injection Engine...')

        self.active_faults: dict[str, Fault] = {}
        self.fault_history: list[dict] = []
        self.fault_event_counter = 0

        # Publishers
        self.fault_state_pub = self.create_publisher(String, '/gracemo/fault_state', 10)
        self.fault_event_pub = self.create_publisher(String, '/gracemo/fault_events', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/inject_fault', self.on_inject_fault, 10)
        self.create_subscription(String, '/gracemo/clear_fault', self.on_clear_fault, 10)
        self.create_subscription(String, '/gracemo/clear_all_faults', self.on_clear_all, 10)
        self.create_subscription(String, '/gracemo/random_fault', self.on_random_fault, 10)

        # Update timer
        self.create_timer(0.5, self.update_faults)
        self.create_timer(1.0, self.publish_state)

        self.get_logger().info('✅ Fault Injection Engine ready')

    def on_inject_fault(self, msg: String):
        """Inject a specific fault."""
        try:
            data = json.loads(msg.data)
            fault_type = data.get('type', '')
            severity = data.get('severity', 'critical')
            duration = data.get('duration', -1)

            if fault_type not in Fault.TYPES:
                self.get_logger().warn(f'Unknown fault type: {fault_type}')
                return

            fault = Fault(fault_type, severity, duration)
            self.active_faults[fault.id] = fault

            self._publish_event('fault_injected', fault)
            self.get_logger().warn(f'🔴 FAULT INJECTED: {fault_type} [{severity}] — {fault.id}')
        except Exception as e:
            self.get_logger().error(f'Failed to inject fault: {e}')

    def on_clear_fault(self, msg: String):
        """Clear a specific fault by ID or type."""
        target = msg.data.strip()
        cleared = []
        for fid, fault in list(self.active_faults.items()):
            if fid == target or fault.type == target:
                fault.active = False
                fault.recovery_state = 'manually_cleared'
                self.fault_history.append(fault.to_dict())
                cleared.append(fid)
                self._publish_event('fault_cleared', fault)

        for fid in cleared:
            del self.active_faults[fid]

        if cleared:
            self.get_logger().info(f'🟢 Faults cleared: {cleared}')

    def on_clear_all(self, msg: String):
        """Clear all active faults."""
        for fault in self.active_faults.values():
            fault.active = False
            fault.recovery_state = 'manually_cleared'
            self.fault_history.append(fault.to_dict())
            self._publish_event('fault_cleared', fault)

        count = len(self.active_faults)
        self.active_faults.clear()
        self.get_logger().info(f'🟢 All {count} faults cleared')

    def on_random_fault(self, msg: String):
        """Inject a random fault for testing."""
        fault_type = random.choice(Fault.TYPES)
        severity = random.choice(Fault.SEVERITIES)
        duration = random.uniform(5, 30)  # Auto-recover in 5-30 seconds
        fault = Fault(fault_type, severity, duration)
        self.active_faults[fault.id] = fault
        self._publish_event('fault_injected', fault)
        self.get_logger().warn(f'🎲 RANDOM FAULT: {fault_type} [{severity}] — auto-recover in {duration:.0f}s')

    def update_faults(self):
        """Check for expired faults."""
        expired = []
        for fid, fault in self.active_faults.items():
            if fault.check_expired():
                self.fault_history.append(fault.to_dict())
                expired.append(fid)
                self._publish_event('fault_auto_recovered', fault)
                self.get_logger().info(f'🟡 Fault auto-recovered: {fault.type} ({fid})')

        for fid in expired:
            del self.active_faults[fid]

    def _publish_event(self, event_type: str, fault: Fault):
        """Publish a fault event."""
        self.fault_event_counter += 1
        event = {
            'event_id': self.fault_event_counter,
            'event_type': event_type,
            'timestamp': time.time(),
            'fault': fault.to_dict()
        }
        msg = String()
        msg.data = json.dumps(event)
        self.fault_event_pub.publish(msg)

    def publish_state(self):
        """Publish current fault injection state."""
        state = {
            'active_faults': {fid: f.to_dict() for fid, f in self.active_faults.items()},
            'active_count': len(self.active_faults),
            'history_count': len(self.fault_history),
            'affected_subsystems': list(set(f.affected_subsystem for f in self.active_faults.values()))
        }
        msg = String()
        msg.data = json.dumps(state)
        self.fault_state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = FaultInjectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
