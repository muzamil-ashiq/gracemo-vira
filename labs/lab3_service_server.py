#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.srv import Trigger
import random

class GraceEMOExecutiveService(Node):
    """
    Lab 3: Service Server
    Provides an on-demand campus status report when called.
    """
    def __init__(self):
        super().__init__('graceemo_executive_service')
        
        self.srv = self.create_service(
            Trigger,
            '/graceemo/get_campus_status',
            self.handle_campus_status_request
        )
        self.get_logger().info('🏛️ GraceEMO Campus Executive Service is READY on /graceemo/get_campus_status')

    def handle_campus_status_request(self, request, response):
        self.get_logger().info('📥 Incoming Campus Status Request received!')
        
        quotes = [
            "LPU Campus: 600 Acres | NAAC A++ | All Systems Operational.",
            "LPU Campus: 30,000+ Students Active | Weather Clear | AI Systems Online.",
            "LPU Campus: Innovation Labs Active | Robotic Patrols Running."
        ]
        response.success = True
        response.message = random.choice(quotes)
        
        self.get_logger().info(f'📤 Sending Response: "{response.message}"')
        return response

def main(args=None):
    rclpy.init(args=args)
    node = GraceEMOExecutiveService()
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
