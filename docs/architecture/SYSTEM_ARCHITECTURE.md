# GRaCEmo ViRa — System Architecture Specification

## 1. System Vision
**GRaCEmo ViRa** is an embodied AI robotics platform whose real-time awareness and historical memory are provided by **MNSE**, while **ROS 2** and **Gazebo Harmonic** provide the robotic body and physical navigation infrastructure.

---

## 2. Core Architectural Layers

```text
                    ┌─────────────────────────┐
                    │      COGNITIVE AGENT    │
                    │   (LLM / Intent Planner) │
                    └────────────┬────────────┘
                                 │ asks context / receives truth
                                 ▼
              ┌─────────────────────────────────────┐
              │                MNSE                 │
              │                                     │
              │  PRESENT (NOW)    ─ InspectorState  │
              │  PAST (MEMORY)    ─ Event Ledger    │
              │  RELATIONSHIPS    ─ Knowledge Graph │
              │  CONTEXT          ─ Context Compiler│
              └──────────────────▲──────────────────┘
                                 │ typed events
                                 │
              ┌──────────────────┴──────────────────┐
              │          PERCEPTION ADAPTERS        │
              │  Vision (YOLOv11), Audio (Whisper)  │
              │  ROS 2 Bridge (Odometry, LiDAR)     │
              └──────────────────▲──────────────────┘
                                 │ raw sensor streams
                                 │
              ┌──────────────────┴──────────────────┐
              │             ROBOT BODY              │
              │    ROS 2 Humble + Gazebo Harmonic   │
              │    Differential Drive + Sensors     │
              └─────────────────────────────────────┘
```

---

## 3. Non-Negotiable Invariants

1. **Kernel Never Thinks**: The MNSE Kernel owns state, ledger, and context compilation. It never embeds LLMs, never automates by default, and never guesses facts.
2. **Adapters Never Read State**: Adapters (Camera, Audio, ROS 2 Bridge) strictly ingest external sensor streams and emit typed observations.
3. **All Truth Flows Through InspectorState**: The live observed state of the physical robot and environment is continuously reconciled in InspectorState.
4. **Separation of Navigation and Knowledge**:
   - **Spatial Navigation Graph** (ROS 2 / Nav2): Metric coordinates, doorway approaches, and collision tolerances.
   - **MNSE Knowledge Graph** (Kernel): Semantic relationships (e.g. `Laptop located_in Study on Desk`).
