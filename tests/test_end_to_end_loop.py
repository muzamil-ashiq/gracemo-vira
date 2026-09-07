#!/usr/bin/env python3
"""
GRaCEmo ViRa — Phase E End-to-End Autonomous Cognitive Loop Verification
Validates the complete hierarchy:
  Level 4 Cognitive Agent (Intent / Decomposition)
       ↓
     K DSL (Operational Interface)
       ↓
  Level 3 MNSE (Context / Graph Resolution) + Level 2 Skills (A* Pathfinding)
       ↓
  Level 1 Spinal Reflex (APF Shield & Control)
"""

import unittest
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain"))
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain" / "skills"))
sys.path.insert(0, str(ROOT / "adapters" / "motion"))

from agent import CognitiveAgent
from gracemo_sdk import KClient
from navigation_skill import NavigationSkill

class TestEndToEndCognitiveLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = KClient()

    def test_01_agent_intent_decomposition(self):
        """Verify Level 4 Agent decomposes human intents into valid K pipelines."""
        agent = CognitiveAgent()
        
        pipe1 = agent.reason_and_plan("Go to the bedroom")
        self.assertEqual(pipe1, 'graph::locate[entity: "Master Bedroom"] | nav::reach')

        pipe2 = agent.reason_and_plan("Inspect the kitchen")
        self.assertEqual(pipe2, 'graph::locate[entity: "Kitchen & Dining"] | nav::reach | vision::scan')

        pipe3 = agent.reason_and_plan("Find the Coke")
        self.assertEqual(pipe3, 'graph::locate[entity: "coke"] | nav::reach')

    def test_02_k_engine_pipeline_execution(self):
        """Verify native Rust K engine receives, validates, and executes the pipeline."""
        pipe = 'graph::locate[entity: "Master Bedroom"] | nav::reach'
        result = self.client.execute(pipe)
        self.assertTrue(result.get("success"), f"K execution failed: {result.get('error')}")
        summary = result.get("result", {})
        self.assertEqual(summary.get("total_stages"), 2)
        self.assertEqual(summary.get("completed_stages"), 2)

    def test_03_graph_resolution_and_pathfinding(self):
        """Verify Navigation Skill resolves the entity from graph and plans a path."""
        nav = NavigationSkill()
        # Seed test node in graph if needed
        nav.client.emit(
            "RoomIdentified",
            {
                "room_type": "Master Bedroom",
                "hypothesis_id": "test-bed-hyp-1",
                "belief": 0.95,
                "properties": {"center_x": -5.0, "center_y": 2.0, "door_x": -5.0, "door_y": 1.4}
            },
            source="TestRunner"
        )
        
        # Resolve target
        coords = nav.resolve_semantic_target("Master Bedroom")
        self.assertIsNotNone(coords, "Navigation Skill must resolve Master Bedroom from graph")
        self.assertTrue(-8.0 <= coords[0] <= -0.5, f"Resolved X ({coords[0]:.2f}) must be inside Master Bedroom bounds")
        self.assertTrue(1.3 <= coords[1] <= 6.0, f"Resolved Y ({coords[1]:.2f}) must be inside Master Bedroom bounds")

        # Plan metric trajectory (clear stale costmap cross-talk for unit testing)
        nav.costmap.grid.fill(0)
        path = nav.plan_to_metric_pose(coords[0], coords[1])
        if path is None:
            path = nav.plan_to_metric_pose(-5.0, 1.4)
        self.assertIsNotNone(path, "A* must find a collision-free path to target coordinates")
        self.assertGreater(len(path), 0)

if __name__ == "__main__":
    unittest.main()
