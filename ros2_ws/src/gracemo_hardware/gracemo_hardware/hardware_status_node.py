"""
GRaCEmo ViRa — Hardware Status Monitor Node
============================================
Aggregates and publishes robot hardware health on /hardware/status.
Monitors MCU state, LiDAR scan freshness, IMU freshness, and e-stop state.
Publishes structured JSON on /hardware/status (std_msgs/String).
"""

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import String
from sensor_msgs.msg import LaserScan, Imu
from nav_msgs.msg import Odometry


class HardwareStatusNode(Node):
    def __init__(self):
        super().__init__("gracemo_hardware_status")

        self.declare_parameter("hardware_mode", "sim")
        self.declare_parameter("scan_timeout_sec", 2.0)
        self.declare_parameter("imu_timeout_sec", 2.0)
        self.declare_parameter("odom_timeout_sec", 1.0)
        self.declare_parameter("publish_rate_hz", 2.0)

        self._hw_mode = self.get_parameter("hardware_mode").value.lower()
        self._scan_timeout = self.get_parameter("scan_timeout_sec").value
        self._imu_timeout = self.get_parameter("imu_timeout_sec").value
        self._odom_timeout = self.get_parameter("odom_timeout_sec").value
        rate_hz = self.get_parameter("publish_rate_hz").value

        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=5,
        )

        # Sensor freshness tracking
        self._last_scan_time: float = 0.0
        self._last_imu_time: float = 0.0
        self._last_odom_time: float = 0.0
        self._mcu_state: str = "UNKNOWN"
        self._mcu_fault: str = ""
        self._is_mock: bool = False
        self._transport_type: str = "unknown"
        self._estop_active: bool = False

        # Publishers
        self._status_pub = self.create_publisher(String, "/hardware/status", reliable_qos)

        # Subscribers
        self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.create_subscription(Imu, "/imu/data", self._on_imu, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_subscription(String, "/hardware/mcu_state", self._on_mcu_state, reliable_qos)
        self.create_subscription(String, "/hardware/fault", self._on_fault, reliable_qos)

        # Status publish timer
        self.create_timer(1.0 / rate_hz, self._publish_status)

        self.get_logger().info(
            f"Hardware Status Node started in {self._hw_mode.upper()} mode."
        )

    def _on_scan(self, msg: LaserScan):
        self._last_scan_time = time.time()

    def _on_imu(self, msg: Imu):
        self._last_imu_time = time.time()

    def _on_odom(self, msg: Odometry):
        self._last_odom_time = time.time()

    def _on_mcu_state(self, msg: String):
        try:
            data = json.loads(msg.data)
            self._mcu_state = data.get("state", "UNKNOWN")
            self._is_mock = data.get("is_mock", False)
            self._transport_type = data.get("transport_type", "unknown")
            if "ESTOP" in self._mcu_state.upper():
                self._estop_active = True
        except Exception:
            self._mcu_state = msg.data
            self._is_mock = "MOCK" in self._mcu_state.upper()

    def _on_fault(self, msg: String):
        try:
            data = json.loads(msg.data)
            self._mcu_fault = data.get("description", "")
            if data.get("source") == "physical_estop":
                self._estop_active = True
        except Exception:
            self._mcu_fault = msg.data

    def _publish_status(self):
        now = time.time()

        scan_age = now - self._last_scan_time if self._last_scan_time > 0 else None
        imu_age = now - self._last_imu_time if self._last_imu_time > 0 else None
        odom_age = now - self._last_odom_time if self._last_odom_time > 0 else None

        scan_ok = (scan_age is not None) and (scan_age < self._scan_timeout)
        imu_ok = (imu_age is not None) and (imu_age < self._imu_timeout)
        odom_ok = (odom_age is not None) and (odom_age < self._odom_timeout)
        mcu_ok = self._mcu_state in ("CONNECTED", "CONNECTED_MOCK")

        if self._hw_mode == "sim":
            # In simulation, MCU state is not applicable
            mcu_ok = True
            odom_ok = True

        nav_ready = scan_ok and odom_ok and mcu_ok and not self._estop_active
        missing_deps = []
        if not scan_ok:
            missing_deps.append("lidar_scan(/scan)")
        if not odom_ok and self._hw_mode == "hardware":
            missing_deps.append("odometry(/odom)")
        if not mcu_ok and self._hw_mode == "hardware":
            missing_deps.append("mcu_connection(/hardware/mcu_state)")
        if self._estop_active:
            missing_deps.append("estop_cleared")

        if self._hw_mode == "sim":
            overall = "OK" if scan_ok else "DEGRADED"
        else:
            if not nav_ready:
                overall = "DEGRADED"
            elif self._is_mock:
                overall = "MOCK_OPERATIONAL"
            else:
                overall = "OK"

        status = {
            "timestamp": now,
            "hardware_mode": self._hw_mode,
            "overall": overall,
            "navigation_ready": nav_ready,
            "missing_dependencies": missing_deps,
            "estop_active": self._estop_active,
            "sensors": {
                "lidar": {
                    "status": "RECEIVING" if scan_ok else ("NO_DATA" if scan_age is None else "TIMEOUT"),
                    "ok": scan_ok,
                    "topic": "/scan",
                    "frame_id": "lidar_link",
                    "last_msg_age_sec": round(scan_age, 2) if scan_age is not None else None,
                    "timeout_threshold_sec": self._scan_timeout,
                },
                "imu": {
                    "status": "RECEIVING" if imu_ok else ("NO_DATA" if imu_age is None else "TIMEOUT"),
                    "ok": imu_ok,
                    "last_msg_age_sec": round(imu_age, 2) if imu_age is not None else None,
                    "timeout_threshold_sec": self._imu_timeout,
                },
                "odometry": {
                    "status": "RECEIVING" if odom_ok else ("NO_DATA" if odom_age is None else "TIMEOUT"),
                    "ok": odom_ok,
                    "last_msg_age_sec": round(odom_age, 2) if odom_age is not None else None,
                    "timeout_threshold_sec": self._odom_timeout,
                },
            },
            "mcu": {
                "state": self._mcu_state,
                "ok": mcu_ok,
                "is_mock": self._is_mock,
                "transport_type": self._transport_type,
                "physical_hardware_active": (mcu_ok and not self._is_mock),
                "last_fault": self._mcu_fault,
                "warning": "MOCK MODE: Physical motors are NOT being controlled." if self._is_mock else "",
            },
        }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)

        if not nav_ready:
            self.get_logger().warn(
                f"⚠️ Hardware status DEGRADED: "
                f"lidar={'OK' if scan_ok else 'MISSING'} "
                f"odom={'OK' if odom_ok else 'MISSING'} "
                f"mcu={self._mcu_state} "
                f"estop={'ACTIVE' if self._estop_active else 'off'} "
                f"missing={missing_deps}"
            )


def main(args=None):
    rclpy.init(args=args)
    node = HardwareStatusNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
