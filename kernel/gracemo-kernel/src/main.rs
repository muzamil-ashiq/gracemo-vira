use axum::{
    extract::{Query, State},
    response::{
        sse::{Event as SseEvent, KeepAlive, Sse},
        IntoResponse, Json,
    },
    routing::{get, post},
    Router,
};
use gracemo_types::{Event, EventType};
use rusqlite::Connection;
use serde::Deserialize;
use serde_json::json;
use std::{
    fs,
    net::SocketAddr,
    path::PathBuf,
    sync::{Arc, Mutex},
};
use tokio::{
    io::{AsyncBufReadExt, BufReader},
    net::UnixListener,
    sync::{broadcast, RwLock},
};
use tower_http::cors::CorsLayer;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Clone)]
pub struct AppState {
    pub tx: broadcast::Sender<Event>,
    pub live_state: Arc<RwLock<serde_json::Value>>,
    pub db: Arc<Mutex<Connection>>,
}

#[derive(Deserialize)]
struct HistoryQuery {
    limit: Option<usize>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    info!("🧠 Initializing GRaCEmo Kernel Daemon v0.0.1...");

    // 1. Initialize SQLite Append-Only Ledger
    let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let db_dir = PathBuf::from(&home_dir).join(".gracemo");
    fs::create_dir_all(&db_dir)?;
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
    info!("💾 SQLite Ledger active at {:?}", db_path);

    let (tx, _rx) = broadcast::channel::<Event>(2048);
    let state = AppState {
        tx: tx.clone(),
        live_state: Arc::new(RwLock::new(json!({
            "status": "online",
            "robot_position": null,
            "battery": null,
            "last_vision_detection": null,
            "last_voice_command": null,
        }))),
        db: Arc::new(Mutex::new(conn)),
    };

    // 2. Start Unix Domain Socket Listener (/tmp/gracemo.sock)
    let socket_path = "/tmp/gracemo.sock";
    let _ = fs::remove_file(socket_path);
    let unix_listener = UnixListener::bind(socket_path)?;
    info!("🔌 Unix Domain Socket listening at {}", socket_path);

    let socket_state = state.clone();
    tokio::spawn(async move {
        while let Ok((stream, _)) = unix_listener.accept().await {
            let state_clone = socket_state.clone();
            tokio::spawn(async move {
                let reader = BufReader::new(stream);
                let mut lines = reader.lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    if let Ok(event) = serde_json::from_str::<Event>(&line) {
                        process_event(state_clone.clone(), event).await;
                    }
                }
            });
        }
    });

    // 3. Start Axum HTTP REST & SSE API
    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/snapshot", get(snapshot_handler))
        .route("/emit", post(emit_handler))
        .route("/events/live", get(sse_handler))
        .route("/history", get(history_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 7780));
    info!("🚀 GRaCEmo Nervous System HTTP API listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn process_event(state: AppState, event: Event) {
    // 1. Reconcile Live In-Memory Snapshot
    {
        let mut live = state.live_state.write().await;
        match &event.event_type {
            EventType::RobotPosition { x, y, theta, speed } => {
                live["robot_position"] = json!({ "x": x, "y": y, "theta": theta, "speed": speed });
            }
            EventType::RobotBattery { level, charging } => {
                live["battery"] = json!({ "level": level, "charging": charging });
            }
            EventType::PersonVisible { identity, confidence, distance } => {
                live["last_vision_detection"] = json!({ "identity": identity, "confidence": confidence, "distance": distance });
            }
            EventType::VoiceDetected { transcription, confidence } => {
                live["last_voice_command"] = json!({ "text": transcription, "confidence": confidence });
            }
            _ => {}
        }
    }

    // 2. Persist to SQLite Append-Only Ledger
    let payload_str = serde_json::to_string(&event.event_type).unwrap_or_default();
    let source_str = format!("{:?}", event.source);
    let event_type_name = match &event.event_type {
        EventType::RobotPosition { .. } => "RobotPosition",
        EventType::RobotBattery { .. } => "RobotBattery",
        EventType::ObstacleDetected { .. } => "ObstacleDetected",
        EventType::NavigationArrived { .. } => "NavigationArrived",
        EventType::PersonVisible { .. } => "PersonVisible",
        EventType::ObjectDetected { .. } => "ObjectDetected",
        EventType::VoiceDetected { .. } => "VoiceDetected",
        EventType::VoiceIntent { .. } => "VoiceIntent",
        EventType::ActionRequested(_) => "ActionRequested",
        EventType::AdapterConnected { .. } => "AdapterConnected",
        EventType::AdapterHeartbeat { .. } => "AdapterHeartbeat",
        EventType::ErrorDetected { .. } => "ErrorDetected",
        EventType::Custom { .. } => "Custom",
    };

    if let Ok(db) = state.db.lock() {
        let _ = db.execute(
            "INSERT INTO events (id, timestamp, source, observed_by, event_type, payload) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            (
                event.id.to_string(),
                event.timestamp,
                source_str,
                event.observed_by.clone(),
                event_type_name,
                payload_str,
            ),
        );
    }

    // 3. Broadcast to EventBus Subscribers
    let _ = state.tx.send(event);
}

async fn health_handler() -> impl IntoResponse {
    Json(json!({
        "status": "healthy",
        "service": "gracemo-kernel",
        "version": "0.0.1"
    }))
}

async fn snapshot_handler(State(state): State<AppState>) -> impl IntoResponse {
    let snapshot = state.live_state.read().await;
    Json((*snapshot).clone())
}

async fn emit_handler(
    State(state): State<AppState>,
    Json(event): Json<Event>,
) -> impl IntoResponse {
    process_event(state, event).await;
    Json(json!({ "status": "emitted" }))
}

async fn sse_handler(State(state): State<AppState>) -> Sse<impl tokio_stream::Stream<Item = Result<SseEvent, axum::Error>>> {
    let mut rx = state.tx.subscribe();
    let stream = async_stream::stream! {
        while let Ok(event) = rx.recv().await {
            if let Ok(data) = serde_json::to_string(&event) {
                yield Ok(SseEvent::default().data(data));
            }
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn history_handler(
    State(state): State<AppState>,
    Query(params): Query<HistoryQuery>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(20).min(100);
    let mut results = Vec::new();

    if let Ok(db) = state.db.lock() {
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

    Json(results)
}
