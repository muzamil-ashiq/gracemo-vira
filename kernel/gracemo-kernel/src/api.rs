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

#[derive(Deserialize)]
pub struct WorldObjectsQuery {
    pub class: Option<String>,
    pub visible_only: Option<bool>,
    pub nearest_x: Option<f64>,
    pub nearest_y: Option<f64>,
    pub nearest_z: Option<f64>,
    pub id: Option<String>,
    pub room: Option<String>,
}

pub fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/snapshot", get(snapshot_handler))
        .route("/state", get(snapshot_handler))
        .route("/context", get(context_handler))
        .route("/graph", get(graph_handler))
        .route("/world/objects", get(world_objects_handler))
        .route("/world/rooms", get(world_rooms_handler))
        .route("/world/rooms/:room_id", get(world_room_handler))
        .route("/world/rooms/:room_id/objects", get(world_room_objects_handler))
        .route("/world/exploration/status", get(world_exploration_status_handler))
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

    // Sync authoritative world objects to InspectorState
    if let Ok(objs) = state.graph.query_world_objects(None, false) {
        let mut live = state.live_state.write().await;
        live["world_objects"] = json!(objs);
    }

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
    let objs = state.graph.query_world_objects(None, false).unwrap_or_default();
    let mut snapshot = state.live_state.read().await.clone();
    snapshot["world_objects"] = json!(objs);
    Json(snapshot)
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

async fn world_objects_handler(
    State(state): State<AppState>,
    Query(params): Query<WorldObjectsQuery>,
) -> impl IntoResponse {
    let visible_only = params.visible_only.unwrap_or(false);

    if let Some(id) = params.id {
        match state.graph.query_world_object_by_id(&id) {
            Ok(Some(obj)) => Json(json!({ "found": true, "object": obj })).into_response(),
            Ok(None) => Json(json!({ "found": false, "message": format!("Object '{}' not found in world", id) })).into_response(),
            Err(e) => Json(json!({ "found": false, "error": e.to_string() })).into_response(),
        }
    } else if let Some(room) = params.room {
        match state.graph.query_objects_in_room(&room) {
            Ok(objs) => {
                let filtered: Vec<_> = if visible_only {
                    objs.into_iter().filter(|o| o.currently_visible).collect()
                } else {
                    objs
                };
                Json(json!({ "objects": filtered, "count": filtered.len(), "room": room })).into_response()
            }
            Err(e) => Json(json!({ "error": e.to_string() })).into_response(),
        }
    } else if let (Some(nx), Some(ny)) = (params.nearest_x, params.nearest_y) {
        let nz = params.nearest_z.unwrap_or(0.0);
        let class_name = params.class.as_deref().unwrap_or("");
        match state.graph.query_nearest_world_object(class_name, nx, ny, nz, visible_only) {
            Ok(Some(obj)) => Json(json!({ "found": true, "object": obj })).into_response(),
            Ok(None) => Json(json!({ "found": false, "message": format!("No matching objects found for nearest query (class: '{}')", class_name) })).into_response(),
            Err(e) => Json(json!({ "found": false, "error": e.to_string() })).into_response(),
        }
    } else {
        match state.graph.query_world_objects(params.class.as_deref(), visible_only) {
            Ok(objs) => Json(json!({ "objects": objs, "count": objs.len() })).into_response(),
            Err(e) => Json(json!({ "error": e.to_string() })).into_response(),
        }
    }
}

async fn world_rooms_handler(
    State(state): State<AppState>,
) -> impl IntoResponse {
    match state.graph.query_all_rooms() {
        Ok(rooms) => Json(json!({ "rooms": rooms, "count": rooms.len() })).into_response(),
        Err(e) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn world_room_handler(
    State(state): State<AppState>,
    axum::extract::Path(room_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    match state.graph.get_room(&room_id) {
        Ok(Some(room)) => Json(room).into_response(),
        Ok(None) => (
            axum::http::StatusCode::NOT_FOUND,
            Json(json!({ "error": format!("Room '{}' not found", room_id) })),
        )
            .into_response(),
        Err(e) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn world_room_objects_handler(
    State(state): State<AppState>,
    axum::extract::Path(room_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    match state.graph.query_objects_in_room(&room_id) {
        Ok(objs) => Json(json!({ "room": room_id, "objects": objs, "count": objs.len() })).into_response(),
        Err(e) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
    }
}

async fn world_exploration_status_handler(
    State(state): State<AppState>,
) -> impl IntoResponse {
    match state.graph.get_exploration_status() {
        Ok(status) => Json(status).into_response(),
        Err(e) => (
            axum::http::StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": e.to_string() })),
        )
            .into_response(),
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

