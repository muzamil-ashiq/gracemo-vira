#!/usr/bin/env python3
"""
GRaCEmo ViRa — Physical Bumper Contact Live Gazebo Test:
Drives the robot towards a wall, monitors /bumper/contacts,
verifies that a real physical contact event is generated, and stops.
"""

import sys
import time
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.twist_pb2 import Twist as GzTwist
    from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
    try:
        from gz.msgs10.contacts_pb2 import Contacts as GzContacts
    except ImportError:
        from gz.msgs.contacts_pb2 import Contacts as GzContacts
except ImportError:
    print("ERROR: gz.transport13 or protobufs not found.")
    sys.exit(1)

from gracemo_base_controller import BaseController


def test_live_bumper():
    print("=================================================================")
    print("  TESTING LIVE GAZEBO BUMPER CONTACT SENSOR GENERATION")
    print("=================================================================")

    node = gz_transport.Node()
    cmd_pub = node.advertise("/cmd_vel", GzTwist)

    contact_received = False
    contact_details = {}

    def on_contact(msg):
        nonlocal contact_received, contact_details
        if hasattr(msg, "contact") and len(msg.contact) > 0:
            contact_received = True
            c = msg.contact[0]
            contact_details["collision1"] = c.collision1.name if hasattr(c, "collision1") else "unknown"
            contact_details["collision2"] = c.collision2.name if hasattr(c, "collision2") else "unknown"
            contact_details["count"] = len(msg.contact)

    # Subscribe to both topics
    node.subscribe(GzContacts, "/bumper/contacts", on_contact)
    node.subscribe(GzContacts, "/world/gracemo_home/model/gracemo_vira/link/base_footprint/sensor/bumper_contact/contact", on_contact)

    base = BaseController()
    if not base.wait_for_sensors(timeout_sec=4.0):
        print("FAIL: Sensored stream not ready.")
        return False

    print(f"Robot initial pose: ({base.cur_x:.2f}, {base.cur_y:.2f}, yaw={math.degrees(base.cur_yaw):.1f}°)")

    # 1. Determine heading of closest obstacle / wall using LiDAR scan
    target_heading = math.pi / 2.0
    if base.latest_scan and len(base.latest_scan.ranges) > 0:
        valid = [(r, i) for i, r in enumerate(base.latest_scan.ranges) if 0.2 < r < 8.0]
        if valid:
            min_r, min_idx = min(valid, key=lambda x: x[0])
            inc = base.latest_scan.angle_step if base.latest_scan.angle_step > 0 else (2.0 * math.pi / len(base.latest_scan.ranges))
            obs_angle = base.latest_scan.angle_min + min_idx * inc
            target_heading = base.cur_yaw + obs_angle
            print(f"Nearest obstacle detected by LiDAR at dist={min_r:.2f}m, relative angle={math.degrees(obs_angle):.1f}°")

    print(f"1. Aligning towards nearest obstacle/wall (target yaw={math.degrees(target_heading):.1f}°)...")
    base.pivot_to_heading(target_heading, timeout_sec=5.0)
    print(f"Aligned pose: ({base.cur_x:.2f}, {base.cur_y:.2f}, yaw={math.degrees(base.cur_yaw):.1f}°)")

    # 2. Drive straight towards obstacle at 0.25 m/s until contact
    print("2. Driving directly towards obstacle to initiate physical bumper contact...")
    t0 = time.time()
    while time.time() - t0 < 12.0 and not contact_received:
        # Command raw drive so APF safety shield does not brake early
        base.drive_raw_velocity(0.25, 0.0)
        time.sleep(0.02)

    base.stop()
    time.sleep(0.5)

    print(f"\nContact received: {contact_received}")
    if contact_received:
        print(f"✓ BUMPER CONTACT EVENT CONFIRMED!")
        print(f"  Collision 1: {contact_details.get('collision1')}")
        print(f"  Collision 2: {contact_details.get('collision2')}")
        print(f"  Contact count: {contact_details.get('count')}")
        print(f"  BaseController bumper_hit state: {base.bumper_hit}")
        
        # 3. Back off away from wall to leave robot in clean free space
        print("3. Backing off 0.40m away from wall...")
        t_back = time.time()
        while time.time() - t_back < 1.8:
            base.drive_raw_velocity(-0.20, 0.0)
            time.sleep(0.02)
        base.stop()
        print(f"Final pose after backoff: ({base.cur_x:.2f}, {base.cur_y:.2f})")
        return True
    else:
        print("❌ FAIL: No bumper contact event was generated within 6 seconds!")
        return False


if __name__ == "__main__":
    success = test_live_bumper()
    sys.exit(0 if success else 1)
