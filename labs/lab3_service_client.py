#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.srv import Trigger

class GraceEMOClient(Node):
    """
    Lab 3: Service Client
    Calls the '/graceemo/get_campus_status' service and waits for response.
    """
    def __init__(self):
        super().__init__('graceemo_client')
        self.client = self.create_client(Trigger, '/graceemo/get_campus_status')
        
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Waiting for Executive Service to come online...')
            
    def send_request(self):
        req = Trigger.Request()
        self.get_logger().info('🚀 Sending request to server...')
        future = self.client.call_async(req)
        return future

def main(args=None):
    rclpy.init(args=args)
    node = GraceEMOClient()
    future = node.send_request()
    
    rclpy.spin_until_future_complete(node, future)
    
    if future.result() is not None:
        res = future.result()
        node.get_logger().info(f'🎉 Received: Success={res.success} | "{res.message}"')
    else:
        node.get_logger().error(f'Service call failed: {future.exception()}')
        
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()
