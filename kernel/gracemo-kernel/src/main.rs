use gracemo_kernel::api::{create_router, process_incoming_event, AppState};
use gracemo_kernel::graph::GraphDb;
use gracemo_kernel::inspector_state::create_shared_state;
use gracemo_kernel::ledger::Ledger;
use gracemo_types::Event;
use std::{fs, net::SocketAddr, path::PathBuf};
use tokio::{
    io::{AsyncBufReadExt, BufReader},
    net::UnixListener,
    sync::broadcast,
};
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    info!("🧠 Initializing GRaCEmo Kernel v0.0.3 (Dual-Memory Grounded Substrate)...");

    let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let db_dir = PathBuf::from(&home_dir).join(".gracemo");
    std::fs::create_dir_all(&db_dir)?;

    // 1. Initialize SQLite Ledger (PAST) & Graph Memory (RELATIONS)
    let ledger = Ledger::open()?;
    let graph_path = db_dir.join("graph.db");
    let graph = GraphDb::open(&graph_path)?;
    info!("🕸️ SQLite Relational Graph active at {:?}", graph_path);

    // 2. Initialize In-Memory InspectorState (NOW)
    let live_state = create_shared_state();
    let (tx, _rx) = broadcast::channel::<Event>(2048);

    let state = AppState {
        tx: tx.clone(),
        live_state: live_state.clone(),
        ledger: ledger.clone(),
        graph: graph.clone(),
    };

    // 3. Start Unix Domain Socket Listener (/tmp/gracemo.sock)
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
                        process_incoming_event(state_clone.clone(), event).await;
                    }
                }
            });
        }
    });

    // 4. Start Axum HTTP REST, Context Compiler & SSE API
    let app = create_router(state);
    let addr = SocketAddr::from(([127, 0, 0, 1], 7780));
    info!("🚀 GRaCEmo Nervous System HTTP API listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
