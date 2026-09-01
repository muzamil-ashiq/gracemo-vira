#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32
import random

class RobotTelemetryPublisher(Node):
    """
    Lab 1: Robot Telemetry & Battery Publisher
    Publishes status (String) and battery voltage (Float32) at 2.0 Hz.
    """
    def __init__(self):
        super().__init__('robot_telemetry_publisher')
        
        # 1. Create publishers
        self.status_pub = self.create_publisher(String, '/graceemo/status', 10)
        self.battery_pub = self.create_publisher(Float32, '/graceemo/battery_voltage', 10)
        
        # 2. Timer fires every 0.5s (2 Hz)
        self.timer = self.create_timer(0.5, self.publish_telemetry)
        
        self.battery_level = 12.60 # Simulated starting 3S LiPo voltage
        self.get_logger().info('✅ Telemetry Publisher Node is ACTIVE & Broadcasting!')

    def publish_telemetry(self):
        # Publish Status String
        status_msg = String()
        status_msg.data = "SYSTEM_NORMAL"
        self.status_pub.publish(status_msg)
        
        # Simulate slight battery drain & publish voltage
        self.battery_level -= random.uniform(0.002, 0.008)
        battery_msg = Float32()
        battery_msg.data = float(round(self.battery_level, 3))
        self.battery_pub.publish(battery_msg)
        
        self.get_logger().info(f'⚡ Voltage: {battery_msg.data:.3f}V | Status: {status_msg.data}')

def main(args=None):
    rclpy.init(args=args)
    node = RobotTelemetryPublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
