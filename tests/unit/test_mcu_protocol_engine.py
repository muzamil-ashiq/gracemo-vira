#!/usr/bin/env python3
"""
Unit tests for the Python MCU Protocol Engine (mcu_protocol.py).
Validates:
  - Command serialization (DRIVE, STOP, HEARTBEAT) with XOR checksums
  - Telemetry deserialization into MCUTelemetry objects
  - Checksum verification, corruption detection, and length bounds
  - Rejection of malformed lines, NaN/Inf, and field count mismatches
  - Response parsing (ACK, ERR)
"""
import unittest
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "gracemo_hardware"))

from gracemo_hardware.mcu_transport import MCUCommand, MCUTelemetry
from gracemo_hardware.mcu_protocol import (
    calculate_xor_checksum,
    encode_command,
    decode_telemetry,
    decode_response,
    MAX_FRAME_LENGTH,
)


class TestMCUProtocolEngine(unittest.TestCase):
    def test_checksum_calculation(self):
        msg = "CMD,101,HEARTBEAT"
        chk = calculate_xor_checksum(msg)
        self.assertEqual(len(chk), 2)
        # Verify manual XOR
        expected = 0
        for c in msg:
            expected ^= ord(c)
        self.assertEqual(chk, f"{expected:02X}")

    def test_encode_drive_command_with_checksum(self):
        cmd = MCUCommand(linear_vel_mps=0.25, angular_vel_rps=-0.50, seq=42)
        encoded = encode_command(cmd, use_checksum=True)
        text = encoded.decode("ascii")
        self.assertTrue(text.startswith("CMD,42,DRIVE,0.250,-0.500*"))
        self.assertTrue(text.endswith("\n"))

        # Verify checksum validity
        payload, chk = text.strip().split("*")
        self.assertEqual(chk, calculate_xor_checksum(payload))

    def test_encode_stop_command(self):
        cmd = MCUCommand(linear_vel_mps=0.25, angular_vel_rps=-0.50, emergency_stop=True, seq=99)
        encoded = encode_command(cmd, use_checksum=True)
        text = encoded.decode("ascii")
        self.assertTrue(text.startswith("CMD,99,STOP*"))
        self.assertTrue(text.endswith("\n"))

    def test_encode_command_without_checksum(self):
        cmd = MCUCommand(linear_vel_mps=0.10, angular_vel_rps=0.0, seq=7)
        encoded = encode_command(cmd, use_checksum=False)
        text = encoded.decode("ascii")
        self.assertEqual(text, "CMD,7,DRIVE,0.100,0.000\n")

    def test_decode_valid_telemetry_with_checksum(self):
        payload = "TELEM,1001,0.200,0.200,2048,2048,1.250,0.500,0.785,12.42,0,0"
        chk = calculate_xor_checksum(payload)
        line = f"{payload}*{chk}\n"

        telem = decode_telemetry(line)
        self.assertIsNotNone(telem)
        self.assertEqual(telem.heartbeat_seq, 1001)
        self.assertAlmostEqual(telem.left_wheel_vel_mps, 0.200)
        self.assertAlmostEqual(telem.right_wheel_vel_mps, 0.200)
        self.assertEqual(telem.left_encoder_ticks, 2048)
        self.assertEqual(telem.right_encoder_ticks, 2048)
        self.assertAlmostEqual(telem.odom_x, 1.250)
        self.assertAlmostEqual(telem.odom_y, 0.500)
        self.assertAlmostEqual(telem.odom_yaw, 0.785)
        self.assertAlmostEqual(telem.battery_voltage_v, 12.42)
        self.assertFalse(telem.physical_estop_pressed)
        self.assertEqual(telem.mcu_fault_code, 0)

    def test_decode_telemetry_corrupted_checksum(self):
        payload = "TELEM,1001,0.200,0.200,2048,2048,1.250,0.500,0.785,12.42,0,0"
        corrupted = f"{payload}*FF\n"
        self.assertIsNone(decode_telemetry(corrupted))

    def test_decode_telemetry_nan_or_inf_rejected(self):
        nan_line = "TELEM,1001,nan,0.200,2048,2048,1.250,0.500,0.785,12.42,0,0\n"
        self.assertIsNone(decode_telemetry(nan_line))

        inf_line = "TELEM,1001,0.200,inf,2048,2048,1.250,0.500,0.785,12.42,0,0\n"
        self.assertIsNone(decode_telemetry(inf_line))

    def test_decode_telemetry_wrong_field_count(self):
        short_line = "TELEM,1001,0.200,0.200\n"
        self.assertIsNone(decode_telemetry(short_line))

    def test_decode_oversized_line_rejected(self):
        long_line = "TELEM," + "0," * 50 + "\n"
        self.assertTrue(len(long_line) > MAX_FRAME_LENGTH)
        self.assertIsNone(decode_telemetry(long_line))

    def test_decode_response_ack_and_err(self):
        ack_res = decode_response("ACK,105,HEARTBEAT\n")
        self.assertIsNotNone(ack_res)
        status, seq, detail = ack_res
        self.assertEqual(status, "ACK")
        self.assertEqual(seq, 105)
        self.assertEqual(detail, "HEARTBEAT")

        err_res = decode_response("ERR,106,DRIVE_RANGE\n")
        self.assertIsNotNone(err_res)
        status, seq, detail = err_res
        self.assertEqual(status, "ERR")
        self.assertEqual(seq, 106)
        self.assertEqual(detail, "DRIVE_RANGE")


if __name__ == "__main__":
    unittest.main()
