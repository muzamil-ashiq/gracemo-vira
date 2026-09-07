# Event Ledger — Persistent Experiential Record

## 1. Role of the Event Ledger
The `Event Ledger` represents the **"PAST"** dimension of the MNSE Kernel. It stores an append-only, chronologically indexed record of all events observed by the robot.

---

## 2. Storage & Schema
- Backed by **SQLite with Write-Ahead Logging (WAL)** at `~/.gracemo/ledger.db`.
- Schema:
  ```sql
  CREATE TABLE events (
      id TEXT PRIMARY KEY,
      timestamp INTEGER NOT NULL,
      source TEXT NOT NULL,
      observed_by TEXT NOT NULL,
      event_type TEXT NOT NULL,
      payload TEXT NOT NULL
  );
  CREATE INDEX idx_events_ts ON events(timestamp DESC);
  ```

---

## 3. Query Guarantees
- Provides deterministic historical retrieval for questions such as *"What did you see yesterday at 10:00?"*
- Eliminates AI hallucination by returning verified database facts.
