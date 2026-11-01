"""
GRaCEmo ViRa — Phase 4 Step 2: Persistent World / Object Context in MNSE
Authoritative typed client and representation for Rust MNSE World Objects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import requests


VISIBILITY_TIMEOUT_SEC: float = 10.0
ASSOCIATION_DISTANCE_THRESHOLD: float = 0.5
AMBIGUITY_THRESHOLD: float = 0.01


@dataclass
class WorldObject:
    """Canonical representation of a persistent 3D world object in MNSE."""
    object_id: str
    class_name: str
    confidence: float
    world_x: float
    world_y: float
    world_z: float
    first_seen: float
    last_seen: float
    observation_count: int = 1
    currently_visible: bool = True
    source: str = "Vision"
    frame_id: str = "world"
    bbox: Optional[List[float]] = None
    depth_m: Optional[float] = None
    max_confidence: float = 0.0

    def __post_init__(self):
        if self.max_confidence == 0.0:
            self.max_confidence = self.confidence

    @property
    def position(self) -> Tuple[float, float, float]:
        """Convenience 3D tuple (x, y, z)."""
        return (self.world_x, self.world_y, self.world_z)

    def distance_to(self, x: float, y: float, z: float) -> float:
        """3D Euclidean distance to target metric coordinates."""
        dx = self.world_x - x
        dy = self.world_y - y
        dz = self.world_z - z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def is_visible_at(self, current_time: float, timeout_sec: float = VISIBILITY_TIMEOUT_SEC) -> bool:
        """Evaluates visibility lifecycle against an arbitrary reference timestamp."""
        return (current_time - self.last_seen) <= timeout_sec

    def update(
        self,
        confidence: float,
        detected_x: float,
        detected_y: float,
        detected_z: float,
        timestamp: float,
        source: str = "Vision",
        frame_id: str = "world",
        bbox: Optional[List[float]] = None,
        depth_m: Optional[float] = None,
    ):
        """Deterministically updates object state with new spatial observation."""
        self.observation_count += 1
        self.last_seen = timestamp
        self.currently_visible = True
        self.confidence = confidence
        if confidence > self.max_confidence:
            self.max_confidence = confidence

        # Smoothed position update: 0.7 * detected + 0.3 * previous
        self.world_x = 0.7 * detected_x + 0.3 * self.world_x
        self.world_y = 0.7 * detected_y + 0.3 * self.world_y
        self.world_z = 0.7 * detected_z + 0.3 * self.world_z

        self.source = source
        self.frame_id = frame_id
        if bbox is not None:
            self.bbox = bbox
        if depth_m is not None:
            self.depth_m = depth_m

    def to_dict(self) -> Dict[str, Any]:
        """Serializes object to canonical JSON representation."""
        return {
            "object_id": self.object_id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 3),
            "max_confidence": round(float(self.max_confidence), 3),
            "world_x": round(float(self.world_x), 3),
            "world_y": round(float(self.world_y), 3),
            "world_z": round(float(self.world_z), 3),
            "position": [
                round(float(self.world_x), 3),
                round(float(self.world_y), 3),
                round(float(self.world_z), 3),
            ],
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "observation_count": self.observation_count,
            "currently_visible": self.currently_visible,
            "source": self.source,
            "frame_id": self.frame_id,
            "bbox": self.bbox,
            "depth_m": round(float(self.depth_m), 3) if self.depth_m is not None else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> WorldObject:
        """Constructs WorldObject from dictionary returned by Kernel or SQLite."""
        pos = d.get("position")
        if pos and len(pos) == 3:
            wx, wy, wz = pos[0], pos[1], pos[2]
        else:
            wx = d.get("world_x", 0.0)
            wy = d.get("world_y", 0.0)
            wz = d.get("world_z", 0.0)

        return cls(
            object_id=d["object_id"],
            class_name=d["class_name"],
            confidence=float(d.get("confidence", 1.0)),
            max_confidence=float(d.get("max_confidence", d.get("confidence", 1.0))),
            world_x=float(wx),
            world_y=float(wy),
            world_z=float(wz),
            first_seen=float(d.get("first_seen", 0.0)),
            last_seen=float(d.get("last_seen", 0.0)),
            observation_count=int(d.get("observation_count", 1)),
            currently_visible=bool(d.get("currently_visible", True)),
            source=d.get("source", "Vision"),
            frame_id=d.get("frame_id", "world"),
            bbox=d.get("bbox"),
            depth_m=float(d["depth_m"]) if d.get("depth_m") is not None else None,
        )


class WorldModelClient:
    """
    Client for querying the authoritative Rust MNSE Kernel world object store.
    Does NOT maintain an independent state in production.
    """

    def __init__(self, kernel_url: str = "http://127.0.0.1:7780", timeout: float = 2.0):
        self.kernel_url = kernel_url.rstrip("/")
        self.timeout = timeout

    def get_objects(self, visible_only: bool = False, class_name: Optional[str] = None) -> List[WorldObject]:
        """Queries all world objects from Rust MNSE."""
        params: Dict[str, Any] = {}
        if visible_only:
            params["visible_only"] = "true"
        if class_name:
            params["class"] = class_name

        try:
            resp = requests.get(f"{self.kernel_url}/world/objects", params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                objs = data.get("objects", [])
                return [WorldObject.from_dict(o) for o in objs]
        except Exception:
            pass
        return []

    def get_objects_by_class(self, class_name: str, visible_only: bool = False) -> List[WorldObject]:
        """Queries world objects filtered by class name."""
        return self.get_objects(visible_only=visible_only, class_name=class_name)

    def get_nearest_object(
        self,
        class_name: str,
        from_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        visible_only: bool = False,
    ) -> Optional[WorldObject]:
        """Queries nearest world object of given class to specified coordinates."""
        params = {
            "class": class_name,
            "nearest_x": from_pos[0],
            "nearest_y": from_pos[1],
            "nearest_z": from_pos[2],
            "visible_only": "true" if visible_only else "false",
        }
        try:
            resp = requests.get(f"{self.kernel_url}/world/objects", params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found") and "object" in data:
                    return WorldObject.from_dict(data["object"])
        except Exception:
            pass
        return None

    def get_visible_objects(self) -> List[WorldObject]:
        """Queries all currently visible world objects."""
        return self.get_objects(visible_only=True)

    def get_object_by_id(self, object_id: str) -> Optional[WorldObject]:
        """Queries a specific world object by its deterministic identifier."""
        try:
            resp = requests.get(
                f"{self.kernel_url}/world/objects",
                params={"id": object_id},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("found") and "object" in data:
                    return WorldObject.from_dict(data["object"])
        except Exception:
            pass
        return None

    def get_compiled_world_context(self) -> Dict[str, Any]:
        """Fetches full compiled context package (/context) from Kernel."""
        try:
            resp = requests.get(f"{self.kernel_url}/context", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def get_toon_context(self) -> str:
        """Fetches compiled TOON representation (/context?format=toon) from Kernel."""
        try:
            resp = requests.get(f"{self.kernel_url}/context?format=toon", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""


class StandaloneWorldTracker:
    """
    Deterministic world object tracker mirroring Rust MNSE logic.
    Exclusively for offline unit tests without requiring a running live kernel server.
    """

    def __init__(self, visibility_timeout: float = VISIBILITY_TIMEOUT_SEC):
        self.objects: Dict[str, WorldObject] = {}
        self.visibility_timeout = visibility_timeout

    def process_detection(
        self,
        class_name: str,
        confidence: float,
        x: float,
        y: float,
        z: float,
        timestamp: float,
        source: str = "Vision",
        frame_id: str = "world",
        bbox: Optional[List[float]] = None,
        depth_m: Optional[float] = None,
    ) -> WorldObject:
        """Processes an observation and performs deterministic 3D Euclidean association."""
        # 1. Filter existing objects of the same class (case-insensitive)
        candidates: List[Tuple[float, WorldObject]] = []
        for obj in self.objects.values():
            if obj.class_name.lower() == class_name.lower():
                d = obj.distance_to(x, y, z)
                if d <= ASSOCIATION_DISTANCE_THRESHOLD:
                    candidates.append((d, obj))

        candidates.sort(key=lambda item: item[0])

        # 2. Ambiguity check: if 2+ candidates within 0.5m and |d0 - d1| <= AMBIGUITY_THRESHOLD, do not merge!
        is_ambiguous = False
        if len(candidates) >= 2:
            if abs(candidates[1][0] - candidates[0][0]) <= AMBIGUITY_THRESHOLD:
                is_ambiguous = True

        if candidates and not is_ambiguous:
            # Associate with closest existing object
            matched_obj = candidates[0][1]
            matched_obj.update(
                confidence=confidence,
                detected_x=x,
                detected_y=y,
                detected_z=z,
                timestamp=timestamp,
                source=source,
                frame_id=frame_id,
                bbox=bbox,
                depth_m=depth_m,
            )
            return matched_obj
        else:
            # Create new object with deterministic ID: {class_name}_{next_index:03d}
            matching_ids = [
                obj.object_id
                for obj in self.objects.values()
                if obj.class_name.lower() == class_name.lower()
            ]
            max_idx = 0
            for oid in matching_ids:
                try:
                    num = int(oid.split("_")[-1])
                    if num > max_idx:
                        max_idx = num
                except ValueError:
                    pass

            next_idx = max_idx + 1
            slug = class_name.lower().replace(" ", "_")
            new_id = f"{slug}_{next_idx:03d}"

            new_obj = WorldObject(
                object_id=new_id,
                class_name=class_name,
                confidence=confidence,
                world_x=x,
                world_y=y,
                world_z=z,
                first_seen=timestamp,
                last_seen=timestamp,
                observation_count=1,
                currently_visible=True,
                source=source,
                frame_id=frame_id,
                bbox=bbox,
                depth_m=depth_m,
            )
            self.objects[new_id] = new_obj
            return new_obj

    def get_objects(
        self,
        visible_only: bool = False,
        class_name: Optional[str] = None,
        reference_time: Optional[float] = None,
    ) -> List[WorldObject]:
        """Returns objects with dynamic visibility evaluation."""
        result: List[WorldObject] = []
        for obj in self.objects.values():
            if reference_time is not None:
                obj.currently_visible = obj.is_visible_at(reference_time, self.visibility_timeout)
            if class_name and obj.class_name.lower() != class_name.lower():
                continue
            if visible_only and not obj.currently_visible:
                continue
            result.append(obj)
        result.sort(key=lambda o: o.object_id)
        return result

    def get_objects_by_class(
        self,
        class_name: str,
        visible_only: bool = False,
        reference_time: Optional[float] = None,
    ) -> List[WorldObject]:
        return self.get_objects(visible_only=visible_only, class_name=class_name, reference_time=reference_time)

    def get_nearest_object(
        self,
        class_name: str,
        from_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        visible_only: bool = False,
        reference_time: Optional[float] = None,
    ) -> Optional[WorldObject]:
        candidates = self.get_objects_by_class(class_name, visible_only=visible_only, reference_time=reference_time)
        if not candidates:
            return None
        return min(candidates, key=lambda o: o.distance_to(*from_pos))

    def get_visible_objects(self, reference_time: Optional[float] = None) -> List[WorldObject]:
        return self.get_objects(visible_only=True, reference_time=reference_time)

    def get_object_by_id(self, object_id: str) -> Optional[WorldObject]:
        return self.objects.get(object_id)

    def to_toon(self, reference_time: Optional[float] = None) -> str:
        """Generates #OBJECTS TOON section matching Rust MNSE compiler."""
        objs = self.get_objects(reference_time=reference_time)
        if not objs:
            return ""
        items = []
        for o in objs:
            vis = 1 if o.currently_visible else 0
            items.append(
                f"{o.object_id}[class:{o.class_name},pos:({o.world_x:.2f},{o.world_y:.2f},{o.world_z:.2f}),conf:{o.confidence:.2f},vis:{vis},obs:{o.observation_count}]"
            )
        return f"#OBJECTS:{'!'.join(items)}"
