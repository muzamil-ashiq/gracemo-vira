"""
GRaCEmo ViRa — MCU Transport Abstraction Layer
===============================================
Provides a transport-agnostic interface between ROS 2 and the STM32 MCU.

IMPORTANT: The actual STM32 firmware protocol, serial port, baud rate, and CAN
bus configuration MUST be confirmed against the physical hardware before use.
This file provides the interface contract and a fully functional mock transport
for automated testing. The real serial transport is a skeleton that must be
completed once the hardware and firmware are available.

Confirmed robot geometry (from gracemo_vira.urdf.xacro + gazebo_plugins.xacro):
  wheel_separation:  0.34 m
  wheel_radius:      0.065 m
  base_frame:        base_footprint
  odom_frame:        odom
  lidar_frame:       lidar_link (to be confirmed on hardware)

All parameters labelled [PENDING] require physical hardware confirmation.
"""

from __future__ import annotations

import abc
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

log = logging.getLogger("gracemo.hardware.mcu_transport")

# ---------------------------------------------------------------------------
# Protocol constants — MUST be validated against actual STM32 firmware
# ---------------------------------------------------------------------------

# [PENDING] — confirm baud rate with firmware team / from STM32 firmware source
MCU_DEFAULT_BAUD_RATE: int = 115200

# [PENDING] — confirm USB/UART device path on Jetson Orin Nano
MCU_DEFAULT_PORT: str = "/dev/ttyUSB0"

# Heartbeat timeout: if no MCU heartbeat received within this period, fault
MCU_HEARTBEAT_TIMEOUT_SEC: float = 1.0

# Command watchdog: zero velocity if no command received within this period
MCU_CMD_WATCHDOG_SEC: float = 0.5

# Maximum safe velocities for hardware (conservative until tuned on real robot)
# These are intentionally lower than simulation limits.
HW_MAX_LINEAR_VEL_MPS: float = 0.35   # m/s  [PENDING: confirm with motor controller ratings]
HW_MAX_ANGULAR_VEL_RPS: float = 0.75  # rad/s [PENDING: confirm with motor controller ratings]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class MCUConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    FAULT = "FAULT"
    TIMEOUT = "TIMEOUT"


@dataclass
class MCUTelemetry:
    """Telemetry received from the STM32 MCU."""
    timestamp: float = 0.0
    left_wheel_vel_mps: float = 0.0
    right_wheel_vel_mps: float = 0.0
    left_encoder_ticks: int = 0
    right_encoder_ticks: int = 0
    odom_x: float = 0.0
    odom_y: float = 0.0
    odom_yaw: float = 0.0
    battery_voltage_v: float = 0.0          # [PENDING: actual voltage range]
    physical_estop_pressed: bool = False
    mcu_fault_code: int = 0                 # [PENDING: define fault code enum with firmware]
    heartbeat_seq: int = 0


@dataclass
class MCUCommand:
    """Command to send to the STM32 MCU."""
    linear_vel_mps: float = 0.0    # bounded to HW_MAX_LINEAR_VEL_MPS
    angular_vel_rps: float = 0.0   # bounded to HW_MAX_ANGULAR_VEL_RPS
    emergency_stop: bool = False
    seq: int = 0                   # Incremented each command for freshness check


@dataclass
class MCUFault:
    """Structured hardware fault report."""
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    code: int = 0
    description: str = ""
    is_critical: bool = False


# ---------------------------------------------------------------------------
# Abstract base transport
# ---------------------------------------------------------------------------

class BaseMCUTransport(abc.ABC):
    """Abstract interface for MCU communication transports."""

    def __init__(
        self,
        wheel_separation_m: float = 0.34,
        wheel_radius_m: float = 0.065,
    ):
        self.wheel_separation_m = wheel_separation_m
        self.wheel_radius_m = wheel_radius_m
        self._connection_state = MCUConnectionState.DISCONNECTED
        self._fault_callback: Optional[Callable[[MCUFault], None]] = None
        self._telemetry_callback: Optional[Callable[[MCUTelemetry], None]] = None
        self._seq = 0

    @property
    def is_mock(self) -> bool:
        """Indicates whether this transport is a simulation/mock."""
        return False

    @property
    def connection_state(self) -> MCUConnectionState:
        return self._connection_state

    @property
    def is_connected(self) -> bool:
        return self._connection_state == MCUConnectionState.CONNECTED

    def on_fault(self, callback: Callable[[MCUFault], None]) -> None:
        self._fault_callback = callback

    def on_telemetry(self, callback: Callable[[MCUTelemetry], None]) -> None:
        self._telemetry_callback = callback

    @abc.abstractmethod
    def connect(self) -> bool:
        """Open the transport. Returns True if successful."""
        ...

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close the transport cleanly."""
        ...

    @abc.abstractmethod
    def send_command(self, cmd: MCUCommand) -> bool:
        """Send a velocity command. Returns True if sent successfully."""
        ...

    @abc.abstractmethod
    def send_estop(self) -> bool:
        """Send an immediate emergency stop. Must be callable from any thread."""
        ...

    def _clamp_command(self, cmd: MCUCommand) -> MCUCommand:
        """Enforce hardware velocity limits."""
        cmd.linear_vel_mps = max(
            -HW_MAX_LINEAR_VEL_MPS,
            min(HW_MAX_LINEAR_VEL_MPS, cmd.linear_vel_mps)
        )
        cmd.angular_vel_rps = max(
            -HW_MAX_ANGULAR_VEL_RPS,
            min(HW_MAX_ANGULAR_VEL_RPS, cmd.angular_vel_rps)
        )
        return cmd

    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) % 65536
        return self._seq


# ---------------------------------------------------------------------------
# MOCK transport — for automated testing only
# ---------------------------------------------------------------------------

class MockMCUTransport(BaseMCUTransport):
    """
    Mock MCU transport for automated testing.
    Simulates MCU telemetry based on commanded velocities with simple kinematics.
    This is NOT a hardware interface. Tests using this transport do NOT verify
    physical hardware behavior.
    """

    @property
    def is_mock(self) -> bool:
        return True

    def __init__(
        self,
        wheel_separation_m: float = 0.34,
        wheel_radius_m: float = 0.065,
        simulate_fault_after_n_commands: Optional[int] = None,
        simulate_disconnect_after_sec: Optional[float] = None,
    ):
        super().__init__(wheel_separation_m, wheel_radius_m)
        self._simulate_fault_n = simulate_fault_after_n_commands
        self._simulate_disconnect_sec = simulate_disconnect_after_sec

        self._telem = MCUTelemetry()
        self._lock = threading.Lock()
        self._cmd_count = 0
        self._last_cmd_time: float = 0.0
        self._connect_time: float = 0.0
        self._active = False
        self._bg_thread: Optional[threading.Thread] = None

        # Injected fault state for test scenarios
        self._inject_estop = False
        self._inject_mcu_fault = False
        self._inject_timeout = False

    def connect(self) -> bool:
        with self._lock:
            self._connection_state = MCUConnectionState.CONNECTED
            self._active = True
            self._connect_time = time.time()
            self._last_cmd_time = time.time()
        log.warning("[MOCK_MCU] Connected in MOCK mode (simulated kinematics). Physical motors are NOT being controlled.")
        self._bg_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self._bg_thread.start()
        return True

    def disconnect(self) -> None:
        with self._lock:
            self._active = False
            self._connection_state = MCUConnectionState.DISCONNECTED
        if self._bg_thread:
            self._bg_thread.join(timeout=1.0)
        log.info("[MOCK_MCU] Disconnected")

    def send_command(self, cmd: MCUCommand) -> bool:
        if not self.is_connected:
            return False
        cmd = self._clamp_command(cmd)
        with self._lock:
            self._cmd_count += 1
            self._last_cmd_time = time.time()
            # Simple kinematic update for mock telemetry
            self._telem.left_wheel_vel_mps = cmd.linear_vel_mps - \
                cmd.angular_vel_rps * self.wheel_separation_m / 2.0
            self._telem.right_wheel_vel_mps = cmd.linear_vel_mps + \
                cmd.angular_vel_rps * self.wheel_separation_m / 2.0

            # Simulate fault injection
            if self._simulate_fault_n and self._cmd_count >= self._simulate_fault_n:
                self._inject_mcu_fault = True

        if self._inject_mcu_fault and self._fault_callback:
            fault = MCUFault(
                source="mock",
                code=0xFF,
                description="Simulated MCU fault for testing",
                is_critical=True,
            )
            self._fault_callback(fault)
            self._inject_mcu_fault = False

        return True

    def send_estop(self) -> bool:
        with self._lock:
            self._telem.left_wheel_vel_mps = 0.0
            self._telem.right_wheel_vel_mps = 0.0
            if self._inject_estop:
                self._telem.physical_estop_pressed = True
        log.info("[MockMCU] E-STOP sent")
        return True

    def inject_estop(self):
        """Test helper: simulate physical e-stop button press."""
        with self._lock:
            self._inject_estop = True
            self._telem.physical_estop_pressed = True

    def inject_disconnect(self):
        """Test helper: simulate MCU disconnection."""
        with self._lock:
            self._connection_state = MCUConnectionState.TIMEOUT
            self._active = False
        if self._fault_callback:
            self._fault_callback(MCUFault(
                source="mock",
                code=0x01,
                description="Simulated MCU disconnection",
                is_critical=True,
            ))

    def inject_timeout(self):
        """Test helper: simulate heartbeat timeout."""
        with self._lock:
            self._inject_timeout = True

    def _telemetry_loop(self):
        dt = 0.05  # 20 Hz
        while True:
            with self._lock:
                if not self._active:
                    break
                # Check simulated disconnect
                if self._simulate_disconnect_sec:
                    if time.time() - self._connect_time > self._simulate_disconnect_sec:
                        self._connection_state = MCUConnectionState.TIMEOUT
                        self._active = False
                        break

                # Check command watchdog
                age = time.time() - self._last_cmd_time
                if age > MCU_CMD_WATCHDOG_SEC and (
                    abs(self._telem.left_wheel_vel_mps) > 0.001 or
                    abs(self._telem.right_wheel_vel_mps) > 0.001
                ):
                    log.warning("[MockMCU] Command watchdog: zeroing velocities")
                    self._telem.left_wheel_vel_mps = 0.0
                    self._telem.right_wheel_vel_mps = 0.0

                # Update mock odometry
                v_l = self._telem.left_wheel_vel_mps
                v_r = self._telem.right_wheel_vel_mps
                v = (v_l + v_r) / 2.0
                omega = (v_r - v_l) / self.wheel_separation_m
                self._telem.odom_x += v * math.cos(self._telem.odom_yaw) * dt
                self._telem.odom_y += v * math.sin(self._telem.odom_yaw) * dt
                self._telem.odom_yaw += omega * dt
                self._telem.timestamp = time.time()
                self._telem.heartbeat_seq = (self._telem.heartbeat_seq + 1) % 65536
                self._telem.battery_voltage_v = 12.4  # nominal mock
                telem_copy = MCUTelemetry(**self._telem.__dict__)

            if self._telemetry_callback:
                try:
                    self._telemetry_callback(telem_copy)
                except Exception as e:
                    log.error(f"[MockMCU] Telemetry callback error: {e}")

            time.sleep(dt)

        # Signal disconnection fault
        if self._fault_callback:
            self._fault_callback(MCUFault(
                source="mock",
                code=0x01,
                description="Mock MCU transport stopped",
                is_critical=True,
            ))


# ---------------------------------------------------------------------------
# REAL Serial Transport — SKELETON (requires hardware + firmware confirmation)
# ---------------------------------------------------------------------------

class SerialMCUTransport(BaseMCUTransport):
    """
    Real serial transport for STM32 MCU over USB-UART or UART.

    STATUS: Protocol implemented with ASCII CSV + XOR checksum (mcu_protocol.py).
    SAFETY GUARD: PROTOCOL_CONFIRMED is False by default. Must NOT be enabled
    until physical hardware measurements, E-stop circuit, and UART loopback
    are completed according to docs/hardware_verification_checklist.md.

    This class raises RuntimeError on connect(), send_command(), and send_estop()
    until PROTOCOL_CONFIRMED is set to True.
    """

    PROTOCOL_CONFIRMED: bool = False  # Set to True only after physical hardware validation

    def __init__(
        self,
        port: str = MCU_DEFAULT_PORT,
        baud_rate: int = MCU_DEFAULT_BAUD_RATE,
        wheel_separation_m: float = 0.34,
        wheel_radius_m: float = 0.065,
        telemetry_timeout_sec: float = 1.5,
    ):
        super().__init__(wheel_separation_m, wheel_radius_m)
        self.port = port
        self.baud_rate = baud_rate
        self.telemetry_timeout_sec = telemetry_timeout_sec
        self._serial = None
        self._rx_thread: Optional[threading.Thread] = None
        self._active = False
        self._lock = threading.Lock()
        self._last_heartbeat: float = 0.0
        self._rx_buffer: str = ""
        self._max_buffer_len: int = 1024

        # Diagnostic counters
        self.frames_received: int = 0
        self.checksum_errors: int = 0
        self.malformed_frames: int = 0
        self.buffer_overflows: int = 0

    def connect(self) -> bool:
        if not self.PROTOCOL_CONFIRMED:
            raise RuntimeError(
                "SerialMCUTransport: Protocol not confirmed. "
                "Set SerialMCUTransport.PROTOCOL_CONFIRMED = True only after "
                "validating the ASCII frame format and physical wiring against the STM32 firmware. "
                "Use MockMCUTransport for automated testing."
            )
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baud_rate, timeout=0.05)
            self._connection_state = MCUConnectionState.CONNECTED
            self._active = True
            self._last_heartbeat = time.time()
            self._rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._rx_thread.start()
            return True
        except Exception as e:
            log.error(f"[SerialMCU] Connection failed on {self.port}: {e}")
            self._connection_state = MCUConnectionState.FAULT
            if self._fault_callback:
                self._fault_callback(MCUFault(source="serial_connect", description=str(e), is_critical=True))
            return False

    def disconnect(self) -> None:
        with self._lock:
            self._active = False
            if self._serial:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None
            self._connection_state = MCUConnectionState.DISCONNECTED

    def send_command(self, cmd: MCUCommand) -> bool:
        """
        Send velocity command to STM32 MCU.
        SAFETY GUARD: Blocked until PROTOCOL_CONFIRMED is True.
        """
        if not self.PROTOCOL_CONFIRMED:
            raise RuntimeError(
                "SerialMCUTransport: Protocol not confirmed. "
                "Cannot send commands to physical motors. "
                "Set SerialMCUTransport.PROTOCOL_CONFIRMED = True only after "
                "validating the ASCII frame format against verified STM32 firmware."
            )
        if not self.is_connected or not self._serial:
            return False
        cmd = self._clamp_command(cmd)
        cmd.seq = self._next_seq()
        from .mcu_protocol import encode_command
        frame = encode_command(cmd, use_checksum=True)
        with self._lock:
            self._serial.write(frame)
        return True

    def send_estop(self) -> bool:
        """
        Send immediate software stop request over communication link.
        CRITICAL SAFETY NOTICE:
        This is a software-commanded stop over the serial link and does NOT
        replace an independent, hardwired physical emergency-stop circuit.
        """
        if not self.PROTOCOL_CONFIRMED:
            raise RuntimeError(
                "SerialMCUTransport: Protocol not confirmed. Cannot send serial stop command."
            )
        if not self.is_connected or not self._serial:
            return False
        from .mcu_protocol import encode_command
        stop_cmd = MCUCommand(emergency_stop=True, seq=self._next_seq())
        frame = encode_command(stop_cmd, use_checksum=True)
        with self._lock:
            self._serial.write(frame)
        return True

    def feed_bytes(self, raw_bytes: bytes) -> int:
        """
        Process incoming serial bytes with bounded buffering.
        Handles split chunks, concatenated lines, and oversized frame recovery.
        Returns the number of successfully parsed telemetry frames.
        """
        from .mcu_protocol import decode_telemetry, MAX_FRAME_LENGTH

        new_text = raw_bytes.decode("ascii", errors="replace")
        self._rx_buffer += new_text

        # Prevent unbounded buffer growth
        if len(self._rx_buffer) > self._max_buffer_len:
            self.buffer_overflows += 1
            # Keep only the last valid frame boundary slice if any
            last_nl = self._rx_buffer.rfind("\n")
            if last_nl != -1:
                self._rx_buffer = self._rx_buffer[last_nl + 1 :]
            else:
                self._rx_buffer = ""
            return 0

        parsed_count = 0
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            if len(line) > MAX_FRAME_LENGTH:
                self.malformed_frames += 1
                continue

            telem = decode_telemetry(line)
            if telem:
                self.frames_received += 1
                parsed_count += 1
                self._last_heartbeat = time.time()
                if self._telemetry_callback:
                    try:
                        self._telemetry_callback(telem)
                    except Exception as e:
                        log.error(f"[SerialMCU] Telemetry callback error: {e}")
            else:
                if "*" in line:
                    self.checksum_errors += 1
                self.malformed_frames += 1

        return parsed_count

    def check_telemetry_freshness(self, now: Optional[float] = None) -> bool:
        """Checks if telemetry is fresh within telemetry_timeout_sec."""
        curr_time = now if now is not None else time.time()
        if self._last_heartbeat > 0 and (curr_time - self._last_heartbeat > self.telemetry_timeout_sec):
            if self._connection_state == MCUConnectionState.CONNECTED:
                self._connection_state = MCUConnectionState.TIMEOUT
                if self._fault_callback:
                    self._fault_callback(
                        MCUFault(
                            source="serial_telemetry_watchdog",
                            code=0x01,
                            description=f"MCU telemetry silent > {self.telemetry_timeout_sec:.1f}s",
                            is_critical=True,
                        )
                    )
            return False
        return True

    def _receive_loop(self) -> None:
        while self._active and self._serial and self._serial.is_open:
            try:
                chunk = self._serial.read(self._serial.in_waiting or 1)
                if chunk:
                    self.feed_bytes(chunk)
                self.check_telemetry_freshness()
            except Exception as e:
                log.warning(f"[SerialMCU] RX exception: {e}")
                time.sleep(0.01)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_mcu_transport(
    transport_type: str,
    port: str = MCU_DEFAULT_PORT,
    baud_rate: int = MCU_DEFAULT_BAUD_RATE,
    wheel_separation_m: float = 0.34,
    wheel_radius_m: float = 0.065,
) -> BaseMCUTransport:
    """
    Factory for MCU transports.

    transport_type:
      "mock"   — MockMCUTransport (automated testing, never physical hardware)
      "serial" — SerialMCUTransport (real hardware, requires protocol confirmation)
    """
    t = transport_type.lower().strip()
    if t == "mock":
        return MockMCUTransport(
            wheel_separation_m=wheel_separation_m,
            wheel_radius_m=wheel_radius_m,
        )
    elif t in ("serial", "uart", "usb"):
        return SerialMCUTransport(
            port=port,
            baud_rate=baud_rate,
            wheel_separation_m=wheel_separation_m,
            wheel_radius_m=wheel_radius_m,
        )
    else:
        raise ValueError(f"Unknown MCU transport type: '{transport_type}'. Use 'mock' or 'serial'.")
