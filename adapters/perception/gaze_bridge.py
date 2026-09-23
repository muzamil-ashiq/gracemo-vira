"""
GRaCEmo ViRa — Perception to Gaze Bridge
Consumes 3D world coordinates from Detection objects and routes them to the
EXISTING Phase 3 LookAt subsystem.

CRITICAL INVARIANTS:
1. Does NOT directly publish neck commands.
2. Does NOT calculate neck pan/tilt in the perception layer.
3. Exclusively uses the existing LookAt tool / ActionRequested pipeline.
"""

import logging
from typing import Optional, Dict, Any

from .models import Detection, Point3D

logger = logging.getLogger("perception.gaze_bridge")


class GazeBridge:
    """
    Exposes 3D world positions of detected objects to the existing LookAt capability.
    """

    def __init__(self, kernel_url: str = "http://127.0.0.1:7780"):
        self.kernel_url = kernel_url
        self.registry = None
        self._init_registry()

    def _init_registry(self):
        """Attempts to load existing ToolRegistry from adapters.gemini_robotics.tools."""
        try:
            from adapters.gemini_robotics.tools import ToolRegistry
            self.registry = ToolRegistry(kernel_url=self.kernel_url, use_direct_skills=False)
            logger.info("✓ GazeBridge connected to existing ToolRegistry.")
        except Exception as e:
            logger.warning(f"Could not initialize ToolRegistry in GazeBridge ({e}). Will use direct Kernel ActionRequested emission.")
            self.registry = None

    def look_at_detection(self, detection: Detection) -> Dict[str, Any]:
        """
        Directs gaze to the world position of the detected object.
        Pipes (world_x, world_y, world_z) to the existing LookAt pipeline.
        """
        pos = detection.position_world
        return self.look_at_world_point(pos.x, pos.y, pos.z, target_name=detection.class_name)

    def look_at_world_point(self, x: float, y: float, z: float, target_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Consumes 3D world coordinates and dispatches to the existing LookAt subsystem.
        """
        target_label = target_name or f"Point({x:.2f}, {y:.2f}, {z:.2f})"
        logger.info(f"👀 [GAZE] Directing existing LookAt to target '{target_label}' at world ({x:.2f}, {y:.2f}, {z:.2f})")

        # Route 1: via existing ToolRegistry
        if self.registry is not None:
            tool_res = self.registry.execute("look_at", {"x": float(x), "y": float(y), "z": float(z)})
            return {
                "success": tool_res.success,
                "message": tool_res.message,
                "data": tool_res.data,
                "target": {"x": x, "y": y, "z": z, "name": target_name},
            }

        # Route 2: Canonical ActionRequested emission directly to Rust Kernel /emit
        import uuid
        import time
        import requests

        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "source": "Vision",
            "observed_by": "gaze_bridge",
            "event_type": {
                "type": "ActionRequested",
                "data": {
                    "action": "LookAt",
                    "params": {
                        "x": float(x),
                        "y": float(y),
                        "z": float(z),
                    },
                },
            },
            "parent_event_id": None,
        }

        try:
            resp = requests.post(f"{self.kernel_url}/emit", json=envelope, timeout=2.0)
            return {
                "success": resp.status_code == 200,
                "message": f"Emitted ActionRequested::LookAt to Kernel ({resp.status_code})",
                "target": {"x": x, "y": y, "z": z, "name": target_name},
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to dispatch LookAt: {e}",
                "target": {"x": x, "y": y, "z": z, "name": target_name},
            }
