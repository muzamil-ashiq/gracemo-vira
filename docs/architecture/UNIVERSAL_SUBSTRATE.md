# Universal Context Substrate Specification (MNSE Core)

## 1. Architectural Philosophy
MNSE is a **Context Operating Layer** that provides a single authoritative, real-time source of system and environmental truth.

```text
                 MNSE / Kernel
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
     PRESENT          PAST        RELATIONSHIPS
 InspectorState      Ledger          Graph
     "now"          "before"       "connected"
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                Context Compiler
                       │
                       ▼
                 Agent Context
```

---

## 2. Invariant Rules
1. **Kernel Never Thinks**: No internal LLMs, no automation heuristics, no generative extrapolation.
2. **Kernel Owns State**: All live truth lives in `InspectorState`. Outside consumers receive read-only compiled snapshots.
3. **Deterministic Persistence**: Every event entering the system is recorded to an append-only SQLite WAL ledger.
4. **Domain Neutrality**: The Kernel contains no hardcoded robotics, OS, or browser logic; domain specifics belong entirely to adapters.
