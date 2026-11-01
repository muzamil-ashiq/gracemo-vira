"""
Configuration and Settings Manager for GRaCEmo ViRa UARCC.
Handles authoritative destination resolution from config/destinations.json
without code duplication.
"""

import os
import json
from typing import Dict, Any, Optional

# Default Paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
PROTOTYPE_ROOT = "/home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1"

# Primary Destinations File Locations (Checked in order)
DESTINATION_CANDIDATE_PATHS = [
    os.path.join(PROTOTYPE_ROOT, "config", "destinations.json"),
    os.path.join(PROJECT_ROOT, "config", "destinations.json"),
    os.path.join(PROJECT_ROOT, "vira_interaction", "config", "places.json"),
]

# Telemetry Refresh Rates (Hz / ms)
DEFAULT_UI_UPDATE_RATE_MS = 50       # 20 Hz UI refresh loop
DEFAULT_SYSTEM_MONITOR_RATE_MS = 1000 # 1 Hz host CPU/GPU/RAM
DEFAULT_DIAGNOSTICS_RATE_MS = 1000   # 1 Hz ROS node / topic probe
DEFAULT_CAMERA_FPS_LIMIT = 30        # Bounded image display rate
DEFAULT_LIDAR_MAX_POINTS = 720       # 360 degree scan points
STALE_DATA_TIMEOUT_SEC = 2.0         # Seconds before topic is deemed stale


class Settings:
    """Manages application runtime settings and authoritative destination registry."""

    def __init__(self):
        self.destinations_file = self._find_destinations_file()
        self.destinations: Dict[str, Dict[str, Any]] = self.load_destinations()
        self.ui_update_rate_ms = DEFAULT_UI_UPDATE_RATE_MS
        self.system_monitor_rate_ms = DEFAULT_SYSTEM_MONITOR_RATE_MS
        self.stale_timeout_sec = STALE_DATA_TIMEOUT_SEC
        self.camera_rgb_enabled = True
        self.camera_depth_enabled = True
        self.lidar_enabled = True
        self.point_size_lidar = 3
        self.theme = "dark"

    def _find_destinations_file(self) -> str:
        for path in DESTINATION_CANDIDATE_PATHS:
            if os.path.isfile(path):
                return path
        return DESTINATION_CANDIDATE_PATHS[0]

    def load_destinations(self) -> Dict[str, Dict[str, Any]]:
        """Load destinations from authoritative JSON file."""
        if not os.path.isfile(self.destinations_file):
            return self._fallback_destinations()
        try:
            with open(self.destinations_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "destinations" in data:
                    return data["destinations"]
                return data
        except Exception as e:
            print(f"[Settings] Error loading destinations from {self.destinations_file}: {e}")
            return self._fallback_destinations()

    def _fallback_destinations(self) -> Dict[str, Dict[str, Any]]:
        """Exact canonical fallback matching the accepted baseline."""
        return {
            "hallway": {
                "name": "Central Hallway",
                "x": 0.0,
                "y": 0.0,
                "yaw": 0.0,
                "frame_id": "map"
            },
            "living_room": {
                "name": "Living Room",
                "x": 4.0,
                "y": -2.5,
                "yaw": -1.57,
                "frame_id": "map"
            },
            "kitchen": {
                "name": "Kitchen & Dining",
                "x": -5.0,
                "y": -2.5,
                "yaw": -1.57,
                "frame_id": "map"
            },
            "bedroom": {
                "name": "Master Bedroom",
                "x": -5.0,
                "y": 2.2,
                "yaw": 1.57,
                "frame_id": "map"
            },
            "study": {
                "name": "Home Study",
                "x": 4.5,
                "y": 3.0,
                "yaw": 1.57,
                "frame_id": "map"
            },
            "lab": {
                "name": "Robotics Research Lab",
                "x": 2.5,
                "y": 2.0,
                "yaw": 0.0,
                "frame_id": "map"
            }
        }
