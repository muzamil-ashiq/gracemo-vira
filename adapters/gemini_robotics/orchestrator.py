"""
GRaCEmo ViRa — Closed-Loop Embodied Reasoning Orchestrator
Coordinates the closed-loop perception-cognition-action cycle:
  OBSERVE (MNSE) -> REASON (Gemini ER 2) -> ACT (Tool Layer) -> EMIT (Kernel) -> RE-OBSERVE -> COMPLETE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from adapters.gemini_robotics.config import GeminiRoboticsConfig
from adapters.gemini_robotics.context import MNSEContextProvider
from adapters.gemini_robotics.client import GeminiRoboticsClient, ToolCall
from adapters.gemini_robotics.tools import ToolRegistry, ToolResult

log = logging.getLogger("gemini_robotics.orchestrator")


@dataclass
class ReasoningTurn:
    """Detailed trace of a single reasoning & action turn."""
    turn_index: int
    prompt_sent: str
    response_text: Optional[str]
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None


@dataclass
class OrchestratorResult:
    """Overall outcome of a multi-turn task execution."""
    success: bool
    user_command: str
    turns_count: int
    turns: List[ReasoningTurn] = field(default_factory=list)
    final_response: str = ""
    actions_dispatched: List[str] = field(default_factory=list)

    def summary(self) -> str:
        actions_str = ", ".join(self.actions_dispatched) if self.actions_dispatched else "None"
        return (
            f"Task: \"{self.user_command}\" | Success: {self.success} | "
            f"Turns: {self.turns_count} | Actions Dispatched: [{actions_str}] | "
            f"Response: {self.final_response}"
        )


class GeminiRoboticsOrchestrator:
    """
    Closed-loop Embodied Task Orchestrator powered by Gemini Robotics ER 2.
    Ensures Gemini ER 2 operates as a cognitive supervisor governing physical
    actions through verified GRaCEmo skills and kernel state.
    """

    def __init__(
        self,
        config: Optional[GeminiRoboticsConfig] = None,
        client: Optional[GeminiRoboticsClient] = None,
        registry: Optional[ToolRegistry] = None,
        context_provider: Optional[MNSEContextProvider] = None,
    ):
        self.config = config or GeminiRoboticsConfig()
        self.context_provider = context_provider or MNSEContextProvider(kernel_url=self.config.kernel_url)
        self.registry = registry or ToolRegistry(kernel_url=self.config.kernel_url)
        self.client = client or GeminiRoboticsClient(config=self.config)

    def run_task(self, user_command: str) -> OrchestratorResult:
        """
        Executes a closed-loop reasoning cycle to fulfill the user's intent.
        Cycle:
          1. Retrieve initial grounded MNSE reality.
          2. Query Gemini ER 2 with context and registered tools.
          3. Execute selected tool via GRaCEmo skill layer.
          4. Emit canonical event and retrieve updated reality.
          5. Feed feedback to Gemini until task completion or max_turns.
        """
        log.info(f"🚀 Starting embodied task: \"{user_command}\"")

        turns: List[ReasoningTurn] = []
        actions_dispatched: List[str] = []
        current_prompt = self.context_provider.build_grounded_prompt(user_command)
        tool_callables = self.registry.get_tool_callables()
        current_image_bytes: Optional[bytes] = None

        for turn_idx in range(1, self.config.max_turns + 1):
            log.debug(f"--- Reasoning Turn {turn_idx}/{self.config.max_turns} ---")

            # 1. Ask Gemini Robotics ER 2 to reason and choose an action
            response = self.client.reason(
                prompt=current_prompt,
                tools=tool_callables,
                image_bytes=current_image_bytes,
            )

            # 2. Check if a high-level tool was called
            if response.has_function_calls:
                call = response.primary_tool_call
                tool_name = call.name
                tool_args = call.args
                log.info(f"⚡ [TURN {turn_idx}] Gemini Selected Tool: {tool_name}({tool_args})")
                actions_dispatched.append(tool_name)

                # 3. Execute tool through verified GRaCEmo substrate
                tool_result = self.registry.execute(tool_name, tool_args)
                log.info(f"✓ [TURN {turn_idx}] Tool Execution Result: {tool_result.message}")

                # 4. If visual scene inspection was executed, attach latest frame for next reasoning turn
                if tool_name == "inspect_visual_scene":
                    current_image_bytes = self.context_provider.get_latest_camera_frame()
                else:
                    current_image_bytes = None

                # 5. Record turn
                turns.append(ReasoningTurn(
                    turn_index=turn_idx,
                    prompt_sent=current_prompt,
                    response_text=response.text,
                    tool_call=call,
                    tool_result=tool_result,
                ))

                # 6. Fetch updated reality context from MNSE (closed-loop feedback)
                updated_toon = self.context_provider.get_compiled_context(fmt="toon")

                # 7. Formulate feedback prompt for the next turn
                current_prompt = (
                    f"Action Completed: {tool_name}\n"
                    f"Result: {tool_result.message}\n"
                    f"Data: {tool_result.data}\n\n"
                    f"Updated MNSE Grounded State:\n"
                    f"{updated_toon}\n\n"
                    f"Original User Command: \"{user_command}\"\n\n"
                    f"Evaluate progress: If the task is finished, provide a concise verbal completion response. "
                    f"If more actions are required, invoke the next tool."
                )
            else:
                # No more tools called: Gemini completed the task and generated final explanation
                final_text = response.text or "Task completed."
                turns.append(ReasoningTurn(
                    turn_index=turn_idx,
                    prompt_sent=current_prompt,
                    response_text=final_text,
                ))
                log.info(f"🏁 Task Completed in {turn_idx} turn(s). Response: \"{final_text}\"")
                return OrchestratorResult(
                    success=True,
                    user_command=user_command,
                    turns_count=turn_idx,
                    turns=turns,
                    final_response=final_text,
                    actions_dispatched=actions_dispatched,
                )

        # Max turns reached without final text completion
        fallback_msg = (
            f"Executed actions [{', '.join(actions_dispatched)}], "
            f"reached maximum reasoning limit of {self.config.max_turns} turns."
        )
        return OrchestratorResult(
            success=True,
            user_command=user_command,
            turns_count=self.config.max_turns,
            turns=turns,
            final_response=fallback_msg,
            actions_dispatched=actions_dispatched,
        )
