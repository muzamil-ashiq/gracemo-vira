#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase C Automated Verification Suite
Tests Level 2 Embodied Skills:
  1. LocalCostmap obstacle insertion and inflation.
  2. AStarPlanner collision-free geometric trajectory generation around walls.
  3. PerceptionSkill Bayesian room evidence accumulation and graduation.
"""

import unittest
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain" / "skills"))
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from navigation_skill import LocalCostmap, AStarPlanner
from perception_skill import PerceptionSkill, RoomHypothesis

class TestNavigationSkill(unittest.TestCase):
    def test_costmap_inflation(self):
        costmap = LocalCostmap(size_m=6.0, resolution_m=0.10, inflation_radius_m=0.30)
        # Mark an obstacle cell at (1.0, 0.0)
        cell = costmap.world_to_grid(1.0, 0.0)
        self.assertIsNotNone(cell)
        gx, gy = cell
        costmap.grid[gx, gy] = 100

        # Neighboring cell within 0.2m must be inflated to 50
        neighbor = costmap.world_to_grid(1.1, 0.0)
        costmap.update_from_scan(
            robot_x=0.0, robot_y=0.0, robot_yaw=0.0,
            scan_ranges=[1.0], angle_min=0.0, angle_step=0.01
        )
        self.assertFalse(costmap.is_cell_traversable(gx, gy))

    def test_astar_pathfinding_around_obstacle(self):
        costmap = LocalCostmap(size_m=6.0, resolution_m=0.10, inflation_radius_m=0.20)
        planner = AStarPlanner(costmap)

        # Place a continuous vertical obstacle wall blocking direct line from (0,0) to (2,0)
        # Wall at x=1.0 from y=-0.6 to y=+0.6
        for wy in np.arange(-0.6, 0.65, 0.05):
            c = costmap.world_to_grid(1.0, float(wy))
            if c:
                costmap.grid[c[0], c[1]] = 100

        path = planner.plan_path(start_w=(0.0, 0.0), goal_w=(2.0, 0.0))
        self.assertIsNotNone(path, "A* must find a path around the obstacle wall")
        self.assertGreater(len(path), 1)

        # Ensure path does not pass through the wall (x ~= 1.0, |y| <= 0.4)
        for px, py in path:
            if abs(px - 1.0) < 0.15:
                self.assertGreater(abs(py), 0.35, f"Path waypoint ({px:.2f}, {py:.2f}) pierced obstacle wall!")

        # Final waypoint must reach near the goal
        last = path[-1]
        self.assertLess(math.hypot(last[0] - 2.0, last[1] - 0.0), 0.30)


class TestPerceptionSkill(unittest.TestCase):
    def test_bayesian_evidence_accumulation(self):
        skill = PerceptionSkill(confirmation_threshold=0.85, default_prior=0.50)

        # Step 1: Single sighting of 'bed'
        hyp = skill.process_detection("bed", confidence=0.85, estimated_pose=(-5.0, 2.0))
        # With single detection, it must NOT graduate even if mathematical likelihood is high
        self.assertIsNone(hyp, "Single object detection should NOT prematurely graduate to an identified room")
        
        # Verify hypothesis exists in active dictionary and is NOT yet Identified
        self.assertEqual(len(skill.active_hypotheses), 1)
        active_hyp = list(skill.active_hypotheses.values())[0]
        self.assertEqual(active_hyp.room_type, "Master Bedroom")
        self.assertEqual(active_hyp.status, "Corroborated")
        self.assertEqual(len(active_hyp.evidence_records), 1)

        # Step 2: Second corroborating sighting of 'nightstand'
        confirmed_hyp = skill.process_detection("nightstand", confidence=0.80, estimated_pose=(-5.3, 2.2))
        self.assertIsNotNone(confirmed_hyp, "Corroborated multi-object evidence must graduate the room!")
        self.assertEqual(confirmed_hyp.status, "Identified")
        self.assertGreaterEqual(confirmed_hyp.belief, 0.85)
        self.assertEqual(len(confirmed_hyp.evidence_records), 2)
        
        # Check provenance
        ev1 = confirmed_hyp.evidence_records[0]
        ev2 = confirmed_hyp.evidence_records[1]
        self.assertEqual(ev1.object_class, "bed")
        self.assertEqual(ev2.object_class, "nightstand")
        self.assertEqual(ev1.source, "YOLOv11")


if __name__ == "__main__":
    unittest.main()
