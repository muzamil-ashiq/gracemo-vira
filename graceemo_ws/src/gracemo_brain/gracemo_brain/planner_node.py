#!/usr/bin/env python3
"""
GraceEMO kernel — InspectorState, reaction, and action dispatch.

Phase 1: wheeled navigate_to / stop / speak, plus body commands for
neck and 90° hands (executed by gracemo_control C++ or local joints).
"""

import json
import math
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, Quaternion, PoseStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import String, Float64

try:
    from gracemo_interfaces.msg import Detection, VoiceCommand, RobotState, BodyCommand
    from gracemo_interfaces.srv import AskQuestion, Recall
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False

# Fallback default seed places if memory service is unreachable
FALLBACK_PLACES = {
    'door': (2.5, -2.5, 'Welcome Reception Desk'),
    'reception': (2.5, -2.5, 'Welcome Reception Desk'),
    'lab': (2.5, 2.0, 'Robotics Research Lab'),
    'robotics': (2.5, 2.0, 'Robotics Research Lab'),
    'commons': (-2.5, -2.5, 'Campus Commons'),
    'kitchen': (-2.5, -2.5, 'Campus Commons'),
    'ai': (-2.5, 2.0, 'AI Compute Center'),
    'library': (45.0, 20.0, 'Central Library (B37)'),
    'mall': (30.0, -40.0, 'Uni-Mall Shopping Center'),
    'gate': (0.0, -95.0, 'Main Campus Gate 1'),
}

HAND_DOWN = 0.0
HAND_HI = 0.70
HAND_UP = 1.5708  # 90 degrees full raise


def yaw_from_quat(q):
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class InspectorState:
    """
    Unified cognitive telemetry:
    - pose: x, y, yaw
    - battery: live level (%)
    - obstacle: ahead, distance (m), direction
    - person: visible, distance (m), bearing (rad)
    - last_voice_command: transcript
    """
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.battery = 98.5
        self.obstacle_ahead = False
        self.obstacle_distance = 12.0
        self.obstacle_direction = 'none'
        self.min_range = 12.0
        self.person_visible = False
        self.person_distance = 99.0
        self.person_bearing = 0.0
        self.last_voice = ''
        self.current_task = 'IDLE'
        self.status = 'READY'

    def to_dict(self):
        return {
            'pose': {
                'x': round(self.x, 3),
                'y': round(self.y, 3),
                'yaw': round(self.yaw, 3),
            },
            'battery': round(self.battery, 1),
            'obstacle': {
                'detected': bool(self.obstacle_ahead),
                'distance': round(float(self.obstacle_distance), 2),
                'direction': self.obstacle_direction,
            },
            'person': {
                'visible': bool(self.person_visible),
                'distance': round(float(self.person_distance), 2) if self.person_visible else None,
                'bearing': round(float(self.person_bearing), 2) if self.person_visible else None,
            },
            'last_voice_command': self.last_voice,
            'task': self.current_task,
            'status': self.status,
        }


class AutonomyPlannerNode(Node):
    def __init__(self):
        super().__init__('planner_node')
        self.state = InspectorState()
        self.known_places = dict(FALLBACK_PLACES)

        self.declare_parameter('direct_cmd_vel', True)
        self.declare_parameter('actuate_joints', True)
        self.direct_cmd_vel = self._as_bool(self.get_parameter('direct_cmd_vel').value)
        self.actuate_joints = self._as_bool(self.get_parameter('actuate_joints').value)

        self.nav_active = False
        self.nav_x = 0.0
        self.nav_y = 0.0
        self.nav_name = ''
        self.last_greeting_time = 0.0
        self.neck_yaw = 0.0
        self.neck_pitch = 0.0
        self.left_hand = HAND_DOWN
        self.right_hand = HAND_DOWN

        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.desired_pub = self.create_publisher(Twist, '/gracemo/cmd_vel_desired', 10)
        self.say_pub = self.create_publisher(String, '/gracemo/say', 10)
        self.nav_goal_pub = self.create_publisher(String, '/gracemo/nav_goal', 10)
        self.nav2_goal_pub = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.inspector_json_pub = self.create_publisher(String, '/gracemo/inspector_state_json', 10)
        self.joint_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.j_yaw = self.create_publisher(Float64, '/neck_yaw/cmd_pos', 10)
        self.j_pitch = self.create_publisher(Float64, '/neck_pitch/cmd_pos', 10)
        self.j_lh = self.create_publisher(Float64, '/left_hand/cmd_pos', 10)
        self.j_rh = self.create_publisher(Float64, '/right_hand/cmd_pos', 10)

        if HAVE_INTERFACES:
            self.body_pub = self.create_publisher(BodyCommand, '/gracemo/body_command', 10)
            self.state_pub = self.create_publisher(RobotState, '/gracemo/inspector_state', 10)
            self.create_subscription(Detection, '/gracemo/detections', self.on_detection, 10)
            self.create_subscription(VoiceCommand, '/gracemo/voice_command', self.on_voice, 10)
            self.create_subscription(BodyCommand, '/gracemo/body_command', self.on_incoming_body, 10)
            self.llm_client = self.create_client(AskQuestion, '/gracemo/ask_question')
            self.recall_client = self.create_client(Recall, '/gracemo/recall')

        # Subscriptions
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)
        self.create_subscription(String, '/gracemo/sensors', self.on_sensors, 10)
        self.create_subscription(String, '/gracemo/robot_pose', self.on_robot_pose, 10)
        self.create_subscription(String, '/gracemo/known_places', self.on_known_places, 10)

        # Timers
        self.create_timer(0.1, self.control_loop)
        self.create_timer(0.05, self.publish_joints)
        self.create_timer(10.0, self.refresh_places_from_memory)

        self.get_logger().info('Kernel online — InspectorState (pose, battery, obstacle, person, voice) + dispatcher')

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('1', 'true', 'yes')

    def on_odom(self, msg):
        self.state.x = msg.pose.pose.position.x
        self.state.y = msg.pose.pose.position.y
        self.state.yaw = yaw_from_quat(msg.pose.pose.orientation)

    def on_robot_pose(self, msg):
        try:
            data = json.loads(msg.data)
            # Update only if odom hasn't set anything or as fallback
            if abs(self.state.x) < 1e-5 and abs(self.state.y) < 1e-5:
                self.state.x = float(data.get('x', self.state.x))
                self.state.y = float(data.get('y', self.state.y))
                self.state.yaw = float(data.get('yaw', self.state.yaw))
        except Exception:
            pass

    def on_sensors(self, msg):
        try:
            data = json.loads(msg.data)
            front_m = data.get('front_range_m')
            if front_m is not None:
                self.state.obstacle_distance = float(front_m)
                self.state.obstacle_ahead = (self.state.obstacle_distance < 1.0) or bool(data.get('bumper', False))
                self.state.obstacle_direction = 'front' if self.state.obstacle_ahead else 'none'
            if 'battery' in data:
                self.state.battery = float(data['battery'])
        except Exception:
            pass

    def on_known_places(self, msg):
        try:
            places = json.loads(msg.data)
            if isinstance(places, dict) and places:
                for k, v in places.items():
                    if isinstance(v, (list, tuple)) and len(v) >= 2:
                        name = v[2] if len(v) > 2 else k.capitalize()
                        self.known_places[k.lower()] = (float(v[0]), float(v[1]), name)
        except Exception:
            pass

    def refresh_places_from_memory(self):
        if HAVE_INTERFACES and self.recall_client.service_is_ready():
            req = Recall.Request()
            req.category = 'place'
            req.key = '*'
            future = self.recall_client.call_async(req)
            future.add_done_callback(self._on_bulk_places_recalled)

    def _on_bulk_places_recalled(self, future):
        try:
            res = future.result()
            if res.success and res.value:
                places = json.loads(res.value)
                for k, v in places.items():
                    if isinstance(v, (list, tuple)) and len(v) >= 2:
                        name = v[2] if len(v) > 2 else k.capitalize()
                        self.known_places[k.lower()] = (float(v[0]), float(v[1]), name)
        except Exception:
            pass

    def on_scan(self, msg):
        ranges = [r for r in msg.ranges if math.isfinite(r)]
        if ranges:
            self.state.min_range = min(ranges)
            self.state.obstacle_distance = min(self.state.obstacle_distance, self.state.min_range)
            if self.state.min_range < 1.0:
                self.state.obstacle_ahead = True
                self.state.obstacle_direction = 'front'

    def on_detection(self, msg):
        if msg.label != 'person' or msg.confidence < 0.6:
            return
        self.state.person_visible = True
        self.state.person_distance = msg.distance_meters
        cx = msg.center_x if msg.center_x else 0.5
        self.state.person_bearing = (cx - 0.5) * 1.2

        now = time.time()
        if msg.distance_meters < 2.5 and now - self.last_greeting_time > 15.0:
            self.last_greeting_time = now
            self.greet()

    def on_incoming_body(self, msg):
        a = (msg.action or '').lower()
        if a == 'stop':
            self.stop(None)
        elif a == 'navigate_to':
            self.navigate_to(msg.target or f'{msg.x:.1f},{msg.y:.1f}')
        elif a == 'speak':
            if msg.text:
                self.speak(msg.text)
        elif a == 'look_at':
            self.look_at(msg.x, msg.y)
        elif a == 'look_home':
            self.look_home()
        elif a == 'hand_hi':
            self.hand_hi()
        elif a == 'hand_up':
            self.hand_up()
        elif a == 'hand_down':
            self.hand_down()

    def on_voice(self, msg):
        text = msg.transcript.strip()
        intent = (msg.intent or '').upper()
        self.state.last_voice = text
        self.get_logger().info(f'Voice: "{text}" intent={intent}')

        if intent == 'STOP' or self._is_stop(text):
            self.stop('Stopping now.')
            return
        if intent == 'NAVIGATE' or self._is_navigate(text):
            place = self._extract_place(text, msg.entities)
            self.navigate_to(place)
            return
        if 'wave' in text.lower() or 'hand hi' in text.lower():
            self.hand_hi()
            self.speak('Hello!')
            return
        if 'hand up' in text.lower() or 'hands up' in text.lower():
            self.hand_up()
            self.speak('Hands raised.')
            return
        if 'hand down' in text.lower() or 'hands down' in text.lower():
            self.hand_down()
            self.speak('Hands lowered.')
            return
        if 'look' in text.lower() and 'home' in text.lower():
            self.look_home()
            self.speak('Looking forward.')
            return

        if HAVE_INTERFACES and self.llm_client.service_is_ready():
            req = AskQuestion.Request()
            req.question = text
            req.context = json.dumps(self.state.to_dict())
            future = self.llm_client.call_async(req)
            future.add_done_callback(self.on_llm_response)
        else:
            self.speak('I heard you, but my reasoning service is offline.')

    def on_llm_response(self, future):
        try:
            res = future.result()
        except Exception as e:
            self.get_logger().warn(f'LLM failed: {e}')
            return
        actions = list(res.suggested_actions) if res.suggested_actions else []
        for act in actions:
            if act.startswith('navigate_to'):
                place = act.split(':')[-1] if ':' in act else self._extract_place(
                    self.state.last_voice, [])
                self.navigate_to(place)
                return
            if act == 'stop':
                self.stop(res.answer or 'Stopping.')
                return
            if act == 'hand_hi':
                self.hand_hi()
            elif act == 'hand_up':
                self.hand_up()
            elif act == 'hand_down':
                self.hand_down()
            elif act == 'look_home':
                self.look_home()
        if res.answer:
            self.speak(res.answer)

    def greet(self):
        self.stop(None)
        self.look_at_person()
        self.hand_hi()
        self.speak(
            'Hello! I am GraceEMO. Welcome to campus. How may I assist you?'
        )
        self.state.current_task = 'GREET'

    def navigate_to(self, place_key):
        place_key = (place_key or '').lower().strip()
        # Check locally cached memory places first
        parsed = self._lookup_place(place_key)
        if parsed is not None:
            self._begin_nav(place_key, parsed)
            return

        # If not cached, query Recall service
        if HAVE_INTERFACES and self.recall_client.service_is_ready():
            req = Recall.Request()
            req.category = 'place'
            req.key = place_key
            future = self.recall_client.call_async(req)
            future.add_done_callback(
                lambda f, key=place_key: self._on_place_recalled(f, key))
            return

        self._begin_nav(place_key, None)

    def _on_place_recalled(self, future, place_key):
        parsed = None
        try:
            res = future.result()
            if res.success and res.value:
                parts = [p.strip() for p in res.value.split(',')]
                parsed = (float(parts[0]), float(parts[1]),
                          parts[2] if len(parts) > 2 else place_key.capitalize())
                self.known_places[place_key.lower()] = parsed
        except Exception as e:
            self.get_logger().warn(f'Recall failed: {e}')
        if parsed is None:
            parsed = self._lookup_place(place_key)
        self._begin_nav(place_key, parsed)

    def _begin_nav(self, place_key, parsed):
        if parsed is None:
            self.speak(f'I do not know where {place_key or "that"} is.')
            return
        x, y, name = parsed
        self.look_home()
        self.hand_down()
        self.nav_x, self.nav_y, self.nav_name = x, y, name
        self.nav_active = True
        self.state.current_task = f'NAVIGATE:{name}'
        self.speak(f'Going to {name}.')

        # 1. Publish to body_command for C++ safety node
        self._emit_body('navigate_to', place_key, x, y, '')

        # 2. Publish /gracemo/nav_goal for Virtual Space Simulation
        goal_msg = String()
        goal_msg.data = json.dumps({'x': float(x), 'y': float(y), 'name': str(name)})
        self.nav_goal_pub.publish(goal_msg)

        # 3. Publish /goal_pose for Nav2 action waypoint
        pose_stamped = PoseStamped()
        pose_stamped.header.stamp = self.get_clock().now().to_msg()
        pose_stamped.header.frame_id = 'map'
        pose_stamped.pose.position.x = float(x)
        pose_stamped.pose.position.y = float(y)
        pose_stamped.pose.position.z = 0.0
        pose_stamped.pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
        self.nav2_goal_pub.publish(pose_stamped)

        self.get_logger().info(f'navigate_to {name} ({x:.2f}, {y:.2f}) -> emitted to kernel, twin, and nav2')

    def stop(self, say_text):
        self.nav_active = False
        self.state.current_task = 'IDLE'
        cmd = Twist()
        self.desired_pub.publish(cmd)
        if self.direct_cmd_vel:
            self.cmd_pub.publish(cmd)
        self._emit_body('stop', '', 0.0, 0.0, '')
        if say_text:
            self.speak(say_text)

    def speak(self, text):
        msg = String()
        msg.data = text
        self.say_pub.publish(msg)
        self._emit_body('speak', '', 0.0, 0.0, text)

    def look_home(self):
        self.neck_yaw = 0.0
        self.neck_pitch = 0.0
        self._emit_body('look_home', '', 0.0, 0.0, '')

    def look_at(self, yaw, pitch=0.15):
        self.neck_yaw = max(-1.2, min(1.2, float(yaw)))
        self.neck_pitch = max(-0.5, min(0.6, float(pitch)))
        self._emit_body('look_at', '', self.neck_yaw, self.neck_pitch, '')

    def look_at_person(self):
        self.look_at(self.state.person_bearing, 0.15)

    def hand_hi(self):
        self.hand_pose('hi')

    def hand_up(self):
        self.hand_pose('up')

    def hand_down(self):
        self.hand_pose('down')

    def hand_pose(self, name):
        angle = {'hi': HAND_HI, 'up': HAND_UP, 'down': HAND_DOWN}.get(name, HAND_DOWN)
        self.left_hand = angle
        self.right_hand = angle
        self._emit_body(f'hand_{name}', '', 0.0, 0.0, '')

    def _emit_body(self, action, target, x, y, text):
        if not HAVE_INTERFACES:
            return
        cmd = BodyCommand()
        cmd.action = action
        cmd.target = target
        cmd.x = float(x)
        cmd.y = float(y)
        cmd.text = text
        self.body_pub.publish(cmd)

    def _lookup_place(self, key):
        k = (key or '').lower().strip()
        if k in self.known_places:
            return self.known_places[k]
        for name, data in self.known_places.items():
            if k in name or name in k:
                return data
        return None

    def _extract_place(self, text, entities):
        blob = (text or '').lower()
        # Match dynamically against all known places recalled from memory!
        for name in sorted(self.known_places.keys(), key=len, reverse=True):
            if name in blob:
                return name
        if entities:
            for e in entities:
                el = e.lower()
                if el in self.known_places:
                    return el
        return 'door'

    def _is_stop(self, text):
        t = text.lower()
        return any(w in t for w in ('stop', 'halt', 'freeze', 'emergency', 'wait'))

    def _is_navigate(self, text):
        t = text.lower()
        return any(phrase in t for phrase in ('go to', 'navigate', 'take me', 'drive to', 'head to', 'walk to'))

    def control_loop(self):
        cmd = Twist()
        if self.state.obstacle_ahead and self.nav_active:
            self.nav_active = False
            self.state.current_task = 'IDLE'
            self.speak('Obstacle ahead. Stopping.')
        elif self.nav_active:
            dx = self.nav_x - self.state.x
            dy = self.nav_y - self.state.y
            dist = math.hypot(dx, dy)
            if dist < 0.40:
                self.nav_active = False
                self.state.current_task = 'IDLE'
                self.speak(f'I have arrived at {self.nav_name}.')
            else:
                target = math.atan2(dy, dx)
                err = (target - self.state.yaw + math.pi) % (2 * math.pi) - math.pi
                if abs(err) > 0.4:
                    cmd.angular.z = 0.8 if err > 0 else -0.8
                    cmd.linear.x = 0.05
                else:
                    cmd.linear.x = min(0.35, 0.15 + dist * 0.2)
                    cmd.angular.z = err * 1.2

        self.desired_pub.publish(cmd)
        if self.direct_cmd_vel:
            self.cmd_pub.publish(cmd)

        # Publish unified InspectorState
        if HAVE_INTERFACES:
            st = RobotState()
            st.status = self.state.status
            st.battery_voltage = float(self.state.battery)
            st.cpu_temperature = 42.0
            st.current_task = self.state.current_task
            st.current_pose.position.x = self.state.x
            st.current_pose.position.y = self.state.y
            qz = math.sin(self.state.yaw * 0.5)
            qw = math.cos(self.state.yaw * 0.5)
            st.current_pose.orientation = Quaternion(x=0.0, y=0.0, z=qz, w=qw)
            st.active_nodes = ['planner_node', 'virtual_space_node', 'memory_node']
            self.state_pub.publish(st)

        # Publish structured JSON state
        json_msg = String()
        json_msg.data = json.dumps(self.state.to_dict())
        self.inspector_json_pub.publish(json_msg)

    def publish_joints(self):
        if not self.actuate_joints:
            return
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name = ['neck_yaw', 'neck_pitch', 'left_hand', 'right_hand']
        js.position = [
            float(self.neck_yaw),
            float(self.neck_pitch),
            float(self.left_hand),
            float(self.right_hand),
        ]
        self.joint_pub.publish(js)
        for pub, val in (
            (self.j_yaw, self.neck_yaw),
            (self.j_pitch, self.neck_pitch),
            (self.j_lh, self.left_hand),
            (self.j_rh, self.right_hand),
        ):
            m = Float64()
            m.data = float(val)
            pub.publish(m)


def main(args=None):
    rclpy.init(args=args)
    node = AutonomyPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
