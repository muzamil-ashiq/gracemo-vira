#!/usr/bin/env python3
"""
GraceEMO — Persistent memory + named-place recall.
"""

import os
import json
import sqlite3
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from gracemo_interfaces.msg import Detection, VoiceCommand
    from gracemo_interfaces.srv import Remember, Recall
    HAVE_INTERFACES = True
except ImportError:
    HAVE_INTERFACES = False

# Campus places used by navigate_to (x, y, display name)
DEFAULT_PLACES = {
    'door': '2.5,-2.5,Welcome Reception Desk',
    'reception': '2.5,-2.5,Welcome Reception Desk',
    'lab': '2.5,2.0,Robotics Research Lab',
    'robotics': '2.5,2.0,Robotics Research Lab',
    'commons': '-2.5,-2.5,Campus Commons',
    'kitchen': '-2.5,-2.5,Campus Commons',
    'ai': '-2.5,2.0,AI Compute Center',
    'library': '45.0,20.0,Central Library (B37)',
    'mall': '30.0,-40.0,Uni-Mall Shopping Center',
    'gate': '0.0,-95.0,Main Campus Gate 1',
}


class MemoryNode(Node):
    def __init__(self):
        super().__init__('memory_node')
        self.declare_parameter('db_path', '/tmp/graceemo_memory.db')
        self.db_path = self.get_parameter('db_path').value
        self.init_database()
        self.seed_places()

        self.places_pub = self.create_publisher(String, '/gracemo/known_places', 10)
        self.places_timer = self.create_timer(3.0, self.publish_known_places)

        if HAVE_INTERFACES:
            self.remember_srv = self.create_service(
                Remember, '/gracemo/remember', self.handle_remember)
            self.recall_srv = self.create_service(
                Recall, '/gracemo/recall', self.handle_recall)
            self.create_subscription(
                Detection, '/gracemo/detections', self.on_detection, 10)
            self.create_subscription(
                VoiceCommand, '/gracemo/voice_command', self.on_voice, 10)

        # Publish initial known places
        self.publish_known_places()

        self.get_logger().info(f'Memory Engine Active. Database: {self.db_path}')

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        conn = self._connect()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                key TEXT UNIQUE,
                value TEXT,
                importance REAL,
                timestamp REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                description TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()

    def seed_places(self):
        conn = self._connect()
        c = conn.cursor()
        now = time.time()
        for key, value in DEFAULT_PLACES.items():
            c.execute(
                """INSERT OR IGNORE INTO facts
                   (category, key, value, importance, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                ('place', key, value, 1.0, now),
            )
        conn.commit()
        conn.close()

    def get_all_places_dict(self):
        places = {}
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute("SELECT key, value FROM facts WHERE category='place'")
            rows = c.fetchall()
            conn.close()
            for k, val_str in rows:
                parts = [p.strip() for p in val_str.split(',')]
                if len(parts) >= 2:
                    try:
                        x = float(parts[0])
                        y = float(parts[1])
                        name = parts[2] if len(parts) > 2 else k
                        places[k.lower()] = [x, y, name]
                    except ValueError:
                        pass
        except Exception as e:
            self.get_logger().warn(f'Error fetching places: {e}')
        return places

    def publish_known_places(self):
        places = self.get_all_places_dict()
        msg = String()
        msg.data = json.dumps(places)
        self.places_pub.publish(msg)

    def handle_remember(self, request, response):
        try:
            conn = self._connect()
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO facts
                   (category, key, value, importance, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (request.category, request.key, request.value,
                 request.importance, time.time()),
            )
            conn.commit()
            conn.close()
            response.success = True
            response.message = f'Saved [{request.key}] in [{request.category}]'
            if request.category == 'place':
                self.publish_known_places()
        except Exception as e:
            response.success = False
            response.message = str(e)
        return response

    def handle_recall(self, request, response):
        try:
            conn = self._connect()
            c = conn.cursor()
            k = (request.key or '').lower().strip()
            cat = request.category or 'place'
            if k in ('*', 'all', ''):
                if cat == 'place':
                    places = self.get_all_places_dict()
                    response.success = True
                    response.value = json.dumps(places)
                    response.message = f'returned {len(places)} places'
                    conn.close()
                    return response
                else:
                    c.execute('SELECT value FROM facts WHERE category=? ORDER BY id DESC LIMIT 1', (cat,))
            else:
                c.execute(
                    'SELECT value FROM facts WHERE category=? AND key=?',
                    (cat, k),
                )
            row = c.fetchone()
            conn.close()
            if row:
                response.success = True
                response.value = row[0]
                response.message = 'ok'
            else:
                response.success = False
                response.value = ''
                response.message = f'unknown fact: {request.key}'
        except Exception as e:
            response.success = False
            response.value = ''
            response.message = str(e)
        return response

    def on_detection(self, msg):
        if msg.label == 'person' and msg.confidence > 0.6:
            conn = self._connect()
            c = conn.cursor()
            c.execute(
                'INSERT INTO events (event_type, description, timestamp) VALUES (?, ?, ?)',
                ('PERSON_ENCOUNTER',
                 f'Saw person at {msg.distance_meters:.1f}m', time.time()),
            )
            conn.commit()
            conn.close()

    def on_voice(self, msg):
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            'INSERT INTO events (event_type, description, timestamp) VALUES (?, ?, ?)',
            ('VOICE_INTERACTION',
             f'{msg.transcript} ({msg.intent})', time.time()),
        )
        conn.commit()
        conn.close()


def main(args=None):
    rclpy.init(args=args)
    node = MemoryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
