#!/usr/bin/env python3
"""
GraceEMO — Central AI Server Node
FastAPI-based central AI server abstraction providing LLM/VLM inference,
knowledge retrieval, global mission planning, fleet coordination,
and digital twin state management.
"""

import json
import time
import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class CentralServerNode(Node):
    """
    Central AI server abstraction for the LPU Digital Twin.
    Provides heavy AI inference endpoints and manages fleet state.
    """

    def __init__(self):
        super().__init__('central_server_node')
        self.get_logger().info('🖥️  Initializing Central AI Server...')

        self.declare_parameter('server_port', 8090)
        self.declare_parameter('gpu_utilization_sim', 55.0)
        self.declare_parameter('cpu_utilization_sim', 40.0)

        # Server state
        self.server_state = {
            'status': 'online',
            'gpu_utilization': self.get_parameter('gpu_utilization_sim').value,
            'cpu_utilization': self.get_parameter('cpu_utilization_sim').value,
            'ram_usage_gb': 8.2,
            'ram_total_gb': 32.0,
            'inference_latency_ms': 45,
            'active_requests': 0,
            'queue_depth': 0,
            'total_requests_served': 0,
            'models_loaded': ['gemini-2.0-flash', 'yolo11n', 'sentence-transformers'],
            'uptime_seconds': 0,
            'started_at': time.time()
        }

        # Fleet state (multi-robot)
        self.fleet = {
            'ROBOT-01': {
                'status': 'online',
                'last_heartbeat': time.time(),
                'position': {'x': 0, 'y': 0},
                'battery': 98.5,
                'current_mission': None
            }
        }

        # Knowledge base (semantic campus info)
        self.knowledge_base = {}

        # Digital twin state
        self.digital_twin_state = {
            'synchronized': True,
            'last_sync': time.time(),
            'environment_state': 'normal',
            'active_robots': 1,
            'active_missions': 0
        }

        # Publishers
        self.server_state_pub = self.create_publisher(String, '/gracemo/server_state', 10)
        self.fleet_state_pub = self.create_publisher(String, '/gracemo/fleet_state', 10)
        self.twin_state_pub = self.create_publisher(String, '/gracemo/digital_twin_state', 10)
        self.ai_response_pub = self.create_publisher(String, '/gracemo/ai_response', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/ai_request', self.on_ai_request, 10)
        self.create_subscription(String, '/gracemo/robot_heartbeat', self.on_heartbeat, 10)
        self.create_subscription(String, '/gracemo/mission_state', self.on_mission_update, 10)

        # Timers
        self.create_timer(1.0, self.publish_server_state)
        self.create_timer(2.0, self.update_simulated_load)

        # Start FastAPI server in background thread
        self.api_port = self.get_parameter('server_port').value
        self.api_thread = threading.Thread(target=self._start_api_server, daemon=True)
        self.api_thread.start()

        self.get_logger().info(f'✅ Central AI Server ready — API at port {self.api_port}')

    def _start_api_server(self):
        """Start a lightweight API server for the central AI server."""
        try:
            import tornado.ioloop
            import tornado.web

            server_ref = self

            class StatusHandler(tornado.web.RequestHandler):
                def get(self):
                    self.set_header("Content-Type", "application/json")
                    self.write(json.dumps(server_ref.server_state))

            class FleetHandler(tornado.web.RequestHandler):
                def get(self):
                    self.set_header("Content-Type", "application/json")
                    self.write(json.dumps(server_ref.fleet))

            class TwinHandler(tornado.web.RequestHandler):
                def get(self):
                    self.set_header("Content-Type", "application/json")
                    self.write(json.dumps(server_ref.digital_twin_state))

            class InferenceHandler(tornado.web.RequestHandler):
                def post(self):
                    try:
                        data = json.loads(self.request.body)
                        # Simulate inference
                        server_ref.server_state['active_requests'] += 1
                        server_ref.server_state['total_requests_served'] += 1
                        time.sleep(0.01)  # Simulate processing
                        server_ref.server_state['active_requests'] -= 1
                        self.set_header("Content-Type", "application/json")
                        self.write(json.dumps({
                            'status': 'success',
                            'result': f'Processed: {data.get("query", "unknown")}',
                            'latency_ms': server_ref.server_state['inference_latency_ms']
                        }))
                    except Exception as e:
                        self.set_status(500)
                        self.write(json.dumps({'error': str(e)}))

            app = tornado.web.Application([
                (r'/api/status', StatusHandler),
                (r'/api/fleet', FleetHandler),
                (r'/api/twin', TwinHandler),
                (r'/api/inference', InferenceHandler),
            ])

            loop = tornado.ioloop.IOLoop()
            loop.make_current()
            app.listen(self.api_port)
            loop.start()
        except Exception as e:
            self.get_logger().error(f'Failed to start API server: {e}')

    def on_ai_request(self, msg: String):
        """Handle AI inference requests from robot edge."""
        try:
            data = json.loads(msg.data)
            self.server_state['active_requests'] += 1
            self.server_state['total_requests_served'] += 1

            # Simulate processing and publish response
            response = {
                'request_id': data.get('request_id', ''),
                'status': 'success',
                'result': f'Server processed: {data.get("query", "")}',
                'source': 'central_server',
                'latency_ms': self.server_state['inference_latency_ms']
            }
            resp_msg = String()
            resp_msg.data = json.dumps(response)
            self.ai_response_pub.publish(resp_msg)
            self.server_state['active_requests'] = max(0, self.server_state['active_requests'] - 1)
        except Exception as e:
            self.get_logger().error(f'AI request error: {e}')

    def on_heartbeat(self, msg: String):
        """Handle robot heartbeat messages."""
        try:
            data = json.loads(msg.data)
            robot_id = data.get('robot_id', 'ROBOT-01')
            if robot_id in self.fleet:
                self.fleet[robot_id]['last_heartbeat'] = time.time()
                self.fleet[robot_id]['position'] = data.get('position', {})
                self.fleet[robot_id]['battery'] = data.get('battery', 0)
                self.fleet[robot_id]['status'] = 'online'
        except Exception:
            pass

    def on_mission_update(self, msg: String):
        """Track mission state for fleet coordination."""
        try:
            data = json.loads(msg.data)
            active = data.get('active_mission')
            self.digital_twin_state['active_missions'] = 1 if active else 0
        except Exception:
            pass

    def update_simulated_load(self):
        """Simulate server load variations."""
        import random
        self.server_state['gpu_utilization'] = round(
            max(10, min(95, self.server_state['gpu_utilization'] + random.uniform(-5, 5))), 1)
        self.server_state['cpu_utilization'] = round(
            max(10, min(90, self.server_state['cpu_utilization'] + random.uniform(-3, 3))), 1)
        self.server_state['inference_latency_ms'] = max(10, int(
            self.server_state['inference_latency_ms'] + random.randint(-5, 5)))
        self.server_state['uptime_seconds'] = int(time.time() - self.server_state['started_at'])

        # Update digital twin sync
        self.digital_twin_state['last_sync'] = time.time()
        self.digital_twin_state['synchronized'] = True

        # Check fleet health
        for rid, robot in self.fleet.items():
            if time.time() - robot.get('last_heartbeat', 0) > 10:
                robot['status'] = 'offline'

    def publish_server_state(self):
        """Publish server, fleet, and digital twin state."""
        msg = String()
        msg.data = json.dumps(self.server_state)
        self.server_state_pub.publish(msg)

        fleet_msg = String()
        fleet_msg.data = json.dumps(self.fleet)
        self.fleet_state_pub.publish(fleet_msg)

        twin_msg = String()
        twin_msg.data = json.dumps(self.digital_twin_state)
        self.twin_state_pub.publish(twin_msg)


def main(args=None):
    rclpy.init(args=args)
    node = CentralServerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
