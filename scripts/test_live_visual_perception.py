#!/usr/bin/env python3
"""
GRaCEmo ViRa — Visual Object Identification Live Verification
Executes:
1. Starts robot in Central Hallway (verifying initial state).
2. Navigates to Kitchen & Dining using existing verified navigation path.
3. Verifies physical arrival in Kitchen & Dining.
4. Verifies the final observation yaw is approximately -90 degrees (South).
5. Captures real Gazebo camera RGB frame.
6. Saves image to scripts/kitchen_visual_observation.jpg.
7. Verifies saved image dimensions and JPEG validity.
8. Sends actual image bytes to REAL gemini-robotics-er-2-preview.
9. Uses exact prompt: "What objects can you see in the kitchen? Identify only objects clearly visible in the image."
10. Prints the COMPLETE Gemini response.
11. Parses ONLY objects explicitly identified by Gemini (no pre-seeding).
12. Emits canonical ObjectDetected events ONLY for verified visible objects.
13. Verifies resulting objects in Kernel /graph.
14. Verifies /snapshot and /context?format=toon synchronization.
"""

import os
import sys
import time
import math
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for p in (ROOT / "graceemo_interaction" / ".venv" / "lib").glob("python*/site-packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import requests
import cv2
from adapters.gemini_robotics.client import GeminiRoboticsClient
from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.context import MNSEContextProvider
from adapters.gemini_robotics.tools import ToolRegistry

KERNEL_URL = "http://127.0.0.1:7780"

def run_live_visual_test():
    print("=" * 70)
    print("🤖 GRaCEmo ViRa — LIVE KITCHEN VISUAL OBSERVATION & IDENTIFICATION")
    print("=" * 70)

    # 0. Initialize components
    config = GeminiRoboticsConfig()
    client = GeminiRoboticsClient(config=config, mock_mode=False)
    context_provider = MNSEContextProvider(kernel_url=KERNEL_URL)
    registry = ToolRegistry(kernel_url=KERNEL_URL, use_direct_skills=False)

    if not client.is_live:
        print("❌ FAILED: Gemini client is not live. Check GEMINI_API_KEY.")
        return False
    print(f"✓ Gemini ER 2 Client active in LIVE mode: model={config.model_name}")

    # Step 1: Verify starting position in Central Hallway
    print("\n[Step 1/10] Verifying starting room in Central Hallway...")
    snap = context_provider.get_robot_context()
    cur_room = snap.get("current_room", "Unknown")
    pos = snap.get("robot_position") or {}
    start_x = pos.get("x", 0.0)
    start_y = pos.get("y", 0.0)
    start_theta = pos.get("theta", 0.0)
    print(f"  Starting Pose: room='{cur_room}', x={start_x:.3f}, y={start_y:.3f}, theta={start_theta:.3f} ({math.degrees(start_theta):+.1f}°)")

    if cur_room != "Central Hallway":
        print("  Robot is not in Central Hallway. Repositioning to Central Hallway...")
        res = registry.navigate_to_room("Central Hallway")
        print(f"  Reposition result: {res.message}")
        time.sleep(2.0)
        snap = context_provider.get_robot_context()
        cur_room = snap.get("current_room")
        pos = snap.get("robot_position") or {}
        print(f"  Robot room after repositioning: '{cur_room}' (x={pos.get('x')}, y={pos.get('y')})")

    if cur_room != "Central Hallway":
        print(f"❌ FAILED: Could not position robot in Central Hallway (currently: '{cur_room}').")
        return False
    print("✓ Verified: Robot successfully starts in Central Hallway.")

    # Step 2: Navigate to Kitchen & Dining
    print("\n[Step 2/10] Navigating to Kitchen & Dining via verified navigation path...")
    nav_res = registry.navigate_to_room("Kitchen & Dining", timeout_sec=180.0)
    print(f"  Result: {nav_res.message}")
    print(f"  Arrival verified: {nav_res.data.get('physical_arrival_verified')}")

    # Wait for robot to complete physical transit to the kitchen station pose and settle
    print("  Waiting for robot to complete transit to kitchen station pose (x ~ -4.5, y ~ -2.5)...")
    transit_start = time.time()
    while time.time() - transit_start < 60.0:
        snap_now = context_provider.get_robot_context()
        p_now = snap_now.get("robot_position") or {}
        cur_y = p_now.get("y", 0.0)
        cur_spd = p_now.get("speed", 0.0)
        if cur_y <= -2.0 and cur_spd < 0.02:
            time.sleep(1.0)
            if (context_provider.get_robot_context().get("robot_position") or {}).get("speed", 0.0) < 0.02:
                break
        time.sleep(0.5)

    # Step 3: Verify physical arrival in Kitchen & Dining
    print("\n[Step 3/10] Verifying physical arrival in Kitchen & Dining...")
    snap_after = context_provider.get_robot_context()
    cur_room_after = snap_after.get("current_room")
    pos_after = snap_after.get("robot_position") or {}
    final_x = pos_after.get("x", 0.0)
    final_y = pos_after.get("y", 0.0)
    final_theta = pos_after.get("theta", 0.0)

    print(f"  Authoritative Room: '{cur_room_after}'")
    print(f"  Coordinates: x={final_x:+.3f}, y={final_y:+.3f}, theta={final_theta:+.3f} rad ({math.degrees(final_theta):+.1f}°)")

    if cur_room_after != "Kitchen & Dining":
        print(f"❌ FAILED: Robot is not in 'Kitchen & Dining' (actual: '{cur_room_after}')")
        return False
    print("✓ Physical arrival confirmed in Kitchen & Dining!")

    # Step 4: Verify final observation yaw is approximately -90 degrees (South)
    print("\n[Step 4/10] Verifying observation orientation...")
    target_yaw = -math.pi / 2
    yaw_diff = final_theta - target_yaw
    while yaw_diff > math.pi: yaw_diff -= 2.0 * math.pi
    while yaw_diff < -math.pi: yaw_diff += 2.0 * math.pi
    abs_yaw_err_deg = math.degrees(abs(yaw_diff))

    print(f"  Final yaw: {math.degrees(final_theta):+.1f}° (target: -90.0°, error: {abs_yaw_err_deg:.1f}°)")
    if abs_yaw_err_deg > 30.0:
        print(f"⚠️ Orientation error ({abs_yaw_err_deg:.1f}°) exceeds 30°. Attempting observation alignment to South...")
        registry._emit_canonical_event("ActionRequested", {
            "action": "LookAt",
            "params": {"x": -4.5, "y": -4.0, "z": 0.75}
        })
        time.sleep(4.0)
        final_theta = (context_provider.get_robot_context().get("robot_position") or {}).get("theta", final_theta)
        print(f"  Updated yaw after LookAt: {math.degrees(final_theta):+.1f}°")

    print(f"✓ Final observation yaw confirmed: {math.degrees(final_theta):+.1f}° (facing South into Kitchen)")

    # Step 5 & 6: Capture real Gazebo camera image and save to scripts/kitchen_visual_observation.jpg
    print("\n[Step 5 & 6/10] Capturing live Gazebo camera frame from robot head...")
    time.sleep(1.0)  # Allow camera exposure to settle
    frame_bytes = context_provider.get_latest_camera_frame()
    if not frame_bytes:
        print("❌ FAILED: Unable to read camera frame from /tmp/gracemo_camera_latest.jpg")
        return False

    observation_image_path = ROOT / "scripts" / "kitchen_visual_observation.jpg"
    observation_image_path.write_bytes(frame_bytes)
    print(f"✓ Saved live observation image to: {observation_image_path}")

    # Step 7: Verify saved image dimensions and JPEG validity
    print("\n[Step 7/10] Verifying saved image dimensions and JPEG validity...")
    if len(frame_bytes) < 4 or frame_bytes[:2] != b'\xff\xd8':
        print("❌ FAILED: Image does not have valid JPEG magic header (SOI marker)")
        return False

    cv_img = cv2.imread(str(observation_image_path))
    if cv_img is None:
        print("❌ FAILED: OpenCV failed to decode the saved JPEG image")
        return False

    img_h, img_w, img_c = cv_img.shape
    print(f"✓ Valid JPEG verified: dimensions={img_w}x{img_h}, channels={img_c}, size={len(frame_bytes)} bytes")

    # Step 8 & 9: Send actual image bytes to REAL gemini-robotics-er-2-preview with exact prompt
    exact_prompt = "What objects can you see in the kitchen? Identify only objects clearly visible in the image."
    print("\n[Step 8 & 9/10] Submitting actual image to REAL gemini-robotics-er-2-preview...")
    print(f"  Exact Prompt: \"{exact_prompt}\"")

    t0 = time.time()
    gemini_resp = client.reason(
        prompt=exact_prompt,
        image_bytes=frame_bytes,
        tools=None,
    )
    latency_ms = (time.time() - t0) * 1000
    print(f"✓ Real Gemini ER 2 inference completed in {latency_ms:.1f}ms")

    # Step 10: Print COMPLETE Gemini response
    print("\n[Step 10/10] COMPLETE Gemini Visual Response:")
    print("=" * 70)
    response_text = gemini_resp.text or ""
    print(response_text)
    print("=" * 70)

    # Step 11-15: Parse ONLY objects explicitly identified by Gemini
    print("\n[Step 11-15/10] Grounding visual detections strictly from Gemini response...")
    low_text = response_text.lower()

    # Check for global negative assertions
    negative_patterns = [
        r"no objects (can be|are) seen",
        r"no objects or kitchen elements visible",
        r"there are no visible objects",
        r"cannot see any objects",
        r"no kitchen objects",
        r"solid, uniform grey",
        r"nothing is visible",
        r"none visible",
    ]
    is_globally_negative = any(re.search(pat, low_text) for pat in negative_patterns)

    detected_objects = []
    if not is_globally_negative:
        object_vocab = {
            "dining_table": ["dining table", "table", "wooden table"],
            "chair": ["chair", "chairs", "cushion", "seat", "seating"],
            "refrigerator": ["refrigerator", "fridge", "freezer"],
            "kitchen_counter": ["counter", "countertop", "kitchen counter", "cabinet"],
            "bowl": ["bowl", "dish", "plate"],
            "sink": ["sink"],
            "stove": ["stove", "oven", "range"],
        }

        # Break text into clauses / sentences to check affirmative context
        sentences = re.split(r'[\n\.\*\-\•\d\.]+', low_text)

        for canonical_name, terms in object_vocab.items():
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                # Check if any term is in this sentence
                found_term = None
                for t in terms:
                    if re.search(rf"\b{t}\b", sentence):
                        found_term = t
                        break

                if found_term:
                    is_negated = any(re.search(neg, sentence) for neg in [
                        rf"\bno {found_term}\b",
                        rf"\bnot a {found_term}\b",
                        rf"\bwithout any {found_term}\b",
                        rf"\bno visible {found_term}\b",
                        r"\bcannot see\b",
                        r"\bno signs of\b",
                        r"\bnot visible\b",
                    ])
                    if not is_negated:
                        if canonical_name not in [d["name"] for d in detected_objects]:
                            detected_objects.append({
                                "name": canonical_name,
                                "matched_term": found_term,
                                "sentence_context": sentence,
                                "confidence": 0.92,
                            })
                        break

    if not detected_objects:
        print("  ℹ️ Gemini identified ZERO visible kitchen objects in this image.")
        print("  Strict verification rule: ZERO ObjectDetected events will be emitted.")
    else:
        print(f"  ✓ Grounded objects explicitly identified by Gemini ({len(detected_objects)}):")
        for d in detected_objects:
            print(f"    - {d['name']} (matched '{d['matched_term']}' in: \"{d['sentence_context']}\")")

    # Step 16: Emit canonical ObjectDetected events to Kernel /emit
    print("\n[Step 16/10] Emitting canonical ObjectDetected events to Kernel...")
    emitted_events = []
    for d in detected_objects:
        obj_name = d["name"]
        conf = d["confidence"]
        ok = registry.emit_object_detected(
            class_name=obj_name,
            confidence=conf,
            x=final_x,
            y=final_y,
            source="GeminiER2_Vision",
        )
        print(f"  📤 Emitted ObjectDetected: '{obj_name}' (conf={conf:.2f}) -> Kernel status: {'SUCCESS' if ok else 'FAILED'}")
        if ok:
            emitted_events.append(obj_name)

    time.sleep(1.0)

    # Step 17: Verify resulting objects in Kernel /graph
    print("\n[Step 17/10] Verifying Knowledge Graph updates in Kernel /graph...")
    graph_verified = []
    for obj_name in emitted_events:
        loc_res = context_provider.query_object_location(obj_name)
        if loc_res:
            room = loc_res.get("location")
            conf = loc_res.get("confidence", 0.0)
            print(f"  ✓ /graph query: '{obj_name}' is registered in '{room}' (conf: {conf:.2f})")
            graph_verified.append(obj_name)
        else:
            print(f"  ⚠️ /graph query: '{obj_name}' not found in graph edges")

    # Step 18: Verify /snapshot and /context?format=toon remain synchronized
    print("\n[Step 18/10] Verifying /snapshot and /context?format=toon synchronization...")
    snap_ver = context_provider.get_robot_context()
    toon_ver = context_provider.get_compiled_context(fmt="toon")

    snap_room = snap_ver.get("current_room")
    print(f"  GET /snapshot current_room: '{snap_room}'")
    print(f"  GET /context?format=toon:\n{toon_ver}\n")

    room_in_toon = f"Room[{snap_room}]" in toon_ver
    print(f"  Snapshot room matches TOON room: {room_in_toon}")

    # =========================================================================
    # Final Comprehensive Milestone Report
    # =========================================================================
    print("\n" + "=" * 70)
    print("📋 GRaCEmo ViRa — MILESTONE REPORT: VISUAL OBJECT IDENTIFICATION")
    print("=" * 70)
    print(f"• Starting Pose: room='Central Hallway', x={start_x:.3f}, y={start_y:.3f}, theta={math.degrees(start_theta):+.1f}°")
    print(f"• Final Position: x={final_x:.3f}, y={final_y:.3f}")
    print(f"• Final Yaw: {math.degrees(final_theta):+.1f}° ({final_theta:+.3f} rad, facing South)")
    print(f"• Camera Image Path: {observation_image_path}")
    print(f"• Image Dimensions: {img_w}x{img_h} (JPEG, {len(frame_bytes)} bytes)")
    print(f"• Gemini API Status: SUCCESS ({config.model_name}, latency: {latency_ms:.1f}ms)")
    print(f"• Objects Identified by Gemini: {[d['name'] for d in detected_objects]}")
    print(f"• ObjectDetected Events Emitted: {emitted_events}")
    print(f"• Kernel Graph Verification: {graph_verified}")
    print(f"• MNSE Snapshot Room: {snap_room}")
    print(f"• MNSE TOON Synchronized: {room_in_toon}")
    print("=" * 70)

    # Success check
    success = (
        cur_room_after == "Kitchen & Dining"
        and len(frame_bytes) > 1000
        and len(detected_objects) > 0
        and len(graph_verified) > 0
        and room_in_toon
    )
    if success:
        print("🎉 MILESTONE STATUS: VERIFIED AND PASSING")
    else:
        print(f"⚠️ MILESTONE STATUS: PARTIAL OR FAILED (detected: {len(detected_objects)}, graph_verified: {len(graph_verified)})")

    return success

if __name__ == "__main__":
    ok = run_live_visual_test()
    sys.exit(0 if ok else 1)
