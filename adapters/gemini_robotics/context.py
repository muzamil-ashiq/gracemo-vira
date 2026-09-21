"""
GRaCEmo ViRa — MNSE Context Provider for Gemini Robotics ER 2
Retrieves authoritative, real-time world awareness (NOW + PAST + RELATIONS) from the MNSE Kernel.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add SDK path if not present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sdk_path = ROOT_DIR / "adapters" / "sdk"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

import requests
from gracemo_sdk import AdapterClient

log = logging.getLogger("gemini_robotics.context")


class MNSEContextProvider:
    """
    Authoritative Context Bridge between MNSE Kernel and Gemini Robotics ER 2.
    Ensures Gemini remains an embodied reasoner grounded in physical reality
    rather than guessing robot or world state.
    """

    def __init__(self, kernel_url: str = "http://127.0.0.1:7780", timeout_sec: float = 2.0):
        self.kernel_url = kernel_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.client = AdapterClient(adapter_name="gemini_robotics_er", base_url=self.kernel_url)

    def is_kernel_available(self) -> bool:
        """Pings Kernel /health to check availability."""
        try:
            resp = requests.get(f"{self.kernel_url}/health", timeout=self.timeout_sec)
            return resp.status_code == 200
        except Exception:
            return False

    def get_robot_context(self) -> Dict[str, Any]:
        """
        Retrieves the authoritative 'NOW' InspectorState snapshot:
        - Current room
        - Real-time robot coordinates (x, y, theta, speed)
        - Battery level & charging state
        - Last vision detection
        - Last voice command
        """
        snapshot = self.client.get_snapshot()
        if snapshot:
            return snapshot
        return {
            "status": "offline",
            "current_room": "Unknown",
            "robot_position": None,
            "battery": None,
            "last_vision_detection": None,
            "last_voice_command": None,
        }

    def get_world_context(self, history_limit: int = 10) -> Dict[str, Any]:
        """
        Retrieves compiled contextual truth (NOW + PAST + RELATIONS)
        from the Kernel Context Compiler.
        """
        context = self.client.get_context(history_limit=history_limit)
        if context:
            return context
        return {
            "now": self.get_robot_context(),
            "recent_history": [],
            "graph": {"nodes": [], "edges": []},
        }

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves recent chronological events from the SQLite WAL Event Ledger (PAST).
        """
        try:
            resp = requests.get(f"{self.kernel_url}/history?limit={limit}", timeout=self.timeout_sec)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log.debug(f"Failed to fetch ledger history: {e}")
        return []

    def get_graph_context(self) -> Dict[str, Any]:
        """
        Retrieves the relational Knowledge Graph (RELATIONS):
        - Spatial topology (rooms, doorway portals)
        - Grounded object locations (LOCATED_IN edges)
        """
        graph = self.client.get_graph()
        if graph:
            return graph
        return {"nodes": [], "edges": []}

    def query_object_location(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        Directly queries the MNSE Knowledge Graph for an object's location.
        """
        try:
            resp = requests.get(
                f"{self.kernel_url}/graph",
                params={"object": object_name},
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found"):
                    return data.get("result")
        except Exception as e:
            log.debug(f"Graph query failed for '{object_name}': {e}")
        return None

    def get_compiled_context(self, fmt: str = "toon", limit: int = 10) -> str:
        """
        Retrieves context formatted specifically for LLM prompt ingestion.
        Supports 'toon' (Token-Optimized Object Notation) which reduces token usage by 70-80%.
        """
        try:
            resp = requests.get(
                f"{self.kernel_url}/context",
                params={"format": fmt, "limit": limit},
                timeout=self.timeout_sec,
            )
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            log.debug(f"Failed to fetch compiled context ({fmt}): {e}")

        # Fallback to local TOON-like synthesis if kernel format endpoint is unreachable
        now = self.get_robot_context()
        room = now.get("current_room", "Unknown")
        pos = now.get("robot_position") or {}
        x = pos.get("x", 0.0)
        y = pos.get("y", 0.0)
        theta = pos.get("theta", 0.0)
        import math
        return f"@NOW:Room[{room}]|Pose[x:{x:.2f},y:{y:.2f},yaw:{math.degrees(theta):.0f}°]"

    def build_grounded_prompt(self, user_command: str) -> str:
        """
        Wraps user command in authoritative MNSE sensory context.
        Ensures Gemini ER 2 reasons from verified facts.
        """
        toon = self.get_compiled_context(fmt="toon")
        return (
            f"=== AUTHORITATIVE MNSE GROUNDED REALITY ===\n"
            f"{toon}\n"
            f"===========================================\n\n"
            f"User Command: \"{user_command}\"\n\n"
            f"Select the appropriate high-level robot tool to address the user's command."
        )

    def get_latest_camera_frame(self, frame_path: str = "/tmp/gracemo_camera_latest.jpg") -> Optional[bytes]:
        """
        Retrieves the latest live camera observation frame captured by the robot bridge.
        """
        p = Path(frame_path)
        if p.exists():
            try:
                return p.read_bytes()
            except Exception as e:
                log.debug(f"Could not read latest camera frame from {frame_path}: {e}")
        return None

