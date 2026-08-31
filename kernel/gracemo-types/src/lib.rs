use chrono::Utc;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Source of an event entering the nervous system
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum EventSource {
    RobotBridge,
    Vision,
    Voice,
    Sensor,
    Brain,
    System,
    Custom(String),
}

/// Action types dispatched by the Kernel to actuators / adapters
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "action", content = "params")]
pub enum RobotAction {
    Speak { text: String },
    NavigateTo { x: f64, y: f64 },
    LookAt { x: f32, y: f32, z: f32 },
    Express { emotion: String },
    Stop,
}

/// Strongly-typed event payloads for physical awareness and reasoning
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum EventType {
    // SENSORY: Robot Telemetry & Navigation
    RobotPosition {
        x: f64,
        y: f64,
        theta: f64,
        speed: f64,
    },
    RobotBattery {
        level: u8,
        charging: bool,
    },
    ObstacleDetected {
        distance: f64,
        direction: String,
    },
    NavigationArrived {
        destination: String,
        success: bool,
    },

    // SENSORY: Vision
    PersonVisible {
        identity: String,
        confidence: f32,
        distance: Option<f32>,
    },
    ObjectDetected {
        class_name: String,
        confidence: f32,
        x: f32,
        y: f32,
    },

    // SENSORY: Voice & Interaction
    VoiceDetected {
        transcription: String,
        confidence: Option<f32>,
    },
    VoiceIntent {
        intent: String,
        entities: serde_json::Value,
    },

    // ACTUATION: Actions Requested by Brain or Reflex Loops
    ActionRequested(RobotAction),

    // SYSTEM / LIFECYCLE
    AdapterConnected {
        name: String,
    },
    AdapterHeartbeat {
        name: String,
    },
    ErrorDetected {
        error: String,
        context: Option<String>,
    },
    Custom {
        name: String,
        payload: serde_json::Value,
    },
}

/// Canonical Event Envelope passing through Tokio EventBus
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    pub id: Uuid,
    pub timestamp: i64,
    pub source: EventSource,
    pub observed_by: String,
    pub event_type: EventType,
    #[serde(default)]
    pub parent_event_id: Option<Uuid>,
}

impl Event {
    pub fn new(source: EventSource, observed_by: impl Into<String>, event_type: EventType) -> Self {
        Self {
            id: Uuid::new_v4(),
            timestamp: Utc::now().timestamp(),
            source,
            observed_by: observed_by.into(),
            event_type,
            parent_event_id: None,
        }
    }
}
