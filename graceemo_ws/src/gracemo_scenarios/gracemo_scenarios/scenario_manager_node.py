#!/usr/bin/env python3
"""
GraceEMO — Scenario Manager Node
Controls weather presets, crowd density, traffic density, time of day,
and environmental conditions for the LPU Digital Twin simulation.
"""

import json
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ScenarioManagerNode(Node):
    """
    Manages simulation scenario presets and environment conditions.
    Publishes scenario state changes so other nodes (pedestrians, vehicles,
    sensors, lighting) can adapt.
    """

    def __init__(self):
        super().__init__('scenario_manager_node')
        self.get_logger().info('🌤️  Initializing Scenario Manager...')

        # Declare parameters
        self.declare_parameter('campus_metadata_path', '')
        self.declare_parameter('active_scenario', 'normal_campus')

        # Load campus metadata for scenario presets
        metadata_path = self.get_parameter('campus_metadata_path').value
        self.campus_metadata = {}
        self.scenario_presets = {}
        self.weather_presets = {}
        if metadata_path and os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                self.campus_metadata = json.load(f)
                self.scenario_presets = self.campus_metadata.get('scenario_presets', {})
                self.weather_presets = self.campus_metadata.get('weather_presets', {})
            self.get_logger().info(f'Loaded {len(self.scenario_presets)} scenario presets')

        # Current environment state
        self.current_scenario = {
            'name': 'normal_campus',
            'weather': 'clear_day',
            'crowd_density': 'medium',  # low/medium/high
            'traffic_density': 'low',   # low/medium/high
            'time_of_day': 'day',       # day/dusk/night
            'lighting': 'bright',
            'visibility': 1.0,
            'sensor_noise_factor': 1.0,
            'network_latency_ms': 0,
            'packet_loss_pct': 0.0,
            'server_available': True,
            'special': ''
        }

        # Publishers
        self.scenario_pub = self.create_publisher(String, '/gracemo/scenario_state', 10)
        self.weather_pub = self.create_publisher(String, '/gracemo/weather', 10)
        self.crowd_pub = self.create_publisher(String, '/gracemo/crowd_density', 10)

        # Subscribers — accept scenario commands
        self.create_subscription(String, '/gracemo/set_scenario', self.on_set_scenario, 10)
        self.create_subscription(String, '/gracemo/set_weather', self.on_set_weather, 10)
        self.create_subscription(String, '/gracemo/set_crowd', self.on_set_crowd, 10)
        self.create_subscription(String, '/gracemo/set_traffic', self.on_set_traffic, 10)

        # Apply initial scenario
        initial = self.get_parameter('active_scenario').value
        if initial in self.scenario_presets:
            self._apply_preset(initial)

        # Publish state periodically
        self.create_timer(1.0, self.publish_state)

        self.get_logger().info(f'✅ Scenario Manager ready — active: {self.current_scenario["name"]}')

    def _apply_preset(self, preset_name: str):
        """Apply a named scenario preset."""
        if preset_name not in self.scenario_presets:
            self.get_logger().warn(f'Unknown scenario preset: {preset_name}')
            return

        preset = self.scenario_presets[preset_name]
        self.current_scenario['name'] = preset_name
        self.current_scenario['crowd_density'] = preset.get('crowd_density', 'medium')
        self.current_scenario['traffic_density'] = preset.get('traffic_density', 'low')
        self.current_scenario['special'] = preset.get('special', '')

        weather_name = preset.get('weather', 'clear_day')
        self.current_scenario['weather'] = weather_name
        if weather_name in self.weather_presets:
            wp = self.weather_presets[weather_name]
            self.current_scenario['lighting'] = wp.get('lighting', 'bright')
            self.current_scenario['visibility'] = wp.get('visibility', 1.0)
            self.current_scenario['sensor_noise_factor'] = wp.get('sensor_noise_factor', 1.0)

        self.get_logger().info(f'🔄 Applied scenario: {preset_name}')

    def on_set_scenario(self, msg: String):
        """Handle scenario preset change command."""
        self._apply_preset(msg.data.strip())

    def on_set_weather(self, msg: String):
        """Handle weather change command."""
        weather = msg.data.strip().lower()
        if weather in self.weather_presets:
            wp = self.weather_presets[weather]
            self.current_scenario['weather'] = weather
            self.current_scenario['lighting'] = wp.get('lighting', 'bright')
            self.current_scenario['visibility'] = wp.get('visibility', 1.0)
            self.current_scenario['sensor_noise_factor'] = wp.get('sensor_noise_factor', 1.0)
            self.get_logger().info(f'🌦️  Weather changed to: {weather}')
        else:
            self.get_logger().warn(f'Unknown weather: {weather}')

    def on_set_crowd(self, msg: String):
        """Handle crowd density change."""
        density = msg.data.strip().lower()
        if density in ('low', 'medium', 'high'):
            self.current_scenario['crowd_density'] = density
            self.get_logger().info(f'👥 Crowd density: {density}')

    def on_set_traffic(self, msg: String):
        """Handle traffic density change."""
        density = msg.data.strip().lower()
        if density in ('low', 'medium', 'high'):
            self.current_scenario['traffic_density'] = density
            self.get_logger().info(f'🚗 Traffic density: {density}')

    def publish_state(self):
        """Publish current scenario state as JSON."""
        msg = String()
        msg.data = json.dumps(self.current_scenario)
        self.scenario_pub.publish(msg)

        weather_msg = String()
        weather_msg.data = self.current_scenario['weather']
        self.weather_pub.publish(weather_msg)

        crowd_msg = String()
        crowd_msg.data = self.current_scenario['crowd_density']
        self.crowd_pub.publish(crowd_msg)


def main(args=None):
    rclpy.init(args=args)
    node = ScenarioManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
