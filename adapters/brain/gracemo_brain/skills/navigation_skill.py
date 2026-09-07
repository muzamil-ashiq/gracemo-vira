#!/usr/bin/env python3
"""
GRaCEmo ViRa — Level 2 Embodied Navigation Skill
Cerebellar spatial navigation bridging semantic meaning with physical geometry.

Responsibilities:
  1. Maintains dynamic 20Hz Local Metric Costmap from 2D LiDAR and Odometry.
  2. Collision-free free-space path planning via 2D A* with obstacle inflation.
  3. Queries Level 3 MNSE Knowledge Graph (graph.db) to resolve semantic entities to metric targets.
  4. Translates spatial paths into waypoint streams for the Level 1 Base Controller.
"""

import sys
import os
import time
import math
import heapq
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Set
import numpy as np

ROOT = Path(__file__).resolve()
while ROOT.name != "gracemo-vira" and ROOT.parent != ROOT:
    ROOT = ROOT.parent

for sub in ["sdk", "motion", "brain/gracemo_brain/skills"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_sdk import AdapterClient
from gracemo_base_controller import BaseController


class LocalCostmap:
    """
    Rolling 2D metric occupancy grid centered on the robot.
    Resolution: 0.05m (5cm per cell).
    Default bounds: 10m x 10m (200x200 cells).
    """

    def __init__(self, size_m: float = 10.0, resolution_m: float = 0.05, inflation_radius_m: float = 0.30):
        self.size_m = size_m
        self.resolution_m = resolution_m
        self.inflation_radius_m = inflation_radius_m
        self.grid_dim = int(size_m / resolution_m)
        self.inflation_cells = int(math.ceil(inflation_radius_m / resolution_m))

        # 0 = Unknown/Free, 100 = Occupied/Obstacle, 50 = Inflated Cushion
        self.grid = np.zeros((self.grid_dim, self.grid_dim), dtype=np.uint8)
        self.origin_x = 0.0
        self.origin_y = 0.0

    def world_to_grid(self, wx: float, wy: float) -> Optional[Tuple[int, int]]:
        gx = int(round((wx - (self.origin_x - self.size_m / 2.0)) / self.resolution_m))
        gy = int(round((wy - (self.origin_y - self.size_m / 2.0)) / self.resolution_m))
        if 0 <= gx < self.grid_dim and 0 <= gy < self.grid_dim:
            return (gx, gy)
        return None

    def grid_to_world(self, gx: int, gy: int) -> Tuple[float, float]:
        wx = (self.origin_x - self.size_m / 2.0) + (gx + 0.5) * self.resolution_m
        wy = (self.origin_y - self.size_m / 2.0) + (gy + 0.5) * self.resolution_m
        return (wx, wy)

    def update_from_scan(self, robot_x: float, robot_y: float, robot_yaw: float, scan_ranges: List[float], angle_min: float, angle_step: float):
        """Updates occupancy grid from LiDAR point ranges."""
        self.origin_x = robot_x
        self.origin_y = robot_y
        self.grid.fill(0)  # Reset local window

        obstacle_cells: Set[Tuple[int, int]] = set()

        for i, r in enumerate(scan_ranges):
            if math.isnan(r) or math.isinf(r) or r < 0.15 or r > (self.size_m / 2.0 - 0.2):
                continue

            angle = robot_yaw + angle_min + i * angle_step
            ox = robot_x + r * math.cos(angle)
            oy = robot_y + r * math.sin(angle)

            cell = self.world_to_grid(ox, oy)
            if cell:
                obstacle_cells.add(cell)

        # Mark obstacles and inflate safety margins
        for gx, gy in obstacle_cells:
            self.grid[gx, gy] = 100
            for dx in range(-self.inflation_cells, self.inflation_cells + 1):
                for dy in range(-self.inflation_cells, self.inflation_cells + 1):
                    if dx * dx + dy * dy <= self.inflation_cells * self.inflation_cells:
                        nx, ny = gx + dx, gy + dy
                        if 0 <= nx < self.grid_dim and 0 <= ny < self.grid_dim:
                            if self.grid[nx, ny] < 100:
                                self.grid[nx, ny] = 50

    def is_cell_traversable(self, gx: int, gy: int) -> bool:
        if 0 <= gx < self.grid_dim and 0 <= gy < self.grid_dim:
            return self.grid[gx, gy] == 0
        return False


class AStarPlanner:
    """Computes collision-free shortest paths across the LocalCostmap."""

    def __init__(self, costmap: LocalCostmap):
        self.costmap = costmap

    def plan_path(self, start_w: Tuple[float, float], goal_w: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        start_cell = self.costmap.world_to_grid(start_w[0], start_w[1])
        goal_cell = self.costmap.world_to_grid(goal_w[0], goal_w[1])

        if not start_cell or not goal_cell:
            return None

        # If goal is inside inflation, find nearest traversable cell
        if not self.costmap.is_cell_traversable(goal_cell[0], goal_cell[1]):
            goal_cell = self._find_nearest_free(goal_cell)
            if not goal_cell:
                return None

        open_set = []
        heapq.heappush(open_set, (0.0, start_cell))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start_cell: 0.0}

        def heuristic(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        # 8-connected neighbors
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal_cell:
                # Reconstruct path
                path_cells = [current]
                while current in came_from:
                    current = came_from[current]
                    path_cells.append(current)
                path_cells.reverse()

                # Convert to world coordinates and simplify
                world_path = [self.costmap.grid_to_world(gx, gy) for gx, gy in path_cells]
                return self._simplify_path(world_path)

            for dx, dy in neighbors:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if not self.costmap.is_cell_traversable(nx, ny):
                    continue

                step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                tentative_g = g_score[current] + step_cost

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal_cell)
                    heapq.heappush(open_set, (f, neighbor))

        return None

    def _find_nearest_free(self, cell: Tuple[int, int], max_radius: int = 8) -> Optional[Tuple[int, int]]:
        cx, cy = cell
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = cx + dx, cy + dy
                    if self.costmap.is_cell_traversable(nx, ny):
                        return (nx, ny)
        return None

    def _simplify_path(self, points: List[Tuple[float, float]], step_keep: int = 5) -> List[Tuple[float, float]]:
        """Samples the raw dense grid path into smooth sparse waypoints."""
        if len(points) <= 2:
            return points
        simplified = [points[0]]
        for i in range(step_keep, len(points) - 1, step_keep):
            simplified.append(points[i])
        simplified.append(points[-1])
        return simplified


class NavigationSkill:
    """
    Level 2 Navigation Skill.
    Bridges high-level semantic destinations into collision-free geometric trajectories.
    """

    def __init__(self, base_controller: Optional[BaseController] = None):
        self.controller = base_controller or BaseController()
        self.client = AdapterClient(adapter_name="NavigationSkill", base_url="http://127.0.0.1:7780")
        self.costmap = LocalCostmap(size_m=12.0, resolution_m=0.05, inflation_radius_m=0.28)
        self.planner = AStarPlanner(self.costmap)

    def refresh_costmap(self):
        """Refreshes local costmap from latest LiDAR scan."""
        if self.controller.latest_scan and self.controller.has_odom:
            scan = self.controller.latest_scan
            n = len(scan.ranges)
            step = scan.angle_step if scan.angle_step > 0 else (2.0 * math.pi / n)
            self.costmap.update_from_scan(
                robot_x=self.controller.cur_x,
                robot_y=self.controller.cur_y,
                robot_yaw=self.controller.cur_yaw,
                scan_ranges=list(scan.ranges),
                angle_min=scan.angle_min,
                angle_step=step
            )

    def plan_to_metric_pose(self, target_x: float, target_y: float) -> Optional[List[Tuple[float, float]]]:
        """Plans a geometric path using the local metric costmap."""
        self.refresh_costmap()
        start = (self.controller.cur_x, self.controller.cur_y)
        goal = (target_x, target_y)
        return self.planner.plan_path(start, goal)

    def navigate_to_metric_pose(self, target_x: float, target_y: float, target_yaw: Optional[float] = None) -> bool:
        """Plans and executes path to metric (x, y) coordinates using local costmap A*."""
        print(f"[NAV SKILL] Planning path to ({target_x:+.2f}, {target_y:+.2f})...")
        path = self.plan_to_metric_pose(target_x, target_y)
        if not path:
            print(f"[NAV SKILL] ❌ Direct A* path to ({target_x:+.2f}, {target_y:+.2f}) is blocked by obstacles. Refusing blind pursuit.")
            return False

        print(f"[NAV SKILL] Generated collision-free path with {len(path)} waypoints. Dispatching to Base Controller...")
        return self.controller.follow_waypoints(path, final_yaw=target_yaw)

    def get_current_room(self) -> str:
        """Determines current spatial region from metric odometry."""
        x, y = self.controller.cur_x, self.controller.cur_y
        if abs(y) <= 1.05:
            return "room:hallway"
        elif y > 1.05:
            return "room:bedroom" if x < 0.0 else "room:study"
        else:
            return "room:kitchen" if x < 0.0 else "room:living"

    def resolve_room_portal(self, target_room_id: str) -> Optional[Dict[str, Any]]:
        """
        Queries Level 3 MNSE Knowledge Graph for Doorway Portal leading to target room.
        Supports both seeded topology portals and dynamically discovered portals.
        """
        try:
            full = self.client.get_graph()
            nodes = full.get("nodes", [])
            edges = full.get("edges", [])

            # 1. Look for Portal node connected via LEADS_TO or CONNECTS edge
            portal_id = None
            for e in edges:
                if e.get("target") == target_room_id and e.get("relation") in ("LEADS_TO", "CONNECTS"):
                    portal_id = e.get("source")
                    break

            # 2. Or check portal_id in target room node properties
            if not portal_id:
                for n in nodes:
                    if n.get("id") == target_room_id:
                        portal_id = n.get("properties", {}).get("portal_id")
                        break

            if portal_id:
                for n in nodes:
                    if n.get("id") == portal_id:
                        return n.get("properties", {})
        except Exception as e:
            print(f"[NAV SKILL] Error querying portal from graph: {e}")
        return None

    def resolve_semantic_target(self, target_name: str) -> Optional[Tuple[float, float]]:
        """Resolves target entity name to metric coordinates from MNSE Knowledge Graph."""
        target_clean = target_name.lower().strip()
        canonical_map = {
            "bedroom": "room:bedroom",
            "master bedroom": "room:bedroom",
            "study": "room:study",
            "kitchen": "room:kitchen",
            "living": "room:living",
            "living room": "room:living",
            "hallway": "room:hallway",
        }
        room_id = canonical_map.get(target_clean)
        try:
            nodes = self.client.get_graph_nodes()
            for n in nodes:
                nid = n.get("id", "").lower()
                lbl = n.get("label", "").lower()
                props = n.get("properties", {})
                if (room_id and nid == room_id) or (target_clean in lbl or target_clean in nid):
                    x = props.get("center_x") or props.get("door_x") or props.get("target_x")
                    y = props.get("center_y") or props.get("door_y") or props.get("target_y")
                    if x is not None and y is not None:
                        return (float(x), float(y))
        except Exception:
            pass
        return None

    def navigate_to_semantic_target(self, target_name: str) -> bool:
        """
        Topological Portal-Sequence Navigation:
        Resolves destination from MNSE Graph, checks current room topology,
        and executes corridor approach -> doorway threshold -> interior destination.
        """
        print(f"\n[NAV SKILL] 🧭 Resolving semantic target: '{target_name}'...")
        target_clean = target_name.lower().strip()

        # Canonical room ID mapping
        canonical_map = {
            "bedroom": "room:bedroom",
            "study": "room:study",
            "kitchen": "room:kitchen",
            "living": "room:living",
            "living room": "room:living",
            "hallway": "room:hallway",
            "central hallway": "room:hallway",
        }
        room_id = canonical_map.get(target_clean)

        # Check if target is an object grounded in a room
        if not room_id:
            try:
                full = self.client.get_graph()
                edges = full.get("edges", [])
                for e in edges:
                    src = e.get("source", "").lower()
                    if target_clean in src and e.get("relation") == "LOCATED_IN":
                        room_id = e.get("target")
                        print(f"[NAV SKILL] Object '{target_name}' is grounded in '{room_id}'.")
                        break
            except Exception:
                pass

        if not room_id:
            # Fallback to direct label matching in nodes
            nodes = self.client.get_graph_nodes()
            for n in nodes:
                lbl = n.get("label", "").lower()
                if target_clean in lbl:
                    room_id = n.get("id")
                    break

        if not room_id:
            print(f"[NAV SKILL] ❌ Entity '{target_name}' not yet grounded in MNSE Knowledge Graph.")
            return False

        current_room = self.get_current_room()
        print(f"[NAV SKILL] Current location: {current_room} | Destination: {room_id}")

        # If already at destination
        if current_room == room_id:
            print(f"[NAV SKILL] Already in {room_id}. Checking local fine pose...")
            return True

        # If currently inside a room (not in hallway), exit through its portal first
        if current_room != "room:hallway":
            print(f"[NAV SKILL] Transitioning from {current_room} -> corridor -> {room_id}...")
            curr_portal = self.resolve_room_portal(current_room)
            if curr_portal:
                thr_x = float(curr_portal["threshold_x"])
                thr_y = float(curr_portal["threshold_y"])
                app_x = float(curr_portal["approach_x"])
                app_y = float(curr_portal["approach_y"])

                print(f"[NAV SKILL] Navigating interior path to doorway threshold ({thr_x:+.2f}, {thr_y:+.2f})...")
                ok = self.navigate_to_metric_pose(thr_x, thr_y)
                if not ok:
                    self.controller.drive_to_pose(thr_x, thr_y, reach_dist=0.25)

                print(f"[NAV SKILL] Gliding across portal into corridor centerline ({app_x:+.2f}, {app_y:+.2f})...")
                self.controller.drive_to_pose(app_x, app_y, reach_dist=0.25)

            if room_id == "room:hallway":
                print(f"[NAV SKILL] 🎯 Arrived at hallway!")
                return True
            # Recurse from corridor to target room
            return self.navigate_to_semantic_target(target_name)

        # If destination is the hallway and we are in the hallway
        if room_id == "room:hallway":
            return self.navigate_to_metric_pose(0.0, 0.0)

        # Retrieve Doorway Portal
        portal = self.resolve_room_portal(room_id)
        if not portal:
            print(f"[NAV SKILL] ❌ No doorway portal found in graph connecting to {room_id}.")
            return False

        app_x = float(portal["approach_x"])
        app_y = float(portal["approach_y"])
        app_yaw = float(portal.get("approach_yaw", 0.0))
        thr_x = float(portal["threshold_x"])
        thr_y = float(portal["threshold_y"])
        thr_yaw = float(portal.get("threshold_yaw", app_yaw))
        tgt_x = float(portal["target_x"])
        tgt_y = float(portal["target_y"])

        # Topological Sequence Execution
        # Topological Sequence Execution (now guaranteed to be in hallway)
        # Stage 1: Corridor Alignment (drive down centerline to doorway approach)
        print(f"\n[NAV SKILL] [Stage 1/3] Navigating corridor centerline to approach pose ({app_x:+.2f}, {app_y:+.2f})...")
        ok = self.controller.drive_to_pose(app_x, app_y, target_yaw=app_yaw, reach_dist=0.20)
        if not ok:
            print("[NAV SKILL] ❌ Failed to reach corridor approach pose.")
            return False

        # Stage 2: Orthogonal Doorway Entry (cross 1.2m opening threshold)
        print(f"\n[NAV SKILL] [Stage 2/3] Gliding orthogonally through doorway threshold ({thr_x:+.2f}, {thr_y:+.2f})...")
        ok = self.controller.drive_to_pose(thr_x, thr_y, target_yaw=thr_yaw, reach_dist=0.22)
        if not ok:
            print("[NAV SKILL] ❌ Failed to cross doorway threshold.")
            return False

        # Stage 3: Interior Navigation (reach room target pose)
        print(f"\n[NAV SKILL] [Stage 3/3] Navigating room interior to destination ({tgt_x:+.2f}, {tgt_y:+.2f})...")
        ok = self.navigate_to_metric_pose(tgt_x, tgt_y)
        if not ok:
            # Local line pursuit within the cleared room
            ok = self.controller.drive_to_pose(tgt_x, tgt_y, reach_dist=0.30)

        if ok:
            print(f"[NAV SKILL] 🎯 Successfully arrived at {room_id}!")
            # Update MNSE knowledge graph arrival
            try:
                payload = {"destination": room_id, "success": True}
                self.client.emit_event("NavigationArrived", payload)
            except Exception:
                pass
            return True
        else:
            print(f"[NAV SKILL] ❌ Could not reach final target inside {room_id}.")
            return False


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "bedroom"
    skill = NavigationSkill()
    if not skill.controller.wait_for_sensors():
        print("[NAV SKILL] Sensors offline. Gazebo must be running.")
        sys.exit(1)

    success = skill.navigate_to_semantic_target(target)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
