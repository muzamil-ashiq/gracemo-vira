import json
import time
from typing import Any, Callable, Dict, Generator, Optional, List, Tuple
import uuid
import requests


class AdapterClient:
    """Standardized Python client for GRaCEmo Kernel adapters."""

    def __init__(self, adapter_name: str, base_url: str = "http://127.0.0.1:7780"):
        self.adapter_name = adapter_name
        self.base_url = base_url.rstrip("/")

    def emit(self, event_type: str, data: Dict[str, Any], source: str = "RobotBridge") -> bool:
        """Emit a structured event to the Kernel EventBus."""
        payload = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "source": source,
            "observed_by": self.adapter_name,
            "event_type": {
                "type": event_type,
                "data": data,
            },
            "parent_event_id": None,
        }

        try:
            resp = requests.post(f"{self.base_url}/emit", json=payload, timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def get_snapshot(self) -> Optional[Dict[str, Any]]:
        """Fetch current live state snapshot from Kernel (InspectorState)."""
        try:
            resp = requests.get(f"{self.base_url}/snapshot", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_context(self, history_limit: int = 10) -> Optional[Dict[str, Any]]:
        """Fetch compiled contextual truth (NOW + PAST + RELATIONS) from Kernel Context Compiler."""
        try:
            resp = requests.get(f"{self.base_url}/context?limit={history_limit}", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_graph(self) -> Optional[Dict[str, Any]]:
        """Fetch full Knowledge Graph from Kernel."""
        try:
            resp = requests.get(f"{self.base_url}/graph", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_graph_nodes(self) -> List[Dict[str, Any]]:
        """Fetch list of all nodes in Knowledge Graph."""
        graph = self.get_graph()
        if graph and "nodes" in graph:
            return graph["nodes"]
        return []

    def get_world_objects(
        self,
        visible_only: bool = False,
        class_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries all persistent world objects from Kernel /world/objects."""
        params: Dict[str, Any] = {}
        if visible_only:
            params["visible_only"] = "true"
        if class_name:
            params["class"] = class_name
        try:
            resp = requests.get(f"{self.base_url}/world/objects", params=params, timeout=2.0)
            if resp.status_code == 200:
                return resp.json().get("objects", [])
        except Exception:
            pass
        return []

    def get_objects_by_class(
        self,
        class_name: str,
        visible_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Queries persistent world objects by class name."""
        return self.get_world_objects(visible_only=visible_only, class_name=class_name)

    def get_nearest_object(
        self,
        class_name: str,
        from_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        visible_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Queries nearest world object of given class to specified coordinates."""
        params = {
            "class": class_name,
            "nearest_x": from_pos[0],
            "nearest_y": from_pos[1],
            "nearest_z": from_pos[2],
            "visible_only": "true" if visible_only else "false",
        }
        try:
            resp = requests.get(f"{self.base_url}/world/objects", params=params, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found"):
                    return data.get("object")
        except Exception:
            pass
        return None

    def get_visible_objects(self) -> List[Dict[str, Any]]:
        """Queries all currently visible world objects."""
        return self.get_world_objects(visible_only=True)

    def get_world_object_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Queries a specific world object by its deterministic identifier."""
        try:
            resp = requests.get(f"{self.kernel_url if hasattr(self, 'kernel_url') else self.base_url}/world/objects", params={"id": object_id}, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found"):
                    return data.get("object")
        except Exception:
            pass
        return None

    def get_rooms(self) -> List[Dict[str, Any]]:
        """Queries all seeded room nodes from the Kernel."""
        try:
            resp = requests.get(f"{self.base_url}/world/rooms", timeout=2.0)
            if resp.status_code == 200:
                return resp.json().get("rooms", [])
        except Exception:
            pass
        return []

    def get_room_objects(self, room: str) -> List[Dict[str, Any]]:
        """Queries all persistent world objects located in a designated room."""
        try:
            resp = requests.get(f"{self.base_url}/world/rooms/{room}/objects", timeout=2.0)
            if resp.status_code == 200:
                return resp.json().get("objects", [])
        except Exception:
            pass
        return []

    def get_room(self, room: str) -> Optional[Dict[str, Any]]:
        """Queries authoritative room details, exploration state, and object counts."""
        try:
            resp = requests.get(f"{self.base_url}/world/rooms/{room}", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_exploration_status(self) -> Dict[str, Any]:
        """Queries overall apartment exploration status from the Kernel."""
        try:
            resp = requests.get(f"{self.base_url}/world/exploration/status", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {
            "total_rooms": 0,
            "explored_rooms": 0,
            "unexplored_rooms": 0,
            "all_explored": False,
            "total_objects_grounded": 0,
            "rooms": [],
        }

    def listen_actions(self) -> Generator[Dict[str, Any], None, None]:
        """Listen to live SSE stream for ActionRequested events."""
        import sseclient

        url = f"{self.base_url}/events/live"
        try:
            response = requests.get(url, stream=True, timeout=None)
            client = sseclient.SSEClient(response)
            for msg in client.events():
                if not msg.data:
                    continue
                try:
                    event = json.loads(msg.data)
                    event_type = event.get("event_type", {})
                    if event_type.get("type") == "ActionRequested":
                        yield event_type.get("data", {})
                except Exception:
                    continue
        except Exception:
            pass
