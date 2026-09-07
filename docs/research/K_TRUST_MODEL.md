# K Trust Model & Hallucination Resistance Specification

## 1. The Core Research Problem
Traditional LLM-driven robotics platforms suffer from **hallucination in memory and perception**: when asked about previous observations, ungrounded LLMs fabricate plausible-sounding coordinates, timestamps, and events.

---

## 2. The MNSE Trust Invariant
MNSE solves this at the architectural layer:
1. **Separation of Intelligence and Truth**: Intelligence (LLM) resides outside the Kernel; Authoritative Truth (InspectorState & Ledger) resides inside the Kernel.
2. **Deterministic Querying**: Context compilers output purely observed telemetry without generative extrapolation.
3. **Provable Ledger Chain**: Every fact returned to the agent has an immutable timestamp, observer ID, and raw payload stored in SQLite WAL storage.
