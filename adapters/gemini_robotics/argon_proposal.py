"""
GRaCEmo ViRa — Gemini Argon Stage A Dry-Run Proposal Layer
Validates proposed actions from Gemini 4 Argon without executing any tool,
publishing ROS commands, or emitting events to the Kernel.
"""

from __future__ import annotations

import math
import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Set

log = logging.getLogger("gemini_robotics.argon_proposal")


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    REJECTED_UNSUPPORTED_TOOL = "REJECTED_UNSUPPORTED_TOOL"
    REJECTED_INVALID_ARGUMENTS = "REJECTED_INVALID_ARGUMENTS"
    REJECTED_OUT_OF_BOUNDS = "REJECTED_OUT_OF_BOUNDS"
    REJECTED_MULTIPLE_TOOL_CALLS = "REJECTED_MULTIPLE_TOOL_CALLS"


@dataclass
class ArgonActionProposal:
    """Represents an inspected, validated action proposal during Stage A dry-run."""
    proposal_id: str
    turn_index: int
    user_command: str
    tool_name: str
    arguments: Dict[str, Any]
    status: ProposalStatus
    validation_error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    model: str = "gemini-4-argon"
    dry_run: bool = True
    executed: bool = False
    emitted_to_kernel: bool = False
    ros_published: bool = False

    @property
    def is_valid(self) -> bool:
        return self.status == ProposalStatus.PROPOSED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "turn_index": self.turn_index,
            "user_command": self.user_command,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status.value,
            "validation_error": self.validation_error,
            "timestamp": self.timestamp,
            "model": self.model,
            "dry_run": self.dry_run,
            "executed": self.executed,
            "emitted_to_kernel": self.emitted_to_kernel,
            "ros_published": self.ros_published,
        }


# Whitelist of officially registered GRaCEmo high-level robot tools
DEFAULT_SUPPORTED_TOOLS: Set[str] = {
    "navigate_to_room",
    "navigate_to",
    "look_at",
    "look_at_object",
    "turn_toward_object",
    "navigate_to_object",
    "inspect_visual_scene",
    "find_object",
    "pick_object",
    "verify_grasp",
    "place_object",
    "speak",
    "show_emotion",
    "stop",
    "get_robot_state",
    "get_world_state",
    "scan_room",
    "explore_room",
    "explore_apartment",
}


class ArgonDryRunValidator:
    """
    Validates Gemini 4 Argon proposed tool calls strictly offline.
    Guarantees:
      - 0 physical tool executions
      - 0 ROS /cmd_vel or motor publications
      - 0 HTTP POST /emit requests to MNSE Kernel
      - Complete audit log of all validated / rejected proposals
    """

    def __init__(
        self,
        bounds_x: Tuple[float, float] = (-9.5, 9.5),
        bounds_y: Tuple[float, float] = (-7.5, 7.5),
        supported_tools: Optional[Set[str]] = None,
    ):
        self.bounds_x = bounds_x
        self.bounds_y = bounds_y
        self.supported_tools = set(supported_tools) if supported_tools else set(DEFAULT_SUPPORTED_TOOLS)
        self.proposals_record: List[ArgonActionProposal] = []

    def validate_tool_calls(
        self,
        tool_calls: List[Any],
        turn_index: int,
        user_command: str,
        model: str = "gemini-4-argon",
    ) -> Tuple[Optional[ArgonActionProposal], List[ArgonActionProposal]]:
        """
        Validates a list of tool calls received from a single reasoning turn.
        Returns:
            (primary_valid_proposal, all_proposals_in_this_turn)
        """
        if not tool_calls:
            return None, []

        turn_proposals: List[ArgonActionProposal] = []

        # 1. Reject multiple tool calls in a single turn
        if len(tool_calls) > 1:
            tool_names = [getattr(c, "name", str(c)) for c in tool_calls]
            err_msg = (
                f"Multiple tool calls detected in single turn ({tool_names}). "
                f"Stage A policy allows at most one action per reasoning turn."
            )
            log.warning(f"⚠️ [ARGON DRY-RUN REJECTED] {err_msg}")
            for c in tool_calls:
                name = getattr(c, "name", "unknown")
                args = getattr(c, "args", {}) if hasattr(c, "args") else {}
                proposal = ArgonActionProposal(
                    proposal_id=str(uuid.uuid4()),
                    turn_index=turn_index,
                    user_command=user_command,
                    tool_name=name,
                    arguments=args,
                    status=ProposalStatus.REJECTED_MULTIPLE_TOOL_CALLS,
                    validation_error=err_msg,
                    model=model,
                )
                turn_proposals.append(proposal)
                self.proposals_record.append(proposal)
            return None, turn_proposals

        # Exactly 1 tool call
        call = tool_calls[0]
        tool_name = getattr(call, "name", "")
        args = getattr(call, "args", {}) if hasattr(call, "args") else {}
        proposal_id = str(uuid.uuid4())

        # 2. Reject unsupported tools
        if tool_name not in self.supported_tools:
            err_msg = f"Tool '{tool_name}' is not in the supported tools whitelist."
            log.warning(f"⚠️ [ARGON DRY-RUN REJECTED] {err_msg}")
            proposal = ArgonActionProposal(
                proposal_id=proposal_id,
                turn_index=turn_index,
                user_command=user_command,
                tool_name=tool_name,
                arguments=args,
                status=ProposalStatus.REJECTED_UNSUPPORTED_TOOL,
                validation_error=err_msg,
                model=model,
            )
            turn_proposals.append(proposal)
            self.proposals_record.append(proposal)
            return None, turn_proposals

        # 3. Validate arguments and spatial bounds
        status, error_msg = self._validate_tool_arguments(tool_name, args)
        proposal = ArgonActionProposal(
            proposal_id=proposal_id,
            turn_index=turn_index,
            user_command=user_command,
            tool_name=tool_name,
            arguments=args,
            status=status,
            validation_error=error_msg,
            model=model,
        )
        turn_proposals.append(proposal)
        self.proposals_record.append(proposal)

        if status == ProposalStatus.PROPOSED:
            log.info(f"✓ [ARGON DRY-RUN PROPOSED] Turn {turn_index}: {tool_name}({args})")
            return proposal, turn_proposals
        else:
            log.warning(f"⚠️ [ARGON DRY-RUN REJECTED] Turn {turn_index}: {tool_name} -> {status.value}: {error_msg}")
            return None, turn_proposals

    def _validate_tool_arguments(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Tuple[ProposalStatus, Optional[str]]:
        """Validates tool parameters and navigation boundaries."""
        if not isinstance(args, dict):
            return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "Arguments must be a key-value dictionary."

        # Navigation to specific metric coordinates
        if tool_name == "navigate_to":
            if "x" not in args or "y" not in args:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "navigate_to requires 'x' and 'y' coordinates."
            if isinstance(args["x"], bool) or isinstance(args["y"], bool):
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "Coordinates 'x' and 'y' cannot be boolean values."
            try:
                x = float(args["x"])
                y = float(args["y"])
            except (ValueError, TypeError):
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "Coordinates 'x' and 'y' must be valid numbers."

            if not (math.isfinite(x) and math.isfinite(y)):
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, f"Coordinates cannot be NaN or Inf: ({x}, {y})"

            if not (self.bounds_x[0] <= x <= self.bounds_x[1] and self.bounds_y[0] <= y <= self.bounds_y[1]):
                return (
                    ProposalStatus.REJECTED_OUT_OF_BOUNDS,
                    f"Coordinates ({x:.2f}, {y:.2f}) exceed safe boundary limits "
                    f"X:[{self.bounds_x[0]}, {self.bounds_x[1]}], Y:[{self.bounds_y[0]}, {self.bounds_y[1]}].",
                )
            return ProposalStatus.PROPOSED, None

        # Navigation to room
        if tool_name == "navigate_to_room":
            room = args.get("room")
            if not room or not isinstance(room, str) or len(room.strip()) < 2:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "navigate_to_room requires a non-empty 'room' string."
            return ProposalStatus.PROPOSED, None

        # LookAt 3D coordinate gaze
        if tool_name == "look_at":
            for axis in ("x", "y", "z"):
                if axis not in args:
                    return ProposalStatus.REJECTED_INVALID_ARGUMENTS, f"look_at requires '{axis}' coordinate."
                if isinstance(args[axis], bool):
                    return ProposalStatus.REJECTED_INVALID_ARGUMENTS, f"look_at '{axis}' cannot be a boolean value."
                try:
                    val = float(args[axis])
                    if not math.isfinite(val):
                        return ProposalStatus.REJECTED_INVALID_ARGUMENTS, f"look_at '{axis}' must be finite: {val}"
                except (ValueError, TypeError):
                    return ProposalStatus.REJECTED_INVALID_ARGUMENTS, f"look_at '{axis}' must be a number."
            return ProposalStatus.PROPOSED, None


        # LookAt object gaze
        if tool_name == "look_at_object":
            obj_name = args.get("object_name")
            if not obj_name or not isinstance(obj_name, str) or len(obj_name.strip()) == 0:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "look_at_object requires non-empty 'object_name'."
            return ProposalStatus.PROPOSED, None

        # Turn toward object
        if tool_name == "turn_toward_object":
            obj_name = args.get("object_name")
            if not obj_name or not isinstance(obj_name, str) or len(obj_name.strip()) == 0:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "turn_toward_object requires non-empty 'object_name'."
            return ProposalStatus.PROPOSED, None

        # Navigate to object
        if tool_name == "navigate_to_object":
            obj_name = args.get("object_name")
            if not obj_name or not isinstance(obj_name, str) or len(obj_name.strip()) == 0:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "navigate_to_object requires non-empty 'object_name'."
            return ProposalStatus.PROPOSED, None

        # Speak
        if tool_name == "speak":
            text = args.get("text")
            if not text or not isinstance(text, str) or len(text.strip()) == 0:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "speak requires non-empty 'text' string."
            return ProposalStatus.PROPOSED, None

        # Show emotion
        if tool_name == "show_emotion":
            emotion = args.get("emotion")
            if not emotion or not isinstance(emotion, str) or len(emotion.strip()) == 0:
                return ProposalStatus.REJECTED_INVALID_ARGUMENTS, "show_emotion requires non-empty 'emotion' string."
            return ProposalStatus.PROPOSED, None

        # Other tools without mandatory parameters (e.g. stop, get_robot_state, get_world_state, inspect_visual_scene)
        return ProposalStatus.PROPOSED, None

    def get_proposals_record(self) -> List[ArgonActionProposal]:
        return list(self.proposals_record)

    def clear_record(self):
        self.proposals_record.clear()
