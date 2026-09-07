# InspectorState — Authoritative Real-Time Awareness Substrate

## 1. What is InspectorState?
`InspectorState` represents the **"NOW"** dimension of the MNSE Kernel. It is the single source of truth for the robot's present physical state and immediate sensory environment.

---

## 2. State Invariants
- Reconciled continuously in memory with `RwLock` concurrency protection.
- Updates synchronously upon ingestion of verified events.
- Read-only for external agents; mutations happen exclusively via event ingestion.

```json
{
  "status": "online",
  "current_room": "Home Study",
  "robot_position": {
    "x": 5.03,
    "y": 1.67,
    "theta": 1.56,
    "speed": 0.0
  },
  "battery": {
    "level": 92.5,
    "charging": false
  },
  "last_vision_detection": {
    "identity": "laptop",
    "confidence": 0.94,
    "distance": 1.2
  },
  "last_voice_command": {
    "text": "Where is the laptop?",
    "confidence": 0.98
  }
}
```
