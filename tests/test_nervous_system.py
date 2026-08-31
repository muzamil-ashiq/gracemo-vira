"""
GRaCEmo ViRa - Nervous System End-to-End Verification Test (v0.0.2)

Tests:
1. Kernel health check (GET /health)
2. Event emission (POST /emit) for Battery, Position, Vision, and Voice
3. Snapshot consistency (GET /snapshot)
4. Action emission & SSE live stream verification
"""

import sys
import time
import json
import threading
import requests
from pathlib import Path

# Add adapters/sdk to sys.path
sdk_path = Path(__file__).parent.parent / "adapters" / "sdk"
sys.path.insert(0, str(sdk_path))

from gracemo_sdk import AdapterClient


def test_kernel_live_loop():
    print("=" * 60)
    print("🧠 GRaCEmo ViRa — Nervous System Live Verification (v0.0.2)")
    print("=" * 60)

    client = AdapterClient(adapter_name="test_runner", base_url="http://127.0.0.1:7780")

    # 1. Test Health Endpoint
    print("\n[1/4] Checking Kernel Health...")
    try:
        resp = requests.get("http://127.0.0.1:7780/health", timeout=2.0)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        health_data = resp.json()
        print(f"  ✓ Kernel is ONLINE: {health_data}")
    except Exception as e:
        print(f"  ✗ Failed to connect to Kernel: {e}")
        print("  👉 Please ensure 'cargo run -p gracemo-kernel' is running.")
        return False

    # 2. Test SSE Action Listener in Background Thread
    actions_received = []

    def action_listener():
        try:
            for action in client.listen_actions():
                actions_received.append(action)
                if len(actions_received) >= 2:
                    break
        except Exception as e:
            print(f"  SSE listener exception: {e}")

    listener_thread = threading.Thread(target=action_listener, daemon=True)
    listener_thread.start()
    time.sleep(0.5)  # Allow SSE stream to establish

    # 3. Test Sensory Event Emission
    print("\n[2/4] Emitting Sensory Events...")

    # Battery
    ok = client.emit("RobotBattery", {"level": 85, "charging": False}, source="RobotBridge")
    print(f"  ✓ Emitted RobotBattery (85%): {'OK' if ok else 'FAILED'}")

    # Position
    ok = client.emit("RobotPosition", {"x": 2.45, "y": 1.12, "theta": 0.52, "speed": 0.35}, source="RobotBridge")
    print(f"  ✓ Emitted RobotPosition (x=2.45, y=1.12): {'OK' if ok else 'FAILED'}")

    # Vision
    ok = client.emit("PersonVisible", {"identity": "muzamil", "confidence": 0.98, "distance": 1.4}, source="Vision")
    print(f"  ✓ Emitted PersonVisible (identity='muzamil'): {'OK' if ok else 'FAILED'}")

    # Voice
    ok = client.emit("VoiceDetected", {"transcription": "Hey GraCemo, find Dr. Arora", "confidence": 0.95}, source="Voice")
    print(f"  ✓ Emitted VoiceDetected ('find Dr. Arora'): {'OK' if ok else 'FAILED'}")

    # 4. Test Snapshot Verification
    print("\n[3/4] Verifying Kernel Live Memory Snapshot...")
    time.sleep(0.3)
    snapshot = client.get_snapshot()
    assert snapshot is not None, "Snapshot was None"
    print(f"  Snapshot Data:\n{json.dumps(snapshot, indent=4)}")

    assert snapshot["battery"]["level"] == 85, "Battery level mismatch"
    assert snapshot["robot_position"]["x"] == 2.45, "Position x mismatch"
    assert snapshot["last_vision_detection"]["identity"] == "muzamil", "Vision identity mismatch"
    assert snapshot["last_voice_command"]["text"] == "Hey GraCemo, find Dr. Arora", "Voice text mismatch"
    print("  ✓ All snapshot fields accurately reconciled in Kernel memory!")

    # 5. Test Action Dispatch via SSE
    print("\n[4/4] Dispatching Actions to EventBus...")
    client.emit("ActionRequested", {
        "action": "Speak",
        "params": {"text": "Hello Muzamil, navigating to Dr. Arora's office now."}
    }, source="Brain")

    client.emit("ActionRequested", {
        "action": "NavigateTo",
        "params": {"x": 5.2, "y": 3.1}
    }, source="Brain")

    time.sleep(1.0)
    print(f"  ✓ Actions captured by SSE stream ({len(actions_received)} received):")
    for act in actions_received:
        print(f"     → Dispatched Action: {act}")

    assert len(actions_received) >= 1, "Expected at least 1 action received via SSE"

    print("\n" + "=" * 60)
    print("🎉 ALL NERVOUS SYSTEM END-TO-END TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_kernel_live_loop()
    sys.exit(0 if success else 1)
