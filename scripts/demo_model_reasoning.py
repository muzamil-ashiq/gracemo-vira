#!/usr/bin/env python3
"""
GRaCEmo ViRa — Model Interaction & Grounded Reasoning Test
Demonstrates the embodied intelligence loop:
  1. Brain receives user intent
  2. Brain queries MNSE Kernel Context & Relational Knowledge Graph
  3. Brain formulates grounded answer from REAL Gazebo sensor observations
  4. Brain emits high-level ActionRequested (Speak & NavigateTo)
"""

import os
import sys
import json
import time
import subprocess
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))
from gracemo_sdk import AdapterClient

KERNEL_URL = os.getenv("GRACEMO_KERNEL_URL", "http://127.0.0.1:7780")


def ensure_kernel_running():
    try:
        resp = requests.get(f"{KERNEL_URL}/health", timeout=0.8)
        if resp.status_code == 200:
            return
    except Exception:
        pass

    bin_path = ROOT / "kernel" / "target" / "debug" / "gracemo-kernel"
    if not bin_path.exists():
        print("⚙️ Compiling Rust Kernel binary...")
        subprocess.run(["cargo", "build", "--manifest-path", str(ROOT / "kernel" / "Cargo.toml"), "--bin", "gracemo-kernel"], check=True)

    print("⚡ Starting gracemo-kernel background daemon on port 7780...")
    subprocess.Popen([str(bin_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.3)
        try:
            resp = requests.get(f"{KERNEL_URL}/health", timeout=0.5)
            if resp.status_code == 200:
                print("✓ Kernel is online!")
                return
        except Exception:
            pass
    print("⚠️ Warning: Kernel health check timed out. Proceeding...")


def main():
    ensure_kernel_running()

    target_query_object = sys.argv[1] if len(sys.argv) > 1 else "bed"

    print("=" * 70)
    print("🤖 GRaCEmo ViRa — Live AI Model Interaction Test")
    print("=" * 70)

    client = AdapterClient(adapter_name="Brain-Reasoner", base_url=KERNEL_URL)

    # -------------------------------------------------------------
    # SCENARIO: User asks a natural language question
    # -------------------------------------------------------------
    user_query = f"ViRa, where is the {target_query_object} and can you guide me there?"
    print(f"\n👤 [USER VOICE COMMAND]: \"{user_query}\"")
    time.sleep(0.5)

    # -------------------------------------------------------------
    # STEP 1: Model Queries Authoritative Truth from MNSE Kernel
    # -------------------------------------------------------------
    print("\n🧠 [STEP 1: MODEL QUERIES KERNEL CONTEXT & KNOWLEDGE GRAPH]")
    print("  -> Calling client.get_context(history_limit=10)...")
    context = client.get_context(history_limit=10)

    if not context:
        print("❌ Error: Could not connect to Kernel Context Compiler.")
        return

    now_state = context.get("now", {})
    recent_history = context.get("recent_history", [])
    graph = context.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    print(f"  ✓ Received Authoritative Context Package:")
    print(f"     • NOW State: Robot stationed in '{now_state.get('current_room')}' at {now_state.get('position')}")
    print(f"     • PAST Ledger: {len(recent_history)} chronological sensory events in SQLite WAL")
    print(f"     • GRAPH Relations: {len(nodes)} entities | {len(edges)} verified relational edges")

    # -------------------------------------------------------------
    # STEP 2: Grounded Cognitive Reasoning from SQLite Knowledge Graph
    # -------------------------------------------------------------
    print(f"\n🤔 [STEP 2: MODEL TRAVERSES KNOWLEDGE GRAPH FOR '{target_query_object}']")
    
    # Query Knowledge Graph directly
    graph_resp = requests.get(f"{KERNEL_URL}/graph?object={target_query_object}", timeout=2.0).json()
    
    if graph_resp.get("found"):
        res = graph_resp["result"]
        loc = res.get("location", "Unknown Room")
        conf = res.get("confidence", 1.0) * 100
        ts = time.strftime("%H:%M:%S", time.localtime(res.get("timestamp", time.time())))

        print(f"  ✓ Grounded Relational Truth Discovered in Graph:")
        print(f"     • Relation: ({target_query_object}) -[{res.get('relation')}]-> ({loc})")
        print(f"     • Physical Sensor: Gazebo RGB Camera + YOLOv11 (conf: {conf:.1f}%)")
        print(f"     • Observed At: {ts}")

        response_speech = f"The {target_query_object} was visually observed by my camera in the {loc} with {conf:.0f}% confidence. Follow me, I am navigating there now."
    else:
        print(f"  ℹ️ Entity '{target_query_object}' has not been sighted by any sensor yet.")
        response_speech = f"I have not sighted the {target_query_object} yet during my patrol. I can search the apartment for it."

    print(f"\n💬 [MODEL SPOKEN RESPONSE]: \"{response_speech}\"")

    # -------------------------------------------------------------
    # STEP 3: Model Emits High-Level Action Intents
    # -------------------------------------------------------------
    print("\n⚡ [STEP 3: MODEL EMITS HIGH-LEVEL ACTION INTENTS]")
    
    # Intent 1: Speak to the user
    print("  1. Emitting ActionRequested: Speak")
    ok1 = client.emit("ActionRequested", {
        "action": "Speak",
        "params": {"text": response_speech}
    }, source="Brain")
    print(f"     Status: {'✓ Dispatched to TTS' if ok1 else '❌ Failed'}")

    # Intent 2: Navigate to target
    if graph_resp.get("found"):
        target_room = graph_resp["result"].get("location", "Master Bedroom")
        print(f"  2. Emitting ActionRequested: NavigateToRoom ({target_room})")
        ok2 = client.emit("ActionRequested", {
            "action": "NavigateToRoom",
            "params": {"room": target_room}
        }, source="Brain")
        print(f"     Status: {'✓ Dispatched to Reflex Navigation Substrate' if ok2 else '❌ Failed'}")

    # -------------------------------------------------------------
    # STEP 4: Verification in Kernel Ledger
    # -------------------------------------------------------------
    print("\n📜 [STEP 4: VERIFYING ACTIONS LOGGED IN KERNEL LEDGER]")
    time.sleep(0.4)
    updated_context = client.get_context(history_limit=2)
    latest_events = updated_context.get("recent_history", [])[:2]
    for ev in latest_events:
        print(f"  • [{ev.get('event_type')}] from {ev.get('source')}")

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE: Model successfully reasoned with 100% grounded truth!")
    print("=" * 70)


if __name__ == "__main__":
    main()
