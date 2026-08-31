# GRaCEmo ViRa — Architectural Principles & Lessons Learned from MNSE

> **Guiding Principle**: Build on the proven patterns of the MNSE Context Operating Layer while avoiding its historical pitfalls and early refactors.

---

## 🚫 Top 6 Mistakes from MNSE & How GRaCEmo Prevents Them

### 1. The Hardcoding Trap (The 229-Hardcode Refactor)
- **MNSE Pitfall**: Over months of rapid development, MNSE accumulated 229 hardcoded timeouts, thresholds, model names, and network addresses across Rust and Python, requiring a massive refactoring in `v0.0.53`.
- **GRaCEmo Rule**: **Zero Hardcoded Magic Numbers**.
  - All ports, thresholds, camera IDs, model weights, and timeouts reside in declarative configs (`config/kernel.toml`, `config/perception.yaml`, `config/voice.yaml`, `config/brain.yaml`).

---

### 2. The "Kernel Doing Too Much" Mistake
- **MNSE Pitfall**: Early MNSE versions attempted to execute editor commands (Neovim RPC), run CLI tools directly, and manage complex embeddings inside the core kernel daemon. This violated separation of concerns and was purged in `v0.0.42–43`.
- **GRaCEmo Rule**: **The Kernel is Boring**.
  - The Rust Kernel **only** routes events, stores snapshots/ledgers, and dispatches actions.
  - The Kernel **never** calls LLM APIs, **never** runs YOLO/Whisper inference, and **never** drives motors directly.

---

### 3. Event Flooding & Unbounded State Bloat
- **MNSE Pitfall**: High-frequency adapters (such as terminal pollers or continuous face detectors) emitted events at 30–60 Hz with unbounded payloads (>50MB JSON buffers), risking Out-Of-Memory (OOM) crashes.
- **GRaCEmo Rule**: **Debounced & Throttled Event Emission**.
  - Sensory adapters throttle continuous emissions (e.g. `min_emit_interval_sec: 0.5`).
  - The Tokio EventBus uses bounded broadcast channels (capacity: 2048).
  - Snapshot arrays are capped to fixed lengths.

---

### 4. Eager Model Loading & VRAM Contention
- **MNSE Pitfall**: Preloading all neural networks (Whisper, Kokoro, Embeddings, Face CNN) on startup consumed ~1.5GB RAM and caused CUDA VRAM memory pressure on smaller GPUs.
- **GRaCEmo Rule**: **Decoupled Adapter Processes**.
  - Vision, Voice, and Brain run as independent OS processes.
  - Each adapter can be started, stopped, or restarted without affecting the Rust Kernel daemon or other senses.

---

### 5. Provenance & The "Observed-By" Invariant
- **MNSE Pitfall**: Ambiguous event sources caused the "Epistemic Paradox"—the system couldn't distinguish between an idle environment and a crashed adapter.
- **GRaCEmo Rule**: **Strict Provenance Tracking**.
  - Every event envelope carries `source: EventSource` and `observed_by: String` (e.g. `"vision"`, `"voice"`, `"robot_bridge"`).
  - Adapters emit `AdapterConnected` on boot.

---

### 6. Non-Blocking Asynchronous Action Dispatch
- **MNSE Pitfall**: Synchronous execution of actions caused pipelines to hang if an external tool had network latency.
- **GRaCEmo Rule**: **Decoupled Fire-and-Forget SSE Streaming**.
  - When an action is requested (`ActionRequested(RobotAction)`), the Kernel broadcasts it instantly over the SSE stream (`/events/live`) and returns HTTP 200 immediately.
  - Actuators/TTS consume actions asynchronously.

---

## 🏛️ GRaCEmo Core Architecture Matrix

```
┌─────────────────────────────────────────────────────────────┐
│                       BRAIN ADAPTER                         │
│             LLM Reasoning (Gemini / Claude / Local)         │
│          Reads: GET /snapshot | Emits: ActionRequested      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 GRaCEmo KERNEL (Rust)                       │
│  • Tokio EventBus (2048 capacity)                           │
│  • Live State Snapshot (/snapshot)                          │
│  • High-Speed HTTP/SSE (/emit, /events/live)                │
│  • Future: SQLite Causal Ledger & Knowledge Graph           │
└───────▲──────────────────────▲───────────────────────┬──────┘
        │                      │                       │
        │ PersonVisible        │ VoiceDetected         │ ActionRequested(Speak,
        │ ObjectDetected       │ VoiceIntent           │   NavigateTo, LookAt)
        │                      │                       │
┌───────┴──────────────┐ ┌─────┴────────────────┐ ┌────▼──────────────┐
│   VISION ADAPTER     │ │   VOICE ADAPTER      │ │   ROBOT BRIDGE    │
│  YOLOv11 on GPU      │ │ Faster-Whisper (GPU) │ │ ROS2 / Distrobox  │
│  Throttled 0.5s      │ │ Neural Edge-TTS      │ │ Hardware Motors   │
└──────────────────────┘ └──────────────────────┘ └───────────────────┘
```
