# K Operational Language Specification

## 1. Role of K
**K** is a deterministic, capability-governed operational language and DSL for interacting with the MNSE substrate.

```text
                 AGENT / LLM
                      │
                      │ queries & requests
                      ▼
              ┌───────────────┐
              │       K       │
              │  Lexer → AST  │
              │  → Planner    │
              │  → Runtime    │
              └───────┬───────┘
                      │
                      ▼
                 MNSE KERNEL
```

---

## 2. The Three Functional Domains of K

### 1. QUERY (`k now`, `k history`, `k graph`, `k context`)
Retrieves authoritative truth from InspectorState, Ledger, and Graph without hallucination:
```text
k now robot.position
k history robot --since 1h
k graph where "laptop"
k context robot --summary
```

### 2. COMPOSE (Pipelines & Filters)
Transforms structured data deterministically:
```text
k history robot | filter event_type == "ObstacleDetected" | select [timestamp, payload.distance]
```

### 3. ACT (Capability-Governed Action Requests)
K describes and requests actions without executing physical motor loops:
```text
k action.navigate target="study" speed=0.35
```
Generates a typed `ActionRequested` event:
```json
{
  "action": "Navigate",
  "target": "study",
  "params": { "speed": 0.35 }
}
```
