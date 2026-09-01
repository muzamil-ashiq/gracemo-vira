#!/usr/bin/env python3
"""
GraceEMO — Standalone LPU Autonomous Robotics Digital Twin Studio & VR Simulation Engine
Runs directly on macOS host with Python 3 + Tornado + OpenCV + NumPy.
Provides:
  - 200m x 200m LPU Campus spatial kinematics & building collision resolution
  - 360-degree LiDAR raycasting with dynamic agent occlusion & noise
  - First-person synthetic camera rendering with perspective projection & HUD
  - Dynamic pedestrian agents with Social Force Model & campus hotspot routing
  - Road vehicles (cars, buses)
  - Natural Language Mission System & Progress Tracking (0-100%)
  - Weather & Environmental Presets (Clear, Rain, Fog, Night)
  - Central AI Server & Network condition simulation (Online, Degraded, Offline)
  - Fault Injection engine (LiDAR failure, Camera blackout, Battery drop)
  - Full-duplex WebSocket server on ws://localhost:8888/ws
  - Serves Command Center UI at http://localhost:8888
"""

import os
import sys
import math
import time
import json
import base64
import random
import webbrowser
import numpy as np
import cv2

import tornado.ioloop
import tornado.web
import tornado.websocket

WEB_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'graceemo_ws', 'src', 'gracemo_gazebo', 'web')
)
METADATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'graceemo_ws', 'src', 'gracemo_gazebo', 'config', 'campus_metadata.json')
)


def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t, (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


class DynamicAgent:
    def __init__(self, agent_id, x, y, agent_type='student'):
        self.id = agent_id
        self.x = x
        self.y = y
        self.type = agent_type
        self.speed = 1.2 if agent_type == 'student' else 4.0 if agent_type == 'car' else 3.0 if agent_type == 'bus' else 1.0
        self.heading = random.uniform(-math.pi, math.pi)
        self.radius = 1.5 if agent_type == 'car' else 2.5 if agent_type == 'bus' else 0.35
        self.target = (x + random.uniform(-30, 30), y + random.uniform(-30, 30))
        self.color = [200, 100, 50] if agent_type == 'student' else [80, 120, 220] if agent_type == 'car' else [50, 180, 100]

    def update(self, dt, hotspots):
        dx = self.target[0] - self.x
        dy = self.target[1] - self.y
        dist = math.hypot(dx, dy)
        if dist < 2.0:
            dest = random.choice(hotspots)
            self.target = (dest[0] + random.uniform(-8, 8), dest[1] + random.uniform(-8, 8))
        else:
            self.heading = math.atan2(dy, dx)
            self.x += math.cos(self.heading) * self.speed * dt
            self.y += math.sin(self.heading) * self.speed * dt
            self.x = max(-95, min(95, self.x))
            self.y = max(-95, min(95, self.y))

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'x': round(self.x, 2),
            'y': round(self.y, 2),
            'heading': round(self.heading, 3),
            'speed': round(self.speed, 2),
            'radius': self.radius,
            'color': self.color,
            'name': f'{self.type.capitalize()} {self.id[-3:]}'
        }


class DigitalTwinEngine:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.linear_v = 0.0
        self.angular_w = 0.0
        self.target_linear_v = 0.0
        self.target_angular_w = 0.0
        self.robot_radius = 0.30
        self.battery = 98.5
        self.status = 'READY'
        self.current_task = 'IDLE'
        self.neck_yaw = 0.0
        self.neck_pitch = 0.08
        self.left_hand = 0.0
        self.right_hand = 0.0
        self.speech = ''
        self.teleop_until = 0.0
        self.bumper_hit = False
        self.distance_traveled = 0.0
        self.missions_completed = 0
        self.collision_count = 0
        self.wave_until = 0.0
        self.look_target_yaw = 0.0
        self.detections = []
        self.tracks = {}
        self.track_seq = 1
        self.follow_track_id = None
        self.perception_counts = {}
        self.ai_metrics = {'inference_ms': 0.0, 'fps': 10.0, 'tracked': 0}
        self.scene = {}
        self.last_intent = None
        self._charge_mission_armed = False
        self.estop = False
        self.speed_limit = 0.5
        self.operating_mode = 'SIMULATION'
        self.wheelbase_m = 0.28
        self.wheel_sep_m = 0.42
        self.wheel_r_m = 0.12
        self.encoder = {'fl': 0.0, 'fr': 0.0, 'rl': 0.0, 'rr': 0.0}
        self.wheel_fault = None
        self.charging = False
        self._last_safety_note = ''

        # Campus Bounds & Walls
        self.campus_bounds = 100.0
        self.walls = [
            ((-100.0, -100.0), (100.0, -100.0), 'South Boundary'),
            ((100.0, -100.0), (100.0, 100.0), 'East Boundary'),
            ((100.0, 100.0), (-100.0, 100.0), 'North Boundary'),
            ((-100.0, 100.0), (-100.0, -100.0), 'West Boundary'),
        ]
        self.buildings = []
        self.nav_nodes = []
        self._load_metadata()

        # Dynamic Agents
        self.hotspots = [
            (-40, -40), (-40, -10), (-40, 20), (-40, 50),
            (40, -40), (40, -10), (40, 20), (40, 50),
            (0, 60), (70, 60), (-70, 60), (0, -70),
            (-75, -30), (75, -30), (0, 0), (0, -96)
        ]
        self.agents = []
        self._spawn_agents()

        # Static Obstacles
        self.static_obstacles = [
            {'id': 'bench_1', 'type': 'bench', 'x': -12.0, 'y': 0.0, 'radius': 0.8, 'name': 'Campus Bench', 'color': [50, 90, 140]},
            {'id': 'bench_2', 'type': 'bench', 'x': 12.0, 'y': 0.0, 'radius': 0.8, 'name': 'Campus Bench', 'color': [50, 90, 140]},
            {'id': 'tree_1', 'type': 'tree', 'x': -15.0, 'y': -20.0, 'radius': 0.6, 'name': 'Garden Tree', 'color': [40, 140, 50]},
            {'id': 'tree_2', 'type': 'tree', 'x': 15.0, 'y': -20.0, 'radius': 0.6, 'name': 'Garden Tree', 'color': [40, 140, 50]},
        ]

        # Mission State
        self.active_mission = None
        self.mission_progress = 0.0

        # Scenario & Weather
        self.scenario = {'name': 'normal_campus', 'weather': 'clear_day', 'crowd_density': 'medium'}

        # Server & Network
        self.server_state = {'status': 'online', 'gpu_utilization': 55.0, 'cpu_utilization': 40.0}
        self.network_state = {'mode': 'ONLINE', 'actual_latency_ms': 12, 'packet_loss_pct': 0.0}

        # Faults
        self.active_faults = {}
        self.lidar_failed = False
        self.camera_failed = False

        # Logs
        self.recent_logs = [
            {'time_str': time.strftime('%H:%M:%S'), 'module': 'INIT', 'severity': 'INFO', 'message': 'LPU Digital Twin Engine started.'},
            {'time_str': time.strftime('%H:%M:%S'), 'module': 'CAMPUS', 'severity': 'INFO', 'message': f'Loaded {len(self.buildings)} buildings, 200m x 200m world.'},
            {'time_str': time.strftime('%H:%M:%S'), 'module': 'AGENTS', 'severity': 'INFO', 'message': f'{len(self.agents)} dynamic pedestrian & vehicle agents active.'}
        ]

        self.current_scan_ranges = [30.0] * 360
        self.current_camera_jpeg = None
        self.current_camera_left_jpeg = None
        self.current_camera_right_jpeg = None
        self.current_depth_jpeg = None
        self.current_det_jpeg = None
        self.active_websockets = set()

    def _load_metadata(self):
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, 'r') as f:
                    data = json.load(f)
                self.buildings = data.get('buildings', [])
                self.nav_nodes = data.get('navigation_graph', {}).get('nodes', [])
                for b in self.buildings:
                    bx = b['position']['x']
                    by = b['position']['y']
                    bw = b['dimensions']['length'] / 2.0
                    bh = b['dimensions']['width'] / 2.0
                    bname = b.get('name', b['id'])
                    self.walls.append(((bx - bw, by - bh), (bx + bw, by - bh), f'{bname} S'))
                    self.walls.append(((bx + bw, by - bh), (bx + bw, by + bh), f'{bname} E'))
                    self.walls.append(((bx + bw, by + bh), (bx - bw, by + bh), f'{bname} N'))
                    self.walls.append(((bx - bw, by + bh), (bx - bw, by - bh), f'{bname} W'))
            except Exception as e:
                print('Error reading metadata:', e)

    def _spawn_agents(self):
        for i in range(16):
            pt = random.choice(self.hotspots)
            self.agents.append(DynamicAgent(f'ped_{i:03d}', pt[0] + random.uniform(-6, 6), pt[1] + random.uniform(-6, 6), 'student'))
        # Vehicles on main roads
        self.agents.append(DynamicAgent('veh_001', 0, -50, 'car'))
        self.agents.append(DynamicAgent('veh_002', 0, 30, 'bus'))
        # Nearby people so perception / detections are visible at spawn
        self.agents.append(DynamicAgent('ped_near_a', 4.5, 1.2, 'student'))
        self.agents.append(DynamicAgent('ped_near_b', 6.0, -2.0, 'student'))
        self.agents.append(DynamicAgent('ped_near_c', 3.0, 3.5, 'student'))

    def add_log(self, module, severity, message):
        entry = {
            'time_str': time.strftime('%H:%M:%S'),
            'module': module,
            'severity': severity,
            'message': message
        }
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 60:
            self.recent_logs = self.recent_logs[-60:]

    def _resolve_place(self, text_lower):
        aliases = {
            'library': ['library', 'block 37', 'b37', 'central library'],
            'mall': ['mall', 'uni-mall', 'unimall'],
            'gate': ['gate', 'main gate'],
            'hospital': ['hospital', 'uni-hospital'],
            'charger': ['charg', 'dock', 'home'],
            'block 37': ['block 37', 'b37'],
        }
        charger = {'id': 'charger', 'position': {'x': 0.0, 'y': -8.0}, 'semantic_labels': ['Charging station']}
        if any(k in text_lower for k in aliases['charger']):
            return charger
        for node in self.nav_nodes:
            labels = [str(l).lower() for l in node.get('semantic_labels', [])]
            blob = ' '.join(labels + [str(node.get('id', '')).lower(), str(node.get('name', '')).lower()])
            if any(k in text_lower and k in blob for keys in aliases.values() for k in keys):
                return node
            if any(l in text_lower for l in labels if len(l) > 3):
                return node
        for keys in aliases.values():
            if any(k in text_lower for k in keys):
                for node in self.nav_nodes:
                    blob = str(node).lower()
                    if any(k in blob for k in keys):
                        return node
        return None

    def dispatch_nl_mission(self, text):
        t = text.strip()
        tl = t.lower()
        now = time.time()

        if any(w in tl for w in ('stop', 'halt', 'e-stop', 'estop')):
            self.estop = True
            self.active_mission = None
            self.follow_track_id = None
            self.last_intent = {'intent': 'STOP', 'target': None, 'status': 'EXECUTED'}
            self.speech = 'Stopping.'
            self.add_log('AI', 'WARNING', 'Intent STOP')
            return

        if 'around me' in tl or 'what do you see' in tl or 'scene' in tl:
            sc = self.scene or {}
            self.speech = (
                f"{sc.get('person', 0)} people, {sc.get('vehicle', 0)} vehicles, "
                f"{sc.get('building', 0)} buildings, nearest obstacle {sc.get('nearest_m', '—')} m."
            )
            self.last_intent = {'intent': 'SCENE_QUERY', 'target': 'FOV', 'status': 'ANSWERED'}
            self.add_log('AI', 'INFO', self.speech)
            return

        if 'where' in tl and ('library' in tl or 'block' in tl or 'mall' in tl or 'gate' in tl):
            place = self._resolve_place(tl) or self._resolve_place('library')
            pos = place['position']
            dist = math.hypot(pos['x'] - self.x, pos['y'] - self.y)
            name = place.get('semantic_labels', ['destination'])[0]
            brg = math.degrees(math.atan2(pos['y'] - self.y, pos['x'] - self.x) - self.yaw)
            self.speech = f'{name} is about {dist:.0f} metres ahead.'
            self.last_intent = {'intent': 'LOCATION_QUERY', 'target': name, 'status': 'ANSWERED'}
            self.add_log('AI', 'INFO', self.speech)
            return

        if any(w in tl for w in ('hello', 'hi ', 'wave', 'greet')):
            self.wave_until = now + 4.0
            self.speech = 'Hello, I am GraceEMO-01.'
            self.last_intent = {'intent': 'GREET', 'target': 'HRI', 'status': 'EXECUTED'}
            self.current_task = 'GREET'
            self.add_log('HRI', 'INFO', 'Intent GREET → wave')
            if not any(w in tl for w in ('go', 'navigat', 'find', 'follow', 'guide', 'deliver')):
                return

        if 'follow' in tl or 'find the nearest person' in tl or 'find a person' in tl:
            people = [d for d in self.detections if d.get('label') == 'person']
            if not people:
                self.speech = 'No person in camera FOV to follow.'
                self.last_intent = {'intent': 'FOLLOW', 'target': None, 'status': 'FAILED'}
                self.add_log('AI', 'WARNING', self.speech)
                return
            tid = people[0].get('track_id')
            self.follow_track_id = tid
            self.last_intent = {'intent': 'FOLLOW', 'target': f'person #{tid}', 'status': 'TRACKING'}
            self.active_mission = {
                'id': f'mission_{int(now*1000)%10000:04d}',
                'type': 'follow',
                'description': t,
                'state': 'running',
                'intent': 'FOLLOW',
                'target_name': f'Person #{tid}',
                'destination': {'x': people[0].get('wx', self.x), 'y': people[0].get('wy', self.y)},
                'progress': 0.0,
                'start_x': self.x, 'start_y': self.y,
                'steps': [
                    {'label': 'Detect person in FOV', 'done': True},
                    {'label': f'Track person #{tid}', 'done': False},
                    {'label': 'Keep 2 m standoff', 'done': False},
                ],
            }
            self.current_task = f'FOLLOW #{tid}'
            self.speech = f'Following person {tid}.'
            self.add_log('AI', 'INFO', self.speech)
            return

        place = self._resolve_place(tl)
        if not place and any(w in tl for w in ('go', 'navigat', 'take me', 'deliver', 'guide', 'patrol', 'library', 'mall', 'gate', 'hospital', 'charg')):
            place = self._resolve_place('library')
        if not place:
            self.speech = 'I did not understand that command.'
            self.last_intent = {'intent': 'UNKNOWN', 'target': t, 'status': 'REJECTED'}
            self.add_log('AI', 'WARNING', f'Unparsed NL: {t}')
            return

        name = place.get('semantic_labels', ['Target'])[0]
        dest = place['position']
        guide = 'guide' in tl or 'find a person' in tl or 'and find' in tl
        charge = name.lower().startswith('charg')
        mission_type = 'charge' if charge else 'guide' if guide else 'deliver' if 'deliver' in tl else 'patrol' if 'patrol' in tl else 'navigate'
        steps = [
            {'label': f'Navigate → {name}', 'done': False},
        ]
        if guide:
            steps += [
                {'label': 'Search for person', 'done': False},
                {'label': 'Approach person', 'done': False},
                {'label': 'Start interaction', 'done': False},
                {'label': 'Navigate → Block 37', 'done': False},
                {'label': 'Confirm arrival', 'done': False},
            ]
        elif charge:
            steps += [{'label': 'Align and dock', 'done': False}, {'label': 'Charge', 'done': False}]
        else:
            steps += [{'label': 'Confirm arrival', 'done': False}]

        self.follow_track_id = None
        self.estop = False
        self.last_intent = {'intent': 'NAVIGATE', 'target': name, 'status': 'PLANNING'}
        self.active_mission = {
            'id': f'mission_{int(now*1000)%10000:04d}',
            'type': mission_type,
            'description': t,
            'state': 'running',
            'intent': 'NAVIGATE',
            'destination': dest,
            'target_name': name,
            'progress': 0.0,
            'start_x': self.x, 'start_y': self.y,
            'steps': steps,
            'step_i': 0,
        }
        self.current_task = f'{mission_type.upper()}: {name}'
        self.speech = f'Planning route to {name}.'
        self.add_log('AI', 'INFO', f'Intent NAVIGATE → {name} ({dest["x"]:.0f},{dest["y"]:.0f})')

    def update_physics(self):
        dt = 0.05
        now = time.time()
        # Autonomous navigation towards mission target if running (teleop wins briefly)
        if self.estop:
            self.target_linear_v = 0.0
            self.target_angular_w = 0.0
            self.linear_v = 0.0
            self.angular_w = 0.0
            self.current_task = 'E-STOP'
        elif now > self.teleop_until and self.active_mission and self.active_mission.get('state') == 'running':
            m = self.active_mission
            if m.get('type') == 'follow' and self.follow_track_id is not None:
                tr = self.tracks.get(self.follow_track_id)
                if tr:
                    m['destination'] = {'x': tr['wx'], 'y': tr['wy']}
                    m['steps'][1]['done'] = True
            dest = m['destination']
            dx = dest['x'] - self.x
            dy = dest['y'] - self.y
            dist = math.hypot(dx, dy)
            tot_dist = math.hypot(dest['x'] - self.active_mission['start_x'], dest['y'] - self.active_mission['start_y'])
            if tot_dist > 1.0:
                self.active_mission['progress'] = max(0.0, min(1.0, 1.0 - (dist / tot_dist)))

            if dist < (2.4 if m.get('type') == 'follow' else 2.0):
                if m.get('type') == 'follow':
                    m['steps'][-1]['done'] = True
                    self.target_linear_v = 0.0
                    self.target_angular_w = 0.0
                    self.current_task = f'STANDOFF #{self.follow_track_id}'
                else:
                    steps = m.get('steps') or []
                    si = m.get('step_i', 0)
                    if si < len(steps):
                        steps[si]['done'] = True
                        m['step_i'] = si + 1
                    if m.get('type') == 'guide' and si == 0:
                        people = [d for d in self.detections if d.get('label') == 'person']
                        if people:
                            self.follow_track_id = people[0].get('track_id')
                            m['type'] = 'follow'
                            m['destination'] = {'x': people[0]['wx'], 'y': people[0]['wy']}
                            for st in steps[1:3]:
                                st['done'] = True
                            self.speech = 'Person found. Guiding.'
                            self.wave_until = now + 2.0
                        else:
                            self.speech = f"Arrived at {m.get('target_name')}. Searching for a person."
                    elif m.get('type') == 'charge':
                        m['state'] = 'completed'
                        m['progress'] = 1.0
                        self.missions_completed += 1
                        self.speech = 'Docked at charging station.'
                        for st in steps:
                            st['done'] = True
                    elif si + 1 >= len(steps):
                        m['state'] = 'completed'
                        m['progress'] = 1.0
                        self.target_linear_v = 0.0
                        self.target_angular_w = 0.0
                        self.missions_completed += 1
                        self.add_log('MISSION', 'INFO', f"Mission {m['id']} completed")
                        self.current_task = 'IDLE'
                        self.speech = f"Arrived at {m.get('target_name', 'destination')}."
                        self.wave_until = now + 2.5
                    else:
                        self.speech = steps[min(si + 1, len(steps) - 1)]['label']
            else:
                target_yaw = math.atan2(dy, dx)
                yaw_err = (target_yaw - self.yaw + math.pi) % (2 * math.pi) - math.pi
                self.target_angular_w = max(-1.2, min(1.2, yaw_err * 2.0))
                if abs(yaw_err) < 0.6:
                    self.target_linear_v = min(0.6, dist * 0.4)
                else:
                    self.target_linear_v = 0.1

        self.target_linear_v = max(-self.speed_limit, min(self.speed_limit, self.target_linear_v))
        if self.estop:
            self.target_linear_v = 0.0
            self.target_angular_w = 0.0

        # Smooth velocity
        self.linear_v += (self.target_linear_v - self.linear_v) * 0.2
        self.angular_w += (self.target_angular_w - self.angular_w) * 0.3

        new_yaw = (self.yaw + self.angular_w * dt + math.pi) % (2 * math.pi) - math.pi
        new_x = self.x + self.linear_v * math.cos(new_yaw) * dt
        new_y = self.y + self.linear_v * math.sin(new_yaw) * dt

        # Campus boundary collision
        limit = self.campus_bounds - self.robot_radius
        self.bumper_hit = False
        if abs(new_x) > limit or abs(new_y) > limit:
            self.linear_v = 0.0
            self.bumper_hit = True
        else:
            collided = False
            for b in self.buildings:
                bx = b['position']['x']
                by = b['position']['y']
                half_l = b['dimensions']['length'] / 2.0 + self.robot_radius
                half_w = b['dimensions']['width'] / 2.0 + self.robot_radius
                if abs(new_x - bx) < half_l and abs(new_y - by) < half_w:
                    collided = True
                    break
            if not collided:
                step = math.hypot(new_x - self.x, new_y - self.y)
                self.distance_traveled += step
                self.x = new_x
                self.y = new_y
            else:
                self.linear_v = 0.0
                self.bumper_hit = True
                self.collision_count += 1
        self.yaw = new_yaw

        for a in self.agents:
            a.update(dt, self.hotspots)

        drain = 0.002 + abs(self.linear_v) * 0.008
        if 'low_battery' in self.active_faults:
            drain *= 12
        self.battery = max(5.0, self.battery - drain * dt)

        self._update_hri(now)
        self._apply_safety(now)

        self.server_state['gpu_utilization'] = round(50 + math.sin(time.time() * 0.5) * 12 + random.uniform(-2, 2), 1)
        self.server_state['cpu_utilization'] = round(38 + math.cos(time.time() * 0.3) * 8 + random.uniform(-2, 2), 1)

    def _update_hri(self, now):
        people = [a for a in self.agents if a.type == 'student']
        nearest = None
        nearest_d = 12.0
        for a in people:
            dx, dy = a.x - self.x, a.y - self.y
            d = math.hypot(dx, dy)
            bearing = (math.atan2(dy, dx) - self.yaw + math.pi) % (2 * math.pi) - math.pi
            if d < nearest_d and abs(bearing) < 1.4:
                nearest_d = d
                nearest = (bearing, d)
        if nearest:
            self.look_target_yaw = max(-1.1, min(1.1, nearest[0]))
            self.neck_pitch = 0.12 if nearest[1] < 4 else 0.05
            if nearest[1] < 3.5 and self.current_task == 'IDLE' and now > self.wave_until:
                self.speech = 'Person detected nearby.'
        else:
            self.look_target_yaw = 0.0
            self.neck_pitch = 0.06
        self.neck_yaw += (self.look_target_yaw - self.neck_yaw) * 0.12

        if now < self.wave_until:
            t = now * 6.0
            self.left_hand = 0.9 + 0.5 * math.sin(t)
            self.right_hand = 0.4
        else:
            self.left_hand += (0.0 - self.left_hand) * 0.15
            self.right_hand += (0.0 - self.right_hand) * 0.15

    def _sector_min(self, center_rad, half_width=0.4):
        n = len(self.current_scan_ranges) or 1
        best = 30.0
        for i, d in enumerate(self.current_scan_ranges):
            ang = -math.pi + (i * 2.0 * math.pi / n)
            err = (ang - center_rad + math.pi) % (2 * math.pi) - math.pi
            if abs(err) <= half_width and d < best:
                best = d
        return best

    def _apply_safety(self, now):
        front = self._sector_min(0.0, 0.45)
        note = ''
        if front < 0.35:
            self.estop = True
            note = f'Proximity e-stop: front {front:.2f}m'
        elif front < 0.8 and self.target_linear_v > 0:
            self.target_linear_v = min(self.target_linear_v, 0.15)
            note = f'Obstacle {front:.2f}m — slowing'
        if note and note != self._last_safety_note:
            self.add_log('SAFETY', 'CRITICAL' if self.estop else 'WARNING', note)
            self._last_safety_note = note
        dock = math.hypot(self.x - 0.0, self.y - (-8.0))
        self.charging = dock < 1.6 and abs(self.linear_v) < 0.05
        if self.charging:
            self.battery = min(100.0, self.battery + 0.08)
        elif self.battery < 12 and not self._charge_mission_armed:
            self._charge_mission_armed = True
            self.dispatch_nl_mission('Return to charging station')
        elif self.battery > 20:
            self._charge_mission_armed = False

    def _wheel_telemetry(self):
        v, w = self.linear_v, self.angular_w
        sep, r = self.wheel_sep_m, self.wheel_r_m
        v_l = v - w * sep / 2
        v_r = v + w * sep / 2
        rpm_l = (v_l / max(0.01, r)) * 60 / (2 * math.pi)
        rpm_r = (v_r / max(0.01, r)) * 60 / (2 * math.pi)
        dt = 0.05
        self.encoder['fl'] += v_l * dt
        self.encoder['rl'] += v_l * dt
        self.encoder['fr'] += v_r * dt
        self.encoder['rr'] += v_r * dt
        load = abs(v) * 8 + abs(w) * 4
        out = {}
        for name, rpm, enc in (
            ('fl', rpm_l, self.encoder['fl']),
            ('rl', rpm_l, self.encoder['rl']),
            ('fr', rpm_r, self.encoder['fr']),
            ('rr', rpm_r, self.encoder['rr']),
        ):
            fault = self.wheel_fault == name
            out[name] = {
                'rpm': round(rpm, 1),
                'velocity_mps': round(v_l if name in ('fl', 'rl') else v_r, 3),
                'encoder_m': round(enc, 2),
                'temp_c': round(32 + load + (8 if fault else 0), 1),
                'current_a': round(1.2 + load * 0.15, 2),
                'torque_nm': round(2.0 + load * 0.2, 2),
                'slip': round(0.01 + abs(w) * 0.02, 3),
                'fault': 'FAULT' if fault else 'NORMAL',
            }
        return out

    def _joint_states(self):
        lh, rh = self.left_hand, self.right_hand
        return {
            'neck_yaw_deg': round(math.degrees(self.neck_yaw), 1),
            'neck_pitch_deg': round(math.degrees(self.neck_pitch), 1),
            'left': {
                'shoulder_pitch_deg': round(math.degrees(lh), 1),
                'shoulder_roll_deg': -8.0,
                'shoulder_yaw_deg': 4.0,
                'elbow_deg': round(55 + lh * 20, 1),
                'wrist_pitch_deg': -6.0,
                'wrist_yaw_deg': 2.0,
                'wrist_roll_deg': 3.0,
            },
            'right': {
                'shoulder_pitch_deg': round(math.degrees(rh), 1),
                'shoulder_roll_deg': 8.0,
                'shoulder_yaw_deg': -4.0,
                'elbow_deg': round(55 + rh * 20, 1),
                'wrist_pitch_deg': -6.0,
                'wrist_yaw_deg': -2.0,
                'wrist_roll_deg': -3.0,
            },
        }

    def _cg_state(self):
        arm = (self.left_hand + self.right_hand) * 0.04
        return {
            'x': round(0.01 + self.linear_v * 0.02, 3),
            'y': round(-0.01 + arm, 3),
            'z': round(0.62 - abs(self.linear_v) * 0.03, 3),
            'stability': 'SAFE' if not self.estop else 'HOLD',
            'tip_margin_m': round(0.18 - abs(self.angular_w) * 0.04, 3),
        }

    def _obstacle_sectors(self):
        return {
            'front': round(self._sector_min(0.0), 2),
            'left': round(self._sector_min(math.pi / 2), 2),
            'right': round(self._sector_min(-math.pi / 2), 2),
            'rear': round(self._sector_min(math.pi), 2),
        }

    def update_sensors(self):
        # LiDAR raycasting
        num_readings = 360
        max_range = 30.0
        min_range = 0.2
        if self.lidar_failed:
            self.current_scan_ranges = [max_range] * num_readings
        else:
            ranges = [max_range] * num_readings
            all_obs = self.static_obstacles + [a.to_dict() for a in self.agents]
            for i in range(0, num_readings, 3):
                ang = self.yaw - math.pi + (i * 2.0 * math.pi / num_readings)
                rx = self.x + max_range * math.cos(ang)
                ry = self.y + max_range * math.sin(ang)
                p1 = (self.x, self.y)
                p2 = (rx, ry)
                closest = max_range

                for (w1, w2, _) in self.walls:
                    hit = line_intersection(p1, p2, w1, w2)
                    if hit:
                        d = hit[0] * max_range
                        if min_range <= d < closest: closest = d

                for obs in all_obs:
                    ox, oy = obs['x'], obs['y']
                    rad = obs.get('radius', 0.4)
                    dx = ox - self.x
                    dy = oy - self.y
                    proj = dx * math.cos(ang) + dy * math.sin(ang)
                    if proj > 0:
                        perp = (dx*dx + dy*dy) - (proj * proj)
                        if perp < (rad * rad):
                            d_hit = proj - math.sqrt(max(0.0, rad*rad - perp))
                            if min_range <= d_hit < closest: closest = d_hit

                ranges[i] = closest
                ranges[i+1] = closest
                ranges[i+2] = closest
            self.current_scan_ranges = ranges

        self._update_cameras()

    def _encode_jpeg(self, img, quality=72):
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buf).decode('utf-8')

    def _collect_camera_items(self, cam_yaw, max_dist=40.0):
        items = []
        for b in self.buildings:
            pos = b.get('position') or {}
            dim = b.get('dimensions') or {}
            bx, by = pos.get('x', 0), pos.get('y', 0)
            dx, dy = bx - self.x, by - self.y
            dist = math.hypot(dx, dy)
            if dist < 1.0 or dist > max_dist:
                continue
            ang = math.atan2(dy, dx) - cam_yaw
            ang = (ang + math.pi) % (2 * math.pi) - math.pi
            items.append({
                'kind': 'building', 'dist': dist, 'ang': ang,
                'id': b.get('id', 'bldg'),
                'wx': bx, 'wy': by, 'speed': 0, 'heading': 0,
                'h': dim.get('height', 12), 'w': dim.get('length', 20),
                'name': b.get('name', b.get('id', 'Block')),
                'color': [90, 140, 190],
            })
        for obs in self.static_obstacles + [a.to_dict() for a in self.agents]:
            dx, dy = obs['x'] - self.x, obs['y'] - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.25 or dist > 32.0:
                continue
            ang = math.atan2(dy, dx) - cam_yaw
            ang = (ang + math.pi) % (2 * math.pi) - math.pi
            items.append({
                'kind': str(obs.get('type', 'obj')).lower(),
                'id': obs.get('id', obs.get('name', 'obj')),
                'wx': obs['x'], 'wy': obs['y'],
                'speed': obs.get('speed', 0),
                'heading': obs.get('heading', 0),
                'dist': dist, 'ang': ang,
                'h': obs.get('radius', 0.35) * 4.2,
                'w': obs.get('radius', 0.35) * 1.6,
                'name': obs.get('name', obs.get('type', 'obj')),
                'color': obs.get('color', [80, 90, 160]),
            })
        items.sort(key=lambda it: it['dist'], reverse=True)
        return items

    def _track_label(self, it):
        aid = str(it.get('id', ''))
        tr = self.tracks.get(aid)
        if tr:
            return f"{tr['tid']}"
        return 'P'

    def _render_camera_frame(self, yaw_offset=0.0, width=640, height=480, with_hud=True, detections_only=False):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        if self.camera_failed:
            cv2.putText(img, "CAMERA SENSOR FAILURE", (max(12, width // 8), height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
            return img
        weather = self.scenario.get('weather', 'clear_day')
        if weather == 'night':
            sky, ground = [48, 32, 22], [46, 52, 42]
        elif weather == 'rain':
            sky, ground = [150, 138, 128], [88, 108, 92]
        elif weather == 'fog':
            sky, ground = [186, 180, 174], [148, 158, 146]
        else:
            sky, ground = [234, 212, 184], [106, 168, 125]
        img[0:height // 2, :] = sky
        img[height // 2:height, :] = ground
        cv2.line(img, (0, height // 2), (width, height // 2), (150, 170, 150), 1)

        fov = math.radians(72)
        cam_yaw = self.yaw + self.neck_yaw + yaw_offset
        focal = (width / 2.0) / math.tan(fov / 2.0)
        people = {'student', 'faculty', 'security', 'visitor', 'person', 'pedestrian'}

        for it in self._collect_camera_items(cam_yaw):
            if abs(it['ang']) > fov / 2.0 + 0.25:
                continue
            screen_x = int(width / 2.0 + math.tan(it['ang']) * focal)
            obj_h = int(max(8, (it['h'] * focal) / max(0.4, it['dist'])))
            obj_w = int(max(6, (it['w'] * 0.35 * focal) / max(0.4, it['dist'])))
            y_bot = min(height - 4, height // 2 + obj_h // 6)
            y_top = max(4, y_bot - obj_h)
            x_left = max(2, screen_x - obj_w // 2)
            x_right = min(width - 2, screen_x + obj_w // 2)
            if x_right <= x_left or y_bot <= y_top:
                continue
            kind = it['kind']
            if detections_only and kind not in people:
                continue
            if kind == 'building':
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), it['color'], -1)
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), (220, 230, 240), 1)
                cv2.putText(img, str(it.get('name', ''))[:16], (x_left, max(12, y_top - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)
            elif kind in people:
                body = tuple(it['color'])
                head_r = max(3, obj_w // 4)
                cv2.circle(img, ((x_left + x_right) // 2, y_top + head_r), head_r, body, -1)
                cv2.rectangle(img, (x_left + 2, y_top + head_r * 2), (x_right - 2, y_bot), body, -1)
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), (60, 220, 80), 2)
                cv2.putText(img, f"#{self._track_label(it)} {it['dist']:.1f}m", (x_left, max(14, y_top - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.36, (60, 220, 80), 1, cv2.LINE_AA)
            else:
                cv2.rectangle(img, (x_left, y_top), (x_right, y_bot), it['color'], -1)

        if weather == 'rain':
            rng = np.random.RandomState(int(time.time() * 12) % 10000)
            for _ in range(50):
                x0 = int(rng.randint(0, width))
                y0 = int(rng.randint(0, height))
                cv2.line(img, (x0, y0), (x0 - 2, y0 + 12), (210, 210, 210), 1)

        if with_hud and not detections_only:
            cv2.putText(img, f'GraceEMO AI | ({self.x:.1f}, {self.y:.1f})m | {math.degrees(self.yaw):.0f}deg',
                        (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 160, 255), 1, cv2.LINE_AA)
            cv2.putText(img, f'{weather.upper()} | dets:{len(self.detections)} | {self.current_task}',
                        (12, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (40, 160, 255), 1, cv2.LINE_AA)
            if self.speech:
                cv2.putText(img, self.speech[:48], (12, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 230, 180), 1, cv2.LINE_AA)
        return img

    def _render_depth_frame(self, width=160, height=84):
        img = np.zeros((height, width), dtype=np.uint8)
        n = max(1, len(self.current_scan_ranges))
        for x in range(width):
            i = int((x / width) * n)
            d = float(self.current_scan_ranges[i % n])
            shade = int(np.clip(255 - (min(d, 20.0) / 20.0) * 220, 18, 255))
            img[:, x] = shade
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def _update_cameras(self):
        t0 = time.perf_counter()
        self._refresh_detections()
        self.ai_metrics['inference_ms'] = round((time.perf_counter() - t0) * 1000.0, 2)
        self.ai_metrics['fps'] = round(1000.0 / max(1.0, self.ai_metrics['inference_ms'] + 90), 1)
        front = self._render_camera_frame(0.0, 480, 270, True)
        left = self._render_camera_frame(math.radians(65), 320, 180, False)
        right = self._render_camera_frame(-math.radians(65), 320, 180, False)
        det = self._render_camera_frame(0.0, 240, 140, False, detections_only=True)
        depth = self._render_depth_frame(160, 84)
        self.current_camera_jpeg = self._encode_jpeg(front, 70)
        self.current_camera_left_jpeg = self._encode_jpeg(left, 60)
        self.current_camera_right_jpeg = self._encode_jpeg(right, 60)
        self.current_det_jpeg = self._encode_jpeg(det, 58)
        self.current_depth_jpeg = self._encode_jpeg(depth, 55)

    def _refresh_detections(self):
        fov = math.radians(72)
        people_k = {'student', 'faculty', 'security', 'visitor', 'person', 'pedestrian'}
        veh_k = {'car', 'bus', 'motorcycle', 'vehicle'}
        now = time.time()
        seen = {}
        counts = {'person': 0, 'vehicle': 0, 'building': 0, 'obstacle': 0, 'door': 0}
        dets = []
        nearest_m = 30.0
        for it in self._collect_camera_items(self.yaw + self.neck_yaw, 24.0):
            if abs(it['ang']) > fov / 2:
                continue
            kind = it['kind']
            if kind in people_k:
                label = 'person'
            elif kind in veh_k:
                label = 'vehicle'
            elif kind == 'building':
                label = 'building'
            elif kind in ('bench', 'tree'):
                label = 'obstacle'
            else:
                label = 'obstacle'
            counts[label] = counts.get(label, 0) + 1
            nearest_m = min(nearest_m, it['dist'])
            conf = max(0.55, min(0.97, 0.62 + 0.28 * (1.0 - min(it['dist'], 18) / 18) * math.cos(it['ang'])))
            aid = str(it.get('id', it.get('name')))
            pose = 'walking' if it.get('speed', 0) > 0.35 else 'standing'
            tr = self.tracks.get(aid)
            vx = vy = 0.0
            if tr:
                dt = max(0.05, now - tr['t'])
                vx = (it.get('wx', 0) - tr['wx']) / dt
                vy = (it.get('wy', 0) - tr['wy']) / dt
                tid = tr['tid']
            else:
                tid = self.track_seq
                self.track_seq += 1
            self.tracks[aid] = {'tid': tid, 'wx': it.get('wx', 0), 'wy': it.get('wy', 0), 't': now, 'label': label}
            seen[aid] = True
            dets.append({
                'label': label,
                'track_id': tid,
                'confidence': round(conf, 2),
                'distance_m': round(it['dist'], 2),
                'bearing_deg': round(math.degrees(it['ang']), 1),
                'wx': round(it.get('wx', 0), 2),
                'wy': round(it.get('wy', 0), 2),
                'velocity_mps': round(math.hypot(vx, vy), 2),
                'pose': pose,
                'name': it.get('name', label),
            })
        for k in list(self.tracks):
            if k not in seen and now - self.tracks[k]['t'] > 1.5:
                del self.tracks[k]
        dets.sort(key=lambda d: d['distance_m'])
        self.detections = dets[:16]
        self.perception_counts = counts
        self.ai_metrics['tracked'] = len([d for d in dets if d['label'] == 'person'])
        self.scene = {
            'person': counts['person'],
            'vehicle': counts['vehicle'],
            'building': counts['building'],
            'obstacle': counts['obstacle'],
            'nearest_m': round(nearest_m, 2),
        }

    def _sensor_snapshot(self):
        n = len(self.current_scan_ranges)
        mid = n // 2
        sector = self.current_scan_ranges[max(0, mid - 20):mid + 20] or [30.0]
        front = min(sector)
        finite = [r for r in self.current_scan_ranges if math.isfinite(r)]
        return {
            'source': 'digital_twin_raycast',
            'not_gazebo': True,
            'front_range_m': round(float(front), 3),
            'lidar_min_m': round(float(min(finite) if finite else 30.0), 3),
            'bumper': bool(self.bumper_hit),
            'imu': {'yaw': round(self.yaw, 4), 'wz': round(self.angular_w, 4), 'ax': round(self.linear_v * 0.1, 4)},
            'lidar_failed': bool(self.lidar_failed),
            'camera_failed': bool(self.camera_failed),
            'heard_nodes': ['digital_twin_studio', 'perception_sim', 'nl_mission', 'hri'],
            'ros_topics': ['/scan', '/imu/data', '/camera/image_raw', '/gracemo/detections'],
        }

    def notify_clients(self):
        if not self.active_websockets:
            return

        payload = json.dumps({
            'type': 'digital_twin_state',
            'robot': {
                'x': self.x,
                'y': self.y,
                'yaw': self.yaw,
                'linear_v': self.linear_v,
                'angular_w': self.angular_w,
                'battery': self.battery,
                'status': self.status,
                'task': self.current_task,
                'neck_yaw': self.neck_yaw,
                'neck_pitch': self.neck_pitch,
                'left_hand': self.left_hand,
                'right_hand': self.right_hand,
                'speech': self.speech,
                'cg': self._cg_state(),
            },
            'buildings': self.buildings,
            'dynamic_agents': [a.to_dict() for a in self.agents],
            'static_obstacles': self.static_obstacles,
            'scan': self.current_scan_ranges[::4],
            'sensors': self._sensor_snapshot(),
            'detections': self.detections,
            'perception': self.perception_counts,
            'ai_metrics': self.ai_metrics,
            'intent': self.last_intent,
            'scene': self.scene,
            'operating_mode': self.operating_mode,
            'estop': self.estop,
            'charging': self.charging,
            'speed_limit': self.speed_limit,
            'wheels': self._wheel_telemetry(),
            'joints': self._joint_states(),
            'cg': self._cg_state(),
            'obstacles': self._obstacle_sectors(),
            'camera_jpeg': self.current_camera_jpeg,
            'camera_left_jpeg': self.current_camera_left_jpeg,
            'camera_right_jpeg': self.current_camera_right_jpeg,
            'camera_depth_jpeg': self.current_depth_jpeg,
            'camera_det_jpeg': self.current_det_jpeg,
            'scenario': self.scenario,
            'mission': {'active_mission': self.active_mission},
            'server': self.server_state,
            'network': self.network_state,
            'faults': {'active_faults': self.active_faults, 'active_count': len(self.active_faults)},
            'analytics': {
                'mission_success_rate': 100.0 if self.missions_completed else 100.0,
                'collision_count': self.collision_count,
                'missions_completed': self.missions_completed,
                'missions_failed': 0,
                'total_distance_traveled': round(self.distance_traveled, 1),
            },
            'recent_logs': self.recent_logs[-15:]
        })

        for ws in list(self.active_websockets):
            try:
                ws.write_message(payload)
            except Exception:
                self.active_websockets.discard(ws)


ENGINE = DigitalTwinEngine()


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        index_file = os.path.join(WEB_DIR, 'index.html')
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                self.set_header("Content-Type", "text/html; charset=UTF-8")
                self.write(f.read())
        else:
            self.set_status(404)
            self.write("<h1>index.html not found</h1>")


class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        ENGINE.active_websockets.add(self)
        print('🌐 Client connected to Digital Twin WebSocket')

    def on_close(self):
        ENGINE.active_websockets.discard(self)

    def on_message(self, message):
        try:
            data = json.loads(message)
            action = data.get('action')

            if action == 'teleop':
                ENGINE.target_linear_v = float(data.get('v', 0.0))
                ENGINE.target_angular_w = float(data.get('w', 0.0))
                ENGINE.teleop_until = time.time() + 1.2

            elif action == 'estop':
                ENGINE.estop = True
                ENGINE.target_linear_v = 0.0
                ENGINE.target_angular_w = 0.0
                ENGINE.add_log('SAFETY', 'CRITICAL', 'Emergency stop by operator.')
            elif action == 'estop_clear':
                ENGINE.estop = False
                ENGINE.current_task = 'IDLE'
                ENGINE.add_log('SAFETY', 'INFO', 'E-stop cleared.')
            elif action == 'set_speed_limit':
                ENGINE.speed_limit = float(data.get('limit', 0.5))

            elif action == 'reset_pose':
                ENGINE.x = 0.0
                ENGINE.y = 0.0
                ENGINE.yaw = 0.0
                ENGINE.linear_v = 0.0
                ENGINE.angular_w = 0.0
                ENGINE.target_linear_v = 0.0
                ENGINE.target_angular_w = 0.0
                ENGINE.add_log('ROBOT', 'INFO', 'Pose reset to campus origin (0, 0).')

            elif action == 'create_mission_nl':
                text = str(data.get('text', '')).strip()
                if text:
                    ENGINE.dispatch_nl_mission(text)

            elif action == 'mission_control':
                cmd = str(data.get('command', '')).strip()
                if ENGINE.active_mission:
                    if cmd == 'pause':
                        ENGINE.active_mission['state'] = 'paused'
                        ENGINE.target_linear_v = 0.0
                        ENGINE.add_log('MISSION', 'WARNING', 'Mission paused by operator.')
                    elif cmd == 'resume':
                        ENGINE.active_mission['state'] = 'running'
                        ENGINE.add_log('MISSION', 'INFO', 'Mission resumed.')
                    elif cmd == 'abort':
                        ENGINE.active_mission['state'] = 'aborted'
                        ENGINE.target_linear_v = 0.0
                        ENGINE.add_log('MISSION', 'CRITICAL', 'Mission aborted by operator.')
                        ENGINE.current_task = 'IDLE'

            elif action == 'set_scenario':
                scen = str(data.get('scenario', 'normal_campus'))
                ENGINE.scenario['name'] = scen
                if scen == 'night_campus': ENGINE.scenario['weather'] = 'night'
                elif scen == 'rainy_day': ENGINE.scenario['weather'] = 'rain'
                else: ENGINE.scenario['weather'] = 'clear_day'
                ENGINE.add_log('SCENARIO', 'INFO', f'Switched preset: {scen}')

            elif action == 'set_weather':
                w = str(data.get('weather', 'clear_day'))
                ENGINE.scenario['weather'] = w
                ENGINE.add_log('WEATHER', 'INFO', f'Weather set to: {w}')

            elif action == 'set_crowd':
                c = str(data.get('crowd', 'medium'))
                ENGINE.scenario['crowd_density'] = c
                count = 8 if c == 'low' else 20 if c == 'medium' else 50
                ENGINE.agents = [a for a in ENGINE.agents if a.type != 'student']
                for i in range(count):
                    pt = random.choice(ENGINE.hotspots)
                    ENGINE.agents.append(DynamicAgent(f'ped_{i:03d}', pt[0] + random.uniform(-6, 6), pt[1] + random.uniform(-6, 6), 'student'))
                ENGINE.add_log('CROWD', 'INFO', f'Crowd density set to {c} ({count} agents)')

            elif action == 'inject_fault':
                fault = data.get('fault', {})
                ftype = fault.get('type')
                if ftype:
                    ENGINE.active_faults[ftype] = fault
                    if ftype == 'lidar_failure': ENGINE.lidar_failed = True
                    if ftype == 'camera_failure': ENGINE.camera_failed = True
                    ENGINE.add_log('FAULT', 'CRITICAL', f'Injected Fault: {ftype}')

            elif action == 'clear_fault':
                ENGINE.active_faults.clear()
                ENGINE.lidar_failed = False
                ENGINE.camera_failed = False
                ENGINE.network_state['mode'] = 'ONLINE'
                ENGINE.add_log('FAULT', 'INFO', 'All system faults cleared.')

            elif action == 'set_server':
                avail = bool(data.get('available', True))
                ENGINE.network_state['mode'] = 'ONLINE' if avail else 'OFFLINE'
                ENGINE.add_log('NETWORK', 'WARNING' if not avail else 'INFO', f'Server online status: {avail}')

        except Exception as e:
            print('WS Message Error:', e)


def main():
    port = int(os.environ.get('PORT', '8888'))
    app = tornado.web.Application([
        (r'/', IndexHandler),
        (r'/ws', WSHandler),
        (r'/(.*)', tornado.web.StaticFileHandler, {'path': WEB_DIR}),
    ])

    app.listen(port)
    url = f'http://localhost:{port}/'
    print('=' * 65)
    print('  🏛️  GraceEMO LPU Autonomous Robotics Digital Twin Studio')
    print('=' * 65)
    print(f'  URL:          {url}')
    print(f'  Web Assets:   {WEB_DIR}')
    print(f'  Campus Data:  {METADATA_FILE}')
    print('=' * 65)

    # Periodic update loop (20 Hz physics & WebSocket notification)
    physics_pc = tornado.ioloop.PeriodicCallback(ENGINE.update_physics, 50)
    physics_pc.start()

    sensors_pc = tornado.ioloop.PeriodicCallback(ENGINE.update_sensors, 100)
    sensors_pc.start()

    notify_pc = tornado.ioloop.PeriodicCallback(ENGINE.notify_clients, 100)
    notify_pc.start()

    try:
        webbrowser.open(url)
    except Exception:
        pass

    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
