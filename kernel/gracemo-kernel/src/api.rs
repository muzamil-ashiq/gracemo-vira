use crate::context_compiler::compile_context;
use crate::graph::GraphDb;
use crate::inspector_state::{update_from_event, SharedInspectorState};
use crate::ledger::Ledger;
use axum::{
    extract::{Query, State},
    response::{
        sse::{Event as SseEvent, KeepAlive, Sse},
        IntoResponse, Json,
    },
    routing::{get, post},
    Router,
};
use gracemo_types::Event;
use serde::Deserialize;
use serde_json::json;
use tokio::sync::broadcast;
use tower_http::cors::CorsLayer;

#[derive(Clone)]
pub struct AppState {
    pub tx: broadcast::Sender<Event>,
    pub live_state: SharedInspectorState,
    pub ledger: Ledger,
    pub graph: GraphDb,
}

#[derive(Deserialize)]
pub struct HistoryQuery {
    pub limit: Option<usize>,
}

#[derive(Deserialize)]
pub struct GraphQuery {
    pub object: Option<String>,
}

#[derive(Deserialize)]
pub struct KExecuteRequest {
    pub expression: String,
}

pub fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/snapshot", get(snapshot_handler))
        .route("/state", get(snapshot_handler))
        .route("/context", get(context_handler))
        .route("/graph", get(graph_handler))
        .route("/k/execute", post(k_execute_handler))
        .route("/emit", post(emit_handler))
        .route("/events/live", get(sse_handler))
        .route("/history", get(history_handler))
        .layer(CorsLayer::permissive())
        .with_state(state)
}

pub async fn process_incoming_event(state: AppState, event: Event) {
    // 1. Update InspectorState (NOW)
    update_from_event(&state.live_state, &event.event_type).await;

    // 2. Persist to Ledger (PAST)
    let _ = state.ledger.record_event(&event);

    // 3. Process into Relational Knowledge Graph (RELATIONS)
    let current_room = {
        let read_guard = state.live_state.read().await;
        read_guard
            .get("current_room")
            .and_then(|r| r.as_str())
            .unwrap_or("Central Hallway")
            .to_string()
    };
    let _ = state.graph.process_event(&event, &current_room);

    // 4. Broadcast across EventBus
    let _ = state.tx.send(event);
}

async fn health_handler() -> impl IntoResponse {
    Json(json!({
        "status": "healthy",
        "service": "gracemo-kernel",
        "version": "0.0.3"
    }))
}

#[derive(Deserialize)]
pub struct ContextQuery {
    pub limit: Option<usize>,
    pub format: Option<String>,
}

async fn snapshot_handler(State(state): State<AppState>) -> impl IntoResponse {
    let snapshot = state.live_state.read().await;
    Json((*snapshot).clone())
}

async fn context_handler(
    State(state): State<AppState>,
    Query(params): Query<ContextQuery>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(10).min(50);
    let context = compile_context(&state.live_state, &state.ledger, &state.graph, limit).await;
    match params.format.as_deref() {
        Some("toon") => {
            ([(axum::http::header::CONTENT_TYPE, "text/plain; charset=utf-8")], context.to_toon()).into_response()
        }
        Some("kpipe") | Some("pipe") => {
            ([(axum::http::header::CONTENT_TYPE, "text/plain; charset=utf-8")], context.to_kpipe()).into_response()
        }
        _ => Json(context).into_response(),
    }
}

async fn graph_handler(
    State(state): State<AppState>,
    Query(params): Query<GraphQuery>,
) -> impl IntoResponse {
    if let Some(obj) = params.object {
        match state.graph.query_object_location(&obj) {
            Ok(Some(loc)) => Json(json!({ "found": true, "result": loc })),
            Ok(None) => Json(json!({ "found": false, "message": format!("Object '{}' has not been observed yet in Gazebo", obj) })),
            Err(e) => Json(json!({ "found": false, "error": e.to_string() })),
        }
    } else {
        match state.graph.query_full_graph() {
            Ok(graph) => Json(graph),
            Err(e) => Json(json!({ "error": e.to_string() })),
        }
    }
}

async fn emit_handler(
    State(state): State<AppState>,
    Json(event): Json<Event>,
) -> impl IntoResponse {
    process_incoming_event(state, event).await;
    Json(json!({ "status": "emitted" }))
}

async fn sse_handler(
    State(state): State<AppState>,
) -> Sse<impl tokio_stream::Stream<Item = Result<SseEvent, axum::Error>>> {
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
    let events = state.ledger.query_recent(limit);
    Json(events)
}

async fn k_execute_handler(
    Json(req): Json<KExecuteRequest>,
) -> impl IntoResponse {
    match gracemo_k::execute_k_expression(&req.expression) {
        Ok(summary) => Json(json!({ "success": true, "result": summary })).into_response(),
        Err(e) => (
            axum::http::StatusCode::BAD_REQUEST,
            Json(json!({ "success": false, "error": e })),
        )
            .into_response(),
    }
}

