use gracemo_types::EventType;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Authoritative "NOW" Live Observed State of the Robot and Environment.
/// Kernel owns this state; all truth flows through InspectorState.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectorState {
    pub status: String,
    pub robot_position: Option<PositionState>,
    pub battery: Option<BatteryState>,
    pub last_vision_detection: Option<VisionState>,
    pub last_voice_command: Option<VoiceState>,
    pub current_room: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PositionState {
    pub x: f64,
    pub y: f64,
    pub theta: f64,
    pub speed: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatteryState {
    pub level: f32,
    pub charging: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisionState {
    pub identity: String,
    pub confidence: f32,
    pub distance: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceState {
    pub text: String,
    pub confidence: f32,
}

impl Default for InspectorState {
    fn default() -> Self {
        Self {
            status: "online".to_string(),
            robot_position: None,
            battery: None,
            last_vision_detection: None,
            last_voice_command: None,
            current_room: None,
        }
    }
}

pub type SharedInspectorState = Arc<RwLock<Value>>;

pub fn create_shared_state() -> SharedInspectorState {
    Arc::new(RwLock::new(json!({
        "status": "online",
        "robot_position": null,
        "battery": null,
        "last_vision_detection": null,
        "last_voice_command": null,
        "current_room": "Central Hallway"
    })))
}

pub async fn update_from_event(state: &SharedInspectorState, event_type: &EventType) {
    let mut live = state.write().await;
    match event_type {
        EventType::RobotPosition { x, y, theta, speed } => {
            let room = if *y > 1.0 {
                if *x < 0.0 { "Master Bedroom" } else { "Home Study" }
            } else if *y < -1.0 {
                if *x < 0.0 { "Kitchen & Dining" } else { "Living Room" }
            } else {
                "Central Hallway"
            };
            live["robot_position"] = json!({ "x": x, "y": y, "theta": theta, "speed": speed });
            live["current_room"] = json!(room);
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
