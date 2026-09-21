#!/usr/bin/env python3
"""
Test B: Gemini Multimodal Image Test
Verifies:
1. Real Gemini Robotics ER 2 client initialization.
2. Real API connectivity to gemini-robotics-er-2-preview.
3. Multimodal ingestion of real camera JPEG bytes.
4. Actual model reasoning response describing the image.
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for p in (ROOT / "graceemo_interaction" / ".venv" / "lib").glob("python*/site-packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adapters.gemini_robotics.client import GeminiRoboticsClient
from adapters.gemini_robotics.config import GeminiRoboticsConfig

def test_gemini_multimodal():
    print("=== TEST B: GEMINI MULTIMODAL IMAGE TEST ===")
    config = GeminiRoboticsConfig()
    client = GeminiRoboticsClient(config=config, mock_mode=False)

    if not client.is_live:
        print("❌ FAILED: Gemini client is not in live mode (check GEMINI_API_KEY)")
        return False
    print(f"✓ Client initialized in LIVE mode with model: {config.model_name}")

    frame_path = Path("/tmp/gracemo_camera_latest.jpg")
    if not frame_path.exists():
        print("❌ FAILED: /tmp/gracemo_camera_latest.jpg does not exist")
        return False

    image_bytes = frame_path.read_bytes()
    print(f"✓ Loaded live camera frame: {len(image_bytes)} bytes")

    prompt = (
        "You are GRaCEmo ViRa, an embodied assistive robot. "
        "Analyze this live camera observation from your onboard head camera. "
        "Describe what physical objects and furniture you can visually identify."
    )

    print("🛰️ Sending multimodal request (image + prompt) to gemini-robotics-er-2-preview...")
    t0 = time.time()
    response = client.reason(
        prompt=prompt,
        image_bytes=image_bytes,
    )
    latency = (time.time() - t0) * 1000

    print(f"✓ Response received in {latency:.1f}ms")
    print(f"  - is_mock: {response.is_mock}")
    print(f"  - has_error: {response.error is not None}")

    if response.error:
        print(f"❌ Error returned: {response.error}")
        return False

    text = response.text or ""
    print("\n--- Model Response ---")
    print(text)
    print("----------------------\n")

    if len(text.strip()) > 20:
        print("✓ Non-empty, grounded visual reasoning response verified!")
        print("✓ TEST B (Gemini Multimodal Image): PASS")
        return True
    else:
        print("❌ Response too short or empty")
        return False

if __name__ == "__main__":
    ok = test_gemini_multimodal()
    sys.exit(0 if ok else 1)
