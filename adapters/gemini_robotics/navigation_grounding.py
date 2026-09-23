"""
GRaCEmo ViRa — Navigation-Grounded Object Interaction (Phase 4 Step 4)
Provides:
  1. GazeWorkspaceEvaluator: Authoritative classification of object reachability
     (GAZE_REACHABLE, BASE_TURN_REQUIRED, NAVIGATION_REQUIRED, UNSAFE).
  2. NavigationGroundedStateMachine: Explicit deterministic state machine executing
     object-grounded navigation and closed-loop gaze completion.
"""

from __future__ import annotations

import math
import sys
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
for p in [
    ROOT_DIR / "ros2_ws" / "src" / "gracemo_bridge" / "gracemo_bridge",
    ROOT_DIR / "adapters" / "perception",
    ROOT_DIR / "adapters" / "gemini_robotics",
]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from gracemo_bridge.kernel_bridge import compute_look_at
except ImportError:
    try:
        from kernel_bridge import compute_look_at
    except ImportError:
        # Standalone kinematic fallback matching authoritative equations
        def compute_look_at(
            target_x: float, target_y: float, target_z: float,
            robot_x: float = 0.0, robot_y: float = 0.0, robot_z: float = 0.0,
            robot_yaw: float = 0.0,
        ) -> dict:
            x_neck = robot_x - 0.02 * math.cos(robot_yaw)
            y_neck = robot_y - 0.02 * math.sin(robot_yaw)
            z_neck = robot_z + 0.645

            dx_world = target_x - x_neck
            dy_world = target_y - y_neck
            dz_world = target_z - z_neck

            dx_robot = dx_world * math.cos(robot_yaw) + dy_world * math.sin(robot_yaw)
            dy_robot = -dx_world * math.sin(robot_yaw) + dy_world * math.cos(robot_yaw)
            dz_robot = dz_world

            pan = math.atan2(dy_robot, dx_robot)
            horizontal_dist = math.hypot(dx_robot, dy_robot)
            tilt = math.atan2(-dz_robot, horizontal_dist)

            pan_limit = 2.0944   # ±120°
            tilt_limit = 0.7854  # ±45°
            eps = 1e-5

            reasons = []
            if pan < -pan_limit - eps or pan > pan_limit + eps:
                reasons.append(f"pan {math.degrees(pan):+.1f}° outside limits")
            if tilt < -tilt_limit - eps or tilt > tilt_limit + eps:
                reasons.append(f"tilt {math.degrees(tilt):+.1f}° outside limits")

            exceeded = len(reasons) > 0
            return {
                "success": not exceeded,
                "workspace_exceeded": exceeded,
                "target": {"x": float(target_x), "y": float(target_y), "z": float(target_z)},
                "pan_rad": float(pan),
                "tilt_rad": float(tilt),
                "pan_deg": float(math.degrees(pan)),
                "tilt_deg": float(math.degrees(tilt)),
                "reason": "; ".join(reasons),
            }

from adapters.perception.world_model import WorldObject
from adapters.gemini_robotics.context import MNSEContextProvider, ObjectResolutionResult

log = logging.getLogger("gemini_robotics.navigation_grounding")


class WorkspaceReachability(str, Enum):
    GAZE_REACHABLE = "GAZE_REACHABLE"
    BASE_TURN_REQUIRED = "BASE_TURN_REQUIRED"
    NAVIGATION_REQUIRED = "NAVIGATION_REQUIRED"
    UNSAFE = "UNSAFE"


class NavigationState(str, Enum):
    IDLE = "IDLE"
    RESOLVING = "RESOLVING"
    TARGET_VALIDATED = "TARGET_VALIDATED"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    STOPPING = "STOPPING"
    SETTLING = "SETTLING"
    REOBSERVING = "REOBSERVING"
    LOOKING = "LOOKING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    COLLISION_STOP = "COLLISION_STOP"
    OBJECT_LOST = "OBJECT_LOST"


@dataclass
class WorkspaceEvaluationResult:
    status: WorkspaceReachability
    target_object_id: str
    target_xyz: Tuple[float, float, float]
    robot_pose: Tuple[float, float, float, float]  # (x, y, z, yaw)
    distance_m: float
    relative_bearing_rad: float
    kinematic_pan_deg: float
    kinematic_tilt_deg: float
    recommended_turn_yaw: Optional[float] = None
    recommended_nav_pose: Optional[Tuple[float, float, float]] = None  # (x, y, yaw)
    reason: str = ""

    @property
    def is_gaze_reachable(self) -> bool:
        return self.status == WorkspaceReachability.GAZE_REACHABLE

    @property
    def requires_base_motion(self) -> bool:
        return self.status in (WorkspaceReachability.BASE_TURN_REQUIRED, WorkspaceReachability.NAVIGATION_REQUIRED)


class GazeWorkspaceEvaluator:
    """
    Evaluates whether an authoritative persistent 3D world object is within
    the active 2-DOF neck mechanical workspace (±120° pan, ±45° tilt) from
    the robot's current pose, or whether base turning or translation is required.
    """

    def __init__(
        self,
        min_interaction_dist_m: float = 0.35,
        max_turn_only_dist_m: float = 5.00,
        default_standoff_dist_m: float = 1.20,
    ):
        self.min_interaction_dist = min_interaction_dist_m
        self.max_turn_only_dist = max_turn_only_dist_m
        self.default_standoff_dist = default_standoff_dist_m

    def evaluate(
        self,
        target_obj: WorldObject,
        robot_pose: Dict[str, Any],
        desired_standoff_m: Optional[float] = None,
    ) -> WorkspaceEvaluationResult:
        """
        Evaluates physical reachability of target_obj from robot_pose.
        robot_pose expected format: {"x": float, "y": float, "theta"|"yaw": float, "z"?: float}
        """
        standoff_dist = desired_standoff_m or self.default_standoff_dist

        # 1. Validate finite coordinates
        tx, ty, tz = target_obj.world_x, target_obj.world_y, target_obj.world_z
        if not (math.isfinite(tx) and math.isfinite(ty) and math.isfinite(tz)):
            return WorkspaceEvaluationResult(
                status=WorkspaceReachability.UNSAFE,
                target_object_id=target_obj.object_id,
                target_xyz=(tx, ty, tz),
                robot_pose=(0.0, 0.0, 0.0, 0.0),
                distance_m=0.0,
                relative_bearing_rad=0.0,
                kinematic_pan_deg=0.0,
                kinematic_tilt_deg=0.0,
                reason=f"Target coordinates are non-finite: ({tx}, {ty}, {tz})",
            )

        rx = float(robot_pose.get("x", 0.0))
        ry = float(robot_pose.get("y", 0.0))
        rz = float(robot_pose.get("z", 0.0))
        ryaw = float(robot_pose.get("theta", robot_pose.get("yaw", 0.0)))

        dx = tx - rx
        dy = ty - ry
        dist = math.hypot(dx, dy)
        bearing = math.atan2(dy, dx)
        rel_bearing = bearing - ryaw
        while rel_bearing > math.pi: rel_bearing -= 2.0 * math.pi
        while rel_bearing < -math.pi: rel_bearing += 2.0 * math.pi

        # 2. Run authoritative LookAt inverse kinematics from current pose
        look_res = compute_look_at(
            target_x=tx, target_y=ty, target_z=tz,
            robot_x=rx, robot_y=ry, robot_z=rz,
            robot_yaw=ryaw,
        )

        pan_deg = look_res.get("pan_deg", math.degrees(rel_bearing))
        tilt_deg = look_res.get("tilt_deg", 0.0)

        # 3. Check if directly gaze-reachable
        if not look_res.get("workspace_exceeded", False):
            return WorkspaceEvaluationResult(
                status=WorkspaceReachability.GAZE_REACHABLE,
                target_object_id=target_obj.object_id,
                target_xyz=(tx, ty, tz),
                robot_pose=(rx, ry, rz, ryaw),
                distance_m=round(dist, 3),
                relative_bearing_rad=round(rel_bearing, 4),
                kinematic_pan_deg=round(pan_deg, 2),
                kinematic_tilt_deg=round(tilt_deg, 2),
                reason="Object is within active neck workspace (pan ±120°, tilt ±45°). No base motion required.",
            )

        # 4. Gaze workspace exceeded: Evaluate TurnTo vs NavigateTo
        # Check if aligning base heading to bearing makes it gaze-reachable
        turn_check = compute_look_at(
            target_x=tx, target_y=ty, target_z=tz,
            robot_x=rx, robot_y=ry, robot_z=rz,
            robot_yaw=bearing,
        )

        # If aligned heading solves workspace and distance is within acceptable interaction bounds
        if not turn_check.get("workspace_exceeded", False) and (self.min_interaction_dist <= dist <= self.max_turn_only_dist):
            return WorkspaceEvaluationResult(
                status=WorkspaceReachability.BASE_TURN_REQUIRED,
                target_object_id=target_obj.object_id,
                target_xyz=(tx, ty, tz),
                robot_pose=(rx, ry, rz, ryaw),
                distance_m=round(dist, 3),
                relative_bearing_rad=round(rel_bearing, 4),
                kinematic_pan_deg=round(pan_deg, 2),
                kinematic_tilt_deg=round(tilt_deg, 2),
                recommended_turn_yaw=round(bearing, 4),
                reason=f"Object is outside neck pan limits ({pan_deg:+.1f}°) but at acceptable distance ({dist:.2f}m). In-place base rotation to {math.degrees(bearing):+.1f}° required.",
            )

        # 5. Translation is required to achieve a safe observation vantage point
        # Compute safe standoff position along the line connecting robot to object
        nav_x = tx - standoff_dist * math.cos(bearing)
        nav_y = ty - standoff_dist * math.sin(bearing)
        nav_yaw = bearing

        # Check world bounds safety (apartment floor boundary: x in [-9, 9], y in [-7, 7])
        if not (-9.5 <= nav_x <= 9.5 and -7.5 <= nav_y <= 7.5):
            return WorkspaceEvaluationResult(
                status=WorkspaceReachability.UNSAFE,
                target_object_id=target_obj.object_id,
                target_xyz=(tx, ty, tz),
                robot_pose=(rx, ry, rz, ryaw),
                distance_m=round(dist, 3),
                relative_bearing_rad=round(rel_bearing, 4),
                kinematic_pan_deg=round(pan_deg, 2),
                kinematic_tilt_deg=round(tilt_deg, 2),
                reason=f"Calculated navigation standoff goal ({nav_x:.2f}, {nav_y:.2f}) violates world bounds.",
            )

        return WorkspaceEvaluationResult(
            status=WorkspaceReachability.NAVIGATION_REQUIRED,
            target_object_id=target_obj.object_id,
            target_xyz=(tx, ty, tz),
            robot_pose=(rx, ry, rz, ryaw),
            distance_m=round(dist, 3),
            relative_bearing_rad=round(rel_bearing, 4),
            kinematic_pan_deg=round(pan_deg, 2),
            kinematic_tilt_deg=round(tilt_deg, 2),
            recommended_turn_yaw=round(bearing, 4),
            recommended_nav_pose=(round(nav_x, 3), round(nav_y, 3), round(nav_yaw, 4)),
            reason=f"Object requires translation (current dist={dist:.2f}m, pan={pan_deg:+.1f}°). Navigating to safe standoff vantage point ({nav_x:.2f}, {nav_y:.2f}) facing object.",
        )


@dataclass
class StateMachineExecutionResult:
    success: bool
    state: NavigationState
    target_object_id: str
    action_dispatched: str  # "look_at", "turn_to", "navigate_to"
    initial_pose: Tuple[float, float, float]
    final_pose: Tuple[float, float, float]
    base_displacement_m: float
    re_observed: bool
    final_look_at_success: bool
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class NavigationGroundedStateMachine:
    """
    Deterministic execution state machine for navigation-grounded object interaction:
      IDLE -> RESOLVING -> TARGET_VALIDATED -> PLANNING -> NAVIGATING
           -> STOPPING -> SETTLING -> REOBSERVING -> LOOKING -> VERIFYING -> COMPLETE
    """

    def __init__(
        self,
        context_provider: MNSEContextProvider,
        emit_action_fn: Callable[[str, Dict[str, Any]], bool],
        look_at_fn: Callable[[float, float, float], Any],
        perception_fn: Optional[Callable[[], Any]] = None,
        evaluator: Optional[GazeWorkspaceEvaluator] = None,
        timeout_sec: float = 20.0,
    ):
        self.context_provider = context_provider
        self.emit_action = emit_action_fn
        self.look_at = look_at_fn
        self.perception_fn = perception_fn
        self.evaluator = evaluator or GazeWorkspaceEvaluator()
        self.timeout_sec = timeout_sec

        self.current_state = NavigationState.IDLE
        self.bumper_hit = False

    def trigger_collision_stop(self):
        """External safety trigger called on bumper/contact sensor event."""
        self.bumper_hit = True
        self.current_state = NavigationState.COLLISION_STOP
        self.emit_action("Stop", {})
        log.warning("🚨 [STATE MACHINE] Emergency Bumper Collision Stop Triggered!")

    def execute(
        self,
        object_name: str,
        preferred_action: Optional[str] = None,  # "turn", "navigate", or None (auto)
        desired_standoff_m: float = 1.20,
    ) -> StateMachineExecutionResult:
        """Executes the full object-grounded navigation and gaze cycle."""
        self.current_state = NavigationState.IDLE
        self.bumper_hit = False

        init_ctx = self.context_provider.get_robot_context()
        init_pos = init_ctx.get("robot_position") or {}
        rx0 = float(init_pos.get("x", 0.0))
        ry0 = float(init_pos.get("y", 0.0))
        ryaw0 = float(init_pos.get("theta", init_pos.get("yaw", 0.0)))
        initial_pose = (rx0, ry0, ryaw0)

        # 1. RESOLVING
        self.current_state = NavigationState.RESOLVING
        log.info(f"[STATE MACHINE] State: RESOLVING ('{object_name}')")
        resolution = self.context_provider.resolve_object(object_name, visible_only=True)

        if not resolution.is_resolved:
            self.current_state = NavigationState.FAILED
            return StateMachineExecutionResult(
                success=False,
                state=self.current_state,
                target_object_id=object_name,
                action_dispatched="none",
                initial_pose=initial_pose,
                final_pose=initial_pose,
                base_displacement_m=0.0,
                re_observed=False,
                final_look_at_success=False,
                message=f"Object resolution failed: {resolution.status} - {resolution.message}",
                metadata={"resolution_status": resolution.status},
            )

        target_obj = resolution.object
        target_id = target_obj.object_id

        # 2. TARGET_VALIDATED & GAZE WORKSPACE CHECK
        self.current_state = NavigationState.TARGET_VALIDATED
        log.info(f"[STATE MACHINE] State: TARGET_VALIDATED ({target_id} at ({target_obj.world_x:.2f}, {target_obj.world_y:.2f}, {target_obj.world_z:.2f}))")

        ws_eval = self.evaluator.evaluate(
            target_obj=target_obj,
            robot_pose={"x": rx0, "y": ry0, "yaw": ryaw0, "theta": ryaw0},
            desired_standoff_m=desired_standoff_m,
        )

        if ws_eval.status == WorkspaceReachability.UNSAFE:
            self.current_state = NavigationState.FAILED
            return StateMachineExecutionResult(
                success=False,
                state=self.current_state,
                target_object_id=target_id,
                action_dispatched="none",
                initial_pose=initial_pose,
                final_pose=initial_pose,
                base_displacement_m=0.0,
                re_observed=False,
                final_look_at_success=False,
                message=f"Workspace evaluation returned UNSAFE: {ws_eval.reason}",
                metadata={"workspace_evaluation": ws_eval.status},
            )

        # If directly gaze-reachable, execute pure LookAt without base motion (Step 3 compatible)
        if ws_eval.is_gaze_reachable and preferred_action != "navigate":
            log.info(f"✓ [STATE MACHINE] Object {target_id} is GAZE_REACHABLE. Skipping base locomotion.")
            self.current_state = NavigationState.LOOKING
            look_res = self.look_at(target_obj.world_x, target_obj.world_y, target_obj.world_z)
            self.current_state = NavigationState.VERIFYING if look_res.success else NavigationState.FAILED
            if self.current_state == NavigationState.VERIFYING:
                self.current_state = NavigationState.COMPLETE
            return StateMachineExecutionResult(
                success=look_res.success,
                state=self.current_state,
                target_object_id=target_id,
                action_dispatched="look_at",
                initial_pose=initial_pose,
                final_pose=initial_pose,
                base_displacement_m=0.0,
                re_observed=True,
                final_look_at_success=look_res.success,
                message=f"Direct LookAt executed for {target_id} (base stationary: displacement=0.00m).",
                metadata={"workspace": ws_eval.status.value},
            )

        # 3. PLANNING
        self.current_state = NavigationState.PLANNING
        log.info(f"[STATE MACHINE] State: PLANNING (Action required: {ws_eval.status.value})")

        chosen_action = "turn_to" if ws_eval.status == WorkspaceReachability.BASE_TURN_REQUIRED and preferred_action != "navigate" else "navigate_to"

        if chosen_action == "turn_to":
            target_yaw = ws_eval.recommended_turn_yaw if ws_eval.recommended_turn_yaw is not None else ryaw0
            action_name = "TurnTo"
            action_params = {"yaw": target_yaw}
        else:
            nav_pose = ws_eval.recommended_nav_pose
            if not nav_pose:
                self.current_state = NavigationState.FAILED
                return StateMachineExecutionResult(
                    success=False,
                    state=self.current_state,
                    target_object_id=target_id,
                    action_dispatched="none",
                    initial_pose=initial_pose,
                    final_pose=initial_pose,
                    base_displacement_m=0.0,
                    re_observed=False,
                    final_look_at_success=False,
                    message="Planning failed: No valid navigation standoff pose.",
                )
            action_name = "NavigateTo"
            action_params = {"x": nav_pose[0], "y": nav_pose[1], "yaw": nav_pose[2]}

        # 4. NAVIGATING: Emit canonical ActionRequested to Rust Kernel EventBus
        self.current_state = NavigationState.NAVIGATING
        log.info(f"🚀 [STATE MACHINE] State: NAVIGATING -> Emitting ActionRequested::{action_name}({action_params})")
        emitted = self.emit_action(action_name, action_params)
        if not emitted:
            self.current_state = NavigationState.FAILED
            return StateMachineExecutionResult(
                success=False,
                state=self.current_state,
                target_object_id=target_id,
                action_dispatched=chosen_action,
                initial_pose=initial_pose,
                final_pose=initial_pose,
                base_displacement_m=0.0,
                re_observed=False,
                final_look_at_success=False,
                message=f"Failed to emit ActionRequested::{action_name} to Kernel EventBus.",
            )

        # Wait for physical locomotion to complete with timeout & bumper checks
        t0 = time.time()
        reached = False
        while time.time() - t0 < self.timeout_sec:
            if self.bumper_hit:
                self.current_state = NavigationState.COLLISION_STOP
                self.emit_action("Stop", {})
                return StateMachineExecutionResult(
                    success=False,
                    state=self.current_state,
                    target_object_id=target_id,
                    action_dispatched=chosen_action,
                    initial_pose=initial_pose,
                    final_pose=initial_pose,
                    base_displacement_m=0.0,
                    re_observed=False,
                    final_look_at_success=False,
                    message="Locomotion aborted due to physical bumper contact collision.",
                )

            time.sleep(0.5)
            # Check current odometry pose
            cur_ctx = self.context_provider.get_robot_context()
            cur_pos = cur_ctx.get("robot_position") or {}
            cx = float(cur_pos.get("x", rx0))
            cy = float(cur_pos.get("y", ry0))
            cyaw = float(cur_pos.get("theta", cur_pos.get("yaw", ryaw0)))

            if chosen_action == "turn_to":
                err = abs(target_yaw - cyaw)
                while err > math.pi: err -= 2.0 * math.pi
                while err < -math.pi: err += 2.0 * math.pi
                if abs(err) < 0.12:  # ~7 degrees
                    reached = True
                    break
            else:
                d_goal = math.hypot(nav_pose[0] - cx, nav_pose[1] - cy)
                if d_goal < 0.35:
                    reached = True
                    break

        if not reached and (time.time() - t0 >= self.timeout_sec):
            self.current_state = NavigationState.TIMEOUT
            self.emit_action("Stop", {})
            return StateMachineExecutionResult(
                success=False,
                state=self.current_state,
                target_object_id=target_id,
                action_dispatched=chosen_action,
                initial_pose=initial_pose,
                final_pose=(cx, cy, cyaw),
                base_displacement_m=math.hypot(cx - rx0, cy - ry0),
                re_observed=False,
                final_look_at_success=False,
                message=f"Locomotion timed out after {self.timeout_sec:.1f}s.",
            )

        # 5. STOPPING & SETTLING
        self.current_state = NavigationState.STOPPING
        self.emit_action("Stop", {})
        self.current_state = NavigationState.SETTLING
        log.info("[STATE MACHINE] State: SETTLING (Allowing physics and odom to stabilize)...")
        time.sleep(1.0)

        # Capture post-navigation pose
        settled_ctx = self.context_provider.get_robot_context()
        settled_pos = settled_ctx.get("robot_position") or {}
        rx1 = float(settled_pos.get("x", rx0))
        ry1 = float(settled_pos.get("y", ry0))
        ryaw1 = float(settled_pos.get("theta", settled_pos.get("yaw", ryaw0)))
        final_pose = (rx1, ry1, ryaw1)
        base_disp = math.hypot(rx1 - rx0, ry1 - ry0)

        # 6. REOBSERVING
        self.current_state = NavigationState.REOBSERVING
        log.info(f"[STATE MACHINE] State: REOBSERVING ({target_id} from new pose ({rx1:.2f}, {ry1:.2f}, {math.degrees(ryaw1):.1f}°))...")
        if self.perception_fn:
            try:
                self.perception_fn()
            except Exception as e:
                log.warning(f"Perception frame trigger error: {e}")
            time.sleep(0.5)

        # Query updated MNSE persistent object
        re_obj = self.context_provider.get_world_object_by_id(target_id)
        if not re_obj or not re_obj.currently_visible:
            # Fallback to class query
            re_res = self.context_provider.resolve_object(target_obj.class_name, visible_only=True)
            if re_res.is_resolved:
                re_obj = re_res.object

        if not re_obj:
            self.current_state = NavigationState.OBJECT_LOST
            return StateMachineExecutionResult(
                success=False,
                state=self.current_state,
                target_object_id=target_id,
                action_dispatched=chosen_action,
                initial_pose=initial_pose,
                final_pose=final_pose,
                base_displacement_m=base_disp,
                re_observed=False,
                final_look_at_success=False,
                message=f"Post-locomotion re-observation failed: Object '{target_id}' lost from MNSE world context.",
            )

        identity_preserved = (re_obj.object_id == target_id)
        log.info(f"✓ [STATE MACHINE] Re-observation success: {re_obj.object_id} (identity preserved={identity_preserved}) at ({re_obj.world_x:.2f}, {re_obj.world_y:.2f}, {re_obj.world_z:.2f})")

        # 7. LOOKING: Execute final LookAt with updated authoritative coordinates
        self.current_state = NavigationState.LOOKING
        log.info(f"[STATE MACHINE] State: LOOKING -> LookAt({re_obj.world_x:.2f}, {re_obj.world_y:.2f}, {re_obj.world_z:.2f})")
        look_result = self.look_at(re_obj.world_x, re_obj.world_y, re_obj.world_z)

        # 8. VERIFYING & COMPLETE
        self.current_state = NavigationState.VERIFYING
        success = look_result.success and identity_preserved
        self.current_state = NavigationState.COMPLETE if success else NavigationState.FAILED

        return StateMachineExecutionResult(
            success=success,
            state=self.current_state,
            target_object_id=target_id,
            action_dispatched=chosen_action,
            initial_pose=initial_pose,
            final_pose=final_pose,
            base_displacement_m=round(base_disp, 4),
            re_observed=True,
            final_look_at_success=look_result.success,
            message=f"Navigation-grounded interaction complete: Repositioned base (disp={base_disp:.2f}m), re-observed {re_obj.object_id}, and executed final LookAt gaze.",
            metadata={
                "action": action_name,
                "identity_preserved": identity_preserved,
                "re_observed_position": (re_obj.world_x, re_obj.world_y, re_obj.world_z),
            },
        )
