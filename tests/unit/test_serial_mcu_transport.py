"""
Unit tests for SerialMCUTransport streaming buffer, frame splitting,
checksum validation, oversized frame recovery, and telemetry timeout.
"""

import time
import pytest
from gracemo_hardware.mcu_transport import (
    SerialMCUTransport,
    MCUCommand,
    MCUTelemetry,
    MCUConnectionState,
    MCUFault,
)
from gracemo_hardware.mcu_protocol import calculate_xor_checksum


def test_serial_transport_safety_guards_default():
    """Verify that PROTOCOL_CONFIRMED is False by default and blocks operations."""
    transport = SerialMCUTransport()
    assert transport.PROTOCOL_CONFIRMED is False

    with pytest.raises(RuntimeError, match="Protocol not confirmed"):
        transport.connect()

    with pytest.raises(RuntimeError, match="Protocol not confirmed"):
        transport.send_command(MCUCommand(linear_vel_mps=0.1))

    with pytest.raises(RuntimeError, match="Protocol not confirmed"):
        transport.send_estop()


def test_feed_bytes_single_valid_frame():
    """Verify feeding a complete valid TELEM frame."""
    transport = SerialMCUTransport()
    received = []
    transport.on_telemetry(lambda t: received.append(t))

    payload = "TELEM,1,0.100,0.200,100,200,0.010,0.020,0.030,12.40,0,0"
    chk = calculate_xor_checksum(payload)
    frame = f"{payload}*{chk}\n".encode("ascii")

    count = transport.feed_bytes(frame)
    assert count == 1
    assert len(received) == 1
    assert received[0].heartbeat_seq == 1
    assert received[0].left_wheel_vel_mps == 0.1
    assert received[0].battery_voltage_v == 12.4
    assert transport.frames_received == 1
    assert transport.checksum_errors == 0


def test_feed_bytes_split_chunks():
    """Verify feeding a frame split across multiple incoming OS reads."""
    transport = SerialMCUTransport()
    received = []
    transport.on_telemetry(lambda t: received.append(t))

    payload = "TELEM,42,0.000,0.000,0,0,0.000,0.000,0.000,12.50,0,0"
    chk = calculate_xor_checksum(payload)
    full_frame = f"{payload}*{chk}\n"

    chunk1 = full_frame[:15].encode("ascii")
    chunk2 = full_frame[15:30].encode("ascii")
    chunk3 = full_frame[30:].encode("ascii")

    assert transport.feed_bytes(chunk1) == 0
    assert len(received) == 0

    assert transport.feed_bytes(chunk2) == 0
    assert len(received) == 0

    assert transport.feed_bytes(chunk3) == 1
    assert len(received) == 1
    assert received[0].heartbeat_seq == 42


def test_feed_bytes_concatenated_multiple_frames():
    """Verify multiple frames arriving in a single read buffer."""
    transport = SerialMCUTransport()
    received = []
    transport.on_telemetry(lambda t: received.append(t))

    p1 = "TELEM,10,0.050,0.050,10,10,0.001,0.001,0.000,12.30,0,0"
    p2 = "TELEM,11,0.060,0.060,20,20,0.002,0.002,0.000,12.30,0,0"
    p3 = "TELEM,12,0.070,0.070,30,30,0.003,0.003,0.000,12.30,0,0"

    buffer = (
        f"{p1}*{calculate_xor_checksum(p1)}\n"
        f"{p2}*{calculate_xor_checksum(p2)}\n"
        f"{p3}*{calculate_xor_checksum(p3)}\n"
    ).encode("ascii")

    count = transport.feed_bytes(buffer)
    assert count == 3
    assert len(received) == 3
    assert [t.heartbeat_seq for t in received] == [10, 11, 12]


def test_feed_bytes_oversized_frame_recovery():
    """Verify recovery after encountering an oversized junk frame (>96 chars)."""
    transport = SerialMCUTransport()
    received = []
    transport.on_telemetry(lambda t: received.append(t))

    junk = "JUNK" * 30 + "\n"  # 120 chars > 96
    valid_payload = "TELEM,99,0.000,0.000,0,0,0.000,0.000,0.000,12.00,0,0"
    valid = f"{valid_payload}*{calculate_xor_checksum(valid_payload)}\n"

    stream = (junk + valid).encode("ascii")
    count = transport.feed_bytes(stream)

    assert count == 1
    assert len(received) == 1
    assert received[0].heartbeat_seq == 99
    assert transport.malformed_frames >= 1


def test_feed_bytes_checksum_failure_rejection():
    """Verify that a corrupted checksum is rejected."""
    transport = SerialMCUTransport()
    received = []
    transport.on_telemetry(lambda t: received.append(t))

    bad_frame = b"TELEM,5,0.000,0.000,0,0,0.000,0.000,0.000,12.00,0,0*FF\n"
    count = transport.feed_bytes(bad_frame)

    assert count == 0
    assert len(received) == 0
    assert transport.checksum_errors == 1


def test_telemetry_freshness_watchdog():
    """Verify that telemetry silence beyond timeout trips fault."""
    faults = []
    transport = SerialMCUTransport(telemetry_timeout_sec=0.2)
    transport.on_fault(lambda f: faults.append(f))

    # Manually transition to connected state for watchdog verification
    transport._connection_state = MCUConnectionState.CONNECTED
    transport._last_heartbeat = 100.0

    # Fresh within timeout
    assert transport.check_telemetry_freshness(now=100.1) is True
    assert transport.connection_state == MCUConnectionState.CONNECTED

    # Stale beyond timeout
    assert transport.check_telemetry_freshness(now=100.3) is False
    assert transport.connection_state == MCUConnectionState.TIMEOUT
    assert len(faults) == 1
    assert faults[0].source == "serial_telemetry_watchdog"
