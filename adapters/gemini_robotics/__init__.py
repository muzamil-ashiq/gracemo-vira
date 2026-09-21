"""
GRaCEmo ViRa — Gemini Robotics ER 2 Adapter
Embodied intelligence and multimodal reasoning layer for autonomous robotics.
"""

from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.context import MNSEContextProvider
from adapters.gemini_robotics.client import (
    GeminiRoboticsClient,
    GeminiResponse,
    ToolCall,
)
from adapters.gemini_robotics.tools import (
    ToolRegistry,
    ToolResult,
)
from adapters.gemini_robotics.orchestrator import (
    GeminiRoboticsOrchestrator,
    OrchestratorResult,
    ReasoningTurn,
)

__all__ = [
    "GeminiRoboticsConfig",
    "MNSEContextProvider",
    "GeminiRoboticsClient",
    "GeminiResponse",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "GeminiRoboticsOrchestrator",
    "OrchestratorResult",
    "ReasoningTurn",
]
