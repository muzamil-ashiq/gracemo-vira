#!/usr/bin/env python3
"""
GRaCEmo ViRa — Native Gazebo Harmonic to ROS 2 Physical Sensor Bridge Node
Authoritatively bridges:
  1. LiDAR:               Gazebo /scan               -> ROS 2 /scan (sensor_msgs/msg/LaserScan)
  2. TF & Odometry:       Gazebo /odom               -> ROS 2 /odom (nav_msgs/msg/Odometry) & TF (odom -> base_footprint, world -> odom)
  3. Joint States:        Gazebo joint_state (Model) -> ROS 2 /joint_states (sensor_msgs/msg/JointState)
  4. IMU:                 Gazebo /imu/data           -> ROS 2 /imu/data (sensor_msgs/msg/Imu)
  5. RGB Camera & Info:   Gazebo /camera/image_raw   -> ROS 2 /camera/image_raw & /camera/camera_info
  6. Depth Camera & Info: Gazebo /camera/depth_image -> ROS 2 /camera/depth_image & /camera/depth/camera_info
  7. PointCloud2:         Gazebo .../points          -> ROS 2 /camera/depth/points (sensor_msgs/msg/PointCloud2)
  8. Velocity Commands:   ROS 2 /cmd_vel             -> Gazebo /cmd_vel (gz.msgs.Twist)
"""

import math
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import (
    LaserScan as RosLaserScan,
    JointState as RosJointState,
    Imu as RosImu,
    Image as RosImage,
    CameraInfo as RosCameraInfo,
    PointCloud2 as RosPointCloud2,
    PointField as RosPointField,
)
from rosgraph_msgs.msg import Clock as RosClock
from nav_msgs.msg import Odometry as RosOdometry
from geometry_msgs.msg import Twist as RosTwist, TransformStamped
import tf2_ros

# Gazebo Harmonic Transport & Messages
import gz.transport13 as gz_transport
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.imu_pb2 import IMU as GzIMU
from gz.msgs10.model_pb2 import Model as GzModel
from gz.msgs10.pointcloud_packed_pb2 import PointCloudPacked as GzPointCloudPacked
from gz.msgs10.clock_pb2 import Clock as GzClock


class SensorBridgeNode(Node):
    def __init__(self):
        super().__init__("gracemo_sensor_bridge")

        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)

        # ── 1. Setup ROS 2 Publishers ──
        self.pub_clock = self.create_publisher(RosClock, "/clock", 10)
        self.pub_scan = self.create_publisher(RosLaserScan, "/scan", 10)
        self.pub_joint_states = self.create_publisher(RosJointState, "/joint_states", 20)
        self.pub_odom = self.create_publisher(RosOdometry, "/odom", 20)
        self.pub_imu = self.create_publisher(RosImu, "/imu/data", 20)
        self.pub_rgb_image = self.create_publisher(RosImage, "/camera/image_raw", 10)
        self.pub_rgb_info = self.create_publisher(RosCameraInfo, "/camera/camera_info", 10)
        self.pub_depth_image = self.create_publisher(RosImage, "/camera/depth_image", 10)
        self.pub_depth_info = self.create_publisher(RosCameraInfo, "/camera/depth/camera_info", 10)
        self.pub_depth_points = self.create_publisher(RosPointCloud2, "/camera/depth/points", 10)

        # ── 2. Setup TF Broadcasters ──
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.static_tf_broadcaster = tf2_ros.StaticTransformBroadcaster(self)
        self._publish_static_world_tf()

        # ── 3. Setup ROS 2 Subscribers ──
        self.sub_cmd_vel = self.create_subscription(
            RosTwist, "/cmd_vel", self._on_ros_cmd_vel, 10
        )

        # ── 4. Precompute Optical Camera Intrinsics & PointCloud Fields ──
        # RGB: 640x480, hfov=1.15 rad
        self.rgb_info_msg = self._build_camera_info(
            width=640, height=480, hfov=1.15, frame_id="camera_optical_link"
        )
        # Depth: 320x240, hfov=1.15 rad
        self.depth_info_msg = self._build_camera_info(
            width=320, height=240, hfov=1.15, frame_id="camera_optical_link"
        )
        # Precomputed PointField descriptors (FLOAT32 = 7)
        self.pc_fields = []
        for name, offset in [("x", 0), ("y", 4), ("z", 8), ("rgb", 16)]:
            pf = RosPointField()
            pf.name = name
            pf.offset = offset
            pf.datatype = RosPointField.FLOAT32
            pf.count = 1
            self.pc_fields.append(pf)

        self._last_js_time = 0.0
        self._last_imu_time = 0.0
        self._last_pc_time = 0.0
        self._last_depth_time = 0.0
        self._last_rgb_time = 0.0

        # ── 5. Setup Gazebo Harmonic Transport Subscriptions ──
        self.gz_node = gz_transport.Node()

        # Clock
        self.gz_node.subscribe(GzClock, "/clock", self._on_gz_clock)

        # Velocity commanding
        self.gz_cmd_pub = self.gz_node.advertise("/cmd_vel", GzTwist)

        # Sensor callbacks
        self.gz_node.subscribe(GzLaserScan, "/scan", self._on_gz_scan)
        self.gz_node.subscribe(
            GzModel,
            "/world/gracemo_home/model/gracemo_vira/joint_state",
            self._on_gz_joint_state,
        )
        self.gz_node.subscribe(GzOdometry, "/odom", self._on_gz_odom)
        self.gz_node.subscribe(GzIMU, "/imu/data", self._on_gz_imu)
        self.gz_node.subscribe(GzImage, "/camera/image_raw", self._on_gz_rgb_image)
        self.gz_node.subscribe(GzImage, "/camera/depth_image", self._on_gz_depth_image)
        self.gz_node.subscribe(
            GzPointCloudPacked,
            "/camera/depth_image/points",
            self._on_gz_depth_points,
        )

        self.get_logger().info("✓ GRaCEmo Sensor Bridge initialized: All physical Gazebo sensors mapped to ROS 2!")

    def _to_ros_time(self, gz_header) -> Time:
        """Extract ROS 2 timestamp from Gazebo Header with fallback to node clock."""
        if gz_header and gz_header.HasField("stamp") and (gz_header.stamp.sec > 0 or gz_header.stamp.nsec > 0):
            return Time(seconds=gz_header.stamp.sec, nanoseconds=gz_header.stamp.nsec).to_msg()
        return self.get_clock().now().to_msg()

    def _publish_static_world_tf(self):
        """Broadcast static transform world -> odom."""
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "world"
        t.child_frame_id = "odom"
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        self.static_tf_broadcaster.sendTransform(t)

    def _build_camera_info(self, width: int, height: int, hfov: float, frame_id: str) -> RosCameraInfo:
        """Construct static CameraInfo matching pinhole camera optics."""
        info = RosCameraInfo()
        info.width = width
        info.height = height
        info.distortion_model = "plumb_bob"
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]

        fx = (width / 2.0) / math.tan(hfov / 2.0)
        fy = fx
        cx = width / 2.0
        cy = height / 2.0

        info.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info.p = [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
        info.header.frame_id = frame_id
        return info

    # ── Gazebo Callbacks ──

    def _on_gz_scan(self, msg: GzLaserScan):
        ros_scan = RosLaserScan()
        ros_scan.header.stamp = self._to_ros_time(msg.header)
        ros_scan.header.frame_id = "lidar_link"

        ros_scan.angle_min = float(msg.angle_min)
        ros_scan.angle_max = float(msg.angle_max)
        ros_scan.angle_increment = float(msg.angle_step)
        ros_scan.time_increment = 0.0
        ros_scan.scan_time = 1.0 / 15.0
        ros_scan.range_min = float(msg.range_min)
        ros_scan.range_max = float(msg.range_max)
        ros_scan.ranges = [float(r) for r in msg.ranges]
        ros_scan.intensities = [float(i) for i in msg.intensities]

        self.pub_scan.publish(ros_scan)

    def _on_gz_clock(self, msg: GzClock):
        ros_clock = RosClock()
        ros_clock.clock.sec = int(msg.sim.sec)
        ros_clock.clock.nanosec = int(msg.sim.nsec)
        self.pub_clock.publish(ros_clock)

    def _on_gz_joint_state(self, msg: GzModel):
        now = time.time()
        if now - self._last_js_time < 0.033:  # Throttle to 30 Hz
            return
        self._last_js_time = now

        ros_js = RosJointState()
        ros_js.header.stamp = self._to_ros_time(msg.header)
        ros_js.header.frame_id = ""

        for j in msg.joint:
            ros_js.name.append(j.name)
            if j.HasField("axis1"):
                ros_js.position.append(float(j.axis1.position))
                ros_js.velocity.append(float(j.axis1.velocity))
            else:
                ros_js.position.append(0.0)
                ros_js.velocity.append(0.0)
            ros_js.effort.append(0.0)

        self.pub_joint_states.publish(ros_js)

    def _on_gz_odom(self, msg: GzOdometry):
        stamp = self._to_ros_time(msg.header)

        # 1. Publish Odometry message
        ros_odom = RosOdometry()
        ros_odom.header.stamp = stamp
        ros_odom.header.frame_id = "odom"
        ros_odom.child_frame_id = "base_footprint"

        ros_odom.pose.pose.position.x = float(msg.pose.position.x)
        ros_odom.pose.pose.position.y = float(msg.pose.position.y)
        ros_odom.pose.pose.position.z = float(msg.pose.position.z)
        ros_odom.pose.pose.orientation.x = float(msg.pose.orientation.x)
        ros_odom.pose.pose.orientation.y = float(msg.pose.orientation.y)
        ros_odom.pose.pose.orientation.z = float(msg.pose.orientation.z)
        ros_odom.pose.pose.orientation.w = float(msg.pose.orientation.w)

        ros_odom.twist.twist.linear.x = float(msg.twist.linear.x)
        ros_odom.twist.twist.linear.y = float(msg.twist.linear.y)
        ros_odom.twist.twist.linear.z = float(msg.twist.linear.z)
        ros_odom.twist.twist.angular.x = float(msg.twist.angular.x)
        ros_odom.twist.twist.angular.y = float(msg.twist.angular.y)
        ros_odom.twist.twist.angular.z = float(msg.twist.angular.z)

        self.pub_odom.publish(ros_odom)

        # 2. Broadcast TF: odom -> base_footprint
        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = "odom"
        t.child_frame_id = "base_footprint"
        t.transform.translation.x = float(msg.pose.position.x)
        t.transform.translation.y = float(msg.pose.position.y)
        t.transform.translation.z = float(msg.pose.position.z)
        t.transform.rotation.x = float(msg.pose.orientation.x)
        t.transform.rotation.y = float(msg.pose.orientation.y)
        t.transform.rotation.z = float(msg.pose.orientation.z)
        t.transform.rotation.w = float(msg.pose.orientation.w)

        self.tf_broadcaster.sendTransform(t)

    def _on_gz_imu(self, msg: GzIMU):
        now = time.time()
        if now - self._last_imu_time < 0.025:  # Throttle to 40 Hz
            return
        self._last_imu_time = now

        ros_imu = RosImu()
        ros_imu.header.stamp = self._to_ros_time(msg.header)
        ros_imu.header.frame_id = "imu_link"

        if msg.HasField("orientation"):
            ros_imu.orientation.x = float(msg.orientation.x)
            ros_imu.orientation.y = float(msg.orientation.y)
            ros_imu.orientation.z = float(msg.orientation.z)
            ros_imu.orientation.w = float(msg.orientation.w)

        if msg.HasField("angular_velocity"):
            ros_imu.angular_velocity.x = float(msg.angular_velocity.x)
            ros_imu.angular_velocity.y = float(msg.angular_velocity.y)
            ros_imu.angular_velocity.z = float(msg.angular_velocity.z)

        if msg.HasField("linear_acceleration"):
            ros_imu.linear_acceleration.x = float(msg.linear_acceleration.x)
            ros_imu.linear_acceleration.y = float(msg.linear_acceleration.y)
            ros_imu.linear_acceleration.z = float(msg.linear_acceleration.z)

        self.pub_imu.publish(ros_imu)

    def _on_gz_rgb_image(self, msg: GzImage):
        if self.pub_rgb_image.get_subscription_count() == 0 and self.pub_rgb_info.get_subscription_count() == 0:
            return
        now = time.time()
        if now - self._last_rgb_time < 0.033:  # 30 Hz
            return
        self._last_rgb_time = now

        stamp = self._to_ros_time(msg.header)

        # Image message
        ros_img = RosImage()
        ros_img.header.stamp = stamp
        ros_img.header.frame_id = "camera_optical_link"
        ros_img.width = int(msg.width)
        ros_img.height = int(msg.height)
        ros_img.encoding = "rgb8"
        ros_img.is_bigendian = 0
        ros_img.step = int(msg.step)
        ros_img.data = bytes(msg.data)
        self.pub_rgb_image.publish(ros_img)

        # CameraInfo message
        self.rgb_info_msg.header.stamp = stamp
        self.pub_rgb_info.publish(self.rgb_info_msg)

    def _on_gz_depth_image(self, msg: GzImage):
        if self.pub_depth_image.get_subscription_count() == 0 and self.pub_depth_info.get_subscription_count() == 0:
            return
        now = time.time()
        if now - self._last_depth_time < 0.066:  # 15 Hz
            return
        self._last_depth_time = now

        stamp = self._to_ros_time(msg.header)

        ros_img = RosImage()
        ros_img.header.stamp = stamp
        ros_img.header.frame_id = "camera_optical_link"
        ros_img.width = int(msg.width)
        ros_img.height = int(msg.height)
        ros_img.encoding = "32FC1"
        ros_img.is_bigendian = 0
        ros_img.step = int(msg.step)
        ros_img.data = bytes(msg.data)
        self.pub_depth_image.publish(ros_img)

        self.depth_info_msg.header.stamp = stamp
        self.pub_depth_info.publish(self.depth_info_msg)

    def _on_gz_depth_points(self, msg: GzPointCloudPacked):
        if self.pub_depth_points.get_subscription_count() == 0:
            return
        now = time.time()
        if now - self._last_pc_time < 0.10:  # 10 Hz
            return
        self._last_pc_time = now

        stamp = self._to_ros_time(msg.header)

        ros_cloud = RosPointCloud2()
        ros_cloud.header.stamp = stamp
        ros_cloud.header.frame_id = "camera_optical_link"
        ros_cloud.height = int(msg.height)
        ros_cloud.width = int(msg.width)
        ros_cloud.is_bigendian = False
        ros_cloud.point_step = int(msg.point_step)
        ros_cloud.row_step = int(msg.row_step)
        ros_cloud.is_dense = bool(msg.is_dense)
        ros_cloud.data = bytes(msg.data)
        ros_cloud.fields = self.pc_fields
        self.pub_depth_points.publish(ros_cloud)

    def _on_ros_cmd_vel(self, msg: RosTwist):
        """Forward ROS 2 /cmd_vel to Gazebo diff_drive."""
        if self.gz_cmd_pub:
            gz_tw = GzTwist()
            gz_tw.linear.x = float(msg.linear.x)
            gz_tw.angular.z = float(msg.angular.z)
            self.get_logger().info(f"Forwarding cmd_vel: lin={gz_tw.linear.x:.2f}, ang={gz_tw.angular.z:.2f}")
            self.gz_cmd_pub.publish(gz_tw)


def main(args=None):
    rclpy.init(args=args)
    node = SensorBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
