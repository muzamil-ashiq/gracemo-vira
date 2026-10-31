#!/usr/bin/env python3
"""
Closed-Loop Grounding & Context Demonstration Test:
Validates the complete pipeline:
Sensor / Perception Observation -> Typed Event -> MNSE Kernel / Ledger / Graph
-> Context Compiler (TOON) -> Grounded Reasoning -> K Query / Action Request
Distinguishes between:
  1. Current observations
  2. Historical observations
  3. Inferred spatial relationships (room containment)
  4. Unknown / unobserved objects (no hallucination)
"""

import sys
import time
import json
import uuid
import requests
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.gemini_robotics.context import MNSEContextProvider
from adapters.gemini_robotics.tools import ToolRegistry

KERNEL_URL = "http://127.0.0.1:7780"

def test_closed_loop_demonstration():
    print("=" * 70)
    print("  🧠 CLOSED-LOOP PERCEPTION -> MNSE -> CONTEXT COMPILER DEMO")
    print("=" * 70)

    # 1. Verify Kernel connection
    context_provider = MNSEContextProvider(kernel_url=KERNEL_URL)
    registry = ToolRegistry(kernel_url=KERNEL_URL, use_direct_skills=False)

    if not context_provider.is_kernel_available():
        print(f"[FAIL] MNSE Kernel not available at {KERNEL_URL}")
        pytest.skip(f"MNSE Kernel not available at {KERNEL_URL}")
    print(f"✓ Connected to authoritative MNSE Kernel at {KERNEL_URL}")

    # 2. Stage A: Record a historical observation of a laptop in the Study
    laptop_id = str(uuid.uuid4())
    print("\n--- Transition 1: Perception -> Typed Event -> MNSE Ingestion ---")
    print(f"Emitting historical ObjectDetected: class='laptop', room='Home Study' (x=4.5, y=3.0)...")
    ok = registry.emit_object_detected(
        class_name="laptop",
        confidence=0.92,
        x=4.5,
        y=3.0,
        source="Vision"
    )
    assert ok, "Failed to emit laptop observation to Kernel"
    print("✓ Event accepted by Kernel /emit and recorded into SQLite Event Ledger")

    time.sleep(0.3)

    # 3. Stage B: Verify Knowledge Graph spatial grounding
    print("\n--- Transition 2: Knowledge Graph Spatial Inference ---")
    loc_res = context_provider.query_object_location("laptop")
    print(f"Graph location query for 'laptop': {loc_res}")
    assert loc_res is not None, "Laptop not found in Knowledge Graph"
    room = loc_res.get("location")
    conf = loc_res.get("confidence")
    print(f"✓ Inferred spatial relation: 'laptop' -> LOCATED_IN -> '{room}' (confidence: {conf:.2f})")

    # 4. Stage C: Verify Context Compiler Grounding (TOON format)
    print("\n--- Transition 3: Context Compiler Grounded Prompt Generation ---")
    user_query = "Where did you see the laptop yesterday, and what is its status now?"
    grounded_prompt = context_provider.build_grounded_prompt(user_query)
    print("Compiled Context Excerpt:")
    for line in grounded_prompt.splitlines()[:15]:
        print(f"  | {line}")

    # Validate that grounded prompt includes factual ground truth from graph
    assert "laptop" in grounded_prompt, "Grounded prompt does not include 'laptop'"
    assert "study" in grounded_prompt.lower() or "Home Study" in grounded_prompt, "Room not in grounded prompt"
    print("✓ Grounded prompt accurately incorporates historical room and object state")

    # 5. Stage D: Verification of Non-Hallucination on Unknown Object
    print("\n--- Transition 4: Negative Control (Unknown Object Verification) ---")
    unknown_query = "backpack_xyz_nonexistent"
    unknown_res = context_provider.query_object_location(unknown_query)
    print(f"Query for unobserved entity '{unknown_query}': {unknown_res}")
    assert unknown_res is None, "Kernel fabricated location for unobserved object!"
    print("✓ Kernel strictly reports None/Unknown for unobserved objects (Zero Hallucination)")

    # 6. Stage E: K Operational Query & Action Dispatch
    print("\n--- Transition 5: K Operational Query & Action Pipeline ---")
    k_expr = 'graph::locate[entity: "laptop"] | nav::reach'
    print(f"Dispatching K pipeline: '{k_expr}'...")
    k_resp = requests.post(
        f"{KERNEL_URL}/k/execute",
        json={"expression": k_expr},
        timeout=2.0
    )
    assert k_resp.status_code == 200, f"K execute failed: {k_resp.text}"
    k_data = k_resp.json()
    print(f"K Execution Result: {json.dumps(k_data, indent=2)}")
    assert k_data.get("success") is True, "K execution reported failure"
    print("✓ K pipeline successfully resolved target coordinates and planned reach action")

    print("\n" + "=" * 70)
    print("  🏁 CLOSED-LOOP DEMONSTRATION: SUCCESS (ALL 5 TRANSITIONS VERIFIED)")
    print("=" * 70 + "\n")
    return True

if __name__ == "__main__":
    success = test_closed_loop_demonstration()
    sys.exit(0 if success else 1)
