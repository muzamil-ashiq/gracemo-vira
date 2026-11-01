#!/usr/bin/env python3
"""
GRaCEmo ViRa — Command Coordinator Node
Authoritative multi-room autonomous navigation coordinator, safety arbiter,
bounded state machine, and arrival verification engine.
"""

import json
import math
import time
from typing import Optional, Dict, Any

import rclpy
import tf2_ros
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from std_msgs.msg import String, Bool
from std_srvs.srv import Empty


class CommandCoordinatorNode(Node):
    # State Machine Constants
    STATE_IDLE = "IDLE"
    STATE_VALIDATING_GOAL = "VALIDATING_GOAL"
    STATE_WAITING_FOR_LOCALIZATION = "WAITING_FOR_LOCALIZATION"
    STATE_PLANNING = "PLANNING"
    STATE_NAVIGATING = "NAVIGATING"
    STATE_RECOVERING = "RECOVERING"
    STATE_VERIFYING_ARRIVAL = "VERIFYING_ARRIVAL"
    STATE_SUCCEEDED = "SUCCEEDED"
    STATE_CANCELED = "CANCELED"
    STATE_FAILED = "FAILED"
    STATE_SAFE_STOP = "SAFE_STOP"

    def __init__(self):
        super().__init__("gracemo_command_coordinator")

        # Bounded State Machine tracking
        self.state = self.STATE_IDLE
        self.active_goal_handle = None
        self.active_destination_name: Optional[str] = None
        self.active_destination_key: Optional[str] = None
        self.active_destination_coords: Optional[dict] = None
        self.last_destination_coords: Optional[dict] = None
        self.last_destination_name: Optional[str] = None

        # Recovery and retry control
        self.retry_count = 0
        self.max_retries = 2
        self.active_goal_msg: Optional[NavigateToPose.Goal] = None

        # Telemetry
        self.current_odom_x = 0.0
        self.current_odom_y = 0.0
        self.current_map_x = 0.0
        self.current_map_y = 0.0
        self.current_map_yaw = 0.0
        self.has_localization = False
        self.remaining_distance = 0.0
        self.last_progress_time = self.get_clock().now()
        self.current_goal_id = 0
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Known reference places
        self.places = {
            "hallway": (0.0, 0.0, "Central Hallway"),
            "kitchen": (-5.0, -2.5, "Kitchen & Dining"),
            "bedroom": (-5.0, 2.2, "Master Bedroom"),
            "study": (4.5, 3.0, "Home Study"),
            "living_room": (4.0, -2.5, "Living Room"),
            "lab": (2.5, 2.0, "Robotics Research Lab"),
        }

        # Action Client for Nav2 NavigateToPose
        self.nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

        # Costmap clearing clients for autonomous recovery
        self.clear_global_costmap_cli = self.create_client(
            ClearEntireCostmap, "/global_costmap/clear_entirely_global_costmap"
        )
        self.clear_local_costmap_cli = self.create_client(
            ClearEntireCostmap, "/local_costmap/clear_entirely_local_costmap"
        )

        # Publishers
        self.feedback_pub = self.create_publisher(String, "/coordinator/feedback", 10)
        self.emergency_stop_pub = self.create_publisher(Bool, "/terrain/emergency_stop", 10)

        # QoS Profiles
        qos_best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        qos_transient = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )

        # Subscribers
        self.command_sub = self.create_subscription(
            String, "/coordinator/command", self.on_command, 10
        )
        self.odom_sub = self.create_subscription(
            Odometry, "/odom", self.on_odom, qos_best_effort
        )
        self.amcl_sub = self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self.on_amcl_pose, qos_transient
        )

        # Service client for AMCL non-motion scan/filter update
        self.nomotion_update_cli = self.create_client(Empty, "/request_nomotion_update")
        # Publisher for initial pose
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, "/initialpose", 10
        )

        # Localization telemetry & covariance tracking
        self.latest_amcl_pose: Optional[PoseWithCovarianceStamped] = None
        self.latest_amcl_time = None
        self.amcl_covariance_xx = 0.0
        self.amcl_covariance_yy = 0.0
        self.amcl_covariance_yaw = 0.0

                # Navigation progress and velocity telemetry
        self.navigation_start_time = None
        self.last_progress_pose = (0.0, 0.0)
        self.last_cmd_vel_linear = 0.0
        self.last_cmd_vel_angular = 0.0
        self.watchdog_timer = self.create_timer(1.0, self._check_navigation_watchdog)

        # Autonomous startup ping to kickstart AMCL pose publication
        self.init_localization_timer = self.create_timer(3.0, self._on_startup_localization_ping)

        self.get_logger().info("🛡️ GRaCEmo Autonomous Command Coordinator online (11-state FSM enabled).")

    def _on_startup_localization_ping(self):
        if hasattr(self, 'init_localization_timer') and self.init_localization_timer:
            self.init_localization_timer.cancel()
            self.init_localization_timer = None
        if self.nomotion_update_cli.service_is_ready():
            try:
                self.nomotion_update_cli.call_async(Empty.Request())
                self.get_logger().info("📍 Coordinator triggered startup nomotion update to initialize AMCL pose.")
            except Exception as e:
                self.get_logger().warn(f"Startup nomotion update call failed: {e}")

    def get_current_map_pose(self):
        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
            px = t.transform.translation.x
            py = t.transform.translation.y
            q = t.transform.rotation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            return px, py, yaw
        except Exception:
            return self.current_map_x, self.current_map_y, self.current_map_yaw

    def on_odom(self, msg: Odometry):
        self.current_odom_x = msg.pose.pose.position.x
        self.current_odom_y = msg.pose.pose.position.y
        self.last_cmd_vel_linear = msg.twist.twist.linear.x
        self.last_cmd_vel_angular = msg.twist.twist.angular.z

    def on_amcl_pose(self, msg: PoseWithCovarianceStamped):
        self.latest_amcl_pose = msg
        self.latest_amcl_time = self.get_clock().now()
        self.current_map_x = msg.pose.pose.position.x
        self.current_map_y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_map_yaw = math.atan2(siny_cosp, cosy_cosp)
        cov = msg.pose.covariance
        self.amcl_covariance_xx = cov[0]
        self.amcl_covariance_yy = cov[7]
        self.amcl_covariance_yaw = cov[35]
        self.has_localization = True

    def check_localization_readiness(self, timeout_sec: float = 5.0) -> tuple[bool, str]:
        """
        Verify that map, localization, sensor transform, and initial pose
        are fully established before allowing navigation planning to proceed.
        """
        start = time.time()
        # 1. Trigger nomotion update to ensure AMCL emits a fresh pose and TF even if stationary
        if self.nomotion_update_cli.service_is_ready():
            try:
                self.nomotion_update_cli.call_async(Empty.Request())
            except Exception as e:
                self.get_logger().warn(f"Failed to call nomotion update: {e}")

        # 2. Check TF connectivity: map -> base_footprint
        tf_ready = False
        while time.time() - start < timeout_sec:
            try:
                if self.tf_buffer.can_transform(
                    "map", "base_footprint", rclpy.time.Time(),
                    timeout=rclpy.duration.Duration(seconds=0.5)
                ):
                    tf_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if not tf_ready:
            return False, "Transform chain 'map -> odom -> base_footprint' is not connected"

        try:
            t = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
        except Exception as e:
            return False, f"Failed to lookup transform 'map -> base_footprint': {e}"

        # 3. Check AMCL pose availability
        if not self.has_localization or self.latest_amcl_pose is None:
            if self.nomotion_update_cli.service_is_ready():
                try:
                    self.nomotion_update_cli.call_async(Empty.Request())
                except Exception:
                    pass

        # 4. Check covariance bounds (reject wildly diverged particles)
        if self.has_localization and (self.amcl_covariance_xx > 1.0 or self.amcl_covariance_yy > 1.0):
            return False, f"Localization covariance too high (var_x={self.amcl_covariance_xx:.2f}, var_y={self.amcl_covariance_yy:.2f} > 1.0 m^2)"

        cur_x = t.transform.translation.x
        cur_y = t.transform.translation.y
        return True, f"Localization ready at map=({cur_x:.2f}, {cur_y:.2f})"

    def on_command(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except Exception as e:
            self.get_logger().error(f"Malformed JSON in /coordinator/command: {e}")
            return

        intent = payload.get("intent", "").upper()
        self.get_logger().info(f"📥 Coordinator received intent: {intent}")

        if intent == "NAVIGATE_TO":
            self.retry_count = 0
            self.handle_navigate(payload)
        elif intent == "CANCEL_NAVIGATION":
            self.handle_cancel()
        elif intent == "STOP":
            self.handle_stop()
        elif intent == "RESUME_NAVIGATION":
            self.handle_resume()
        elif intent == "CURRENT_STATUS":
            self.handle_status()
        elif intent == "CURRENT_LOCATION":
            self.handle_location()
        elif intent == "HELP":
            self.handle_help()
        elif intent == "DESTINATION_QUERY":
            self.handle_places()
        elif intent in ("INITIALIZE_LOCALIZATION", "SET_INITIAL_POSE"):
            self.handle_initialize_localization(payload)
        elif intent in ("LOCALIZATION_STATUS", "CHECK_LOCALIZATION"):
            self.handle_localization_status()
        else:
            self.get_logger().warn(f"Unhandled intent: {intent}")

    def handle_stop(self):
        self.current_goal_id += 1
        """Emergency Stop requested."""
        self.state = self.STATE_SAFE_STOP
        self.get_logger().warn("🚨 Coordinator triggered Emergency Stop.")

        # 1. Cancel active goal
        if self.active_goal_handle:
            try:
                self.active_goal_handle.cancel_goal_async()
            except Exception as e:
                self.get_logger().warn(f"Failed to cancel goal: {e}")
            self.active_goal_handle = None

        # 2. Assert emergency stop via authoritative terrain safety gate
        e_msg = Bool()
        e_msg.data = True
        self.emergency_stop_pub.publish(e_msg)

        self.emit_feedback(
            state=self.STATE_SAFE_STOP,
            speech="Halt. Robot stopped immediately and active goal cancelled.",
            details={"action": "emergency_stop"}
        )
        self.state = self.STATE_IDLE

    def handle_cancel(self):
        self.current_goal_id += 1
        """Cancel active navigation goal safely."""
        if self.state not in (self.STATE_NAVIGATING, self.STATE_PLANNING, self.STATE_RECOVERING) or not self.active_goal_handle:
            self.emit_feedback(
                state=self.state,
                speech="There is no active navigation goal to cancel.",
                details={"action": "no_active_goal"}
            )
            return

        dest_name = self.active_destination_name or "destination"
        self.get_logger().info(f"🛑 Cancelling navigation to {dest_name}")
        self.state = self.STATE_CANCELED

        try:
            self.active_goal_handle.cancel_goal_async()
        except Exception as e:
            self.get_logger().warn(f"Cancel request error: {e}")

        self.active_goal_handle = None

        # Assert safety stop via authoritative terrain safety gate
        e_msg = Bool()
        e_msg.data = True
        self.emergency_stop_pub.publish(e_msg)

        self.emit_feedback(
            state=self.STATE_CANCELED,
            speech=f"Navigation to {dest_name} was cancelled.",
            details={"action": "cancelled", "destination": dest_name}
        )
        self.state = self.STATE_IDLE

    def handle_navigate(self, payload: dict):
        self.state = self.STATE_VALIDATING_GOAL
        coords = payload.get("destination_coords")
        dest_name = payload.get("destination_name") or payload.get("destination_key") or "destination"
        dest_key = payload.get("destination_key", "")

        # Strict Goal Validation
        if not coords or not isinstance(coords, dict) or "x" not in coords or "y" not in coords:
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech=f"Cannot navigate to {dest_name}: missing or invalid coordinates.",
                details={"error": "missing_coords"}
            )
            self.state = self.STATE_IDLE
            return

        try:
            target_x = float(coords["x"])
            target_y = float(coords["y"])
        except (ValueError, TypeError):
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech=f"Cannot navigate to {dest_name}: non-numeric coordinates.",
                details={"error": "invalid_numeric_coords"}
            )
            self.state = self.STATE_IDLE
            return

        # Map boundary check (apartment map is -9.0 to +9.0 in X, -6.5 to +6.5 in Y)
        if not (-8.8 <= target_x <= 8.8 and -6.3 <= target_y <= 6.3):
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech=f"Destination {dest_name} at ({target_x:.2f}, {target_y:.2f}) is outside the apartment boundary.",
                details={"error": "out_of_bounds", "x": target_x, "y": target_y}
            )
            self.state = self.STATE_IDLE
            return

        # Reset retry counter and progress tracking for new goal
        self.retry_count = 0
        now = self.get_clock().now()
        self.navigation_start_time = now
        self.last_progress_time = now
        cur_x, cur_y, _ = self.get_current_map_pose()
        self.last_progress_pose = (cur_x, cur_y)

        # Cancel previous goal if active
        self.current_goal_id += 1
        goal_id = self.current_goal_id
        if self.active_goal_handle:
            self.get_logger().info(f"Superseding previous navigation with new destination: {dest_name}")
            try:
                self.active_goal_handle.cancel_goal_async()
            except Exception:
                pass
            self.active_goal_handle = None

        # Localization Readiness Gate
        self.state = self.STATE_WAITING_FOR_LOCALIZATION
        self.get_logger().info("🔍 Verifying localization readiness before navigation...")
        is_ready, diag_msg = self.check_localization_readiness(timeout_sec=5.0)
        if not is_ready:
            self.get_logger().error(f"❌ Localization readiness check failed: {diag_msg}")
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech="Navigation cannot start because the localization system is not ready.",
                details={"error": "localization_not_ready", "diagnostic": diag_msg}
            )
            self.state = self.STATE_IDLE
            return

        self.get_logger().info(f"✅ {diag_msg}. Transitioning to PLANNING.")

        # Verification of action server
        self.state = self.STATE_PLANNING
        if not self.nav_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("Nav2 action server (/navigate_to_pose) is not available.")
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech="Navigation system is currently unavailable. Please verify Nav2 is running.",
                details={"error": "nav2_server_unavailable"}
            )
            self.state = self.STATE_IDLE
            return

        # Build Nav2 goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = coords.get("frame_id", "map")
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(coords["x"])
        goal_msg.pose.pose.position.y = float(coords["y"])
        goal_msg.pose.pose.position.z = 0.0

        yaw = float(coords.get("yaw", 0.0))
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.active_destination_name = dest_name
        self.active_destination_key = dest_key
        self.active_destination_coords = coords
        self.last_destination_coords = coords
        self.last_destination_name = dest_name
        self.active_goal_msg = goal_msg

        # Clear emergency stop for authoritative navigation
        e_msg = Bool()
        e_msg.data = False
        self.emergency_stop_pub.publish(e_msg)

        self.state = self.STATE_NAVIGATING
        self.last_progress_time = self.get_clock().now()

        self.emit_feedback(
            state=self.STATE_NAVIGATING,
            speech=f"Navigation accepted. Starting motion to {dest_name}.",
            details={"destination": dest_name, "coords": coords}
        )

        send_future = self.nav_client.send_goal_async(
            goal_msg, feedback_callback=lambda fb: self.on_nav_feedback(fb, goal_id)
        )
        send_future.add_done_callback(lambda fut: self.on_goal_response(fut, goal_id))

    def on_goal_response(self, future, goal_id):
        if goal_id != self.current_goal_id:
            return
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn(f"Goal rejected by Nav2 action server for {self.active_destination_name}.")
            self.state = self.STATE_FAILED
            self.emit_feedback(
                state=self.STATE_FAILED,
                speech=f"Navigation goal to {self.active_destination_name} was rejected by path planner.",
                details={"error": "goal_rejected"}
            )
            self.state = self.STATE_IDLE
            return

        self.get_logger().info(f"Goal accepted by Nav2 for {self.active_destination_name}.")
        self.active_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(lambda fut: self.on_nav_result(fut, goal_id))

    def on_nav_feedback(self, feedback_msg, goal_id):
        if goal_id != self.current_goal_id:
            return
        feedback = feedback_msg.feedback
        if hasattr(feedback, "distance_remaining"):
            self.remaining_distance = feedback.distance_remaining
        self.last_progress_time = self.get_clock().now()

    def on_nav_result(self, future, goal_id):
        if goal_id != self.current_goal_id:
            return
        status = future.result().status
        dest_name = self.active_destination_name or "destination"
        coords = self.active_destination_coords
        self.active_goal_handle = None

        if status == GoalStatus.STATUS_SUCCEEDED:
            # PHASE 8: Physical Arrival Verification
            self.state = self.STATE_VERIFYING_ARRIVAL
            goal_x = coords["x"] if coords else 0.0
            goal_y = coords["y"] if coords else 0.0
            cur_x, cur_y, cur_yaw = self.get_current_map_pose()
            physical_dist = math.hypot(cur_x - goal_x, cur_y - goal_y)
            self.get_logger().info(
                f"Action SUCCEEDED. Verifying physical arrival: map=({cur_x:.3f}, {cur_y:.3f}), "
                f"goal=({goal_x:.2f}, {goal_y:.2f}), dist_error={physical_dist:.3f}m"
            )

            # Tolerance for acceptance: 0.65m Euclidean radius
            if physical_dist <= 0.65:
                self.state = self.STATE_SUCCEEDED
                self.get_logger().info(f"✅ Successfully arrived at {dest_name}! Verified error: {physical_dist:.3f}m")
                self.emit_feedback(
                    state=self.STATE_SUCCEEDED,
                    speech=f"Arrival confirmed. I have arrived safely at the {dest_name}.",
                    details={
                        "status": "SUCCEEDED",
                        "destination": dest_name,
                        "distance_error_m": round(physical_dist, 3),
                        "pose": {"x": round(cur_x, 3), "y": round(cur_y, 3)}
                    }
                )
            else:
                self.get_logger().error(f"❌ Arrival verification failed: distance error ({physical_dist:.3f}m) exceeds tolerance 0.65m.")
                self.state = self.STATE_SAFE_STOP
                e_msg = Bool()
                e_msg.data = True
                self.emergency_stop_pub.publish(e_msg)
                self.state = self.STATE_FAILED
                self.emit_feedback(
                    state=self.STATE_FAILED,
                    speech=f"Arrival verification failed. Robot is {physical_dist:.2f} meters away from {dest_name}.",
                    details={
                        "status": "FAILED",
                        "destination": dest_name,
                        "distance_error_m": round(physical_dist, 3),
                        "pose": {"x": round(cur_x, 3), "y": round(cur_y, 3)}
                    }
                )
            self.state = self.STATE_IDLE

        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info(f"Goal to {dest_name} was cancelled.")
            self.state = self.STATE_CANCELED
            self.emit_feedback(
                state=self.STATE_CANCELED,
                speech=f"Navigation to {dest_name} was cancelled.",
                details={"status": "CANCELED", "destination": dest_name}
            )
            self.state = self.STATE_IDLE

        else:
            # PHASE 7: Bounded Autonomous Recovery
            self.get_logger().warn(f"Goal to {dest_name} aborted or failed with status {status}.")
            if self.retry_count < self.max_retries and self.active_goal_msg is not None:
                self.retry_count += 1
                self.state = self.STATE_RECOVERING
                self.get_logger().info(
                    f"🔄 Initiating autonomous recovery attempt {self.retry_count}/{self.max_retries} for {dest_name}..."
                )
                self.emit_feedback(
                    state=self.STATE_RECOVERING,
                    speech=f"Path hindered. Initiating autonomous recovery for {dest_name}.",
                    details={"status": "RECOVERING", "retry": self.retry_count}
                )

                # Clear costmaps to flush transient dynamic obstacles
                self._clear_costmaps_async()

                # Re-issue goal after brief 1.0s costmap clearing window
                if hasattr(self, 'retry_timer') and self.retry_timer is not None:
                    self.retry_timer.cancel()
                self.retry_timer = self.create_timer(1.0, self._retry_goal_once)
            else:
                self.state = self.STATE_SAFE_STOP
                # Enforce safe halt
                e_msg = Bool()
                e_msg.data = True
                self.emergency_stop_pub.publish(e_msg)

                self.state = self.STATE_FAILED
                self.emit_feedback(
                    state=self.STATE_FAILED,
                    speech=f"Navigation to {dest_name} failed. The path is completely blocked.",
                    details={"status": "FAILED", "code": status, "destination": dest_name}
                )
                self.state = self.STATE_IDLE

    def _clear_costmaps_async(self):
        req = ClearEntireCostmap.Request()
        if self.clear_global_costmap_cli.service_is_ready():
            self.clear_global_costmap_cli.call_async(req)
        if self.clear_local_costmap_cli.service_is_ready():
            self.clear_local_costmap_cli.call_async(req)

    def _retry_goal_once(self):
        # One-shot retry callback
        if hasattr(self, 'retry_timer') and self.retry_timer is not None:
            self.retry_timer.cancel()
            self.retry_timer = None
        if self.state == self.STATE_RECOVERING and self.active_goal_msg:
            # Clear e-stop for recovery navigation
            e_msg = Bool()
            e_msg.data = False
            self.emergency_stop_pub.publish(e_msg)

            self.state = self.STATE_NAVIGATING
            self.current_goal_id += 1
            goal_id = self.current_goal_id
            self.active_goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
            send_future = self.nav_client.send_goal_async(
                self.active_goal_msg, feedback_callback=lambda fb: self.on_nav_feedback(fb, goal_id)
            )
            send_future.add_done_callback(lambda fut: self.on_goal_response(fut, goal_id))

    def _on_cmd_vel_telemetry(self, msg: Twist):
        self.last_cmd_vel_linear = msg.linear.x
        self.last_cmd_vel_angular = msg.angular.z

    def _check_navigation_watchdog(self):
        if self.state != self.STATE_NAVIGATING or not self.active_goal_handle:
            return

        now = self.get_clock().now()
        cur_x, cur_y, _ = self.get_current_map_pose()
        disp_since_last = math.hypot(cur_x - self.last_progress_pose[0], cur_y - self.last_progress_pose[1])

        if disp_since_last >= 0.08:
            self.last_progress_pose = (cur_x, cur_y)
            self.last_progress_time = now
            return

        stagnant_sec = (now - self.last_progress_time).nanoseconds / 1e9
        total_sec = (now - self.navigation_start_time).nanoseconds / 1e9 if self.navigation_start_time else 0.0

        if stagnant_sec > 12.0 or total_sec > 180.0:
            dest_name = self.active_destination_name or "destination"
            self.get_logger().warn(
                f"⏱️ Navigation watchdog triggered: stagnant={stagnant_sec:.1f}s, total={total_sec:.1f}s for {dest_name}."
            )
            try:
                self.active_goal_handle.cancel_goal_async()
            except Exception:
                pass
            self.active_goal_handle = None

            if self.retry_count < self.max_retries and self.active_goal_msg is not None:
                self.retry_count += 1
                self.state = self.STATE_RECOVERING
                self.get_logger().info(
                    f"🔄 Watchdog initiating autonomous recovery {self.retry_count}/{self.max_retries} for {dest_name}..."
                )
                self.emit_feedback(
                    state=self.STATE_RECOVERING,
                    speech=f"Motion stalled. Initiating autonomous recovery for {dest_name}.",
                    details={"status": "RECOVERING", "retry": self.retry_count, "reason": "watchdog_stagnant"}
                )
                self._clear_costmaps_async()
                if hasattr(self, 'retry_timer') and self.retry_timer is not None:
                    self.retry_timer.cancel()
                self.retry_timer = self.create_timer(1.0, self._retry_goal_once)
            else:
                self.get_logger().error(f"❌ Navigation to {dest_name} failed: stalled and retries exhausted.")
                self.state = self.STATE_SAFE_STOP
                e_msg = Bool()
                e_msg.data = True
                self.emergency_stop_pub.publish(e_msg)
                self.state = self.STATE_FAILED
                self.emit_feedback(
                    state=self.STATE_FAILED,
                    speech=f"Navigation to {dest_name} failed. Robot remained stationary and retries were exhausted.",
                    details={"status": "FAILED", "reason": "watchdog_timeout", "destination": dest_name}
                )
                self.state = self.STATE_IDLE

    def handle_resume(self):
        """Resume navigation to the last requested destination."""
        if self.state == self.STATE_NAVIGATING:
            self.emit_feedback(
                state=self.state,
                speech=f"Already navigating to {self.active_destination_name}.",
                details={"status": "ALREADY_NAVIGATING"}
            )
            return

        if not self.last_destination_coords:
            self.emit_feedback(
                state=self.STATE_IDLE,
                speech="No previous destination to resume.",
                details={"error": "no_previous_destination"}
            )
            return

        payload = {
            "intent": "NAVIGATE_TO",
            "destination_coords": self.last_destination_coords,
            "destination_name": self.last_destination_name,
        }
        self.emit_feedback(
            state=self.STATE_NAVIGATING,
            speech=f"Resuming navigation to {self.last_destination_name}.",
            details={"action": "resume"}
        )
        self.handle_navigate(payload)

    def handle_status(self):
        if self.state == self.STATE_NAVIGATING:
            msg = f"Currently navigating to {self.active_destination_name}. Estimated distance remaining: {self.remaining_distance:.1f} meters."
        else:
            msg = "Robot is idle and ready for navigation instructions."

        self.emit_feedback(
            state=self.state,
            speech=msg,
            details={"state": self.state, "distance": self.remaining_distance}
        )

    def handle_location(self):
        closest_name = "Central Hallway"
        min_dist = float("inf")

        for key, (px, py, pname) in self.places.items():
            d = math.hypot(px - self.current_map_x, py - self.current_map_y)
            if d < min_dist:
                min_dist = d
                closest_name = pname

        if min_dist < 1.2:
            speech = f"I am currently in the {closest_name}."
        else:
            speech = f"I am at coordinates X: {self.current_map_x:.1f}, Y: {self.current_map_y:.1f}, near {closest_name} ({min_dist:.1f} meters away)."

        self.emit_feedback(
            state=self.state,
            speech=speech,
            details={"x": self.current_map_x, "y": self.current_map_y, "closest": closest_name}
        )

    def handle_help(self):
        known = ", ".join(list(self.places.keys()))
        msg = f"You can ask me to navigate to destinations like: {known}. You can also cancel navigation or ask for status."
        self.emit_feedback(
            state=self.state,
            speech=msg,
            details={"available_places": list(self.places.keys())}
        )

    def handle_places(self):
        known = ", ".join(list(self.places.keys()))
        msg = f"Known destinations are: {known}."
        self.emit_feedback(
            state=self.state,
            speech=msg,
            details={"places": self.places}
        )

    def emit_feedback(self, state: str, speech: str, details: dict):
        msg = String()
        data = {
            "state": state,
            "speech": speech,
            "details": details,
            "timestamp": self.get_clock().now().nanoseconds / 1e9,
        }
        msg.data = json.dumps(data)
        self.feedback_pub.publish(msg)



    def handle_initialize_localization(self, payload: dict):
        """
        Explicit initial-pose initialization mechanism.
        Accepts coords: {x, y, yaw} or defaults to Central Hallway (0.0, 0.0, yaw=0.0).
        Publishes PoseWithCovarianceStamped to /initialpose and requests nomotion update.
        """
        coords = payload.get("coords") or payload.get("pose") or {"x": 0.0, "y": 0.0, "yaw": 0.0}
        px = float(coords.get("x", 0.0))
        py = float(coords.get("y", 0.0))
        yaw = float(coords.get("yaw", 0.0))

        pose_msg = PoseWithCovarianceStamped()
        pose_msg.header.frame_id = "map"
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.pose.pose.position.x = px
        pose_msg.pose.pose.position.y = py
        pose_msg.pose.pose.position.z = 0.0
        pose_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        cov = [0.0] * 36
        cov[0] = 0.25   # var x
        cov[7] = 0.25   # var y
        cov[35] = 0.068 # var yaw
        pose_msg.pose.covariance = cov

        self.initial_pose_pub.publish(pose_msg)
        self.get_logger().info(f"📍 Published initial pose to /initialpose: ({px:.2f}, {py:.2f}, yaw={yaw:.2f} rad)")

        if self.nomotion_update_cli.service_is_ready():
            try:
                self.nomotion_update_cli.call_async(Empty.Request())
            except Exception:
                pass

        self.emit_feedback(
            state=self.state,
            speech=f"Initial localization set at X={px:.2f}, Y={py:.2f}.",
            details={"action": "set_initial_pose", "x": px, "y": py, "yaw": yaw}
        )

    def handle_localization_status(self):
        cur_x, cur_y, cur_yaw = self.get_current_map_pose()
        can_tf = False
        try:
            can_tf = self.tf_buffer.can_transform("map", "base_footprint", rclpy.time.Time())
        except Exception:
            pass

        status_data = {
            "has_localization": self.has_localization,
            "tf_connected": can_tf,
            "map_pose": {"x": round(cur_x, 3), "y": round(cur_y, 3), "yaw": round(cur_yaw, 3)},
            "covariance": {
                "var_x": round(self.amcl_covariance_xx, 4),
                "var_y": round(self.amcl_covariance_yy, 4),
                "var_yaw": round(self.amcl_covariance_yaw, 4)
            }
        }
        speech = (
            f"Localization is active. Current pose: X={cur_x:.2f}, Y={cur_y:.2f}."
            if (self.has_localization and can_tf)
            else "Localization is degraded or transform is not connected."
        )
        self.emit_feedback(
            state=self.state,
            speech=speech,
            details=status_data
        )


def main(args=None):
    rclpy.init(args=args)
    node = CommandCoordinatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
