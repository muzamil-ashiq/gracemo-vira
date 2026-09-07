#!/usr/bin/env python3
"""
GRaCEmo ViRa — Level 2 Embodied Perception & Bayesian Grounding Skill
Transforms transient neural visual detections into grounded, evidential spatial knowledge.

Responsibilities:
  1. Receives bounding box detections and projects optical rays to metric 3D ground coordinates.
  2. Implements Bayesian Room Grounding:
     - Maintains active RoomHypothesis instances with configurable priors and thresholds.
     - Formulates posterior beliefs using Bayes' Rule over multi-object evidence.
     - Maintains full evidence provenance records (object, confidence, weight, timestamp, source).
  3. Emits RoomIdentified and ObjectGrounding events to the Level 3 MNSE Substrate (graph.db).
"""

import sys
import os
import time
import math
import uuid
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

ROOT = Path(__file__).resolve()
while ROOT.name != "gracemo-vira" and ROOT.parent != ROOT:
    ROOT = ROOT.parent

for sub in ["sdk", "motion", "brain/gracemo_brain/skills"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from gracemo_sdk import AdapterClient

# Likelihood ratios P(Object | Room) vs P(Object | ~Room)
OBJECT_ROOM_LIKELIHOODS = {
    "bed":         {"room": "Master Bedroom",  "p_in": 0.92, "p_out": 0.02, "weight": 0.40},
    "nightstand":  {"room": "Master Bedroom",  "p_in": 0.78, "p_out": 0.05, "weight": 0.25},
    "wardrobe":    {"room": "Master Bedroom",  "p_in": 0.80, "p_out": 0.08, "weight": 0.25},
    
    "refrigerator":{"room": "Kitchen & Dining","p_in": 0.94, "p_out": 0.01, "weight": 0.45},
    "sink":        {"room": "Kitchen & Dining","p_in": 0.75, "p_out": 0.12, "weight": 0.20},
    "dining table":{"room": "Kitchen & Dining","p_in": 0.82, "p_out": 0.08, "weight": 0.30},

    "couch":       {"room": "Living Room",     "p_in": 0.88, "p_out": 0.04, "weight": 0.40},
    "sofa":        {"room": "Living Room",     "p_in": 0.88, "p_out": 0.04, "weight": 0.40},
    "tv":          {"room": "Living Room",     "p_in": 0.75, "p_out": 0.10, "weight": 0.25},

    "desk":        {"room": "Home Study",      "p_in": 0.85, "p_out": 0.10, "weight": 0.35},
    "chair":       {"room": "Home Study",      "p_in": 0.60, "p_out": 0.30, "weight": 0.15},
    "book":        {"room": "Home Study",      "p_in": 0.70, "p_out": 0.15, "weight": 0.20},
}


class EvidenceRecord:
    def __init__(self, object_class: str, confidence: float, weight: float, source: str = "YOLOv11", location: Optional[Tuple[float, float]] = None):
        self.evidence_id = str(uuid.uuid4())
        self.object_class = object_class
        self.confidence = confidence
        self.weight = weight
        self.source = source
        self.timestamp = int(time.time())
        self.location = location

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "object_class": self.object_class,
            "confidence": self.confidence,
            "weight": self.weight,
            "source": self.source,
            "timestamp": self.timestamp,
            "location": self.location
        }


class RoomHypothesis:
    def __init__(self, hypothesis_id: str, room_type: str, initial_prior: float = 0.50, anchor_location: Tuple[float, float] = (0.0, 0.0)):
        self.hypothesis_id = hypothesis_id
        self.room_type = room_type
        self.belief = initial_prior
        self.anchor_location = anchor_location
        self.evidence_records: List[EvidenceRecord] = []
        self.status = "Hypothesized"  # Hypothesized -> Corroborated -> Identified
        self.created_at = int(time.time())

    def update_belief(self, evidence: EvidenceRecord, p_in: float, p_out: float) -> float:
        """
        Bayesian belief update:
          P(Room | E) = [P(E | Room) * P(Room)] / [P(E | Room)*P(Room) + P(E | ~Room)*P(~Room)]
        Modulated by detection confidence.
        """
        self.evidence_records.append(evidence)

        # Scale likelihood by detection confidence
        eff_p_in = 0.5 + (p_in - 0.5) * evidence.confidence
        eff_p_out = 0.5 + (p_out - 0.5) * evidence.confidence

        numerator = eff_p_in * self.belief
        denominator = (eff_p_in * self.belief) + (eff_p_out * (1.0 - self.belief))

        if denominator > 0:
            self.belief = float(np.clip(numerator / denominator, 0.01, 0.99))

        if self.belief >= 0.70 and self.status == "Hypothesized":
            self.status = "Corroborated"

        return self.belief


class PerceptionSkill:
    """
    Level 2 Perception & Bayesian Evidence Skill.
    Grounds visual objects and manages room identification lifecycle.
    """

    def __init__(self, confirmation_threshold: float = 0.85, default_prior: float = 0.50, min_corroborating_objects: int = 2):
        self.confirmation_threshold = confirmation_threshold
        self.default_prior = default_prior
        self.min_corroborating_objects = min_corroborating_objects
        self.active_hypotheses: Dict[str, RoomHypothesis] = {}
        self.client = AdapterClient(adapter_name="PerceptionSkill", base_url="http://127.0.0.1:7780")

    def process_detection(self, object_class: str, confidence: float, estimated_pose: Tuple[float, float]) -> Optional[RoomHypothesis]:
        """
        Processes a single visual object detection through Bayesian evidence accumulation.
        Returns the confirmed RoomHypothesis if threshold is crossed AND min corroborating objects met, else None.
        """
        model = OBJECT_ROOM_LIKELIHOODS.get(object_class.lower())
        if not model or confidence < 0.40:
            return None

        target_room = model["room"]
        evidence = EvidenceRecord(
            object_class=object_class,
            confidence=confidence,
            weight=model["weight"],
            source="YOLOv11",
            location=estimated_pose
        )

        # Look for existing hypothesis of the same room type nearby
        hyp: Optional[RoomHypothesis] = None
        for h in self.active_hypotheses.values():
            if h.room_type == target_room and math.hypot(h.anchor_location[0] - estimated_pose[0], h.anchor_location[1] - estimated_pose[1]) < 4.0:
                hyp = h
                break

        if not hyp:
            hyp_id = str(uuid.uuid4())
            hyp = RoomHypothesis(
                hypothesis_id=hyp_id,
                room_type=target_room,
                initial_prior=self.default_prior,
                anchor_location=estimated_pose
            )
            self.active_hypotheses[hyp_id] = hyp
            print(f"[PERCEPTION SKILL] Formed new RoomHypothesis for '{target_room}' at ({estimated_pose[0]:.2f}, {estimated_pose[1]:.2f}). Prior: {self.default_prior:.2f}")

        # Bayesian update
        updated_belief = hyp.update_belief(evidence, p_in=model["p_in"], p_out=model["p_out"])
        print(f"[PERCEPTION SKILL] Evidence added: '{object_class}' (conf={confidence:.2f}) -> {target_room} Belief: {updated_belief:.3f} [{hyp.status}] (Evidence count: {len(hyp.evidence_records)})")

        # Check for graduation to confirmed room (requires both confidence threshold AND multi-object corroboration)
        if updated_belief >= self.confirmation_threshold and len(hyp.evidence_records) >= self.min_corroborating_objects and hyp.status != "Identified":
            hyp.status = "Identified"
            print(f"🎉 [PERCEPTION SKILL] CONFIRMED ROOM GRADUATION! '{target_room}' identified with belief {updated_belief:.3f} >= {self.confirmation_threshold:.2f} across {len(hyp.evidence_records)} corroborating objects!")
            self._sync_room_to_mnse_graph(hyp)
            return hyp

        return None

    def _sync_room_to_mnse_graph(self, hyp: RoomHypothesis):
        """Synchronizes confirmed room entity to Level 3 MNSE Knowledge Graph (graph.db)."""
        properties = {
            "center_x": hyp.anchor_location[0],
            "center_y": hyp.anchor_location[1],
            "confidence": round(hyp.belief, 3),
            "evidence_count": len(hyp.evidence_records),
            "evidence_provenance": [e.to_dict() for e in hyp.evidence_records]
        }
        try:
            self.client.emit(
                "RoomIdentified",
                {
                    "room_type": hyp.room_type,
                    "hypothesis_id": hyp.hypothesis_id,
                    "belief": hyp.belief,
                    "properties": properties
                },
                source="PerceptionSkill"
            )
            print(f"[PERCEPTION SKILL] Dispatched 'RoomIdentified' event with full provenance to MNSE Kernel.")
        except Exception as e:
            print(f"[PERCEPTION SKILL] Failed to sync to MNSE Kernel: {e}")


if __name__ == "__main__":
    skill = PerceptionSkill(confirmation_threshold=0.85)
    print("Simulating visual sighting 1: bed...")
    skill.process_detection("bed", 0.88, (-5.0, 2.0))
    print("\nSimulating visual sighting 2: nightstand...")
    confirmed = skill.process_detection("nightstand", 0.75, (-5.5, 2.2))
    print(f"Final confirmation: {confirmed is not None}")
