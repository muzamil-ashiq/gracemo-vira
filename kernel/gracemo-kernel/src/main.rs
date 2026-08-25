use axum::{
    extract::State,
    response::{
        sse::{Event as SseEvent, KeepAlive, Sse},
        IntoResponse, Json,
    },
    routing::{get, post},
    Router,
};
use gracemo_types::{Event, EventType};
use serde_json::json;
use std::{net::SocketAddr, sync::Arc};
use tokio::sync::{broadcast, RwLock};
use tower_http::cors::CorsLayer;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Clone)]
pub struct AppState {
    pub tx: broadcast::Sender<Event>,
    pub live_state: Arc<RwLock<serde_json::Value>>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    info!("🧠 Initializing GRaCEmo Kernel Daemon v0.1.0...");

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
    };

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/snapshot", get(snapshot_handler))
        .route("/emit", post(emit_handler))
        .route("/events/live", get(sse_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 7780));
    info!("🚀 GRaCEmo Nervous System HTTP API listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_handler() -> impl IntoResponse {
    Json(json!({
        "status": "healthy",
        "service": "gracemo-kernel",
        "version": "0.1.0"
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
    // Update live memory snapshot based on event
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

    info!(
        "⚡ Event received from [{}] ({:?}): {:?}",
        event.observed_by, event.source, event.event_type
    );

    // Broadcast across event bus subscribers
    let _ = state.tx.send(event);

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
