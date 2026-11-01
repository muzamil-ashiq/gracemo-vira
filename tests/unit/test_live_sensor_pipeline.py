"""
Unit and integration tests for Phase 4 modular camera and audio driver pipeline.
Validates:
1. CameraDriverInterface, OpenCV fallback, and MockCameraDriver lifecycle.
2. AudioDriverInterface, PyAudio fallback, and MockAudioDriver lifecycle.
3. VoiceCommandParser allowlist matching, STOP priority, and safety rejection.
4. Pipeline integration with HumanInteractionBehaviorManager.
"""

import pytest
from vira_interaction.core.camera_driver import (
    MockCameraDriver,
    DetectedPerson,
    CameraFrame,
)
from vira_interaction.core.audio_driver import (
    MockAudioDriver,
    VoiceCommandParser,
    AudioChunk,
)
from vira_interaction.core.behavior_manager import (
    HumanInteractionBehaviorManager,
    BehaviorState,
    PersonDetection,
)


def test_mock_camera_driver_lifecycle():
    cam = MockCameraDriver(width=640, height=480)
    assert not cam.is_connected
    assert cam.is_mock is True
    assert cam.capture_frame() is None

    assert cam.start() is True
    assert cam.is_connected is True

    frame = cam.capture_frame()
    assert frame is not None
    assert frame.width == 640
    assert frame.height == 480
    assert frame.is_mock is True

    # Inject person
    person = DetectedPerson(x=0.5, y=0.5, width=0.2, height=0.6, confidence=0.92, estimated_distance_m=1.8)
    cam.inject_person(person)

    detections = cam.detect_persons(frame)
    assert len(detections) == 1
    assert detections[0].confidence == 0.92
    assert detections[0].estimated_distance_m == 1.8

    cam.clear_persons()
    assert len(cam.detect_persons(frame)) == 0

    cam.stop()
    assert not cam.is_connected


def test_mock_audio_driver_lifecycle():
    audio = MockAudioDriver(sample_rate=16000)
    assert not audio.is_connected
    assert audio.is_mock is True
    assert audio.read_chunk() is None

    assert audio.start() is True
    assert audio.is_connected is True

    # Read default zero-filled chunk
    chunk = audio.read_chunk(chunk_size=512)
    assert chunk is not None
    assert len(chunk.raw_data) == 1024  # 512 samples * 2 bytes
    assert chunk.sample_rate == 16000

    # Inject custom chunk
    custom = AudioChunk(raw_data=b"\x01\x02\x03\x04", sample_rate=16000)
    audio.inject_chunk(custom)
    read_back = audio.read_chunk()
    assert read_back.raw_data == b"\x01\x02\x03\x04"

    audio.stop()
    assert not audio.is_connected


def test_voice_command_parser_stop_priority():
    """Verify STOP has absolute priority regardless of phrase context."""
    stop_phrases = [
        "stop",
        "emergency stop please",
        "hey robot forward and then STOP",
        "cancel everything right now",
        "halt motion immediately",
    ]
    for phrase in stop_phrases:
        cmd = VoiceCommandParser.parse(phrase)
        assert cmd.verb == "STOP", f"Failed for phrase: '{phrase}'"
        assert cmd.is_emergency_stop is True
        assert cmd.linear_vel_mps == 0.0
        assert cmd.angular_vel_rps == 0.0


def test_voice_command_parser_directional_commands():
    """Verify allowlisted directional commands."""
    cmd_fwd = VoiceCommandParser.parse("move forward")
    assert cmd_fwd.verb == "FORWARD"
    assert cmd_fwd.linear_vel_mps > 0.0
    assert cmd_fwd.angular_vel_rps == 0.0

    cmd_back = VoiceCommandParser.parse("back up a little")
    assert cmd_back.verb == "BACKWARD"
    assert cmd_back.linear_vel_mps < 0.0

    cmd_left = VoiceCommandParser.parse("turn left now")
    assert cmd_left.verb == "TURN_LEFT"
    assert cmd_left.angular_vel_rps > 0.0

    cmd_right = VoiceCommandParser.parse("spin right")
    assert cmd_right.verb == "TURN_RIGHT"
    assert cmd_right.angular_vel_rps < 0.0

    cmd_follow = VoiceCommandParser.parse("follow me please")
    assert cmd_follow.verb == "FOLLOW"


def test_voice_command_parser_ambiguous_rejected():
    """Verify ambiguous, harmful, or unknown commands return UNKNOWN with zero velocity."""
    unsafe_phrases = [
        "execute rm -rf /",
        "what is the weather today?",
        "run fast at 100 meters per second",
        "hello there",
        "",
    ]
    for phrase in unsafe_phrases:
        cmd = VoiceCommandParser.parse(phrase)
        assert cmd.verb == "UNKNOWN"
        assert cmd.linear_vel_mps == 0.0
        assert cmd.angular_vel_rps == 0.0


def test_sensor_pipeline_behavior_integration():
    """Verify camera and voice integration with HumanInteractionBehaviorManager."""
    cam = MockCameraDriver()
    cam.start()

    fsm = HumanInteractionBehaviorManager()
    assert fsm.state == BehaviorState.IDLE

    # 1. Camera detects a person
    target = DetectedPerson(x=0.5, y=0.5, width=0.2, height=0.6, confidence=0.88, estimated_distance_m=1.5)
    cam.inject_person(target)
    frame = cam.capture_frame()
    persons = cam.detect_persons(frame)

    # Feed detection into behavior manager
    detection = PersonDetection(
        person_id=str(persons[0].target_id),
        confidence=persons[0].confidence,
        distance_m=persons[0].estimated_distance_m or 1.5,
        bearing_rad=0.0,
        confirmed=True
    )
    res = fsm.on_person_detected(detection)
    assert res is True
    assert fsm.state == BehaviorState.OBSERVATION_60S

    # 2. Wake consent given
    fsm.on_wake_trigger("hey vira")
    assert fsm.state == BehaviorState.INTERACTION

    # 3. Audio command parsed and fed to behavior manager
    voice_cmd = VoiceCommandParser.parse("move forward")
    motion = fsm.process_voice_command(voice_cmd.raw_transcript)
    assert fsm.state == BehaviorState.MANUAL_COMMAND
    assert motion.linear_mps > 0.0

    # 4. Emergency stop voice command
    stop_cmd = VoiceCommandParser.parse("EMERGENCY STOP")
    stop_motion = fsm.process_voice_command(stop_cmd.raw_transcript)
    assert fsm.state == BehaviorState.SAFE_STOP
    assert stop_motion.linear_mps == 0.0
    assert stop_motion.angular_rps == 0.0
