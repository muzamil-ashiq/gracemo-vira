# Context Compilers — Deterministic Truth Transformation

## 1. What is a Context Compiler?
A `Context Compiler` transforms `InspectorState` (NOW), `Event Ledger` (PAST), and `Knowledge Graph` (RELATIONS) into a structured truth package for the Cognitive Agent.

---

## 2. Invariants
- **Zero Hallucination**: The compiler never adds assumptions, predictions, or AI-generated text.
- **Deterministic**: Given the same state snapshot and ledger history, the compiler produces the exact same context output.

---

## 3. Output Schema (`/context` endpoint)
```json
{
  "now": {
    "current_room": "Home Study",
    "robot_position": { "x": 5.03, "y": 1.67, "speed": 0.0 }
  },
  "recent_history": [
    { "timestamp": 1772648400, "event_type": "NavigationArrived", "payload": "Study" },
    { "timestamp": 1772648390, "event_type": "ObjectDetected", "payload": "laptop" }
  ],
  "environment_graph": {
    "known_landmarks": {
      "Home Study": ["desk", "laptop", "bookshelf", "chair"]
    }
  }
}
```
