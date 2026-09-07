#!/usr/bin/env python3
"""
GRaCEmo ViRa — Level 4 Cognitive Agent (Mind & Intention)
Translates high-level human intentions into typed K pipelines.

Hierarchy:
  Level 4 Cognitive Agent (Intent / Decomposition)
       ↓
     K DSL (Operational Interface)
       ↓
  Level 3 MNSE (Context & Spatial Graph) + Level 2 Skills (Navigation & Vision)
       ↓
  Level 1.5 Whole-Body Coordinator
       ↓
  Level 1 Spinal Reflex (APF Shield & Velocity Control)
       ↓
     Body (Gazebo Wheels & Sensors)
"""

import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "adapters" / "sdk"))
sys.path.insert(0, str(ROOT / "adapters" / "brain" / "gracemo_brain" / "skills"))

from gracemo_sdk import KClient
from navigation_skill import NavigationSkill


class CognitiveAgent:
    """
    Level 4 Cognitive Agent.
    Owns reasoning, intention, and task decomposition.
    Produces typed K pipelines for downstream substrates.
    """

    def __init__(self, kernel_url: str = "http://127.0.0.1:7780"):
        self.k_client = KClient(kernel_url)
        self.nav_skill = NavigationSkill()

    @staticmethod
    def _canonical_name(target: str) -> str:
        cleaned = re.sub(r"^(?:the|a|an)\s+", "", target.strip().lower())
        if "bed" in cleaned:
            return "Master Bedroom"
        elif "kitchen" in cleaned or "dining" in cleaned:
            return "Kitchen & Dining"
        elif "study" in cleaned or "office" in cleaned:
            return "Home Study"
        elif "living" in cleaned or "lounge" in cleaned:
            return "Living Room"
        elif "hall" in cleaned:
            return "Central Hallway"
        return cleaned.title()

    def reason_and_plan(self, user_intent: str) -> str:
        """
        Decomposes natural language human intent into a valid typed K pipeline.
        Works deterministically for standard directives, and can be driven by LLMs.
        """
        cleaned = user_intent.lower().strip()

        # Directive 1: "Go to <destination>" / "Navigate to <destination>"
        match_goto = re.search(r"(?:go to|navigate to|head to|reach)\s+([a-zA-Z0-9\s]+)", cleaned)
        if match_goto:
            canonical = self._canonical_name(match_goto.group(1))
            return f"graph::locate[entity: \"{canonical}\"] | nav::reach"

        # Directive 2: "Inspect <room>" / "Scan <room>"
        match_inspect = re.search(r"(?:inspect|survey|check|scan)\s+([a-zA-Z0-9\s]+)", cleaned)
        if match_inspect:
            canonical = self._canonical_name(match_inspect.group(1))
            return f"graph::locate[entity: \"{canonical}\"] | nav::reach | vision::scan"

        # Directive 3: "Find <object>" / "Locate <object>"
        match_find = re.search(r"(?:find|locate|search for|get)\s+([a-zA-Z0-9\s]+)", cleaned)
        if match_find:
            obj = re.sub(r"^(?:the|a|an)\s+", "", match_find.group(1).strip())
            return f"graph::locate[entity: \"{obj}\"] | nav::reach"

        # Default fallback
        return f"graph::locate[entity: \"{cleaned}\"] | nav::reach"

    def execute_intent(self, user_intent: str) -> Dict[str, Any]:
        """
        Full end-to-end execution:
          1. Reads compiled reality context from MNSE (TOON).
          2. Generates K pipeline.
          3. Dispatches pipeline via K Engine.
          4. Executes physical movement through Navigation Skill + Base Controller.
        """
        print(f"\n🧠 [AGENT] Processing Intent: \"{user_intent}\"")

        # 1. Fetch current compiled reality from MNSE
        toon_context = self.k_client.get_compiled_context(fmt="toon")
        print(f"📋 [AGENT] Grounded Reality Context (VCSC TOON):\n{toon_context}\n")

        # 2. Decompose into K pipeline
        k_pipeline = self.reason_and_plan(user_intent)
        print(f"⚡ [AGENT] Synthesized K Pipeline: {k_pipeline}")

        # 3. Dispatch to K Engine for validation & planning
        k_result = self.k_client.execute(k_pipeline)
        print(f"✓ [K ENGINE] Result: {json.dumps(k_result)}")

        # 4. Extract target and execute physical navigation skill if present
        if "nav::reach" in k_pipeline:
            # Extract target from pipeline
            m = re.search(r'entity:\s*"([^"]+)"', k_pipeline)
            if m:
                target_entity = m.group(1)
                print(f"🚀 [AGENT] Executing Embodied Navigation Skill for target '{target_entity}'...")
                nav_success = self.nav_skill.navigate_to_semantic_target(target_entity)
                return {
                    "success": nav_success,
                    "pipeline": k_pipeline,
                    "k_result": k_result,
                    "navigation": nav_success
                }

        return {
            "success": True,
            "pipeline": k_pipeline,
            "k_result": k_result
        }


def main():
    intent = sys.argv[1] if len(sys.argv) > 1 else "Go to the bedroom"
    agent = CognitiveAgent()
    res = agent.execute_intent(intent)
    print("\n🏁 [AGENT MISSION RESULT]:", res)


if __name__ == "__main__":
    main()
