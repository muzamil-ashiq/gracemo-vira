"""
GraceEMO Interaction — Data Models
Pure Python dataclasses replacing ROS 2 msg/srv definitions.
No ROS 2 dependencies.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VoiceCommand:
    """Equivalent to gracemo_interfaces/msg/VoiceCommand."""
    transcript: str = ""
    intent: str = "GENERAL_QUERY"
    confidence: float = 0.0
    entities: List[str] = field(default_factory=list)
    audio_duration: float = 0.0


@dataclass
class AskQuestionRequest:
    """Equivalent to gracemo_interfaces/srv/AskQuestion Request."""
    question: str = ""
    context: str = ""


@dataclass
class AskQuestionResponse:
    """Equivalent to gracemo_interfaces/srv/AskQuestion Response."""
    answer: str = "I understand."
    intent: str = "GENERAL_QUERY"
    confidence: float = 0.7
    suggested_actions: List[str] = field(default_factory=lambda: ["speak"])


@dataclass
class ActionResult:
    """Result of an action dispatched by the interaction loop."""
    action: str = "speak"
    target: str = ""
    text: str = ""
    x: float = 0.0
    y: float = 0.0


@dataclass
class InspectorState:
    """
    Unified cognitive telemetry — pure Python equivalent of the
    InspectorState class in planner_node.py.
    """
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    battery: float = 98.5
    obstacle_ahead: bool = False
    obstacle_distance: float = 12.0
    obstacle_direction: str = "none"
    person_visible: bool = False
    person_distance: float = 99.0
    person_bearing: float = 0.0
    last_voice: str = ""
    current_task: str = "IDLE"
    status: str = "READY"

    def to_dict(self) -> dict:
        return {
            "pose": {"x": round(self.x, 3), "y": round(self.y, 3), "yaw": round(self.yaw, 3)},
            "battery": round(self.battery, 1),
            "obstacle": {
                "detected": self.obstacle_ahead,
                "distance": round(self.obstacle_distance, 2),
                "direction": self.obstacle_direction,
            },
            "person": {
                "visible": self.person_visible,
                "distance": round(self.person_distance, 2) if self.person_visible else None,
                "bearing": round(self.person_bearing, 2) if self.person_visible else None,
            },
            "last_voice_command": self.last_voice,
            "task": self.current_task,
            "status": self.status,
        }
