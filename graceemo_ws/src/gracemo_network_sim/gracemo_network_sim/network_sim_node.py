#!/usr/bin/env python3
"""
GraceEMO — Network Simulation Node
Simulates configurable network conditions between the robot edge
and the central AI server: latency, jitter, packet loss, bandwidth limits.
Implements ONLINE / PARTIAL / OFFLINE failover states.
"""

import json
import time
import random
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class NetworkSimNode(Node):
    """
    Simulates network conditions for edge-cloud communication.
    Controls server availability and measures robot performance
    under degraded network conditions.
    """

    def __init__(self):
        super().__init__('network_sim_node')
        self.get_logger().info('🌐 Initializing Network Simulation...')

        # Declare parameters
        self.declare_parameter('latency_ms', 0)
        self.declare_parameter('jitter_ms', 0)
        self.declare_parameter('packet_loss_pct', 0.0)
        self.declare_parameter('bandwidth_mbps', 100.0)
        self.declare_parameter('server_available', True)

        # Network state
        self.network_state = {
            'mode': 'ONLINE',  # ONLINE, PARTIAL, OFFLINE
            'latency_ms': self.get_parameter('latency_ms').value,
            'jitter_ms': self.get_parameter('jitter_ms').value,
            'packet_loss_pct': self.get_parameter('packet_loss_pct').value,
            'bandwidth_mbps': self.get_parameter('bandwidth_mbps').value,
            'server_available': self.get_parameter('server_available').value,
            'actual_latency_ms': 0,
            'packets_sent': 0,
            'packets_dropped': 0,
            'uptime_pct': 100.0,
            'last_server_response': time.time(),
            'connection_quality': 'excellent'
        }

        # Publishers
        self.network_state_pub = self.create_publisher(String, '/gracemo/network_state', 10)
        self.server_status_pub = self.create_publisher(String, '/gracemo/server_status', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/set_network', self.on_set_network, 10)
        self.create_subscription(String, '/gracemo/set_server', self.on_set_server, 10)

        # Timers
        self.create_timer(0.5, self.simulate_network)
        self.create_timer(1.0, self.publish_state)

        self.get_logger().info('✅ Network Simulation ready')

    def _update_mode(self):
        """Determine connection mode based on current conditions."""
        if not self.network_state['server_available']:
            self.network_state['mode'] = 'OFFLINE'
        elif self.network_state['latency_ms'] > 200 or self.network_state['packet_loss_pct'] > 5:
            self.network_state['mode'] = 'PARTIAL'
        else:
            self.network_state['mode'] = 'ONLINE'

        # Connection quality
        latency = self.network_state['latency_ms']
        loss = self.network_state['packet_loss_pct']
        if not self.network_state['server_available']:
            self.network_state['connection_quality'] = 'disconnected'
        elif latency < 25 and loss < 1:
            self.network_state['connection_quality'] = 'excellent'
        elif latency < 100 and loss < 3:
            self.network_state['connection_quality'] = 'good'
        elif latency < 250 and loss < 5:
            self.network_state['connection_quality'] = 'fair'
        else:
            self.network_state['connection_quality'] = 'poor'

    def on_set_network(self, msg: String):
        """Handle network condition changes."""
        try:
            data = json.loads(msg.data)
            if 'latency_ms' in data:
                self.network_state['latency_ms'] = int(data['latency_ms'])
            if 'jitter_ms' in data:
                self.network_state['jitter_ms'] = int(data['jitter_ms'])
            if 'packet_loss_pct' in data:
                self.network_state['packet_loss_pct'] = float(data['packet_loss_pct'])
            if 'bandwidth_mbps' in data:
                self.network_state['bandwidth_mbps'] = float(data['bandwidth_mbps'])
            self._update_mode()
            self.get_logger().info(f'🌐 Network updated: latency={self.network_state["latency_ms"]}ms, '
                                  f'loss={self.network_state["packet_loss_pct"]}%, mode={self.network_state["mode"]}')
        except Exception as e:
            self.get_logger().error(f'Failed to set network: {e}')

    def on_set_server(self, msg: String):
        """Toggle server availability."""
        available = msg.data.strip().lower() in ('true', '1', 'on', 'available', 'online')
        self.network_state['server_available'] = available
        self._update_mode()
        status = 'AVAILABLE' if available else 'UNAVAILABLE'
        self.get_logger().info(f'🖥️  Server: {status} → Mode: {self.network_state["mode"]}')

    def simulate_network(self):
        """Simulate network behavior (latency + jitter + packet loss)."""
        self.network_state['packets_sent'] += 1

        # Simulate actual latency with jitter
        base_latency = self.network_state['latency_ms']
        jitter = self.network_state['jitter_ms']
        actual = max(0, base_latency + random.randint(-jitter, jitter))
        self.network_state['actual_latency_ms'] = actual

        # Simulate packet loss
        loss_pct = self.network_state['packet_loss_pct']
        if random.random() * 100 < loss_pct:
            self.network_state['packets_dropped'] += 1

        # Calculate uptime
        total = self.network_state['packets_sent']
        dropped = self.network_state['packets_dropped']
        self.network_state['uptime_pct'] = round((1.0 - dropped / max(1, total)) * 100, 2)

        if self.network_state['server_available']:
            self.network_state['last_server_response'] = time.time()

        self._update_mode()

    def publish_state(self):
        """Publish current network state."""
        msg = String()
        msg.data = json.dumps(self.network_state)
        self.network_state_pub.publish(msg)

        server_msg = String()
        server_msg.data = json.dumps({
            'available': self.network_state['server_available'],
            'mode': self.network_state['mode'],
            'latency_ms': self.network_state['actual_latency_ms'],
            'quality': self.network_state['connection_quality']
        })
        self.server_status_pub.publish(server_msg)


def main(args=None):
    rclpy.init(args=args)
    node = NetworkSimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
