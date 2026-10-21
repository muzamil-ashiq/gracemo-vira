#!/usr/bin/env python3
"""
GRaCEmo ViRa — EventBus Client & Canonical Envelope Publisher
Bridges the interaction subsystem to the Rust gracemo-kernel EventBus.
Maintains in-memory pub/sub fallback when Kernel daemon is offline.
"""
from __future__ import annotations
import datetime
import json
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
import requests

log = logging.getLogger("gracemo.event_bus")


class EventBusClient:
    """
    Client for the VIRA EventBus.
    Publishes typed events with trace_id correlation and consumes live SSE streams.
    Falls back to an in-memory bus when Kernel is not reachable.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:7780",
        source_name: str = "Interaction",
        observed_by: str = "graceemo_interaction",
    ):
        self.base_url = base_url.rstrip("/")
        self.source_name = source_name
        self.observed_by = observed_by
        self._sequence = 0
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._all_subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._in_memory_ledger: List[Dict[str, Any]] = []
        self._sse_thread: Optional[threading.Thread] = None
        self._running = True
        self._http_available = True
        self._last_http_failure = 0.0


    def create_envelope(
        self,
        event_type: str,
        data: Dict[str, Any],
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: Optional[str] = None,
        parent_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds a canonical Event envelope matching contracts/event-envelope.schema.json."""
        with self._lock:
            self._sequence += 1
            seq = self._sequence

        now = time.time()
        iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        event_id = str(uuid.uuid4())
        tid = trace_id or str(uuid.uuid4())

        return {
            "id": event_id,
            "trace_id": tid,
            "session_id": session_id or "session_default",
            "timestamp": int(now),
            "timestamp_iso": iso,
            "source": source or self.source_name,
            "observed_by": self.observed_by,
            "sequence": seq,
            "parent_event_id": parent_event_id,
            "event_type": {
                "type": event_type,
                "data": data,
            },
        }

    def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: Optional[str] = None,
        parent_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Emits an event to the Kernel EventBus via POST /emit.
        Also publishes to in-memory listeners and in-memory ledger.
        """
        envelope = self.create_envelope(
            event_type=event_type,
            data=data,
            trace_id=trace_id,
            session_id=session_id,
            source=source,
            parent_event_id=parent_event_id,
        )

        # 1. Record in in-memory ledger & notify local subscribers
        with self._lock:
            self._in_memory_ledger.append(envelope)
            if len(self._in_memory_ledger) > 1000:
                self._in_memory_ledger.pop(0)

        self._dispatch_local(envelope)

        # 2. Transmit to Kernel REST API
        if not self._http_available and (time.time() - self._last_http_failure < 5.0):
            return envelope

        try:
            resp = requests.post(f"{self.base_url}/emit", json=envelope, timeout=0.05)
            if resp.status_code == 200:
                self._http_available = True
                log.debug(f"✓ EventBus HTTP emitted: {event_type} (seq={envelope['sequence']})")
            else:
                log.debug(f"EventBus HTTP returned status {resp.status_code}")
        except Exception:
            self._http_available = False
            self._last_http_failure = time.time()

        return envelope

    def emit_envelope(self, envelope: Dict[str, Any]) -> bool:
        """Emits a pre-constructed canonical envelope to ledger, local subscribers, and Kernel."""
        with self._lock:
            self._in_memory_ledger.append(envelope)
            if len(self._in_memory_ledger) > 1000:
                self._in_memory_ledger.pop(0)

        self._dispatch_local(envelope)

        if not self._http_available and (time.time() - self._last_http_failure < 5.0):
            return False

        try:
            resp = requests.post(f"{self.base_url}/emit", json=envelope, timeout=0.05)
            if resp.status_code == 200:
                self._http_available = True
                return True
            return False
        except Exception:
            self._http_available = False
            self._last_http_failure = time.time()
            return False

    def _dispatch_local(self, envelope: Dict[str, Any]):
        event_type_name = envelope.get("event_type", {}).get("type", "")

        # Specific type listeners
        callbacks = list(self._subscribers.get(event_type_name, []))
        for cb in callbacks:
            try:
                cb(envelope)
            except Exception as e:
                log.error(f"Error in local event subscriber for {event_type_name}: {e}")

        # Wildcard listeners
        all_cbs = list(self._all_subscribers)
        for cb in all_cbs:
            try:
                cb(envelope)
            except Exception as e:
                log.error(f"Error in wildcard event subscriber: {e}")

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to all events entering this bus."""
        with self._lock:
            self._all_subscribers.append(callback)

    def get_ledger(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._in_memory_ledger)

    def start_sse_listener(self):
        """Starts background SSE listener to pull Kernel events into local subscribers."""
        if self._sse_thread and self._sse_thread.is_alive():
            return
        self._running = True
        self._sse_thread = threading.Thread(target=self._sse_worker, daemon=True, name="eventbus-sse")
        self._sse_thread.start()

    def _sse_worker(self):
        while self._running:
            try:
                resp = requests.get(f"{self.base_url}/events/live", stream=True, timeout=10)
                for line in resp.iter_lines():
                    if not self._running:
                        break
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data:"):
                            raw = decoded[5:].strip()
                            if raw:
                                event = json.loads(raw)
                                self._dispatch_local(event)
            except Exception:
                time.sleep(2.0)

    def stop(self):
        self._running = False
