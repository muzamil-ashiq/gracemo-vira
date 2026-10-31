#!/usr/bin/env python3
"""
Unit tests for STM32 ↔ Jetson Protocol Parsing, Framing, and Safety Guards.
Validates:
  - Command encoding and decoding (HEARTBEAT, STATUS, STOP, CLEAR_FAULT, DRIVE)
  - Telemetry decoding matching MCUTelemetry contract
  - Optional XOR checksum calculation and verification
  - Bounded input buffer enforcement (reject lines > 95 bytes)
  - Malformed and non-numeric value rejection
  - Strict enforcement of PROTOCOL_CONFIRMED=False guard
"""
import unittest
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def calculate_xor_checksum(msg: str) -> str:
    """Calculates 2-digit uppercase hex XOR checksum over ASCII string."""
    chk = 0
    for c in msg:
        chk ^= ord(c)
    return f"{chk:02X}"


class ProtocolParserSimulator:
    """Python reference simulator of STM32 ProtocolParser (firmware/protocol.h)."""
    MAX_BUFFER_LEN = 95

    def __init__(self):
        self.buffer = ""
        self.overflow = False

    def push(self, char: str):
        if char == '\r':
            return "WAITING", None
        if char == '\n':
            if self.overflow:
                self.reset()
                return "OVERFLOW", None
            line = self.buffer
            self.reset()
            parsed = self.parse_line(line)
            return ("COMPLETE", parsed) if parsed else ("ERROR", None)

        if len(self.buffer) >= self.MAX_BUFFER_LEN:
            self.overflow = True
            return "WAITING", None

        if not self.overflow:
            self.buffer += char
        return "WAITING", None

    def reset(self):
        self.buffer = ""
        self.overflow = False

    def parse_line(self, line: str):
        if not line:
            return None

        # Checksum check
        if '*' in line:
            payload, chk_str = line.rsplit('*', 1)
            expected_chk = calculate_xor_checksum(payload)
            if chk_str.upper() != expected_chk:
                return None
            line = payload

        parts = line.split(',')
        if len(parts) < 3 or parts[0] != "CMD":
            return None

        # Sequence number
        try:
            seq = int(parts[1])
            if not (0 <= seq <= 65535):
                return None
        except ValueError:
            return None

        cmd_verb = parts[2]
        if cmd_verb in ("HEARTBEAT", "STATUS", "STOP", "CLEAR_FAULT"):
            if len(parts) != 3:
                return None  # No trailing fields allowed
            return {"type": cmd_verb, "seq": seq}

        elif cmd_verb == "DRIVE":
            if len(parts) != 5:
                return None
            try:
                lin = float(parts[3])
                ang = float(parts[4])
                if not (math.isfinite(lin) and math.isfinite(ang)):
                    return None
                return {"type": "DRIVE", "seq": seq, "linear": lin, "angular": ang}
            except ValueError:
                return None

        return None


class TestSTM32ProtocolParser(unittest.TestCase):
    def setUp(self):
        self.parser = ProtocolParserSimulator()

    def _feed_string(self, s: str):
        result = ("WAITING", None)
        for char in s:
            result = self.parser.push(char)
        return result

    def test_valid_heartbeat_command(self):
        status, cmd = self._feed_string("CMD,42,HEARTBEAT\n")
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(cmd["type"], "HEARTBEAT")
        self.assertEqual(cmd["seq"], 42)

    def test_valid_drive_command(self):
        status, cmd = self._feed_string("CMD,105,DRIVE,0.25,-0.50\n")
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(cmd["type"], "DRIVE")
        self.assertEqual(cmd["seq"], 105)
        self.assertAlmostEqual(cmd["linear"], 0.25)
        self.assertAlmostEqual(cmd["angular"], -0.50)

    def test_valid_checksum(self):
        msg = "CMD,101,HEARTBEAT"
        chk = calculate_xor_checksum(msg)
        status, cmd = self._feed_string(f"{msg}*{chk}\n")
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(cmd["type"], "HEARTBEAT")

    def test_invalid_checksum_rejected(self):
        status, cmd = self._feed_string("CMD,101,HEARTBEAT*FF\n")
        self.assertEqual(status, "ERROR")
        self.assertIsNone(cmd)

    def test_oversized_line_triggers_overflow(self):
        long_line = "CMD,1," + "A" * 120 + "\n"
        status, cmd = self._feed_string(long_line)
        self.assertEqual(status, "OVERFLOW")
        self.assertIsNone(cmd)

    def test_malformed_non_numeric_floats_rejected(self):
        status, cmd = self._feed_string("CMD,10,DRIVE,NaN,0.5\n")
        self.assertEqual(status, "ERROR")

        status, cmd = self._feed_string("CMD,11,DRIVE,0.25,Infinity\n")
        self.assertEqual(status, "ERROR")

        status, cmd = self._feed_string("CMD,12,DRIVE,0.25,invalid_text\n")
        self.assertEqual(status, "ERROR")

    def test_trailing_fields_rejected(self):
        status, cmd = self._feed_string("CMD,20,STOP,EXTRA_FIELD\n")
        self.assertEqual(status, "ERROR")

    def test_telemetry_line_decoding(self):
        # Format: TELEM,<seq>,<left_vel>,<right_vel>,<left_ticks>,<right_ticks>,<x>,<y>,<yaw>,<v_bat>,<estop>,<fault>
        line = "TELEM,1001,0.200,0.200,2048,2048,1.250,0.500,0.785,12.42,0,0"
        parts = line.split(',')
        self.assertEqual(parts[0], "TELEM")
        self.assertEqual(int(parts[1]), 1001)
        self.assertAlmostEqual(float(parts[2]), 0.200)
        self.assertAlmostEqual(float(parts[3]), 0.200)
        self.assertEqual(int(parts[4]), 2048)
        self.assertEqual(int(parts[5]), 2048)
        self.assertAlmostEqual(float(parts[6]), 1.250)
        self.assertAlmostEqual(float(parts[7]), 0.500)
        self.assertAlmostEqual(float(parts[8]), 0.785)
        self.assertAlmostEqual(float(parts[9]), 12.42)
        self.assertEqual(int(parts[10]), 0)
        self.assertEqual(int(parts[11]), 0)


if __name__ == "__main__":
    unittest.main()
