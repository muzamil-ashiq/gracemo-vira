# Universal Adapter & Executor Protocol Specification

## 1. System-Independent Boundary
The Adapter & Executor Protocol decouples external environments (ROS 2, Linux OS, Smart Home, Web Browser) from the MNSE Kernel.

```text
                 MNSE
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
   observation             action
       │                     │
       ▼                     ▼
    Adapter              Executor
       │                     │
       └──────────┬──────────┘
                  ▼
         EXTERNAL SYSTEM
```

---

## 2. Adapter Contract (Inward Ingestion)
Every adapter implements:
- `connect(target: str) -> bool`: Establishes communication with external system.
- `observe() -> Stream[Observation]`: Continuously reads external sensory streams.
- `emit(event_type: str, data: dict)`: Maps observations into typed MNSE events.

---

## 3. Executor Contract (Outward Actuation)
Every executor implements:
- `execute(action: ActionRequested) -> ExecutionResult`: Translates high-level action intent into physical commands (e.g. `Twist` velocity commands to `/cmd_vel`).
