#!/usr/bin/env python3
"""
Interactive drive demo for Piece 1: Mobile Base Subsystem.
Demonstrates forward driving, reverse, and frictionless in-place rotation.
"""
import time
import sys
import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist

def main():
    node = gz_transport.Node()
    pub = node.advertise("/cmd_vel", Twist)
    time.sleep(0.5)

    def send_cmd(vx, wz, duration, desc):
        print(f"▶ {desc} (vx={vx:.2f} m/s, wz={wz:.2f} rad/s) for {duration}s...")
        t_end = time.time() + duration
        while time.time() < t_end:
            msg = Twist()
            msg.linear.x = float(vx)
            msg.angular.z = float(wz)
            pub.publish(msg)
            time.sleep(0.05)
        # Stop briefly
        msg = Twist()
        pub.publish(msg)
        time.sleep(0.2)

    print("=========================================================")
    print("  GRaCEmo ViRa — Piece 1 Base Mobility Demo")
    print("=========================================================")
    time.sleep(1.0)

    # 1. Drive Forward
    send_cmd(0.35, 0.0, 2.0, "Driving Forward smoothly")

    # 2. In-Place Frictionless Spin (Counter-Clockwise)
    send_cmd(0.0, 1.20, 2.5, "Spinning 360° in place (Testing casters & balanced CoM)")

    # 3. Drive Backward
    send_cmd(-0.25, 0.0, 1.5, "Reversing cleanly")

    # 4. In-Place Spin (Clockwise)
    send_cmd(0.0, -1.20, 2.5, "Spinning Clockwise back to initial heading")

    # Final Stop
    msg = Twist()
    pub.publish(msg)
    print("✓ Mobility demo complete! Base stationed.")

if __name__ == "__main__":
    main()
