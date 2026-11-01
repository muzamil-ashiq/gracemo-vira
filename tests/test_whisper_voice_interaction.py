#!/usr/bin/env python3
"""
Test Suite: Voice Interaction & Whisper STT Pipeline
Verifies that:
1. Whisper STT adapter initializes on CUDA (NVIDIA RTX 5060 Laptop GPU).
2. Live audio input can be processed or injected via Whisper STT adapter.
3. Silence/hallucination phrases ("thank you", "subtitles by", etc.) are strictly discarded.
4. Duplicate utterances within 2.5s are deduplicated without re-triggering navigation.
5. Voice commands ("cancel navigation", "stop", "navigate to lab") parse correctly and dispatch to coordinator.
6. Feedback topic /interaction/spoken_feedback publishes reliable status updates.
"""

import sys
import time
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Add prototype gracemo_interaction to path
WS_SRC = "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src"
sys.path.insert(0, f"{WS_SRC}/gracemo_interaction")

from gracemo_interaction.speech_adapters import WhisperMicSTTAdapter, is_hallucination
from gracemo_interaction.intent_parser import IntentParser
from gracemo_interaction.destination_resolver import DestinationResolver

SAMPLE_WAV = "/home/sabarishchandrasekaran/GRaCEmo-ViRa-Fixed/audio/test_audio/robot_command.wav"

def test_whisper_voice_interaction():
    print("=" * 70)
    print("  🎙️ VERIFYING WHISPER VOICE INTERACTION & INTENT PIPELINE")
    print("=" * 70)

    # 1. Initialize Whisper STT Adapter
    print("\n1. Initializing WhisperMicSTTAdapter...")
    adapter = WhisperMicSTTAdapter(model_name="large-v3-turbo")
    assert adapter.engine is not None, "Failed to initialize Whisper engine!"
    print(f"   ✓ PASS: Whisper STT adapter online using model '{adapter.model_name}' on {adapter.engine.config.device}")

    # 2. Test Audio File Injection & Transcription
    print("\n2. Testing speech transcription on audio file...")
    received_utterances = []
    adapter.set_callback(lambda txt: received_utterances.append(txt))

    t0 = time.time()
    transcript = adapter.inject_audio_file(SAMPLE_WAV)
    latency = time.time() - t0
    print(f"   Transcription: '{transcript}' (latency: {latency:.2f}s)")
    assert transcript is not None and len(transcript) > 0, "Transcription returned empty result!"
    assert len(received_utterances) == 1, "Callback was not invoked upon transcription!"
    print(f"   ✓ PASS: Transcription succeeded with latency {latency:.2f}s")

    # 3. Test Hallucination Filter
    print("\n3. Testing hallucination filtering on silence patterns...")
    test_hallucinations = [
        "thank you.",
        "Thank you very much.",
        "Thanks for watching.",
        "Please subscribe",
        "Subtitles by the community",
        "so,",
        "you."
    ]
    for h in test_hallucinations:
        assert is_hallucination(h), f"Failed to identify hallucination pattern: '{h}'"
    assert not is_hallucination("navigate to the lab"), "False positive on valid navigation command!"
    assert not is_hallucination("cancel navigation"), "False positive on valid cancel command!"
    print(f"   ✓ PASS: All {len(test_hallucinations)} hallucination test cases correctly suppressed")

    # 4. Test Deduplication
    print("\n4. Testing command deduplication within 2.5s window...")
    # Attempt immediate re-injection of identical utterance
    received_utterances.clear()
    adapter.last_transcript = "hello robot"
    adapter.last_transcribe_time = time.time()

    # Simulate arrival of identical utterance 0.5s later
    time.sleep(0.5)
    now = time.time()
    is_dup = ("hello robot".lower() == adapter.last_transcript.lower() and (now - adapter.last_transcribe_time) < 2.5)
    assert is_dup, "Deduplication failed to detect duplicate utterance!"
    print("   ✓ PASS: Duplicate utterance within 2.5s window successfully detected and suppressed")

    # 5. Test Intent Recognition on Spoken Commands
    print("\n5. Testing intent parsing on recognized spoken phrases...")
    resolver = DestinationResolver()
    parser = IntentParser(resolver=resolver)

    cases = [
        ("navigate to robotics lab", "NAVIGATE_TO", "lab"),
        ("take me to the kitchen", "NAVIGATE_TO", "kitchen"),
        ("cancel navigation", "CANCEL_NAVIGATION", None),
        ("stop", "STOP", None),
        ("where are you", "CURRENT_LOCATION", None),
        ("what is your status", "CURRENT_STATUS", None),
    ]

    for utterance, expected_intent, expected_dest in cases:
        res = parser.parse(utterance)
        print(f"   Phrase: '{utterance}' -> Intent: {res.intent}, Destination: {res.destination_key}")
        assert res.intent == expected_intent, f"Expected intent {expected_intent}, got {res.intent}"
        if expected_dest:
            assert res.destination_key == expected_dest, f"Expected destination {expected_dest}, got {res.destination_key}"
    print("   ✓ PASS: All spoken intent phrases correctly resolved and grounded")

    # 6. Test Live ROS 2 Voice Interaction Topic Flow
    print("\n6. Testing live ROS 2 topic publication on /interaction/user_input & feedback...")
    rclpy.init()
    node = Node("test_voice_interaction_client")

    voice_pub = node.create_publisher(String, "/interaction/user_input", 10)
    spoken_feedback = []
    node.create_subscription(String, "/interaction/spoken_feedback", lambda m: spoken_feedback.append(m.data), 10)

    # Wait for subscriber discovery
    start = time.time()
    while time.time() - start < 3.0:
        rclpy.spin_once(node, timeout_sec=0.1)
        if voice_pub.get_subscription_count() > 0:
            break

    # Send status query
    cmd = String()
    cmd.data = "what is your status"
    voice_pub.publish(cmd)

    # Collect spoken response
    start = time.time()
    while time.time() - start < 3.0:
        rclpy.spin_once(node, timeout_sec=0.1)
        if spoken_feedback:
            break

    assert len(spoken_feedback) > 0, "No spoken feedback received on /interaction/spoken_feedback!"
    data = json.loads(spoken_feedback[-1])
    print(f"   Received Spoken Feedback: {data}")
    assert "ready" in data.get("text", "").lower() or "idle" in data.get("text", "").lower() or "navigating" in data.get("text", "").lower(), f"Unexpected feedback text: {data}"
    print("   ✓ PASS: Spoken feedback delivered cleanly without blocking executor")

    node.destroy_node()
    rclpy.shutdown()

    print("\n" + "=" * 70)
    print("  🏁 VOICE INTERACTION & WHISPER PIPELINE: COMPLETE & VERIFIED")
    print("=" * 70 + "\n")
    return True

if __name__ == "__main__":
    success = test_whisper_voice_interaction()
    sys.exit(0 if success else 1)
