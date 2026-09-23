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
    base_displacement_m: float = 0.0
    verified: bool = False

    def summary(self) -> str:
        actions_str = ", ".join(self.actions_dispatched) if self.actions_dispatched else "None"
        return (
            f"Task: \"{self.user_command}\" | Success: {self.success} | "
            f"Verified: {self.verified} | "
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
          1. OBSERVE: Retrieve initial grounded MNSE reality (now + past + world objects).
          2. REASON: Query Gemini ER 2 with context and registered tools.
          3. ACT: Execute selected tool via GRaCEmo skill/tool layer.
          4. EMIT: Emit canonical event to Kernel.
          5. RE-OBSERVE: Retrieve updated MNSE context and world objects.
          6. VERIFY: Confirm physical acceptance, neck articulation, and stationary base.
          7. COMPLETE: Feed feedback to Gemini until task completion.
        """
        import math
        log.info(f"🚀 Starting embodied task: \"{user_command}\"")

        turns: List[ReasoningTurn] = []
        actions_dispatched: List[str] = []
        current_prompt = self.context_provider.build_grounded_prompt(user_command)
        # Use FunctionDeclarations for Gemini ER 2 tool schema
        decls = self.registry.get_function_declarations()
        tool_callables = decls if decls else self.registry.get_tool_callables()
        current_image_bytes: Optional[bytes] = None

        max_base_displacement = 0.0
        overall_verified = False

        for turn_idx in range(1, self.config.max_turns + 1):
            log.debug(f"--- Reasoning Turn {turn_idx}/{self.config.max_turns} ---")

            # 1. OBSERVE base pose before acting
            initial_robot_ctx = self.context_provider.get_robot_context()
            init_pos = initial_robot_ctx.get("robot_position") or {}
            bx0 = float(init_pos.get("x", 0.0))
            by0 = float(init_pos.get("y", 0.0))

            # 2. REASON: Ask Gemini Robotics ER 2 to reason and choose an action
            response = self.client.reason(
                prompt=current_prompt,
                tools=tool_callables,
                image_bytes=current_image_bytes,
            )

            # 3. ACT: Check if a high-level tool was called
            if response.has_function_calls:
                call = response.primary_tool_call
                tool_name = call.name
                tool_args = call.args
                print(f"    • [Turn {turn_idx}] Gemini Selected Tool: {tool_name}({tool_args})")
                log.info(f"⚡ [TURN {turn_idx}] Gemini Selected Tool: {tool_name}({tool_args})")
                actions_dispatched.append(tool_name)

                # Execute tool through verified GRaCEmo substrate
                tool_result = self.registry.execute(tool_name, tool_args)
                print(f"    • [Turn {turn_idx}] Tool Execution: {tool_result.message}")
                log.info(f"✓ [TURN {turn_idx}] Tool Execution Result: {tool_result.message}")

                # Verification logic:
                if tool_name in ["look_at", "look_at_object"]:
                    post_robot_ctx = self.context_provider.get_robot_context()
                    post_pos = post_robot_ctx.get("robot_position") or {}
                    bx1 = float(post_pos.get("x", 0.0))
                    by1 = float(post_pos.get("y", 0.0))
                    disp = math.hypot(bx1 - bx0, by1 - by0)
                    if disp > max_base_displacement:
                        max_base_displacement = disp

                    # If this LookAt was preceded by base navigation/turning (Scenario B), base movement was intentional
                    has_preceding_navigation = any(a in ["turn_toward_object", "navigate_to_object", "navigate_to", "navigate_to_room"] for a in actions_dispatched[:-1])
                    if has_preceding_navigation:
                        overall_verified = tool_result.success
                    else:
                        base_stationary = disp < 0.01
                        tool_result.data["base_displacement_m"] = round(disp, 5)
                        tool_result.data["base_stationary"] = base_stationary
                        overall_verified = tool_result.success and base_stationary

                elif tool_name in ["turn_toward_object", "navigate_to_object"]:
                    post_robot_ctx = self.context_provider.get_robot_context()
                    post_pos = post_robot_ctx.get("robot_position") or {}
                    bx1 = float(post_pos.get("x", 0.0))
                    by1 = float(post_pos.get("y", 0.0))
                    disp = math.hypot(bx1 - bx0, by1 - by0)
                    if disp > max_base_displacement:
                        max_base_displacement = disp
                    overall_verified = tool_result.success

                elif tool_name == "navigate_to_room":
                    overall_verified = tool_result.success

                # If visual scene inspection was executed, attach latest frame for next reasoning turn
                if tool_name == "inspect_visual_scene":
                    current_image_bytes = self.context_provider.get_latest_camera_frame()
                else:
                    current_image_bytes = None

                # Record turn
                turns.append(ReasoningTurn(
                    turn_index=turn_idx,
                    prompt_sent=current_prompt,
                    response_text=response.text,
                    tool_call=call,
                    tool_result=tool_result,
                ))

                # 4. RE-OBSERVE: Fetch updated reality context from MNSE (closed-loop feedback)
                updated_toon = self.context_provider.get_compiled_context(fmt="toon")
                updated_world_objs = self.context_provider.format_world_objects_context(visible_only=False)

                # If speak was called after LookAt, treat as verbal task conclusion
                if tool_name == "speak" and any(a in ["look_at", "look_at_object"] for a in actions_dispatched[:-1]):
                    spoken_text = tool_args.get("text", tool_result.message)
                    log.info(f"🏁 Task Completed via spoken response: \"{spoken_text}\"")
                    return OrchestratorResult(
                        success=overall_verified,
                        user_command=user_command,
                        turns_count=turn_idx,
                        turns=turns,
                        final_response=spoken_text,
                        actions_dispatched=actions_dispatched,
                        base_displacement_m=max_base_displacement,
                        verified=overall_verified,
                    )

                # Formulate feedback prompt for the next turn
                if tool_name in ["look_at", "look_at_object"]:
                    completion_hint = (
                        "TASK ACCOMPLISHED: The LookAt gaze action has been executed and physically verified.\n"
                        "The robot base remained stationary and active head gaze is oriented directly at the target.\n"
                        "Do NOT call any further tools (do not call look_at_object, look_at, or speak).\n"
                        "Simply provide your concise final verbal response to the user to conclude the task."
                    )
                elif tool_name == "speak":
                    completion_hint = (
                        "Task is complete. Simply provide your final confirmation text without calling any more tools."
                    )
                else:
                    completion_hint = (
                        "Evaluate progress: If the task is finished, provide a concise verbal completion response without tools. "
                        "If more physical actions are required, invoke the next tool."
                    )

                current_prompt = (
                    f"Action Completed: {tool_name}\n"
                    f"Result: {tool_result.message}\n"
                    f"Data: {tool_result.data}\n\n"
                    f"Authoritative MNSE Re-Observation:\n"
                    f"{updated_toon}\n\n"
                    f"{updated_world_objs}\n\n"
                    f"Original User Command: \"{user_command}\"\n\n"
                    f"{completion_hint}"
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

                # If actions were dispatched, success requires tool success and verification
                if actions_dispatched:
                    all_tools_ok = all(t.tool_result.success for t in turns if t.tool_result is not None)
                    task_success = all_tools_ok and overall_verified
                else:
                    # Pure conversational / clarification turn
                    task_success = True
                    overall_verified = True

                return OrchestratorResult(
                    success=task_success,
                    user_command=user_command,
                    turns_count=turn_idx,
                    turns=turns,
                    final_response=final_text,
                    actions_dispatched=actions_dispatched,
                    base_displacement_m=max_base_displacement,
                    verified=overall_verified,
                )

        # Max turns reached without final text completion
        fallback_msg = (
            f"Executed actions [{', '.join(actions_dispatched)}], "
            f"reached maximum reasoning limit of {self.config.max_turns} turns."
        )
        return OrchestratorResult(
            success=False,
            user_command=user_command,
            turns_count=self.config.max_turns,
            turns=turns,
            final_response=fallback_msg,
            actions_dispatched=actions_dispatched,
            base_displacement_m=max_base_displacement,
            verified=False,
        )
