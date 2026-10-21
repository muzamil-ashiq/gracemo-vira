# GRaCEmo ViRa — Event Contracts & Protocol Specification
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-CONTRACTS-P1-004`  
**System Version:** v0.0.3  

---

## 1. Universal Event Envelope

All communication between perception adapters, the cognitive brain, the safety gateway, and the embodied robot bridge flows as strongly typed JSON events matching the Rust [`gracemo-types`](file:///Users/samdavi/projects/VIRA/kernel/gracemo-types/src/lib.rs) envelope:

```json
{
  "id": "c4b9e288-5c49-4171-886d-3b56cf287a91",
  "trace_id": "7f8e1234-9876-4321-ba98-76543210fedc",
  "session_id": "session_20261003_001",
  "timestamp": 1790987200,
  "timestamp_iso": "2026-10-03T00:30:00.125Z",
  "source": "Voice",
  "observed_by": "graceemo_interaction_stt",
  "sequence": 42,
  "parent_event_id": null,
  "event_type": {
    "type": "VoiceDetected",
    "data": {
      "transcription": "Take me to the Robotics Lab",
      "confidence": 0.96,
      "language": "en",
      "duration_sec": 2.1
    }
  }
}
```

### Envelope Fields Specification

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `id` | `UUIDv4` | Yes | Globally unique identifier for this event. |
| `trace_id` | `UUIDv4` | Yes | Causal trace identifier linking audio input $\to$ intent $\to$ action $\to$ arrival. |
| `session_id` | `String` | No | Identifier for active human conversation session. |
| `timestamp` | `Integer` | Yes | Unix epoch timestamp in seconds. |
| `timestamp_iso` | `ISO-8601` | Yes | UTC timestamp with millisecond precision. |
| `source` | `Enum` | Yes | `RobotBridge`, `Vision`, `Voice`, `Interaction`, `Sensor`, `Brain`, `SafetyGateway`, `System`. |
| `observed_by` | `String` | Yes | Component instance name (e.g. `kernel_bridge`, `stt_engine`, `face_id`). |
| `sequence` | `Integer` | No | Monotonically increasing sequence number per source. |
| `parent_event_id`| `UUIDv4` | No | ID of the event that caused this event (causal lineage). |
| `event_type` | `Object` | Yes | Tagged enum containing `type` and strongly typed `data`. |

---

## 2. Standard Event Catalog

### 2.1 Interaction & Voice Events

#### `VoiceDetected`
Emitted by STT upon transcribing human speech.
```json
{
  "type": "VoiceDetected",
  "data": {
    "transcription": "Hello GraceEMO, what is happening in the lab?",
    "confidence": 0.95
  }
}
```

#### `VoiceIntent`
Emitted by DialogueEngine or Brain after intent classification.
```json
{
  "type": "VoiceIntent",
  "data": {
    "intent": "NAVIGATE",
    "confidence": 0.95,
    "entities": { "destination": "Robotics Research Lab" }
  }
}
```

### 2.2 Actuation & Action Requests

#### `ActionRequested`
Emitted by Cognitive Brain or Fast Path to request robot or screen action.
```json
{
  "type": "ActionRequested",
  "data": {
    "action": "NavigateTo",
    "params": {
      "x": 2.5,
      "y": 2.0,
      "yaw": 1.5708
    }
  }
}
```

#### `RobotAction::Speak`
```json
{
  "type": "ActionRequested",
  "data": {
    "action": "Speak",
    "params": {
      "text": "Certainly! Navigating to the Robotics Research Lab now. Please follow me."
    }
  }
}
```

#### `RobotAction::Express`
```json
{
  "type": "ActionRequested",
  "data": {
    "action": "Express",
    "params": {
      "emotion": "happy"
    }
  }
}
```

#### `RobotAction::LookAt`
```json
{
  "type": "ActionRequested",
  "data": {
    "action": "LookAt",
    "params": {
      "x": 5.5,
      "y": 4.0,
      "z": 0.75
    }
  }
}
```

### 2.3 Robot Telemetry & Feedback Events

#### `RobotPosition`
Emitted at 5 Hz by Robot Bridge from live odometry.
```json
{
  "type": "RobotPosition",
  "data": {
    "x": 1.25,
    "y": -0.45,
    "theta": 0.12,
    "speed": 0.28
  }
}
```

#### `NavigationArrived`
Emitted when target coordinates or room destination are reached.
```json
{
  "type": "NavigationArrived",
  "data": {
    "destination": "Robotics Research Lab",
    "success": true
  }
}
```

#### `ObstacleDetected`
Emitted when LiDAR or bumper detects proximate collision hazard.
```json
{
  "type": "ObstacleDetected",
  "data": {
    "distance": 0.38,
    "direction": "front"
  }
}
```

---

## 3. Schema Governance & Versioning

1. All events must strictly validate against the JSON schemas in [`contracts/`](file:///Users/samdavi/projects/VIRA/contracts):
   - [`event-envelope.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/event-envelope.schema.json)
   - [`interaction.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/interaction.schema.json)
   - [`robot-command.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/robot-command.schema.json)
   - [`robot-event.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/robot-event.schema.json)
   - [`navigation.schema.json`](file:///Users/samdavi/projects/VIRA/contracts/navigation.schema.json)
2. **Schema Invariant**: No unversioned breaking changes to event field types. Unknown fields are dropped gracefully by the Kernel's `#[serde(default)]` deserializer.
