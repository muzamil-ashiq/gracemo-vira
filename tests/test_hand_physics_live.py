#!/usr/bin/env python3
"""
GRaCEmo ViRa — Live Physics Verification for Hand Subsystem (Milestone 1)
Tests live Gazebo Harmonic physics with joint controllers and contact sensors:
  1. Communicates via Gazebo transport with running simulation.
  2. Verifies physical finger motion and symmetry.
  3. Verifies anti-false-positive grasp on air under real physics.
"""

import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from hand_controller import HandSubsystem, HandState


def main():
    print("=== LIVE GAZEBO HAND SUBSYSTEM PHYSICS TEST ===")
    hand = HandSubsystem(mock=False)
    if hand.mock:
        print("ERROR: Could not connect to live Gazebo transport!")
        sys.exit(1)

    print("1. Waiting 1.0s for initial joint state telemetry...")
    time.sleep(1.0)
    l, r = hand.get_joint_positions()
    w = hand.get_width()
    print(f"   Initial: Left={l*1000:.2f}mm, Right={r*1000:.2f}mm, Aperture={w*1000:.2f}mm")

    print("\n2. Actuating hand::open to 80mm...")
    t0 = time.time()
    opened = hand.open(width_m=0.080, timeout_sec=2.5)
    dt = time.time() - t0
    l, r = hand.get_joint_positions()
    w = hand.get_width()
    print(f"   Result: opened={opened} in {dt:.2f}s | L={l*1000:.2f}mm, R={r*1000:.2f}mm, Aperture={w*1000:.2f}mm")
    assert opened, "Failed to open hand in Gazebo!"
    assert w >= 0.075, f"Aperture did not reach open width: {w*1000:.1f}mm"
    assert abs(l - r) < 0.005, f"Asymmetric motion observed: L={l}, R={r}"

    print("\n3. Actuating hand::close to minimum gap...")
    t0 = time.time()
    closed = hand.close(timeout_sec=2.5)
    dt = time.time() - t0
    l, r = hand.get_joint_positions()
    w = hand.get_width()
    print(f"   Result: closed={closed} in {dt:.2f}s | L={l*1000:.2f}mm, R={r*1000:.2f}mm, Aperture={w*1000:.2f}mm")
    assert closed, "Failed to close hand in Gazebo!"
    assert w <= 0.025, f"Gripper did not close: {w*1000:.1f}mm"

    print("\n4. Testing Live Anti-False-Positive Grasp (closing on air)...")
    # First open back up
    hand.open(width_m=0.075, timeout_sec=2.0)
    time.sleep(0.5)
    t0 = time.time()
    grasped = hand.grasp(timeout_sec=3.0)
    dt = time.time() - t0
    l, r = hand.get_joint_positions()
    w = hand.get_width()
    state = hand.get_state()
    print(f"   Result: grasped={grasped} (expected False) in {dt:.2f}s | State={state} | Aperture={w*1000:.2f}mm")
    assert not grasped, "CRITICAL: Live grasp falsely reported success on empty air!"
    assert state == HandState.EMPTY_CLOSED.value, f"Expected state EMPTY_CLOSED, got {state}"

    print("\n5. Testing hand::release...")
    released = hand.release(open_width_m=0.080)
    w = hand.get_width()
    print(f"   Result: released={released}, Aperture={w*1000:.2f}mm, State={hand.get_state()}")
    assert released, "Failed to release!"
    assert w >= 0.075, f"Did not re-open upon release: {w*1000:.1f}mm"

    print("\n>>> ALL LIVE GAZEBO PHYSICS CHECKS PASSED! <<<")


if __name__ == "__main__":
    main()
