#!/usr/bin/env python3
"""
GRaCEmo ViRa — Robot Bridge Command Handler
Dispatches incoming semantic actions (from EventBus ActionRequested events)
to appropriate sub-adapters after safety validation.
"""
from __future__ import annotations
import logging
from enum import IntEnum
from typing import Any, Dict, Optional
from .navigation_adapter import NavigationAdapter
from .safety_adapter import SafetyAdapter
from .state_machine import HardwareMode, RobotState, RobotStateMachine

log = logging.getLogger("gracemo.bridge.command_handler")


class CommandPriority(IntEnum):
    EMERGENCY_STOP = 1
    STOP = 2
    SAFETY_COMMAND = 3
    ACTIVE_ROBOT_COMMAND = 4
    NORMAL_INTERACTION = 5


def get_action_priority(action: str) -> CommandPriority:
    """Returns priority level (1 = highest, 5 = lowest)."""
    if action == "EmergencyStop":
        return CommandPriority.EMERGENCY_STOP
    elif action == "Stop":
        return CommandPriority.STOP
    elif action in ("Pause", "Resume"):
        return CommandPriority.SAFETY_COMMAND
    elif action in ("NavigateTo", "NavigateToRoom", "TurnTo", "Move"):
        return CommandPriority.ACTIVE_ROBOT_COMMAND
    else:
        return CommandPriority.NORMAL_INTERACTION


class CommandHandler:
    """
    Receives validated ActionRequested commands and routes them to navigation or safety adapters.
    """

    def __init__(
        self,
        state_machine: RobotStateMachine,
        safety_adapter: SafetyAdapter,
        navigation_adapter: NavigationAdapter,
        hardware_adapter: Optional[Any] = None,
    ):
        self.sm = state_machine
        self.safety = safety_adapter
        self.nav = navigation_adapter
        self.hardware_adapter = hardware_adapter

    def handle_stop(self, reason: str = "Stop requested", trace_id: str = "trace_stop") -> bool:
        """Convenience method to execute stop action."""
        return self.handle_action("Stop", {"reason": reason}, trace_id=trace_id)

    def handle_action(
        self,
        action: str,
        params: Dict[str, Any],
        trace_id: str,
        timestamp: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Evaluates and dispatches a single semantic robot action."""
        # 1. Validate safety & preconditions
        v_res = self.safety.validate_command(action, params, timestamp=timestamp)
        if not v_res.allowed:
            log.warning(f"⛔ Command '{action}' rejected by SafetyAdapter: {v_res.reason}")
            return False

        # 2. Dispatch by action type
        if action in ("Stop", "EmergencyStop"):
            reason = params.get("reason", f"{action} commanded")
            res = self.nav.stop_immediately(reason=reason, trace_id=trace_id)
            if self.hardware_adapter and self.sm.mode != HardwareMode.SIMULATION:
                self.hardware_adapter.trigger_emergency_stop(reason=reason)
            return res

        elif action == "NavigateTo":
            try:
                x = float(params["x"])
                y = float(params["y"])
            except (KeyError, ValueError, TypeError):
                log.error(f"Malformed NavigateTo parameters: {params}")
                return False
            yaw = float(params["yaw"]) if params.get("yaw") is not None else None
            name = str(params.get("target_name") or f"Pose({x:.2f}, {y:.2f})")
            tol = float(params.get("tolerance_m", 0.30))
            return self.nav.navigate_to(
                target_x=x,
                target_y=y,
                target_name=name,
                trace_id=trace_id,
                target_yaw=yaw,
                tolerance_m=tol,
                session_id=session_id,
            )

        elif action in ("Teleop", "DriveVelocity", "Move"):
            vx = float(params.get("linear_x", params.get("vx", params.get("linear", 0.0))))
            wz = float(params.get("angular_z", params.get("wz", params.get("angular", 0.0))))
            if self.hardware_adapter:
                safe_lin, safe_ang, accepted = self.hardware_adapter.send_velocity_command(vx, wz)
                return accepted
            return True

        elif action == "AuthorizeTestMotion":
            reason = str(params.get("reason", "Test Authorized"))
            if self.hardware_adapter:
                return self.hardware_adapter.authorize_test_motion(reason=reason)
            return self.sm.authorize_test_motion(reason=reason)

        elif action == "RevokeTestMotion":
            reason = str(params.get("reason", "Test Authorization Revoked"))
            if self.hardware_adapter:
                return self.hardware_adapter.revoke_test_authorization(reason=reason)
            return self.sm.revoke_test_authorization(reason=reason)

        elif action == "Pause":
            if self.sm.state == RobotState.NAVIGATING:
                return self.sm.transition_to(RobotState.PAUSED, reason="Pause commanded")
            return True

        elif action == "Resume":
            if self.sm.state == RobotState.PAUSED:
                return self.sm.transition_to(RobotState.NAVIGATING, reason="Resume commanded")
            return True

        elif action == "LookAt":
            # Neck movement only - does NOT touch base velocity
            log.info(f"👀 LookAt action received: {params}")
            return True

        elif action == "TurnTo":
            yaw = float(params.get("yaw", 0.0))
            log.info(f"🔄 TurnTo action received: {yaw:.2f} rad")
            return True

        elif action in ("Speak", "Express"):
            # Spoken/facial actions are handled by InteractionAdapter, not the physical base
            return True

        else:
            log.warning(f"⚠️ Unhandled action type: '{action}'")
            return False
