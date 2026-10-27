#!/usr/bin/env python3
"""
GRaCEmo ViRa — Authoritative Campus & Simulation Place Resolver
Resolves natural language location requests to canonical spatial waypoints.
Loads authoritative configuration from places.json.
Guarantees: If a requested location does not exist, NO navigation command is issued.
"""
from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("gracemo.place_resolver")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "places.json"


@dataclass(frozen=True)
class PlaceInfo:
    key: str
    name: str
    x: float
    y: float
    yaw: Optional[float] = None
    tolerance_m: float = 0.30
    safety_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "yaw": self.yaw,
            "tolerance_m": self.tolerance_m,
            "safety_metadata": dict(self.safety_metadata) if self.safety_metadata else {},
        }


class PlaceResolver:
    """
    Authoritative place resolver for GRaCEmo ViRa.
    Provides deterministic resolution from natural language to metric Nav2 coordinates.
    """

    NAV_PATTERNS = [
        re.compile(r"\b(?:take me to|navigate to|go to|head to|walk to|drive to)\s+(?:the\s+)?(.+)", re.IGNORECASE),
        re.compile(r"\b(?:where is|how to get to|guide me to)\s+(?:the\s+)?(.+)", re.IGNORECASE),
    ]

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH
        self._places: Dict[str, PlaceInfo] = {}
        self.reload()

    def reload(self):
        """Loads places from JSON configuration."""
        self._places.clear()
        if not os.path.exists(self.config_path):
            log.warning(f"Places configuration file not found at {self.config_path}")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, val in data.items():
                if key.startswith("_"):
                    continue
                if isinstance(val, dict):
                    coords = val.get("coordinates", [0.0, 0.0])
                    x = float(coords[0])
                    y = float(coords[1])
                    name = str(val.get("name", key))
                    yaw = float(val["orientation"]) if val.get("orientation") is not None else None
                    tol = float(val.get("tolerance", 0.30))
                    meta = val.get("safety_metadata", {})
                    self._places[key.lower().strip()] = PlaceInfo(
                        key=key.lower().strip(),
                        name=name,
                        x=x,
                        y=y,
                        yaw=yaw,
                        tolerance_m=tol,
                        safety_metadata=meta,
                    )
                elif isinstance(val, (list, tuple)) and len(val) >= 3:
                    x = float(val[0])
                    y = float(val[1])
                    name = str(val[2])
                    yaw = float(val[3]) if len(val) >= 4 and val[3] is not None else None
                    tol = float(val[4]) if len(val) >= 5 and val[4] is not None else 0.30
                    meta = val[5] if len(val) >= 6 and isinstance(val[5], dict) else {}
                    self._places[key.lower().strip()] = PlaceInfo(
                        key=key.lower().strip(),
                        name=name,
                        x=x,
                        y=y,
                        yaw=yaw,
                        tolerance_m=tol,
                        safety_metadata=meta,
                    )
            log.info(f"Loaded {len(self._places)} authoritative places from {self.config_path}")
        except Exception as e:
            log.error(f"Failed to parse places config {self.config_path}: {e}")

    @property
    def places(self) -> Dict[str, PlaceInfo]:
        return dict(self._places)

    def list_known_places(self) -> List[str]:
        """Returns unique display names of known places."""
        seen = set()
        names = []
        for p in self._places.values():
            if p.name not in seen:
                seen.add(p.name)
                names.append(p.name)
        return sorted(names)

    def extract_destination_phrase(self, text: str) -> Optional[str]:
        """Extracts the candidate destination string from a navigation utterance."""
        if not text:
            return None
        clean = text.strip()
        for pat in self.NAV_PATTERNS:
            m = pat.search(clean)
            if m:
                # Strip trailing punctuation
                dest = m.group(1).rstrip(".!?,")
                return dest.strip()
        return None

    def resolve_place(self, text: str) -> Optional[PlaceInfo]:
        """
        Finds a matching known place in text using word boundaries.
        Prefers multi-word keys and checks preceding modifiers on single-word keys
        to reject unknown places like 'Moon Lab' while matching 'Robotics Lab' or 'the lab'.
        """
        if not text:
            return None
        clean = text.lower().strip()
        clean = re.sub(r"^(?:the|to|a|an)\s+", "", clean).strip()

        # 1. Exact match against known keys
        if clean in self._places:
            return self._places[clean]

        # 2. Check multi-word keys first (longest descending)
        for key in sorted(self._places.keys(), key=len, reverse=True):
            if " " in key:
                pattern = r"\b" + re.escape(key) + r"\b"
                if re.search(pattern, clean, re.IGNORECASE):
                    return self._places[key]

        # 3. For single-word keys, ensure preceding words aren't conflicting modifiers
        for key in sorted(self._places.keys(), key=len, reverse=True):
            if " " not in key:
                pattern = r"\b" + re.escape(key) + r"\b"
                m = re.search(pattern, clean, re.IGNORECASE)
                if m:
                    # Check words that precede the matched key
                    prefix = clean[:m.start()].strip()
                    if prefix:
                        ignore = {
                            "the", "to", "our", "main", "new", "go", "take", "me",
                            "navigate", "head", "walk", "drive", "guide", "a", "an", "at"
                        }
                        words = [w for w in prefix.split() if w not in ignore]
                        place_name_lower = self._places[key].name.lower()
                        # If any preceding word is NOT in the canonical place name, reject match
                        if any(w not in place_name_lower for w in words):
                            continue
                    return self._places[key]

        return None

    def resolve_navigation_request(self, text: str) -> Tuple[Optional[PlaceInfo], Optional[str]]:
        """
        Processes a potential navigation command.
        Returns:
            (PlaceInfo, None) if a known destination was matched.
            (None, requested_name) if a navigation intent was detected but the destination is unknown.
            (None, None) if no navigation intent was detected.
        """
        dest_phrase = self.extract_destination_phrase(text)
        if dest_phrase:
            place = self.resolve_place(dest_phrase)
            if place:
                return place, None
            else:
                return None, dest_phrase

        # Fallback check across whole text
        place = self.resolve_place(text)
        if place:
            return place, None

        return None, None

    # Alias resolve to resolve_place
    resolve = resolve_place
