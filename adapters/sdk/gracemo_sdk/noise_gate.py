"""
GRaCEmo ViRa — Sensory Noise Gate Filter
Eliminates high-frequency frame-by-frame sensor noise.
Transforms continuous sensor streams into discrete episodic state transitions.
"""

import time
from typing import Dict, Any, Optional, List, Tuple


class VisionNoiseGate:
    """Filters continuous 30 FPS YOLO detections into discrete discovery events."""

    def __init__(self, confidence_threshold: float = 0.40, cooldown_sec: float = 4.0):
        self.conf_threshold = confidence_threshold
        self.cooldown_sec = cooldown_sec
        # Map: class_name -> last_emitted_timestamp
        self.last_emitted: Dict[str, float] = {}
        # Map: class_name -> last_room
        self.last_room: Dict[str, str] = {}

    def should_emit(self, class_name: str, confidence: float, current_room: str) -> bool:
        """Determines if a detection represents a new or significant observation."""
        if confidence < self.conf_threshold:
            return False

        now = time.time()
        last_time = self.last_emitted.get(class_name, 0.0)
        last_rm = self.last_room.get(class_name, "")

        # Always emit if observed in a new room
        if current_room != last_rm:
            self.last_emitted[class_name] = now
            self.last_room[class_name] = current_room
            return True

        # Throttle duplicate emissions in the same room
        if now - last_time >= self.cooldown_sec:
            self.last_emitted[class_name] = now
            return True

        return False


class OdometryNoiseGate:
    """Filters high-frequency 50Hz odometry ticks into significant movement events."""

    def __init__(self, min_displacement_m: float = 0.25):
        self.min_displacement_m = min_displacement_m
        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None
        self.last_room: str = ""

    def process_pose(self, x: float, y: float, room: str) -> Tuple[bool, bool]:
        """
        Returns (should_emit_position, room_changed).
        """
        room_changed = False
        if room != self.last_room and self.last_room != "":
            room_changed = True
        self.last_room = room

        if self.last_x is None or self.last_y is None:
            self.last_x = x
            self.last_y = y
            return (True, room_changed)

        dx = x - self.last_x
        dy = y - self.last_y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist >= self.min_displacement_m or room_changed:
            self.last_x = x
            self.last_y = y
            return (True, room_changed)

        return (False, False)
