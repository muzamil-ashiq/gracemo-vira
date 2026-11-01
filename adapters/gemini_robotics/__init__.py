"""
GRaCEmo ViRa — Gemini Robotics ER 2 Adapter
Embodied intelligence and multimodal reasoning layer for autonomous robotics.
"""

from adapters.gemini_robotics.config import (
    GeminiRoboticsConfig,
    ER2_SYSTEM_INSTRUCTION,
    ARGON_SYSTEM_INSTRUCTION,
)
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
from adapters.gemini_robotics.argon_proposal import (
    ArgonActionProposal,
    ArgonDryRunValidator,
    ProposalStatus,
)

__all__ = [
    "GeminiRoboticsConfig",
    "ER2_SYSTEM_INSTRUCTION",
    "ARGON_SYSTEM_INSTRUCTION",
    "MNSEContextProvider",
    "GeminiRoboticsClient",
    "GeminiResponse",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "GeminiRoboticsOrchestrator",
    "OrchestratorResult",
    "ReasoningTurn",
    "ArgonActionProposal",
    "ArgonDryRunValidator",
    "ProposalStatus",
]

