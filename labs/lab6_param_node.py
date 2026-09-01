#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

class ConfigurableRobotNode(Node):
    """
    Lab 6: Node with Dynamic Parameters
    Can be dynamically reconfigured at runtime via 'ros2 param set'!
    """
    def __init__(self):
        super().__init__('configurable_robot_node')
        
        # 1. Declare parameters with default values
        self.declare_parameter('robot_name', 'GraceEMO_V1')
        self.declare_parameter('max_speed', 0.50)
        self.declare_parameter('voice_enabled', True)
        
        # 2. Read parameter values
        robot_name = self.get_parameter('robot_name').get_parameter_value().string_value
        max_speed = self.get_parameter('max_speed').get_parameter_value().double_value
        voice_enabled = self.get_parameter('voice_enabled').get_parameter_value().bool_value
        
        self.get_logger().info(f'🤖 Robot Config: Name={robot_name} | MaxSpeed={max_speed}m/s | Voice={voice_enabled}')
        
        # Timer to report active parameter settings
        self.create_timer(2.0, self.timer_callback)

    def timer_callback(self):
        speed = self.get_parameter('max_speed').get_parameter_value().double_value
        name = self.get_parameter('robot_name').get_parameter_value().string_value
        self.get_logger().info(f'⚙️ Active Parameters: Name="{name}" | Speed={speed:.2f} m/s')

def main(args=None):
    rclpy.init(args=args)
    node = ConfigurableRobotNode()
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
