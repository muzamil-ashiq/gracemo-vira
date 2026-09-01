#!/usr/bin/env python3
"""
GraceEMO — Dynamic Pedestrian Agent Node
Spawns and manages dynamic pedestrian agents with realistic campus behavior:
walking paths, random destinations, speed variation, group behavior, crossing behavior.
"""

import json
import math
import random
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Point


class PedestrianAgent:
    """Individual pedestrian with movement behavior."""

    STATES = ['walking', 'waiting', 'talking', 'crossing', 'entering_building', 'idle']

    def __init__(self, agent_id: str, x: float, y: float, agent_type: str = 'student'):
        self.id = agent_id
        self.x = x
        self.y = y
        self.type = agent_type  # student, faculty, security, visitor
        self.state = 'walking'
        self.speed = random.uniform(0.8, 1.5)  # m/s
        self.heading = random.uniform(-math.pi, math.pi)
        self.radius = 0.3
        self.personal_space = 0.8
        self.destination = None
        self.waypoints = []
        self.wait_timer = 0.0
        self.color = self._get_color()

    def _get_color(self):
        colors = {
            'student': [random.randint(50, 220), random.randint(50, 180), random.randint(50, 220)],
            'faculty': [40, 40, 50],
            'security': [50, 80, 50],
            'visitor': [200, 150, 50],
        }
        return colors.get(self.type, [150, 150, 150])

    def set_destination(self, x: float, y: float):
        self.destination = (x, y)
        dx = x - self.x
        dy = y - self.y
        self.heading = math.atan2(dy, dx)
        self.state = 'walking'

    def update(self, dt: float, obstacles: list, other_agents: list):
        """Update pedestrian position and behavior."""
        if self.state == 'waiting':
            self.wait_timer -= dt
            if self.wait_timer <= 0:
                self.state = 'walking'
                # Pick new random destination
                self.set_destination(
                    self.x + random.uniform(-30, 30),
                    self.y + random.uniform(-30, 30)
                )
            return

        if self.state == 'idle':
            # Randomly start walking
            if random.random() < 0.01:
                self.set_destination(
                    self.x + random.uniform(-20, 20),
                    self.y + random.uniform(-20, 20)
                )
            return

        if self.state != 'walking':
            return

        if self.destination is None:
            self.state = 'idle'
            return

        # Move toward destination
        dx = self.destination[0] - self.x
        dy = self.destination[1] - self.y
        dist = math.hypot(dx, dy)

        if dist < 1.0:
            # Arrived — wait or pick new destination
            self.state = 'waiting'
            self.wait_timer = random.uniform(2.0, 10.0)
            return

        # Avoid other agents (social force model simplified)
        avoid_x, avoid_y = 0.0, 0.0
        for other in other_agents:
            if other.id == self.id:
                continue
            ox = self.x - other.x
            oy = self.y - other.y
            od = math.hypot(ox, oy)
            if 0.1 < od < self.personal_space:
                force = (self.personal_space - od) / self.personal_space
                avoid_x += (ox / od) * force * 2.0
                avoid_y += (oy / od) * force * 2.0

        # Compute desired direction
        desired_x = (dx / dist) + avoid_x * 0.3
        desired_y = (dy / dist) + avoid_y * 0.3
        d_mag = math.hypot(desired_x, desired_y)
        if d_mag > 0.01:
            desired_x /= d_mag
            desired_y /= d_mag

        # Update position
        self.x += desired_x * self.speed * dt
        self.y += desired_y * self.speed * dt
        self.heading = math.atan2(desired_y, desired_x)

        # Keep within campus bounds
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
            'state': self.state,
            'radius': self.radius,
            'color': self.color,
            'name': f'{self.type.capitalize()} {self.id[-3:]}'
        }


class VehicleAgent:
    """Simple vehicle agent following road paths."""

    def __init__(self, agent_id: str, x: float, y: float, vehicle_type: str = 'car'):
        self.id = agent_id
        self.x = x
        self.y = y
        self.type = vehicle_type  # car, bus, motorcycle, emergency
        self.speed = {'car': 5.0, 'bus': 3.0, 'motorcycle': 6.0, 'emergency': 8.0}.get(vehicle_type, 5.0)
        self.heading = 0.0
        self.radius = {'car': 1.5, 'bus': 3.0, 'motorcycle': 0.8, 'emergency': 2.0}.get(vehicle_type, 1.5)
        self.destination = None
        self.color = {'car': [80, 80, 180], 'bus': [180, 150, 50], 'motorcycle': [60, 60, 60], 'emergency': [50, 50, 220]}.get(vehicle_type, [100, 100, 100])

    def set_destination(self, x: float, y: float):
        self.destination = (x, y)
        dx = x - self.x
        dy = y - self.y
        self.heading = math.atan2(dy, dx)

    def update(self, dt: float):
        if self.destination is None:
            return

        dx = self.destination[0] - self.x
        dy = self.destination[1] - self.y
        dist = math.hypot(dx, dy)

        if dist < 3.0:
            # Pick new road destination
            self.set_destination(
                random.uniform(-90, 90),
                self.y + random.choice([-1, 1]) * random.uniform(20, 80)
            )
            return

        self.x += (dx / dist) * self.speed * dt
        self.y += (dy / dist) * self.speed * dt
        self.heading = math.atan2(dy, dx)

        # Keep on roads roughly
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


class PedestrianManagerNode(Node):
    """Manages all dynamic pedestrian and vehicle agents in the simulation."""

    DENSITY_COUNTS = {'low': 8, 'medium': 20, 'high': 50}
    TRAFFIC_COUNTS = {'low': 2, 'medium': 5, 'high': 12}

    # Key campus locations for pedestrian spawning/destinations
    CAMPUS_HOTSPOTS = [
        (-40, -40), (-40, -10), (-40, 20), (-40, 50),  # Blocks 34-37
        (40, -40), (40, -10), (40, 20), (40, 50),       # Blocks 38-41
        (0, 60), (70, 60), (-70, 60),                    # Mall, Polis, Hospital
        (0, -70), (-50, -75), (50, -75),                  # Sports
        (-75, -30), (75, -30),                            # Hostels
        (0, 0), (0, 20),                                  # Intersections
    ]

    def __init__(self):
        super().__init__('pedestrian_manager_node')
        self.get_logger().info('👥 Initializing Pedestrian Manager...')

        self.declare_parameter('initial_crowd_density', 'medium')
        self.declare_parameter('initial_traffic_density', 'low')
        self.declare_parameter('update_rate_hz', 10.0)
        self.declare_parameter('personal_space', 0.8)
        self.declare_parameter('min_obstacle_distance', 0.5)
        self.declare_parameter('max_speed_near_pedestrians', 0.3)

        self.crowd_density = self.get_parameter('initial_crowd_density').value
        self.traffic_density = self.get_parameter('initial_traffic_density').value
        update_rate = self.get_parameter('update_rate_hz').value

        self.pedestrians: list[PedestrianAgent] = []
        self.vehicles: list[VehicleAgent] = []

        # Spawn initial agents
        self._spawn_pedestrians(self.DENSITY_COUNTS.get(self.crowd_density, 20))
        self._spawn_vehicles(self.TRAFFIC_COUNTS.get(self.traffic_density, 2))

        # Publishers
        self.agents_pub = self.create_publisher(String, '/gracemo/dynamic_agents', 10)

        # Subscribers
        self.create_subscription(String, '/gracemo/crowd_density', self.on_crowd_density, 10)
        self.create_subscription(String, '/gracemo/spawn_pedestrian', self.on_spawn_pedestrian, 10)

        # Update timer
        self.create_timer(1.0 / update_rate, self.update_agents)

        self.get_logger().info(f'✅ Pedestrian Manager ready — {len(self.pedestrians)} pedestrians, {len(self.vehicles)} vehicles')

    def _spawn_pedestrians(self, count: int):
        """Spawn pedestrian agents at campus hotspots."""
        types = ['student', 'student', 'student', 'faculty', 'visitor']
        for i in range(count):
            hotspot = random.choice(self.CAMPUS_HOTSPOTS)
            x = hotspot[0] + random.uniform(-10, 10)
            y = hotspot[1] + random.uniform(-10, 10)
            agent = PedestrianAgent(
                agent_id=f'ped_{i:03d}',
                x=x, y=y,
                agent_type=random.choice(types)
            )
            # Set initial destination
            dest = random.choice(self.CAMPUS_HOTSPOTS)
            agent.set_destination(dest[0] + random.uniform(-5, 5), dest[1] + random.uniform(-5, 5))
            self.pedestrians.append(agent)

    def _spawn_vehicles(self, count: int):
        """Spawn vehicles on roads."""
        types = ['car', 'car', 'bus', 'motorcycle']
        for i in range(count):
            # Spawn on main road or cross road
            if random.random() < 0.5:
                x = random.uniform(-3, 3)
                y = random.uniform(-90, 90)
            else:
                x = random.uniform(-90, 90)
                y = random.uniform(17, 23)
            vehicle = VehicleAgent(
                agent_id=f'veh_{i:03d}',
                x=x, y=y,
                vehicle_type=random.choice(types)
            )
            vehicle.set_destination(x + random.uniform(-50, 50), y + random.uniform(-50, 50))
            self.vehicles.append(vehicle)

    def on_crowd_density(self, msg: String):
        """Adjust crowd density."""
        density = msg.data.strip().lower()
        if density in self.DENSITY_COUNTS:
            target = self.DENSITY_COUNTS[density]
            current = len(self.pedestrians)
            if target > current:
                self._spawn_pedestrians(target - current)
            elif target < current:
                self.pedestrians = self.pedestrians[:target]
            self.crowd_density = density
            self.get_logger().info(f'👥 Crowd density → {density} ({len(self.pedestrians)} pedestrians)')

    def on_spawn_pedestrian(self, msg: String):
        """Spawn a single pedestrian at specified location."""
        try:
            data = json.loads(msg.data)
            agent = PedestrianAgent(
                agent_id=f'ped_spawn_{int(time.time()*1000)}',
                x=float(data.get('x', 0)),
                y=float(data.get('y', 0)),
                agent_type=data.get('type', 'visitor')
            )
            dest = random.choice(self.CAMPUS_HOTSPOTS)
            agent.set_destination(dest[0], dest[1])
            self.pedestrians.append(agent)
        except Exception as e:
            self.get_logger().error(f'Failed to spawn pedestrian: {e}')

    def update_agents(self):
        """Update all agent positions and publish state."""
        dt = 0.1  # 10 Hz

        # Update pedestrians
        for ped in self.pedestrians:
            ped.update(dt, [], self.pedestrians)
            # If pedestrian wandered too far or got stuck, reset
            if abs(ped.x) > 98 or abs(ped.y) > 98:
                hotspot = random.choice(self.CAMPUS_HOTSPOTS)
                ped.x = hotspot[0] + random.uniform(-5, 5)
                ped.y = hotspot[1] + random.uniform(-5, 5)
                dest = random.choice(self.CAMPUS_HOTSPOTS)
                ped.set_destination(dest[0], dest[1])

        # Update vehicles
        for veh in self.vehicles:
            veh.update(dt)

        # Publish combined agent state
        payload = {
            'pedestrians': [p.to_dict() for p in self.pedestrians],
            'vehicles': [v.to_dict() for v in self.vehicles],
            'timestamp': time.time()
        }
        msg = String()
        msg.data = json.dumps(payload)
        self.agents_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PedestrianManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
