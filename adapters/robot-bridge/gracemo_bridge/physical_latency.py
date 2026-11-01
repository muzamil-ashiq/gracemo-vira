#!/usr/bin/env python3
"""
GRaCEmo ViRa — Physical Latency Instrumentation Subsystem (Phase 8)
Implements Sections 7 & 8: High-precision timestamp instrumentation for:
  - Voice Navigation (T0 through T8)
  - Physical Stop (S0 through S6)
Distinguishes software command dispatch latency from true physical mechanical latency.
"""
from __future__ import annotations
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

log = logging.getLogger("gracemo.physical_latency")


@dataclass
class VoiceNavigationTimestamps:
    """
    Timestamps for Voice Navigation Pipeline:
      T0: speech end
      T1: STT completion
      T2: intent recognition
      T3: SafetyGate acceptance
      T4: EventBus publish
      T5: RobotBridge receipt
      T6: ROS command issued
      T7: motor controller command receipt
      T8: physical wheel movement detected
    """
    T0: float = 0.0
    T1: float = 0.0
    T2: float = 0.0
    T3: float = 0.0
    T4: float = 0.0
    T5: float = 0.0
    T6: float = 0.0
    T7: float = 0.0
    T8: float = 0.0

    @property
    def stt_latency_ms(self) -> float:
        return max(0.0, (self.T1 - self.T0) * 1000.0)

    @property
    def intent_latency_ms(self) -> float:
        return max(0.0, (self.T2 - self.T1) * 1000.0)

    @property
    def safety_latency_ms(self) -> float:
        return max(0.0, (self.T3 - self.T2) * 1000.0)

    @property
    def eventbus_latency_ms(self) -> float:
        return max(0.0, (self.T4 - self.T3) * 1000.0)

    @property
    def bridge_latency_ms(self) -> float:
        return max(0.0, (self.T5 - self.T4) * 1000.0)

    @property
    def ros_latency_ms(self) -> float:
        return max(0.0, (self.T6 - self.T5) * 1000.0)

    @property
    def motor_command_latency_ms(self) -> float:
        return max(0.0, (self.T7 - self.T6) * 1000.0)

    @property
    def first_physical_motion_latency_ms(self) -> float:
        return max(0.0, (self.T8 - self.T7) * 1000.0)

    @property
    def true_voice_to_first_motion_ms(self) -> float:
        """TRUE VOICE-TO-FIRST-MOTION = T8 - T0"""
        return max(0.0, (self.T8 - self.T0) * 1000.0)

    def to_dict(self) -> Dict[str, float]:
        return {
            "T0_speech_end": self.T0,
            "T1_stt_complete": self.T1,
            "T2_intent_recognized": self.T2,
            "T3_safety_accepted": self.T3,
            "T4_eventbus_published": self.T4,
            "T5_bridge_received": self.T5,
            "T6_ros_issued": self.T6,
            "T7_motor_receipt": self.T7,
            "T8_physical_motion": self.T8,
            "stt_latency_ms": round(self.stt_latency_ms, 3),
            "intent_latency_ms": round(self.intent_latency_ms, 3),
            "safety_latency_ms": round(self.safety_latency_ms, 3),
            "eventbus_latency_ms": round(self.eventbus_latency_ms, 3),
            "bridge_latency_ms": round(self.bridge_latency_ms, 3),
            "ros_latency_ms": round(self.ros_latency_ms, 3),
            "motor_command_latency_ms": round(self.motor_command_latency_ms, 3),
            "first_physical_motion_latency_ms": round(self.first_physical_motion_latency_ms, 3),
            "true_voice_to_first_motion_ms": round(self.true_voice_to_first_motion_ms, 3),
        }


@dataclass
class PhysicalStopTimestamps:
    """
    Timestamps for STOP Pipeline:
      S0: STOP speech detected
      S1: STOP intent detected
      S2: SafetyGate processed STOP
      S3: RobotBridge received STOP
      S4: zero velocity command generated
      S5: motor controller receives STOP
      S6: physical wheel velocity reaches zero
    """
    S0: float = 0.0
    S1: float = 0.0
    S2: float = 0.0
    S3: float = 0.0
    S4: float = 0.0
    S5: float = 0.0
    S6: float = 0.0

    @property
    def stop_intent_latency_ms(self) -> float:
        return max(0.0, (self.S1 - self.S0) * 1000.0)

    @property
    def safety_stop_latency_ms(self) -> float:
        return max(0.0, (self.S2 - self.S1) * 1000.0)

    @property
    def bridge_stop_latency_ms(self) -> float:
        return max(0.0, (self.S3 - self.S2) * 1000.0)

    @property
    def command_generation_latency_ms(self) -> float:
        return max(0.0, (self.S4 - self.S3) * 1000.0)

    @property
    def motor_stop_receipt_latency_ms(self) -> float:
        return max(0.0, (self.S5 - self.S4) * 1000.0)

    @property
    def wheel_deceleration_latency_ms(self) -> float:
        return max(0.0, (self.S6 - self.S5) * 1000.0)

    @property
    def command_stop_latency_ms(self) -> float:
        """COMMAND STOP LATENCY = S4 - S0"""
        return max(0.0, (self.S4 - self.S0) * 1000.0)

    @property
    def true_physical_stop_latency_ms(self) -> float:
        """TRUE PHYSICAL STOP LATENCY = S6 - S0"""
        return max(0.0, (self.S6 - self.S0) * 1000.0)

    def to_dict(self) -> Dict[str, float]:
        return {
            "S0_speech_detected": self.S0,
            "S1_intent_detected": self.S1,
            "S2_safety_processed": self.S2,
            "S3_bridge_received": self.S3,
            "S4_zero_cmd_generated": self.S4,
            "S5_motor_received": self.S5,
            "S6_physical_wheel_stopped": self.S6,
            "stop_intent_latency_ms": round(self.stop_intent_latency_ms, 3),
            "safety_stop_latency_ms": round(self.safety_stop_latency_ms, 3),
            "bridge_stop_latency_ms": round(self.bridge_stop_latency_ms, 3),
            "command_stop_latency_ms": round(self.command_stop_latency_ms, 3),
            "motor_stop_receipt_latency_ms": round(self.motor_stop_receipt_latency_ms, 3),
            "wheel_deceleration_latency_ms": round(self.wheel_deceleration_latency_ms, 3),
            "true_physical_stop_latency_ms": round(self.true_physical_stop_latency_ms, 3),
        }
