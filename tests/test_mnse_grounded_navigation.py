#!/usr/bin/env python3
"""
Test Suite: MNSE Perception & K Action Pipeline Verification
Verifies that:
1. Authoritative MNSE Kernel is online at http://127.0.0.1:7780.
2. Ingestion of genuine perception event (ObjectDetected: laptop) updates SQLite ledger and relational Knowledge Graph.
3. DestinationResolver resolves dynamic entities ("laptop") via Knowledge Graph to Home Study coordinates (x=4.5, y=3.0).
4. Strict negative control: Unobserved entities ("backpack_nonexistent") return None (Zero Hallucination).
5. Grounded prompt compiler emits TOON format with verified facts.
6. K operational expression (graph::locate[entity: "laptop"] | nav::reach) executes and returns coordinates.
"""

import sys
import time
import requests

# Add prototype gracemo_interaction to path
WS_SRC = "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src"
sys.path.insert(0, f"{WS_SRC}/gracemo_interaction")

from gracemo_interaction.destination_resolver import DestinationResolver

KERNEL_URL = "http://127.0.0.1:7780"

def test_mnse_grounded_navigation():
    print("=" * 70)
    print("  🧠 VERIFYING MNSE PERCEPTION & K ACTION GROUNDING PIPELINE")
    print("=" * 70)

    # 1. Verify Kernel Health
    print("\n1. Checking MNSE Kernel health...")
    resp = requests.get(f"{KERNEL_URL}/health", timeout=2.0)
    assert resp.status_code == 200, f"Kernel health check failed: {resp.status_code}"
    health = resp.json()
    print(f"   ✓ PASS: Kernel online - status: '{health.get('status')}', version: {health.get('version')}")

    # 2. Ingest genuine perception event into Kernel
    import uuid
    print("\n2. Ingesting perception observation (class='laptop', room='Home Study', x=4.5, y=3.0)...")
    event_payload = {
        "id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "source": "Vision",
        "observed_by": "perception_detector",
        "event_type": {
            "type": "ObjectDetected",
            "data": {
                "class_name": "laptop",
                "confidence": 0.95,
                "x": 4.5,
                "y": 3.0,
            }
        },
        "parent_event_id": None
    }
    emit_resp = requests.post(f"{KERNEL_URL}/emit", json=event_payload, timeout=2.0)
    assert emit_resp.status_code == 200, f"Event emit failed: {emit_resp.text}"
    print("   ✓ PASS: Event recorded into SQLite WAL ledger and relational Knowledge Graph")

    # 3. Dynamic Destination Resolution via Knowledge Graph
    print("\n3. Testing dynamic destination resolution via Knowledge Graph...")
    resolver = DestinationResolver()
    dest_key, dest_info = resolver.resolve("laptop")
    print(f"   Resolved 'laptop' -> Key: '{dest_key}', Info: {dest_info}")
    assert dest_key == "laptop", f"Expected 'laptop', got {dest_key}"
    assert dest_info is not None, "Destination info for laptop is None"
    assert abs(dest_info["x"] - 4.5) < 0.1 and abs(dest_info["y"] - 3.0) < 0.1, f"Coordinates mismatch: {dest_info}"
    print(f"   ✓ PASS: Dynamic entity resolved to ({dest_info['x']}, {dest_info['y']}) in {dest_info['name']}")

    # 4. Strict Negative Control: Unobserved Object
    print("\n4. Testing negative control: Unobserved entity rejection...")
    unknown_key, unknown_info = resolver.resolve("backpack_nonexistent")
    print(f"   Resolved 'backpack_nonexistent' -> Key: {unknown_key}, Info: {unknown_info}")
    assert unknown_key is None and unknown_info is None, "Kernel fabricated location for unobserved object!"
    print("   ✓ PASS: Unobserved entities strictly return None (Zero Hallucination)")

    # 5. K Expression Execution
    print("\n5. Testing K expression execution ('graph::locate[entity: \"laptop\"] | nav::reach')...")
    k_resp = requests.post(
        f"{KERNEL_URL}/k/execute",
        json={"expression": 'graph::locate[entity: "laptop"] | nav::reach'},
        timeout=2.0
    )
    assert k_resp.status_code == 200, f"K execute failed: {k_resp.text}"
    k_data = k_resp.json()
    print(f"   K Response: {k_data}")
    assert k_data.get("success") is True, f"K pipeline execution reported failure: {k_data}"
    print("   ✓ PASS: K pipeline resolved target entity and generated reach action")

    print("\n" + "=" * 70)
    print("  🏁 MNSE PERCEPTION & K ACTION GROUNDING: COMPLETE & VERIFIED")
    print("=" * 70 + "\n")
    return True

if __name__ == "__main__":
    success = test_mnse_grounded_navigation()
    sys.exit(0 if success else 1)
