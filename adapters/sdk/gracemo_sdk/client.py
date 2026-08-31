import json
import time
from typing import Any, Callable, Dict, Generator, Optional
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
        """Fetch current live state snapshot from Kernel."""
        try:
            resp = requests.get(f"{self.base_url}/snapshot", timeout=2.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

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
