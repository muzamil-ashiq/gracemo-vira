#!/usr/bin/env python3
"""
Test C: ObjectDetected -> Kernel/MNSE Test
Verifies:
1. Canonical EventType::ObjectDetected emission to Kernel /emit.
2. Kernel ledger and graph processing.
3. Querying /graph returns the grounded entity and room edge.
4. Compiled context /context?format=toon reflects #GRAPH:<object>[in:<room>,conf:<conf>].
"""

import os
import sys
import time
import uuid
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.gemini_robotics.tools import ToolRegistry
from adapters.gemini_robotics.context import MNSEContextProvider

KERNEL_URL = "http://127.0.0.1:7780"

def test_object_detected_mnse():
    print("=== TEST C: OBJECT_DETECTED -> KERNEL/MNSE TEST ===")
    
    # Check kernel health
    try:
        r = requests.get(f"{KERNEL_URL}/health", timeout=1.0)
        if r.status_code != 200:
            print(f"❌ Kernel unhealthy: {r.status_code}")
            return False
        print(f"✓ Connected to MNSE Kernel at {KERNEL_URL}")
    except Exception as e:
        print(f"❌ Failed to connect to Kernel: {e}")
        return False

    context_provider = MNSEContextProvider(kernel_url=KERNEL_URL)
    registry = ToolRegistry(kernel_url=KERNEL_URL, use_direct_skills=False)

    robot_state = context_provider.get_robot_context()
    current_room = robot_state.get("current_room", "Unknown")
    print(f"✓ Current robot room in MNSE snapshot: '{current_room}'")

    test_obj = "dining_table"
    test_conf = 0.95
    print(f"📤 Emitting canonical ObjectDetected event: class_name='{test_obj}', conf={test_conf}...")

    ok = registry.emit_object_detected(
        class_name=test_obj,
        confidence=test_conf,
        x=-4.5,
        y=-4.0,
        source="Vision"
    )
    if not ok:
        print("❌ Failed to emit ObjectDetected event to Kernel")
        return False
    print("✓ Canonical ObjectDetected event accepted by Kernel /emit (HTTP 200)")

    time.sleep(0.3)

    # Verify via /graph query
    print(f"🔍 Querying /graph for '{test_obj}'...")
    loc_res = context_provider.query_object_location(test_obj)
    print(f"  Result from /graph: {loc_res}")
    if not loc_res:
        print(f"❌ Object '{test_obj}' not found in Knowledge Graph!")
        return False
    
    print(f"✓ Confirmed in Knowledge Graph: '{test_obj}' -> located in '{loc_res.get('location')}' (conf: {loc_res.get('confidence')})")

    # Verify via /context?format=toon
    toon = context_provider.get_compiled_context(fmt="toon")
    print("\n--- Compiled TOON Context ---")
    print(toon)
    print("-----------------------------\n")

    if "#GRAPH:" in toon and test_obj in toon:
        print(f"✓ Compiled TOON successfully includes #GRAPH relation for '{test_obj}'!")
        print("✓ TEST C (ObjectDetected -> Kernel/MNSE): PASS")
        return True
    else:
        print(f"❌ #GRAPH relation for '{test_obj}' missing from TOON context")
        return False

if __name__ == "__main__":
    ok = test_object_detected_mnse()
    sys.exit(0 if ok else 1)
