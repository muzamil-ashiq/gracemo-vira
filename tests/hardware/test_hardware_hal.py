"""
Unit tests for the GRaCEmo ViRa Hardware Abstraction Layer (HAL).
Tests run WITHOUT real hardware — all physical hardware interactions use MockMCUTransport.

A passing test here does NOT verify physical hardware behavior.
Physical hardware validation must be performed separately on the actual robot.
"""

import math
import sys
import time
import threading
from pathlib import Path

# Add hardware package to path for import
ROOT = Path(__file__).resolve().parent.parent.parent
hw_pkg = ROOT / "ros2_ws" / "src" / "gracemo_hardware"
sys.path.insert(0, str(hw_pkg))

from gracemo_hardware.mcu_transport import (
    MockMCUTransport,
    SerialMCUTransport,
    MCUCommand,
    MCUFault,
    MCUTelemetry,
    MCUConnectionState,
    create_mcu_transport,
    MCU_DEFAULT_PORT,
    HW_MAX_LINEAR_VEL_MPS,
    HW_MAX_ANGULAR_VEL_RPS,
)
from gracemo_hardware.lidar_config import (
    LIDAR_PROFILES,
    validate_lidar_scan_msg,
    get_active_lidar_config,
    validate_lidar_profile,
    set_active_lidar_profile,
)


# ── Mock MCU: connect / disconnect ──────────────────────────────────────────

def test_mock_mcu_connects():
    transport = MockMCUTransport()
    assert transport.connection_state == MCUConnectionState.DISCONNECTED
    result = transport.connect()
    assert result is True
    assert transport.is_connected
    assert transport.connection_state == MCUConnectionState.CONNECTED
    transport.disconnect()
    assert transport.connection_state == MCUConnectionState.DISCONNECTED
    print("✓ MockMCU: connect / disconnect")


def test_mock_mcu_command_accepted():
    transport = MockMCUTransport()
    transport.connect()
    cmd = MCUCommand(linear_vel_mps=0.2, angular_vel_rps=0.1)
    ok = transport.send_command(cmd)
    assert ok is True
    transport.disconnect()
    print("✓ MockMCU: command accepted when connected")


def test_mock_mcu_command_rejected_when_disconnected():
    transport = MockMCUTransport()
    # Do NOT connect
    cmd = MCUCommand(linear_vel_mps=0.2, angular_vel_rps=0.0)
    ok = transport.send_command(cmd)
    assert ok is False
    print("✓ MockMCU: command rejected when not connected")


# ── Velocity clamping ───────────────────────────────────────────────────────

def test_velocity_clamping_positive_overspeed():
    transport = MockMCUTransport()
    transport.connect()
    # Send over-limit velocities
    raw_cmd = MCUCommand(linear_vel_mps=99.0, angular_vel_rps=99.0)
    clamped = transport._clamp_command(raw_cmd)
    assert clamped.linear_vel_mps <= HW_MAX_LINEAR_VEL_MPS
    assert clamped.angular_vel_rps <= HW_MAX_ANGULAR_VEL_RPS
    transport.disconnect()
    print(f"✓ Velocity clamped: linear≤{HW_MAX_LINEAR_VEL_MPS}, angular≤{HW_MAX_ANGULAR_VEL_RPS}")


def test_velocity_clamping_negative_overspeed():
    transport = MockMCUTransport()
    transport.connect()
    raw_cmd = MCUCommand(linear_vel_mps=-99.0, angular_vel_rps=-99.0)
    clamped = transport._clamp_command(raw_cmd)
    assert clamped.linear_vel_mps >= -HW_MAX_LINEAR_VEL_MPS
    assert clamped.angular_vel_rps >= -HW_MAX_ANGULAR_VEL_RPS
    transport.disconnect()
    print("✓ Negative velocity clamping")


def test_zero_velocity_command_accepted():
    transport = MockMCUTransport()
    transport.connect()
    ok = transport.send_command(MCUCommand(linear_vel_mps=0.0, angular_vel_rps=0.0))
    assert ok is True
    transport.disconnect()
    print("✓ Zero velocity accepted")


# ── Emergency stop ──────────────────────────────────────────────────────────

def test_estop_accepted():
    transport = MockMCUTransport()
    transport.connect()
    ok = transport.send_estop()
    assert ok is True
    transport.disconnect()
    print("✓ E-stop accepted by mock transport")


def test_physical_estop_triggers_fault():
    faults = []
    transport = MockMCUTransport()
    transport.on_fault(lambda f: faults.append(f))
    transport.connect()
    transport.inject_estop()
    # Give telemetry loop a moment to detect
    time.sleep(0.2)
    transport.disconnect()
    assert transport._telem.physical_estop_pressed is True
    print("✓ Physical e-stop injection detected in telemetry")


# ── MCU timeout / disconnection ─────────────────────────────────────────────

def test_mcu_disconnect_triggers_fault():
    faults = []
    transport = MockMCUTransport()
    transport.on_fault(lambda f: faults.append(f))
    transport.connect()
    time.sleep(0.05)  # Let it initialize
    transport.inject_disconnect()
    time.sleep(0.2)
    assert transport.connection_state in (
        MCUConnectionState.TIMEOUT,
        MCUConnectionState.DISCONNECTED,
        MCUConnectionState.FAULT,
    )
    assert len(faults) >= 1
    assert any(f.is_critical for f in faults)
    print(f"✓ MCU disconnection produced {len(faults)} critical fault(s)")


def test_mcu_simulated_fault_after_n_commands():
    faults = []
    transport = MockMCUTransport(simulate_fault_after_n_commands=3)
    transport.on_fault(lambda f: faults.append(f))
    transport.connect()
    for i in range(5):
        transport.send_command(MCUCommand(linear_vel_mps=0.1))
    time.sleep(0.1)
    transport.disconnect()
    assert len(faults) >= 1
    print(f"✓ Simulated MCU fault after N commands: {len(faults)} fault(s) received")


# ── Command watchdog ────────────────────────────────────────────────────────

def test_command_watchdog_zeros_velocity():
    transport = MockMCUTransport()
    transport.connect()
    # Send a non-zero command, then wait for watchdog to fire
    transport.send_command(MCUCommand(linear_vel_mps=0.3, angular_vel_rps=0.0))
    time.sleep(0.8)  # Longer than MCU_CMD_WATCHDOG_SEC (0.5s)
    assert abs(transport._telem.left_wheel_vel_mps) < 0.01
    assert abs(transport._telem.right_wheel_vel_mps) < 0.01
    transport.disconnect()
    print("✓ Command watchdog zeroed velocities after stale command")


# ── Telemetry callback ───────────────────────────────────────────────────────

def test_telemetry_callback_called():
    received = []
    transport = MockMCUTransport()
    transport.on_telemetry(lambda t: received.append(t))
    transport.connect()
    time.sleep(0.3)
    transport.disconnect()
    assert len(received) > 0
    assert isinstance(received[0], MCUTelemetry)
    print(f"✓ Telemetry callback called {len(received)} times in 300ms")


def test_mock_odometry_integrates():
    transport = MockMCUTransport()
    transport.connect()
    # Command forward motion
    transport.send_command(MCUCommand(linear_vel_mps=0.5, angular_vel_rps=0.0))
    time.sleep(0.5)
    transport.disconnect()
    # Robot should have moved forward
    assert transport._telem.odom_x > 0.1
    assert abs(transport._telem.odom_y) < 0.05
    print(f"✓ Odometry integration: x={transport._telem.odom_x:.3f}m after 0.5s at 0.5m/s")


# ── Factory ──────────────────────────────────────────────────────────────────

def test_factory_creates_mock():
    t = create_mcu_transport("mock")
    assert isinstance(t, MockMCUTransport)
    print("✓ Factory creates MockMCUTransport for 'mock'")


def test_factory_serial_not_confirmed():
    """SerialMCUTransport.connect() must raise until protocol is confirmed."""
    t = create_mcu_transport("serial")
    assert isinstance(t, SerialMCUTransport)
    try:
        t.connect()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Protocol not confirmed" in str(e)
    except NotImplementedError:
        pass  # Also acceptable
    print("✓ SerialMCUTransport raises before protocol confirmation (safe guard active)")


def test_factory_unknown_type_raises():
    try:
        create_mcu_transport("bluetooth_magic")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("✓ Factory raises ValueError for unknown transport type")


# ── LiDAR config validation ──────────────────────────────────────────────────

def test_lidar_profiles_populated():
    assert len(LIDAR_PROFILES) > 0
    for key, cfg in LIDAR_PROFILES.items():
        assert cfg.topic == "/scan", f"{key}: topic should be /scan"
        assert cfg.frame_id == "lidar_link", f"{key}: frame_id should be lidar_link"
        assert cfg.range_min_m >= 0.0
        assert cfg.range_max_m > cfg.range_min_m
    print(f"✓ {len(LIDAR_PROFILES)} LiDAR profiles validated")


def test_lidar_unknown_config_accepts_with_warning():
    ok, msg = validate_lidar_scan_msg(
        angle_min=-3.14, angle_max=3.14,
        range_min=0.15, range_max=12.0,
        ranges_count=360, frame_id="lidar_link"
    )
    assert ok is True  # No confirmed profile → accept with warning
    print("✓ LiDAR validation: accepts scan when profile not confirmed")


def test_lidar_invalid_scan_rejected():
    ok, reason = validate_lidar_scan_msg(
        angle_min=-3.14, angle_max=3.14,
        range_min=0.15, range_max=0.5,  # Suspicious max range
        ranges_count=360, frame_id="lidar_link"
    )
    # If no profile confirmed, still accepted
    # But if we configure a known profile:
    from gracemo_hardware import lidar_config
    original = lidar_config.ACTIVE_LIDAR_PROFILE_KEY
    lidar_config.ACTIVE_LIDAR_PROFILE_KEY = "rplidar_a1"
    ok2, reason2 = validate_lidar_scan_msg(
        angle_min=-3.14, angle_max=3.14,
        range_min=0.15, range_max=0.5,  # Too short for RPLiDAR
        ranges_count=360, frame_id="lidar_link"
    )
    lidar_config.ACTIVE_LIDAR_PROFILE_KEY = original
    assert ok2 is False
    print(f"✓ LiDAR validation: rejects scan with suspicious range_max ({reason2})")


def test_lidar_wrong_frame_rejected():
    from gracemo_hardware import lidar_config
    original = lidar_config.ACTIVE_LIDAR_PROFILE_KEY
    lidar_config.ACTIVE_LIDAR_PROFILE_KEY = "rplidar_a1"
    ok, reason = validate_lidar_scan_msg(
        angle_min=-3.14, angle_max=3.14,
        range_min=0.15, range_max=12.0,
        ranges_count=360, frame_id="wrong_frame"
    )
    lidar_config.ACTIVE_LIDAR_PROFILE_KEY = original
    assert ok is False
    assert "frame_id" in reason.lower()
    print(f"✓ LiDAR validation: rejects wrong frame_id ({reason})")


# ── Sim/hardware mode separation ─────────────────────────────────────────────

def test_sim_mode_does_not_require_mcu():
    """In sim mode, no MCU transport should be instantiated."""
    # This is validated by checking that MockMCU is the only transport
    # that can work without hardware confirmation. SerialMCUTransport must
    # raise if PROTOCOL_CONFIRMED is False.
    assert SerialMCUTransport.PROTOCOL_CONFIRMED is False, \
        "SerialMCUTransport.PROTOCOL_CONFIRMED must be False until validated on hardware"
    print("✓ SerialMCUTransport.PROTOCOL_CONFIRMED is False — hardware guard active")


def test_mock_transport_identified_as_mock():
    mock_t = MockMCUTransport()
    assert mock_t.is_mock is True
    serial_t = SerialMCUTransport()
    assert serial_t.is_mock is False
    print("✓ Mock vs Real transport is_mock property separation verified")


def test_serial_transport_send_command_blocked_by_protocol_guard():
    serial_t = SerialMCUTransport()
    assert SerialMCUTransport.PROTOCOL_CONFIRMED is False
    try:
        serial_t.send_command(MCUCommand(linear_vel_mps=0.1))
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Protocol not confirmed" in str(e)
    print("✓ SerialMCUTransport.send_command blocked by safety protocol guard")


def test_serial_transport_send_estop_blocked_by_protocol_guard():
    serial_t = SerialMCUTransport()
    assert SerialMCUTransport.PROTOCOL_CONFIRMED is False
    try:
        serial_t.send_estop()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Protocol not confirmed" in str(e)
    print("✓ SerialMCUTransport.send_estop blocked by safety protocol guard")


def test_lidar_profile_validation_supported():
    for p in ("rplidar_a1", "rplidar_a2", "ydlidar_x4", "ldrobot_ld19"):
        ok, msg = validate_lidar_profile(p)
        assert ok is True, f"Profile {p} should be valid"
    print("✓ Supported LiDAR profiles validated successfully")


def test_lidar_profile_validation_unsupported():
    ok, msg = validate_lidar_profile("unknown_sensor_9000")
    assert ok is False
    assert "Unsupported LiDAR profile" in msg
    print("✓ Unsupported LiDAR profile rejected with clear error")


def test_set_active_lidar_profile_success_and_failure():
    from gracemo_hardware import lidar_config
    orig = lidar_config.ACTIVE_LIDAR_PROFILE_KEY
    cfg = set_active_lidar_profile("rplidar_a2")
    assert cfg.model == "RPLiDAR A2M8"
    assert lidar_config.ACTIVE_LIDAR_PROFILE_KEY == "rplidar_a2"

    try:
        set_active_lidar_profile("invalid_profile")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported LiDAR profile" in str(e)

    lidar_config.ACTIVE_LIDAR_PROFILE_KEY = orig
    print("✓ set_active_lidar_profile successfully configures profile and rejects invalid key")


def test_lidar_port_separation_from_mcu():
    assert MCU_DEFAULT_PORT == "/dev/ttyUSB0"
    for key, p in LIDAR_PROFILES.items():
        assert p.default_port != MCU_DEFAULT_PORT, f"LiDAR {key} must have separate port from MCU"
    print("✓ LiDAR default ports verified distinct from MCU serial port")


def test_nav2_hardware_params_use_sim_time_false():
    nav_hw_params_path = (
        ROOT
        / "ros2_ws"
        / "src"
        / "gracemo_nav2"
        / "config"
        / "nav2_physical_params.yaml"
    )
    if not nav_hw_params_path.exists():
        nav_hw_params_path = (
            ROOT
            / "ros2_ws"
            / "src"
            / "gracemo_navigation"
            / "config"
            / "nav2_params_hardware.yaml"
        )
    assert nav_hw_params_path.exists(), f"Nav2 physical params must exist at {nav_hw_params_path}"
    text = nav_hw_params_path.read_text()
    assert "use_sim_time: False" in text or "use_sim_time: false" in text
    assert "use_sim_time: True" not in text and "use_sim_time: true" not in text
    print(f"✓ {nav_hw_params_path.name} verified to have use_sim_time: False throughout")


def test_hardware_launch_defaults_to_hardware_nav_params():
    hw_launch_path = (
        ROOT
        / "ros2_ws"
        / "src"
        / "gracemo_hardware"
        / "launch"
        / "hardware.launch.py"
    )
    assert hw_launch_path.exists(), "hardware.launch.py must exist"
    text = hw_launch_path.read_text()
    assert "params_file" in text
    assert "lidar_port" in text
    print("✓ hardware.launch.py verified to declare params_file and lidar_port")


if __name__ == "__main__":
    # Run all tests
    tests = [
        test_mock_mcu_connects,
        test_mock_mcu_command_accepted,
        test_mock_mcu_command_rejected_when_disconnected,
        test_velocity_clamping_positive_overspeed,
        test_velocity_clamping_negative_overspeed,
        test_zero_velocity_command_accepted,
        test_estop_accepted,
        test_physical_estop_triggers_fault,
        test_mcu_disconnect_triggers_fault,
        test_mcu_simulated_fault_after_n_commands,
        test_command_watchdog_zeros_velocity,
        test_telemetry_callback_called,
        test_mock_odometry_integrates,
        test_factory_creates_mock,
        test_factory_serial_not_confirmed,
        test_factory_unknown_type_raises,
        test_lidar_profiles_populated,
        test_lidar_unknown_config_accepts_with_warning,
        test_lidar_invalid_scan_rejected,
        test_lidar_wrong_frame_rejected,
        test_sim_mode_does_not_require_mcu,
        test_mock_transport_identified_as_mock,
        test_serial_transport_send_command_blocked_by_protocol_guard,
        test_serial_transport_send_estop_blocked_by_protocol_guard,
        test_lidar_profile_validation_supported,
        test_lidar_profile_validation_unsupported,
        test_set_active_lidar_profile_success_and_failure,
        test_lidar_port_separation_from_mcu,
        test_nav2_hardware_params_use_sim_time_false,
        test_hardware_launch_defaults_to_hardware_nav_params,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{len(tests)} hardware HAL tests passed.")
