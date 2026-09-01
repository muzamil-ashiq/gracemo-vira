#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

class BatteryWatchdogNode(Node):
    """
    Lab 1: Safety Watchdog Subscriber
    Listens to '/graceemo/battery_voltage'.
    Triggers critical alarm when voltage drops below 12.0V!
    """
    def __init__(self):
        super().__init__('battery_watchdog')
        
        self.sub = self.create_subscription(
            Float32,
            '/graceemo/battery_voltage',
            self.battery_callback,
            10
        )
        self.critical_voltage = 12.00
        self.get_logger().info('🛡️ Battery Safety Watchdog Armed & Monitoring...')

    def battery_callback(self, msg: Float32):
        voltage = msg.data
        if voltage < self.critical_voltage:
            self.get_logger().error(f'🚨 CRITICAL VOLTAGE ALERT: {voltage:.3f}V! Triggering Safe E-Stop!')
        else:
            self.get_logger().info(f'🔋 Normal Battery Voltage: {voltage:.3f}V')

def main(args=None):
    rclpy.init(args=args)
    node = BatteryWatchdogNode()
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
