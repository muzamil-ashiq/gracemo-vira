"""
GRaCEmo ViRa — MCU Bridge ROS 2 Node
=====================================
Bridges the MCU transport layer to standard ROS 2 topics.

In SIMULATION mode (--ros-args -p hardware_mode:=sim):
  - Does NOT instantiate the MCU transport
  - Publishes OFFLINE fault on /hardware/mcu_state
  - Does NOT publish cmd_vel or consume /odom

In HARDWARE mode (--ros-args -p hardware_mode:=hardware):
  - Instantiates MCU transport (mock or serial, selected by transport_type param)
  - Subscribes to /cmd_vel and forwards to MCU
  - Receives MCU telemetry and publishes /odom (nav_msgs/Odometry)
  - Publishes /hardware/mcu_state (std_msgs/String JSON)
  - Publishes /hardware/fault (std_msgs/String JSON) on hardware faults
  - Watchdog: publishes zero velocity if /cmd_vel goes stale

IMPORTANT: A missing or disconnected MCU in hardware mode publishes a visible fault
and does NOT simulate motion. Command velocity is blocked until MCU is connected.
"""

import json
import math
import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import String
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
try:
    import tf2_ros
    HAS_TF2 = True
except ImportError:
    HAS_TF2 = False

from .mcu_transport import (
    BaseMCUTransport,
    MCUCommand,
    MCUFault,
    MCUTelemetry,
    MCUConnectionState,
    create_mcu_transport,
    HW_MAX_LINEAR_VEL_MPS,
    HW_MAX_ANGULAR_VEL_RPS,
)


class MCUBridgeNode(Node):
    """
    Hardware Abstraction Layer — MCU Bridge Node.
    Separates hardware communication from navigation and interaction.
    """

    def __init__(self):
        super().__init__("gracemo_mcu_bridge")

        # ── Parameters ──────────────────────────────────────────────────────
        self.declare_parameter("hardware_mode", "sim")
        # transport_type: "mock" (test) or "serial" (real hardware)
        self.declare_parameter("transport_type", "mock")
        self.declare_parameter("mcu_port", "/dev/ttyUSB0")       # [PENDING: confirm on Jetson]
        self.declare_parameter("mcu_baud_rate", 115200)           # [PENDING: confirm with firmware]
        self.declare_parameter("wheel_separation_m", 0.34)
        self.declare_parameter("wheel_radius_m", 0.065)
        self.declare_parameter("cmd_vel_watchdog_sec", 0.5)
        self.declare_parameter("publish_odom_tf", True)
        self.declare_parameter("odom_frame_id", "odom")
        self.declare_parameter("base_frame_id", "base_footprint")

        self._hw_mode = self.get_parameter("hardware_mode").value.lower()
        self._transport_type = self.get_parameter("transport_type").value
        self._mcu_port = self.get_parameter("mcu_port").value
        self._mcu_baud = self.get_parameter("mcu_baud_rate").value
        self._wheel_sep = self.get_parameter("wheel_separation_m").value
        self._wheel_rad = self.get_parameter("wheel_radius_m").value
        self._watchdog_sec = self.get_parameter("cmd_vel_watchdog_sec").value
        self._publish_odom_tf = self.get_parameter("publish_odom_tf").value
        self._odom_frame = self.get_parameter("odom_frame_id").value
        self._base_frame = self.get_parameter("base_frame_id").value

        self._transport: BaseMCUTransport = None
        self._last_cmd_vel_time = time.time()
        self._last_telemetry_time: float = 0.0
        self._lock = threading.Lock()
        self._odom_x = 0.0
        self._odom_y = 0.0
        self._odom_yaw = 0.0

        # ── QoS ─────────────────────────────────────────────────────────────
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10,
        )

        # ── Publishers ───────────────────────────────────────────────────────
        self._odom_pub = self.create_publisher(Odometry, "/odom", 50)
        self._mcu_state_pub = self.create_publisher(String, "/hardware/mcu_state", reliable_qos)
        self._fault_pub = self.create_publisher(String, "/hardware/fault", reliable_qos)

        if HAS_TF2 and self._publish_odom_tf:
            self._tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # ── Validate hardware mode ──────────────────────────────────────────
        if self._hw_mode not in ("sim", "hardware"):
            err_msg = f"Invalid hardware_mode '{self._hw_mode}'. Supported modes are 'sim' or 'hardware'."
            self.get_logger().error(f"🚨 {err_msg}")
            self._publish_mcu_state("INVALID_MODE", err_msg, is_mock=False)
            self._on_mcu_fault(MCUFault(
                source="config",
                code=0xEE,
                description=err_msg,
                is_critical=True,
            ))
            return

        # ── In simulation mode, advertise offline state and return ───────────
        if self._hw_mode == "sim":
            self._publish_mcu_state("SIMULATION_MODE", "MCU bridge not active in simulation mode.", is_mock=False)
            self.get_logger().info(
                "MCU Bridge: SIMULATION mode — MCU transport inactive. "
                "Use hardware_mode:=hardware to activate."
            )
            # Periodically remind that hardware is not active
            self.create_timer(10.0, self._sim_heartbeat)
            return

        # ── Hardware mode ────────────────────────────────────────────────────
        self.get_logger().info(
            f"MCU Bridge: HARDWARE mode — transport={self._transport_type}, "
            f"port={self._mcu_port}, baud={self._mcu_baud}"
        )

        # Subscribe to cmd_vel
        self._cmd_sub = self.create_subscription(
            Twist, "/cmd_vel", self._on_cmd_vel, 10
        )

        # Connect MCU transport
        try:
            self._transport = create_mcu_transport(
                transport_type=self._transport_type,
                port=self._mcu_port,
                baud_rate=self._mcu_baud,
                wheel_separation_m=self._wheel_sep,
                wheel_radius_m=self._wheel_rad,
            )
            self._transport.on_fault(self._on_mcu_fault)
            self._transport.on_telemetry(self._on_mcu_telemetry)

            if self._transport.connect():
                if self._transport.is_mock:
                    self._publish_mcu_state(
                        "CONNECTED_MOCK",
                        "MOCK transport connected. Simulating kinematics only. Physical motors are NOT connected.",
                        is_mock=True,
                    )
                    self.get_logger().warn(
                        "⚠️ MCU Bridge: CONNECTED IN MOCK MODE. Real motors are NOT connected."
                    )
                else:
                    self._publish_mcu_state("CONNECTED", "Physical MCU serial transport connected.", is_mock=False)
                    self.get_logger().info("✅ Physical MCU transport connected.")
            else:
                self._on_mcu_fault(MCUFault(
                    source="connect",
                    description="MCU transport connect() returned False",
                    is_critical=True,
                ))
        except Exception as e:
            self._on_mcu_fault(MCUFault(
                source="init",
                description=f"MCU transport initialization error: {e}",
                is_critical=True,
            ))

        # Command watchdog timer (20 Hz)
        self.create_timer(0.05, self._watchdog_tick)

    # ── Simulation heartbeat ─────────────────────────────────────────────────

    def _sim_heartbeat(self):
        self._publish_mcu_state("SIMULATION_MODE", "MCU bridge not active in simulation mode.")

    # ── cmd_vel handler ──────────────────────────────────────────────────────

    def _on_cmd_vel(self, msg: Twist):
        if self._transport is None or not self._transport.is_connected:
            self.get_logger().warn_once(
                "MCU Bridge: Received cmd_vel but MCU is not connected. "
                "Command discarded. Check /hardware/fault for details."
            )
            return

        # Clamp velocities to hardware limits
        lin = max(-HW_MAX_LINEAR_VEL_MPS, min(HW_MAX_LINEAR_VEL_MPS, msg.linear.x))
        ang = max(-HW_MAX_ANGULAR_VEL_RPS, min(HW_MAX_ANGULAR_VEL_RPS, msg.angular.z))

        cmd = MCUCommand(linear_vel_mps=lin, angular_vel_rps=ang)
        success = self._transport.send_command(cmd)

        if not success:
            self.get_logger().warn("MCU Bridge: send_command() failed.")

        with self._lock:
            self._last_cmd_vel_time = time.time()

    # ── Command watchdog ─────────────────────────────────────────────────────

    def _watchdog_tick(self):
        if self._transport is None or not self._transport.is_connected:
            return
        now = time.time()
        with self._lock:
            cmd_age = now - self._last_cmd_vel_time
            telem_age = now - self._last_telemetry_time if self._last_telemetry_time > 0 else 0.0

        # Check telemetry staleness: if connected and telemetry previously received, detect freeze
        if self._last_telemetry_time > 0 and telem_age > 1.5:
            self.get_logger().warn(
                f"MCU Bridge: Stale telemetry detected ({telem_age:.2f}s > 1.5s). Zeroing velocity."
            )
            self._transport.send_command(MCUCommand())
            self._on_mcu_fault(MCUFault(
                source="telemetry_watchdog",
                code=0x02,
                description=f"MCU telemetry stale ({telem_age:.2f}s without update)",
                is_critical=True,
            ))

        if cmd_age > self._watchdog_sec:
            # Zero velocity — no command freshness
            self._transport.send_command(MCUCommand())

    # ── MCU telemetry → ROS 2 /odom ─────────────────────────────────────────

    def _on_mcu_telemetry(self, telem: MCUTelemetry):
        now_time = time.time()
        with self._lock:
            self._last_telemetry_time = now_time

        now = self.get_clock().now().to_msg()

        odom_msg = Odometry()
        odom_msg.header.stamp = now
        odom_msg.header.frame_id = self._odom_frame
        odom_msg.child_frame_id = self._base_frame
        odom_msg.pose.pose.position.x = telem.odom_x
        odom_msg.pose.pose.position.y = telem.odom_y
        odom_msg.pose.pose.position.z = 0.0

        # Yaw → quaternion
        odom_msg.pose.pose.orientation.z = math.sin(telem.odom_yaw / 2.0)
        odom_msg.pose.pose.orientation.w = math.cos(telem.odom_yaw / 2.0)

        # Velocities
        v = (telem.left_wheel_vel_mps + telem.right_wheel_vel_mps) / 2.0
        omega = (telem.right_wheel_vel_mps - telem.left_wheel_vel_mps) / self._wheel_sep
        odom_msg.twist.twist.linear.x = v
        odom_msg.twist.twist.angular.z = omega

        self._odom_pub.publish(odom_msg)

        # Publish TF odom → base_footprint (only publisher of this transform in hardware mode)
        if HAS_TF2 and self._publish_odom_tf:
            tf_msg = TransformStamped()
            tf_msg.header.stamp = now
            tf_msg.header.frame_id = self._odom_frame
            tf_msg.child_frame_id = self._base_frame
            tf_msg.transform.translation.x = telem.odom_x
            tf_msg.transform.translation.y = telem.odom_y
            tf_msg.transform.translation.z = 0.0
            tf_msg.transform.rotation.z = math.sin(telem.odom_yaw / 2.0)
            tf_msg.transform.rotation.w = math.cos(telem.odom_yaw / 2.0)
            self._tf_broadcaster.sendTransform(tf_msg)

        # Check physical e-stop
        if telem.physical_estop_pressed:
            self._on_mcu_fault(MCUFault(
                source="physical_estop",
                code=0xFF,
                description="Physical e-stop button pressed",
                is_critical=True,
            ))

    # ── MCU fault handler ────────────────────────────────────────────────────

    def _on_mcu_fault(self, fault: MCUFault):
        fault_data = {
            "timestamp": fault.timestamp,
            "source": fault.source,
            "code": fault.code,
            "description": fault.description,
            "is_critical": fault.is_critical,
        }
        msg = String()
        msg.data = json.dumps(fault_data)
        self._fault_pub.publish(msg)
        self._publish_mcu_state("FAULT", fault.description)

        if fault.is_critical:
            self.get_logger().error(
                f"🚨 HARDWARE FAULT [{fault.source}] code={fault.code}: {fault.description}"
            )
            # Attempt emergency stop
            if self._transport:
                try:
                    self._transport.send_estop()
                except Exception:
                    pass

    def _publish_mcu_state(self, state: str, detail: str = "", is_mock: Optional[bool] = None):
        if is_mock is None:
            is_mock = self._transport.is_mock if self._transport else False
        msg = String()
        msg.data = json.dumps({
            "state": state,
            "detail": detail,
            "is_mock": is_mock,
            "transport_type": self._transport_type,
            "timestamp": time.time(),
        })
        self._mcu_state_pub.publish(msg)

    def destroy_node(self):
        if self._transport and self._transport.is_connected:
            try:
                self._transport.send_estop()
            except Exception:
                pass
            self._transport.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MCUBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
