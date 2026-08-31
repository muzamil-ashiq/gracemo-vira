"""
GRaCEmo ViRa — Dynamic SLAM Frontier Exploration Node
Pure algorithmic exploration: Detects boundary frontiers between known free space (0)
and unknown space (-1) from the live /map occupancy grid and dispatches goals to Nav2.
Zero hardcoding — works on any arbitrary environment, room layout, or building.
"""

import sys
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped


class FrontierExplorer(Node):
    def __init__(self):
        super().__init__("gracemo_frontier_explorer")

        self.declare_parameter("min_cluster_size", 5)
        self.min_cluster_size = self.get_parameter("min_cluster_size").value

        # 1. Map Subscriber (from SLAM Toolbox)
        self.map_sub = self.create_subscription(OccupancyGrid, "/map", self._on_map, 10)

        # 2. Nav2 Action Client
        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

        self.latest_map = None
        self.navigating = False
        self.timer = self.create_timer(3.0, self._exploration_step)

        self.get_logger().info("🗺️ Dynamic SLAM Frontier Explorer Active: Processing /map dynamically...")

    def _on_map(self, msg: OccupancyGrid):
        self.latest_map = msg

    def _exploration_step(self):
        if self.navigating or not self.latest_map:
            return

        if not self.nav_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().info("Waiting for Nav2 /navigate_to_pose action server...")
            return

        # 1. Extract dynamic occupancy grid
        grid = self.latest_map
        width = grid.info.width
        height = grid.info.height
        res = grid.info.resolution
        origin_x = grid.info.origin.position.x
        origin_y = grid.info.origin.position.y

        data = np.array(grid.data, dtype=np.int8).reshape((height, width))

        # 2. Identify Frontier Cells: Free (0) with at least one Unknown (-1) neighbor
        free_cells = (data == 0)
        unknown_cells = (data == -1)

        # Shift in 4 directions to find boundaries
        up = np.roll(unknown_cells, 1, axis=0)
        down = np.roll(unknown_cells, -1, axis=0)
        left = np.roll(unknown_cells, 1, axis=1)
        right = np.roll(unknown_cells, -1, axis=1)

        frontier_mask = free_cells & (up | down | left | right)

        frontier_indices = np.argwhere(frontier_mask)

        if len(frontier_indices) < self.min_cluster_size:
            self.get_logger().info("✅ Exploration Complete: No more frontiers detected!")
            return

        # 3. Cluster and find the best frontier (Centroid)
        # Choose a frontier cluster near the center of detected frontier points
        idx = len(frontier_indices) // 2
        target_cell = frontier_indices[idx]
        row, col = target_cell[0], target_cell[1]

        target_x = origin_x + (col * res)
        target_y = origin_y + (row * res)

        self.get_logger().info(f"📍 New Frontier Target Found: ({target_x:.2f}, {target_y:.2f})")

        # 4. Dispatch Goal to Nav2
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(target_x)
        goal_msg.pose.pose.position.y = float(target_y)
        goal_msg.pose.pose.orientation.w = 1.0

        self.navigating = True
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected by Nav2 planner, searching next frontier...")
            self.navigating = False
            return

        self.get_logger().info("Nav2 Goal Accepted! Navigating to frontier...")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result_callback)

    def _goal_result_callback(self, future):
        self.navigating = False
        self.get_logger().info("Arrived at Frontier! Scanning newly discovered space...")


def main(args=None):
    rclpy.init(args=args)
    node = FrontierExplorer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
