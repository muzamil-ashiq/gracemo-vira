#!/usr/bin/env python3
"""
GRaCEmo ViRa — Production Interaction Gateway
Coordinates the end-to-end interactive nervous system pipeline:
  Audio/Text Input
        ↓
  STT Transcription (Groq Whisper / Fallback)
        ↓
  Intent Routing (Fast-Path vs Brain)
        ↓
  Semantic Command Extraction
        ↓
  Safety & Validation Gate
        ↓
  VIRA EventBus Publication (with trace_id)
        ↓
  TTS & Avatar Synchronization
"""
from __future__ import annotations
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import numpy as np

from .state_machine import CognitiveState, Expression, InteractionFSM
from .safety_gate import CommandValidator, SafetyGate, ValidationResult
from .event_bus import EventBusClient
from .fast_path import FastPathMatcher, FastPathResult
from .brain_adapter import BrainAdapter, BrainResult
from .stt_adapter import STTAdapter, STTResult
from .tts_adapter import TTSAdapter
from .memory_adapter import MemoryAdapter

log = logging.getLogger("gracemo.gateway")


@dataclass
class GatewayResult:
    response: str
    intent: str
    confidence: float
    expression: Expression
    actions: List[Dict[str, Any]] = field(default_factory=list)
    semantic_commands: List[Dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    session_id: str = ""
    state: str = "IDLE"
    latency_ms: float = 0.0
    error: Optional[str] = None


class InteractionGateway:
    """
    Central Coordinator for GRaCEmo ViRa Interaction.
    Ensures safe, observable, and contract-compliant interaction.
    """

    def __init__(
        self,
        fsm: Optional[InteractionFSM] = None,
        event_bus: Optional[EventBusClient] = None,
        safety_gate: Optional[SafetyGate] = None,
        fast_path: Optional[FastPathMatcher] = None,
        brain: Optional[BrainAdapter] = None,
        stt: Optional[STTAdapter] = None,
        tts: Optional[TTSAdapter] = None,
        memory: Optional[MemoryAdapter] = None,
    ):
        self.fsm = fsm or InteractionFSM()
        self.event_bus = event_bus or EventBusClient()
        self.safety_gate = safety_gate or SafetyGate()
        self.fast_path = fast_path or FastPathMatcher()
        self.brain = brain or BrainAdapter()
        self.stt = stt or STTAdapter()
        self.tts = tts or TTSAdapter()
        self.memory = memory or MemoryAdapter()

        # Connect FSM state changes to EventBus
        self.fsm.add_listener(self._on_fsm_transition)
        self.fsm.transition_to(CognitiveState.IDLE, reason="Gateway initialized")

    def _on_fsm_transition(self, prev: CognitiveState, curr: CognitiveState, exp: Expression, reason: str):
        self.event_bus.emit(
            "InteractionStateChanged",
            {
                "previous_state": prev.value,
                "current_state": curr.value,
                "active_expression": exp.value,
                "reason": reason,
            },
            source="Interaction",
        )

    def process_text(
        self,
        text: str,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> GatewayResult:
        """Process a text command or query through the pipeline."""
        start_t = time.perf_counter()
        tid = trace_id or str(uuid.uuid4())
        sid = session_id or "session_default"

        clean_text = (text or "").strip()
        if not clean_text:
            return GatewayResult(
                response="",
                intent="NONE",
                confidence=0.0,
                expression=self.fsm.expression,
                trace_id=tid,
                session_id=sid,
                state=self.fsm.state.value,
            )

        log.info(f"📩 Gateway Ingestion [trace={tid[:8]}]: \"{clean_text}\"")

        # 1. State -> THINKING
        self.fsm.transition_to(CognitiveState.THINKING, reason="Processing text input")

        # 2. Check Fast-Path (STOP, GREET, IDENTITY, NAVIGATE)
        fp_result: FastPathResult = self.fast_path.match(clean_text)

        if fp_result.matched:
            # Handle STOP immediately
            if fp_result.is_emergency or fp_result.intent == "STOP":
                return self._handle_emergency_stop(fp_result, tid, sid, start_t)

            return self._handle_fast_path(fp_result, clean_text, tid, sid, start_t)

        # 3. Cognitive Brain Reasoning
        return self._handle_brain_reasoning(clean_text, tid, sid, start_t)

    def process_audio(
        self,
        audio_data: Union[np.ndarray, bytes, str],
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> GatewayResult:
        """Process an audio utterance buffer through STT then text pipeline."""
        start_t = time.perf_counter()
        tid = trace_id or str(uuid.uuid4())
        sid = session_id or "session_default"

        # 1. State -> LISTENING -> THINKING
        self.fsm.transition_to(CognitiveState.LISTENING, reason="Audio captured")
        stt_res: STTResult = self.stt.transcribe(audio_data, sample_rate=sample_rate)

        if not stt_res.is_valid or not stt_res.text:
            log.info(f"⤍ [STT Filtered] Ambient noise or silence (trace={tid[:8]})")
            self.fsm.transition_to(CognitiveState.IDLE, reason="Speech was silent or filtered")
            return GatewayResult(
                response="",
                intent="FILTERED",
                confidence=0.0,
                expression=self.fsm.expression,
                trace_id=tid,
                session_id=sid,
                state=self.fsm.state.value,
                latency_ms=(time.perf_counter() - start_t) * 1000.0,
            )

        # Emit VoiceDetected
        self.event_bus.emit(
            "VoiceDetected",
            {
                "transcription": stt_res.text,
                "confidence": stt_res.confidence,
                "language": "en",
            },
            trace_id=tid,
            session_id=sid,
            source="Voice",
        )

        return self.process_text(stt_res.text, session_id=sid, trace_id=tid)

    def _handle_emergency_stop(
        self, fp: FastPathResult, trace_id: str, session_id: str, start_t: float
    ) -> GatewayResult:
        """Independent sub-20ms emergency stop dispatch."""
        self.tts.stop()  # Interrupt active audio
        self.fsm.emergency_stop(reason="Voice STOP matched")

        validated_actions = []
        for act in fp.semantic_actions:
            v_res: ValidationResult = self.safety_gate.evaluate_action(act)
            if v_res.valid:
                validated_actions.append(v_res.sanitized_action)
                self.event_bus.emit(
                    "ActionRequested",
                    v_res.sanitized_action,
                    trace_id=trace_id,
                    session_id=session_id,
                    source="SafetyGateway",
                )

        latency = (time.perf_counter() - start_t) * 1000.0
        log.info(f"🛑 E-STOP dispatched successfully in {latency:.2f}ms (trace={trace_id[:8]})")

        return GatewayResult(
            response=fp.response_text,
            intent="STOP",
            confidence=fp.confidence,
            expression=Expression.IDLE,
            actions=validated_actions,
            semantic_commands=validated_actions,
            trace_id=trace_id,
            session_id=session_id,
            state=self.fsm.state.value,
            latency_ms=latency,
        )

    def _handle_fast_path(
        self, fp: FastPathResult, raw_text: str, trace_id: str, session_id: str, start_t: float
    ) -> GatewayResult:
        # 1. Transition FSM state before dispatching events
        target_state = CognitiveState.EXECUTING if fp.semantic_actions else CognitiveState.SPEAKING
        self.fsm.transition_to(target_state, reason=f"Fast-path {fp.intent}", expression=fp.expression)

        # 2. Validate and dispatch semantic actions
        validated_actions = []
        for act in fp.semantic_actions:
            v_res = self.safety_gate.evaluate_action(act)
            if v_res.valid:
                validated_actions.append(v_res.sanitized_action)
                self.event_bus.emit(
                    "ActionRequested",
                    v_res.sanitized_action,
                    trace_id=trace_id,
                    session_id=session_id,
                    source="FastPath",
                )
            else:
                log.warning(f"⚠️ Action rejected by SafetyGate: {v_res.error_message}")

        # 3. Emit VoiceIntent
        self.event_bus.emit(
            "VoiceIntent",
            {
                "intent": fp.intent,
                "confidence": fp.confidence,
                "raw_transcript": raw_text,
            },
            trace_id=trace_id,
            session_id=session_id,
            source="Interaction",
        )

        latency = (time.perf_counter() - start_t) * 1000.0
        return GatewayResult(
            response=fp.response_text,
            intent=fp.intent,
            confidence=fp.confidence,
            expression=fp.expression,
            actions=validated_actions,
            semantic_commands=validated_actions,
            trace_id=trace_id,
            session_id=session_id,
            state=self.fsm.state.value,
            latency_ms=latency,
        )

    def _handle_brain_reasoning(
        self, text: str, trace_id: str, session_id: str, start_t: float
    ) -> GatewayResult:
        if self.brain is None:
            log.warning("☁️ Cloud Brain is offline/unconfigured. Falling back to local offline response.")
            latency = (time.perf_counter() - start_t) * 1000.0
            self.fsm.transition_to(CognitiveState.SPEAKING, reason="Brain offline fallback", expression=Expression.SAD)
            return GatewayResult(
                response="I am currently offline from the cloud brain, but local navigation and safety remain active.",
                intent="OFFLINE_FALLBACK",
                confidence=0.0,
                expression=Expression.SAD,
                actions=[],
                semantic_commands=[],
                trace_id=trace_id,
                session_id=session_id,
                state=self.fsm.state.value,
                latency_ms=latency,
            )

        brain_res: BrainResult = self.brain.reason(text)

        validated_actions = []
        for act in brain_res.semantic_actions:
            v_res = self.safety_gate.evaluate_action(act)
            if v_res.valid:
                validated_actions.append(v_res.sanitized_action)
                self.event_bus.emit(
                    "ActionRequested",
                    v_res.sanitized_action,
                    trace_id=trace_id,
                    session_id=session_id,
                    source="Brain",
                )
            else:
                log.warning(f"⚠️ Action from Brain rejected by SafetyGate: {v_res.error_message}")

        # Emit VoiceIntent
        self.event_bus.emit(
            "VoiceIntent",
            {
                "intent": brain_res.intent,
                "confidence": brain_res.confidence,
                "raw_transcript": text,
            },
            trace_id=trace_id,
            session_id=session_id,
            source="Brain",
        )

        target_state = CognitiveState.EXECUTING if validated_actions else CognitiveState.SPEAKING
        self.fsm.transition_to(target_state, reason=f"Brain {brain_res.intent}", expression=brain_res.expression)

        latency = (time.perf_counter() - start_t) * 1000.0
        return GatewayResult(
            response=brain_res.response_text,
            intent=brain_res.intent,
            confidence=brain_res.confidence,
            expression=brain_res.expression,
            actions=validated_actions,
            semantic_commands=validated_actions,
            trace_id=trace_id,
            session_id=session_id,
            state=self.fsm.state.value,
            latency_ms=latency,
        )
