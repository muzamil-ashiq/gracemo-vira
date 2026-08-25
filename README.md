# GRaCEmo ViRa — Autonomous AI Robot System

> **Event-Driven Nervous System for Autonomous Robotics & Multimodal AI**

---

## 🧭 System Overview

GRaCEmo ViRa decouples high-level reasoning and physical body control using an **event-driven nervous system** pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                       AI REASONING                          │
│               (LLMs / Task Planners / Memory)               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 GRaCEmo KERNEL (Rust)                       │
│     • Tokio EventBus (Broadcast & Priority Queues)          │
│     • Append-Only SQLite Ledger (Causal Event Store)        │
│     • Relational Knowledge Graph (Entity/State Tracking)    │
│     • High-Speed HTTP/SSE & Unix Socket API                 │
└───────▲──────────────────────▲───────────────────────┬──────┘
        │                      │                       │
        │ Event Stream         │ Event Stream          │ Action Dispatch
        │                      │                       │ (navigate, speak, look)
┌───────┴──────────────┐ ┌─────┴────────────────┐ ┌────▼──────────────┐
│   VISION ADAPTER     │ │   VOICE ADAPTER      │ │   ROBOT BRIDGE    │
│   (YOLO / YuNet)     │ │ (Whisper / Kokoro)   │ │  (ROS2 / Hardware)│
└──────────────────────┘ └──────────────────────┘ └───────────────────┘
```

---

## 📁 Repository Layout

- `kernel/` — Core Rust workspace: EventBus, types, ledger, graph, and MCP interfaces.
- `adapters/` — Python perception and actuation bridge adapters (Vision, Voice, Robot Bridge, LLM).
- `simulation/` — Dockerized ROS2 Jazzy + Gazebo simulation workspace for hardware-free development.
- `config/` — Declarative TOML/YAML runtime configurations.
- `docs/` — Architecture documentation, hardware interfaces, and API references.

---

## 🚀 Getting Started

1. **Prerequisites**:
   - Rust toolchain (`cargo`, `rustc`)
   - Python 3.10+ / `uv`
   - Docker (for ROS2 / Gazebo simulation)

2. **Run Kernel**:
   ```bash
   cd kernel && cargo run -p gracemo-kernel
   ```

3. **Connect Adapters**:
   ```bash
   cd adapters/robot-bridge && python3 -m gracemo_bridge.bridge
   ```
