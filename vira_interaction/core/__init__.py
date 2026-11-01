"""
GRaCEmo ViRa — Core Interaction Subsystem Package
Exports the production Interaction Gateway, State Machine, Safety Gate, and Adapters.
"""
from .state_machine import CognitiveState, Expression, InteractionFSM
from .safety_gate import CommandValidator, SafetyGate, ValidationResult
from .event_bus import EventBusClient
from .fast_path import FastPathMatcher, FastPathResult
from .brain_adapter import BrainAdapter, BrainResult
from .stt_adapter import STTAdapter, STTResult
from .tts_adapter import TTSAdapter
from .memory_adapter import MemoryAdapter
from .gateway import InteractionGateway, GatewayResult
from .interaction_adapter import InteractionAdapter
from .interaction_loop import InteractionLoop
from .behavior_manager import (
    BehaviorState,
    HumanInteractionBehaviorManager,
    PersonDetection,
    StructuredMotionRequest,
)
from .camera_driver import (
    CameraDriverInterface,
    CameraFrame,
    DetectedPerson,
    MockCameraDriver,
    OpenCVCameraDriver,
)
from .audio_driver import (
    AudioDriverInterface,
    AudioChunk,
    MockAudioDriver,
    PyAudioDriver,
    VoiceCommandParser,
    ParsedVoiceCommand,
)

__all__ = [
    "CognitiveState",
    "Expression",
    "InteractionFSM",
    "CommandValidator",
    "SafetyGate",
    "ValidationResult",
    "EventBusClient",
    "FastPathMatcher",
    "FastPathResult",
    "BrainAdapter",
    "BrainResult",
    "STTAdapter",
    "STTResult",
    "TTSAdapter",
    "MemoryAdapter",
    "InteractionGateway",
    "GatewayResult",
    "InteractionAdapter",
    "InteractionLoop",
    "BehaviorState",
    "HumanInteractionBehaviorManager",
    "PersonDetection",
    "StructuredMotionRequest",
    "CameraDriverInterface",
    "CameraFrame",
    "DetectedPerson",
    "MockCameraDriver",
    "OpenCVCameraDriver",
    "AudioDriverInterface",
    "AudioChunk",
    "MockAudioDriver",
    "PyAudioDriver",
    "VoiceCommandParser",
    "ParsedVoiceCommand",
]
