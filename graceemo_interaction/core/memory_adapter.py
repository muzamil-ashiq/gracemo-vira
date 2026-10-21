#!/usr/bin/env python3
"""
GRaCEmo ViRa — Memory Adapter
Provides thread-safe access to human_memory.json and synchronizes user profiles.
Degrades gracefully if memory file is missing or inaccessible.
"""
from __future__ import annotations
import datetime
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

log = logging.getLogger("gracemo.memory")


class MemoryAdapter:
    """
    Manages persistent memory of visitors, creators, and prior conversations.
    """

    def __init__(self, memory_file_path: Optional[str] = None):
        if memory_file_path:
            self.memory_path = memory_file_path
        else:
            self.memory_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "human_memory.json"
            )
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {"users": {}}
        self._load()

    def _load(self):
        with self._lock:
            if os.path.exists(self.memory_path):
                try:
                    with open(self.memory_path, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                    log.info(f"✓ Loaded memory for {len(self._data.get('users', {}))} profiles")
                except Exception as e:
                    log.warning(f"Failed to parse memory JSON ({e}); starting fresh memory store")
                    self._data = {"users": {}}
            else:
                self._data = {"users": {}}

    def save(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
                with open(self.memory_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
            except Exception as e:
                log.warning(f"Failed to persist memory: {e}")

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            key = user_id.lower().replace(" ", "_")
            return self._data.get("users", {}).get(key)

    def record_interaction(
        self,
        name: str,
        note: str,
        role: str = "Student / Guest",
        relationship: str = "Visitor",
    ) -> Dict[str, Any]:
        with self._lock:
            key = name.lower().replace(" ", "_")
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            users = self._data.setdefault("users", {})
            user_entry = users.setdefault(
                key,
                {
                    "name": name,
                    "role": role,
                    "notes": [],
                    "relationship": relationship,
                    "interactions_count": 0,
                    "first_met": now_str,
                },
            )

            user_entry["interactions_count"] = user_entry.get("interactions_count", 0) + 1
            user_entry["last_seen"] = now_str
            if note and note not in user_entry["notes"]:
                user_entry["notes"].append(note)
                if len(user_entry["notes"]) > 10:
                    user_entry["notes"].pop(0)

        self.save()
        return user_entry
