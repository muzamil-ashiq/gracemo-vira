# MNSE Event Protocol & Communication Specification

## 1. Event Model
All communication between adapters, the embodied robot, and the Kernel flows as typed JSON events through the **EventBus** and Unix Domain Socket (`/tmp/gracemo.sock`).

```json
{
  "id": "uuid-v4",
  "timestamp": 1772648400,
  "source": "ROS2Bridge",
  "observed_by": "vision",
  "event_type": "RobotPosition",
  "payload": {
    "x": 5.02,
    "y": 1.45,
    "theta": 1.57,
    "speed": 0.35
  }
}
```

---

## 2. Standard Event Catalog

| Event Type | Producer | Description |
| :--- | :--- | :--- |
| `RobotPosition` | ROS 2 Bridge | Live coordinates $(X, Y)$, orientation $(\theta)$, and linear speed. |
| `ObstacleDetected` | ROS 2 Bridge | LiDAR safety obstacle range warnings. |
| `PersonVisible` | Vision Adapter | YuNet face identification & bounding box tracker. |
| `ObjectDetected` | Vision Adapter | YOLOv11 multi-class object detection with $(X, Y, Z)$ spatial depth. |
| `VoiceDetected` | Voice Adapter | Transcribed human speech via Faster-Whisper. |
| `ActionRequested` | Cognitive Brain | High-level action dispatched by the LLM (`Speak`, `Move`, `Navigate`). |
| `NavigationArrived`| Navigation / Bridge | Station arrival confirmation at target destination. |
