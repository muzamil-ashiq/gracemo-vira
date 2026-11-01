#!/usr/bin/env python3
"""
GRaCEmo ViRa Prototype — Terrain-Aware Navigation Monitor
Phase 8: Monitors base pitch and roll, enforces slope speed restrictions,
triggers safety stops when exceeding provisional limits, and computes
torso stabilization posture via the waist pitch joint.

NOTE: Standard 2D Nav2 occupancy grids and costmaps do not represent 3D terrain
or slope traversability. This node provides a dedicated attitude safety envelope.
"""

import math
import json
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu, JointState
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String, Float64


class TerrainMonitorNode(Node):
    def __init__(self):
        super().__init__("gracemo_terrain_monitor")

        # Configurable provisional thresholds (Phase 8)
        self.declare_parameter("pitch_warning_deg", 8.0)
        self.declare_parameter("pitch_limit_deg", 15.0)
        self.declare_parameter("roll_warning_deg", 7.0)
        self.declare_parameter("roll_limit_deg", 12.0)
        self.declare_parameter("slope_speed_reduction", 0.5)
        self.declare_parameter("enable_torso_stabilization", True)
        self.declare_parameter("waist_pitch_limit_deg", 30.0)

        self.pitch_warning = math.radians(self.get_parameter("pitch_warning_deg").value)
        self.pitch_limit = math.radians(self.get_parameter("pitch_limit_deg").value)
        self.roll_warning = math.radians(self.get_parameter("roll_warning_deg").value)
        self.roll_limit = math.radians(self.get_parameter("roll_limit_deg").value)
        self.speed_reduction = self.get_parameter("slope_speed_reduction").value
        self.enable_stabilization = self.get_parameter("enable_torso_stabilization").value
        self.waist_limit = math.radians(self.get_parameter("waist_pitch_limit_deg").value)

        # State tracking
        self.current_roll = 0.0
        self.current_pitch = 0.0
        self.current_yaw = 0.0
        self.slope_state = "NORMAL"  # NORMAL, MODERATE_SLOPE, LIMIT_EXCEEDED
        self.safety_envelope_breached = False
        self.emergency_stop_active = False
        self.speed_factor = 1.0
        self.stabilized_waist_target = 0.0
        self.last_cmd_vel_time = self.get_clock().now()
        self.last_cmd_nonzero = False

        # Subscriptions
        self.imu_sub = self.create_subscription(
            Imu, "/imu/data", self.on_imu, 10
        )
        self.cmd_vel_sub = self.create_subscription(
            Twist, "/cmd_vel_safe", self.on_cmd_vel_nav, 10
        )
        self.emergency_stop_sub = self.create_subscription(
            Bool, "/terrain/emergency_stop", self.on_emergency_stop, 10
        )
        self.watchdog_timer = self.create_timer(0.05, self.on_watchdog_check)

        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.safety_stop_pub = self.create_publisher(Bool, "/terrain/safety_stop", 10)
        self.status_pub = self.create_publisher(String, "/terrain/status", 10)
        self.waist_cmd_pub = self.create_publisher(Float64, "/waist_pitch_cmd", 10)

        # Periodic status publication (5 Hz)
        self.timer = self.create_timer(0.2, self.publish_status)

        self.get_logger().info(
            f"⛰️ GRaCEmo Terrain Monitor online. Limits: Pitch Warning={math.degrees(self.pitch_warning):.1f}°, "
            f"Limit={math.degrees(self.pitch_limit):.1f}° | Roll Warning={math.degrees(self.roll_warning):.1f}°, "
            f"Limit={math.degrees(self.roll_limit):.1f}°"
        )

    def on_imu(self, msg: Imu):
        q = msg.orientation
        # Compute roll, pitch, yaw from quaternion
        sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z)
        cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        self.current_roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        self.current_pitch = math.asin(max(-1.0, min(1.0, sinp)))

        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

        abs_pitch = abs(self.current_pitch)
        abs_roll = abs(self.current_roll)

        # Evaluate terrain safety envelope
        if abs_pitch >= self.pitch_limit or abs_roll >= self.roll_limit:
            if not self.safety_envelope_breached:
                self.get_logger().error(
                    f"🚨 TERRAIN SAFETY ENVELOPE BREACHED! Pitch={math.degrees(self.current_pitch):.1f}°, "
                    f"Roll={math.degrees(self.current_roll):.1f}°. Triggering immediate emergency stop!"
                )
            self.slope_state = "LIMIT_EXCEEDED"
            self.safety_envelope_breached = True
            self.speed_factor = 0.0
            self.emergency_stop()
        elif abs_pitch >= self.pitch_warning or abs_roll >= self.roll_warning:
            if self.slope_state != "MODERATE_SLOPE":
                self.get_logger().warn(
                    f"⚠️ Moderate slope detected: Pitch={math.degrees(self.current_pitch):.1f}°, "
                    f"Roll={math.degrees(self.current_roll):.1f}°. Restricting speed to {self.speed_reduction*100:.0f}%."
                )
            self.slope_state = "MODERATE_SLOPE"
            self.safety_envelope_breached = False
            self.speed_factor = self.speed_reduction
        else:
            self.slope_state = "NORMAL"
            self.safety_envelope_breached = False
            self.speed_factor = 1.0

        # Torso upright stabilization posture control
        if self.enable_stabilization:
            # Compensate base pitch by rotating waist in opposite direction
            target = -self.current_pitch
            self.stabilized_waist_target = max(-self.waist_limit, min(self.waist_limit, target))
            waist_msg = Float64()
            waist_msg.data = self.stabilized_waist_target
            self.waist_cmd_pub.publish(waist_msg)

    def on_emergency_stop(self, msg: Bool):
        self.emergency_stop_active = msg.data
        if self.emergency_stop_active:
            self.get_logger().info("🛑 Terrain Monitor received Emergency Stop request. Halting robot.")
            self.emergency_stop()
            self.last_cmd_nonzero = False

    def on_cmd_vel_nav(self, msg: Twist):
        self.last_cmd_vel_time = self.get_clock().now()

        # Apply terrain-aware speed restriction, safety stop, or emergency stop
        if self.safety_envelope_breached or self.emergency_stop_active:
            self.emergency_stop()
            self.last_cmd_nonzero = False
            return

        is_nonzero = (abs(msg.linear.x) > 0.001 or abs(msg.linear.y) > 0.001 or abs(msg.angular.z) > 0.001)
        self.last_cmd_nonzero = is_nonzero

        cmd = Twist()
        cmd.linear.x = msg.linear.x * self.speed_factor
        cmd.linear.y = msg.linear.y * self.speed_factor
        cmd.angular.z = msg.angular.z * (0.8 if self.speed_factor < 1.0 else 1.0)
        self.cmd_vel_pub.publish(cmd)

    def on_watchdog_check(self):
        # Enforce safe stop if commands time out (>0.5s) while robot was moving or during e-stop
        dt = (self.get_clock().now() - self.last_cmd_vel_time).nanoseconds / 1e9
        if dt > 0.5:
            if self.last_cmd_nonzero or self.emergency_stop_active:
                self.cmd_vel_pub.publish(Twist())
                self.last_cmd_nonzero = False

    def emergency_stop(self):
        stop_twist = Twist()
        self.cmd_vel_pub.publish(stop_twist)
        stop_msg = Bool()
        stop_msg.data = True
        self.safety_stop_pub.publish(stop_msg)

    def publish_status(self):
        payload = {
            "slope_state": self.slope_state,
            "safety_envelope_breached": self.safety_envelope_breached,
            "base_roll_deg": round(math.degrees(self.current_roll), 2),
            "base_pitch_deg": round(math.degrees(self.current_pitch), 2),
            "base_yaw_deg": round(math.degrees(self.current_yaw), 2),
            "speed_factor": self.speed_factor,
            "torso_stabilization_enabled": self.enable_stabilization,
            "waist_pitch_target_deg": round(math.degrees(self.stabilized_waist_target), 2),
            "simulation_mode": True,
            "note": "2D costmaps do not represent terrain grade; this layer provides active dynamic safety."
        }
        status_msg = String()
        status_msg.data = json.dumps(payload)
        self.status_pub.publish(status_msg)


def main(args=None):
    rclpy.init(args=args)
    node = TerrainMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
