"""
GRaCEmo ViRa — STM32 ↔ Jetson Communication Protocol Engine
Implements the proposed framing, serialization, deserialization, and checksum verification
defined in docs/stm32_jetson_protocol_proposal.md.

Protocol Specification:
  Command Frame:   CMD,<seq>,<VERB>[,<arg1>,<arg2>,...][*<chk>]\n
  Telemetry Frame: TELEM,<seq>,<vL>,<vR>,<ticksL>,<ticksR>,<x>,<y>,<yaw>,<vbat>,<estop>,<fault>[*<chk>]\n
  Acknowledge:     ACK,<seq>,<VERB>\n
  Error Frame:     ERR,<seq>,<REASON>\n
"""

import math
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from .mcu_transport import MCUCommand, MCUTelemetry

log = logging.getLogger("gracemo.hardware.mcu_protocol")

MAX_FRAME_LENGTH: int = 96


def calculate_xor_checksum(payload: str) -> str:
    """Calculates 2-digit uppercase hex XOR checksum over ASCII string."""
    chk = 0
    for char in payload:
        chk ^= ord(char)
    return f"{chk:02X}"


def encode_command(cmd: MCUCommand, use_checksum: bool = True) -> bytes:
    """
    Serializes an MCUCommand into a newline-terminated protocol frame.
    Supports HEARTBEAT, STOP, and DRIVE.
    """
    seq = cmd.seq % 65536
    cmd_type = getattr(cmd, "command_type", "DRIVE")
    if cmd.emergency_stop or cmd_type == "STOP":
        payload = f"CMD,{seq},STOP"
    elif cmd_type == "HEARTBEAT" or (abs(cmd.linear_vel_mps) < 1e-6 and abs(cmd.angular_vel_rps) < 1e-6 and cmd_type != "DRIVE"):
        payload = f"CMD,{seq},HEARTBEAT"
    else:
        payload = f"CMD,{seq},DRIVE,{cmd.linear_vel_mps:.3f},{cmd.angular_vel_rps:.3f}"

    if use_checksum:
        chk = calculate_xor_checksum(payload)
        frame = f"{payload}*{chk}\n"
    else:
        frame = f"{payload}\n"

    return frame.encode("ascii")


def decode_telemetry(raw_line: str) -> Optional[MCUTelemetry]:
    """
    Parses an incoming TELEM frame into an MCUTelemetry object.
    Validates framing, length, numeric bounds, and checksum.
    Returns None if malformed.
    """
    line = raw_line.strip()
    if not line or len(line) > MAX_FRAME_LENGTH:
        return None

    # Checksum validation if present
    if "*" in line:
        payload, chk_str = line.rsplit("*", 1)
        expected_chk = calculate_xor_checksum(payload)
        if chk_str.upper() != expected_chk:
            log.warning(f"Telemetry checksum mismatch: got {chk_str}, expected {expected_chk}")
            return None
        line = payload

    parts = line.split(",")
    if len(parts) != 12 or parts[0] != "TELEM":
        return None

    try:
        seq = int(parts[1])
        vl = float(parts[2])
        vr = float(parts[3])
        ticks_l = int(parts[4])
        ticks_r = int(parts[5])
        ox = float(parts[6])
        oy = float(parts[7])
        oyaw = float(parts[8])
        vbat = float(parts[9])
        estop = bool(int(parts[10]))
        fault = int(parts[11])

        # Validate finite values
        for val in (vl, vr, ox, oy, oyaw, vbat):
            if not math.isfinite(val):
                return None

        return MCUTelemetry(
            heartbeat_seq=seq,
            left_wheel_vel_mps=vl,
            right_wheel_vel_mps=vr,
            left_encoder_ticks=ticks_l,
            right_encoder_ticks=ticks_r,
            odom_x=ox,
            odom_y=oy,
            odom_yaw=oyaw,
            battery_voltage_v=vbat,
            physical_estop_pressed=estop,
            mcu_fault_code=fault,
        )
    except (ValueError, IndexError) as e:
        log.warning(f"Telemetry parse error: {e} in '{raw_line}'")
        return None


def decode_response(raw_line: str) -> Optional[Tuple[str, int, str]]:
    """
    Parses ACK or ERR lines:
      ACK,<seq>,<VERB>
      ERR,<seq>,<REASON>
    Returns (status, seq, detail) or None.
    """
    line = raw_line.strip()
    if not line:
        return None

    if "*" in line:
        payload, chk_str = line.rsplit("*", 1)
        expected_chk = calculate_xor_checksum(payload)
        if chk_str.upper() != expected_chk:
            return None
        line = payload

    parts = line.split(",")
    if len(parts) != 3 or parts[0] not in ("ACK", "ERR"):
        return None

    try:
        status = parts[0]
        seq = int(parts[1])
        detail = parts[2]
        return status, seq, detail
    except ValueError:
        return None
