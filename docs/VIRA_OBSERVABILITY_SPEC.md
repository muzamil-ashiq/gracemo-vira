# GRaCEmo ViRa — Observability & Telemetry Specification
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-OBS-P1-008`  
**System Version:** v0.0.3  

---

## 1. Observability Architecture

Production robotics requires end-to-end trace correlation from the millisecond human soundwaves hit the microphone to the millisecond the robot stops at a target waypoint.

```
[Human Voice Input]
  │
  ├─ trace_id = 4a12... (generated at audio capture)
  ▼
[VAD & Speech Endpoint] ──► spans: vad.segment (410ms)
  │
  ▼
[STT Transcription]     ──► spans: stt.transcribe (295ms)
  │
  ▼
[Brain Reasoning]       ──► spans: brain.inference (510ms)
  │
  ▼
[Safety Gate Validation]──► spans: safety.verify (3ms)
  │
  ▼
[Kernel EventBus]       ──► spans: eventbus.route (1ms)
  │
  ├───────────────────────────────────┐
  ▼                                   ▼
[TTS Speech Playback]              [Robot Bridge / ROS 2]
spans: tts.synthesize (180ms)      spans: nav.execute (12400ms)
```

---

## 2. Distributed Trace Envelope

Every log entry and event record carries the canonical tracing context:

```json
{
  "trace_id": "8f3e2b1a-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
  "span_id": "a1b2c3d4e5f60718",
  "parent_span_id": "0000000000000000",
  "session_id": "sess_lpu_20261003_01",
  "robot_id": "gracemo_vira_01",
  "component": "interaction_gateway",
  "event": "speech.transcribed",
  "timestamp_iso": "2026-10-03T00:15:30.412Z",
  "duration_ms": 284.5,
  "status": "OK",
  "attributes": {
    "engine": "groq_whisper_turbo",
    "word_count": 6,
    "confidence": 0.96
  }
}
```

---

## 3. Metrics Catalog

### 3.1 Latency Gauges & Histograms
- `vira_interaction_turn_latency_ms`: Total time from speech endpoint to first TTS audio byte.
- `vira_vad_cutoff_latency_ms`: Time elapsed between last speech sample and VAD silence trip.
- `vira_stt_duration_ms`: Duration of audio transcription.
- `vira_brain_inference_ms`: Time taken by local MLX Qwen or cloud LLM to generate reply.
- `vira_safety_gate_eval_ms`: Time taken to validate coordinates and limits.
- `vira_eventbus_dispatch_ms`: Time from `POST /emit` to SSE client delivery.
- `vira_tts_first_byte_ms`: Time from text submission to soundcard playback start.
- `vira_robot_action_latency_ms`: Time from `ActionRequested` to `/cmd_vel` change.

### 3.2 Counter & Rate Metrics
- `vira_events_total{source, type}`: Monotonic count of events processed.
- `vira_errors_total{subsystem, error_code}`: Count of unhandled or recovered errors.
- `vira_timeouts_total{operation}`: Count of operations exceeding deadline.
- `vira_llm_fallbacks_total{from_provider, to_provider}`: Count of cloud $\to$ local $\to$ heuristic fallbacks.
- `vira_emergency_stops_total{trigger}`: Count of E-STOP events.

---

## 4. Health & Status Endpoints

| Endpoint | Protocol | Port | Response Schema | Description |
| :--- | :---: | :---: | :--- | :--- |
| `GET /health` | HTTP | 7780 | `{"status": "ok", "version": "0.0.3"}` | Kernel heartbeat check. |
| `GET /snapshot` | HTTP | 7780 | In-memory `InspectorState` JSON | Live telemetry, battery, pose, and active task. |
| `GET /context` | HTTP | 7780 | Compiled context (NOW + PAST + RELATIONS) | Grounded truth for reasoning agents. |
| `GET /events/live` | SSE | 7780 | Text stream of typed `Event` JSON | Live EventBus subscription. |
| `GET /api/status` | HTTP | 8420 | `{"robot": "GraceEMO", "status": "READY"}` | Interaction Gateway status endpoint. |
