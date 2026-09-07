use anyhow::Result;
use gracemo_types::Event;
use rusqlite::Connection;
use serde_json::{json, Value};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tracing::info;

/// Persistent "PAST" Record of Observed Events.
/// Implemented as an append-only SQLite WAL ledger.
#[derive(Clone)]
pub struct Ledger {
    conn: Arc<Mutex<Connection>>,
}

impl Ledger {
    pub fn open() -> Result<Self> {
        let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
        let db_dir = PathBuf::from(&home_dir).join(".gracemo");
        std::fs::create_dir_all(&db_dir)?;
        let db_path = db_dir.join("ledger.db");

        let conn = Connection::open(&db_path)?;
        conn.execute_batch(
            "PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             CREATE TABLE IF NOT EXISTS events (
                 id TEXT PRIMARY KEY,
                 timestamp INTEGER NOT NULL,
                 source TEXT NOT NULL,
                 observed_by TEXT NOT NULL,
                 event_type TEXT NOT NULL,
                 payload TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp DESC);",
        )?;
        info!("💾 SQLite Event Ledger active at {:?}", db_path);

        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
        })
    }

    pub fn record_event(&self, event: &Event) -> Result<()> {
        let payload_str = serde_json::to_string(&event.event_type).unwrap_or_default();
        let source_str = format!("{:?}", event.source);
        let event_type_name = format!("{:?}", event.event_type);
        let short_name = event_type_name.split('{').next().unwrap_or("Unknown").trim();

        if let Ok(db) = self.conn.lock() {
            db.execute(
                "INSERT INTO events (id, timestamp, source, observed_by, event_type, payload) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                (
                    event.id.to_string(),
                    event.timestamp,
                    source_str,
                    event.observed_by.clone(),
                    short_name,
                    payload_str,
                ),
            )?;
        }
        Ok(())
    }

    pub fn query_recent(&self, limit: usize) -> Vec<Value> {
        let mut results = Vec::new();
        if let Ok(db) = self.conn.lock() {
            if let Ok(mut stmt) = db.prepare(
                "SELECT id, timestamp, source, observed_by, event_type, payload FROM events ORDER BY timestamp DESC LIMIT ?1",
            ) {
                if let Ok(rows) = stmt.query_map([limit], |row| {
                    Ok(json!({
                        "id": row.get::<_, String>(0)?,
                        "timestamp": row.get::<_, i64>(1)?,
                        "source": row.get::<_, String>(2)?,
                        "observed_by": row.get::<_, String>(3)?,
                        "event_type": row.get::<_, String>(4)?,
                        "payload": row.get::<_, String>(5)?,
                    }))
                }) {
                    for r in rows.flatten() {
                        results.push(r);
                    }
                }
            }
        }
        results
    }
}
