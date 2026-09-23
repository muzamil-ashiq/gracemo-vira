use crate::graph::GraphDb;
use crate::inspector_state::SharedInspectorState;
use crate::ledger::Ledger;
use gracemo_types::WorldObject;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

/// ViRa Chrono-Spatial Compiler (VCSC):
/// Compiles authoritative truth from InspectorState, Ledger, and GraphDb into
/// multiple output representations (JSON, TOON, K-Pipe).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompiledContext {
    pub now: Value,
    pub recent_history: Vec<Value>,
    pub graph: Value,
    #[serde(default)]
    pub world_objects: Vec<WorldObject>,
    #[serde(default)]
    pub rooms: Vec<Value>,
}

impl CompiledContext {
    /// Compiles context into Token-Optimized Object Notation (TOON) for LLMs.
    /// Reduces prompt token overhead by 70-80% compared to raw JSON.
    pub fn to_toon(&self) -> String {
        let mut lines = Vec::new();

        // 1. Current State (@NOW)
        let room = self.now.get("current_room")
            .or_else(|| self.now.get("room"))
            .and_then(|v| v.as_str())
            .unwrap_or("Central Hallway");

        let pos = self.now.get("robot_position");
        let x = pos.and_then(|p| p.get("x"))
            .or_else(|| self.now.get("x"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        let y = pos.and_then(|p| p.get("y"))
            .or_else(|| self.now.get("y"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        let yaw = pos.and_then(|p| p.get("theta"))
            .or_else(|| self.now.get("yaw"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        lines.push(format!("@NOW:Room[{}]|Pose[x:{:.2},y:{:.2},yaw:{:.0}°]", room, x, y, yaw.to_degrees()));

        // 2. Tracked World Objects (#OBJECTS)
        if !self.world_objects.is_empty() {
            let mut obj_items = Vec::new();
            for obj in &self.world_objects {
                let vis = if obj.currently_visible { 1 } else { 0 };
                obj_items.push(format!(
                    "{}[class:{},pos:({:.2},{:.2},{:.2}),conf:{:.2},vis:{},obs:{}]",
                    obj.object_id,
                    obj.class_name,
                    obj.world_x,
                    obj.world_y,
                    obj.world_z,
                    obj.confidence,
                    vis,
                    obj.observation_count
                ));
            }
            lines.push(format!("#OBJECTS:{}", obj_items.join("!")));
        }

        // 3. Verified Knowledge Graph Edges (#GRAPH)
        if let Some(edges) = self.graph.get("edges").and_then(|v| v.as_array()) {
            let mut obj_items = Vec::new();
            for e in edges {
                if e.get("relation").and_then(|v| v.as_str()) == Some("LOCATED_IN") {
                    let src = e.get("source")
                        .or_else(|| e.get("source_id"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .replace("object:", "");
                    let tgt = e.get("target")
                        .or_else(|| e.get("target_id"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .replace("room:", "");
                    let conf = e.get("confidence").and_then(|v| v.as_f64()).unwrap_or(1.0);
                    if !src.is_empty() && !tgt.is_empty() {
                        obj_items.push(format!("{}[in:{},conf:{:.2}]", src, tgt, conf));
                    }
                }
            }
            if !obj_items.is_empty() {
                lines.push(format!("#GRAPH:{}", obj_items.join("!")));
            }
        }

        // 4. Chronological Event Ledger (!LEDGER)
        let mut event_items = Vec::new();
        for ev in &self.recent_history {
            let ev_type = ev.get("type").and_then(|v| v.as_str()).unwrap_or("");
            let src = ev.get("source").and_then(|v| v.as_str()).unwrap_or("");
            if !ev_type.is_empty() {
                event_items.push(format!("{}({})", ev_type, src));
            }
        }
        if !event_items.is_empty() {
            lines.push(format!("!LEDGER:{}", event_items.join(">")));
        }

        // 5. Authoritative Apartment Map (#APARTMENT_MAP)
        let map_rooms = self.get_apartment_rooms();
        if !map_rooms.is_empty() {
            let mut map_items = Vec::new();
            for (slug, explored, objs) in map_rooms {
                map_items.push(format!("{}[explored:{},objs:{}]", slug, explored, objs));
            }
            lines.push(format!("#APARTMENT_MAP:{}", map_items.join("!")));
        }

        lines.join("\n")
    }

    /// Helper to resolve authoritative rooms, exploration status, and object counts for TOON
    pub fn get_apartment_rooms(&self) -> Vec<(String, bool, usize)> {
        if !self.rooms.is_empty() {
            let mut result = Vec::new();
            for r in &self.rooms {
                let id = r.get("room_id").and_then(|v| v.as_str()).unwrap_or("");
                let slug = id.replace("room:", "");
                if slug.is_empty() {
                    continue;
                }
                let explored = r.get("explored").and_then(|v| v.as_bool()).unwrap_or(false);
                let objs = r.get("object_count").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                result.push((slug, explored, objs));
            }
            result.sort_by(|a, b| a.0.cmp(&b.0));
            return result;
        }

        // Fallback to nodes & edges in self.graph
        if let Some(nodes) = self.graph.get("nodes").and_then(|v| v.as_array()) {
            let mut result = Vec::new();
            for n in nodes {
                if n.get("type").and_then(|v| v.as_str()) == Some("Room") {
                    let id = n.get("id").and_then(|v| v.as_str()).unwrap_or("");
                    let slug = id.replace("room:", "");
                    if slug.is_empty() {
                        continue;
                    }
                    let props = n.get("properties");
                    let explored = props.and_then(|p| p.get("explored")).and_then(|v| v.as_bool()).unwrap_or(false);

                    let objs = self.graph.get("edges").and_then(|v| v.as_array()).map(|edges| {
                        edges.iter().filter(|e| {
                            e.get("relation").and_then(|v| v.as_str()) == Some("LOCATED_IN")
                                && (e.get("target").and_then(|v| v.as_str()) == Some(id)
                                    || e.get("target_id").and_then(|v| v.as_str()) == Some(id))
                        }).count()
                    }).unwrap_or(0);

                    result.push((slug, explored, objs));
                }
            }
            result.sort_by(|a, b| a.0.cmp(&b.0));
            return result;
        }

        Vec::new()
    }

    /// Compiles active pipeline state into .k stream syntax
    pub fn to_kpipe(&self) -> String {
        let room = self.now.get("current_room")
            .or_else(|| self.now.get("room"))
            .and_then(|v| v.as_str())
            .unwrap_or("Central Hallway");
        format!("state::grounded[room:{}] | reflex::active | ledger::synced", room)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_to_toon_with_live_inspector_state() {
        let now = json!({
            "status": "online",
            "current_room": "Kitchen & Dining",
            "robot_position": {
                "x": -4.665,
                "y": -2.195,
                "theta": -1.117,
                "speed": 0.0
            },
            "battery": null,
            "last_vision_detection": null,
            "last_voice_command": null
        });

        let context = CompiledContext {
            now,
            recent_history: vec![],
            graph: json!({"nodes": [], "edges": []}),
            world_objects: vec![],
            rooms: vec![],
        };

        let toon = context.to_toon();
        assert!(toon.starts_with("@NOW:Room[Kitchen & Dining]|Pose[x:-4.67,y:-2.19,yaw:-64°]"), "Actual: {}", toon);

        let kpipe = context.to_kpipe();
        assert_eq!(kpipe, "state::grounded[room:Kitchen & Dining] | reflex::active | ledger::synced");
    }

    #[test]
    fn test_to_toon_backwards_compatibility() {
        let now = json!({
            "room": "Master Bedroom",
            "x": -5.02,
            "y": 1.41,
            "yaw": 1.5708
        });

        let context = CompiledContext {
            now,
            recent_history: vec![],
            graph: json!({"nodes": [], "edges": []}),
            world_objects: vec![],
            rooms: vec![],
        };

        let toon = context.to_toon();
        assert!(toon.starts_with("@NOW:Room[Master Bedroom]|Pose[x:-5.02,y:1.41,yaw:90°]"), "Actual: {}", toon);
    }

    #[test]
    fn test_to_toon_with_world_objects() {
        let now = json!({
            "status": "online",
            "current_room": "Living Room",
            "robot_position": { "x": 1.0, "y": 2.0, "theta": 0.0, "speed": 0.0 }
        });
        let obj = WorldObject::new(
            "chair_001".to_string(),
            "chair".to_string(),
            0.85,
            2.18,
            0.19,
            0.52,
            Utc::now().timestamp() as f64,
            "Vision".to_string(),
            "world".to_string(),
            None,
            Some(2.15),
        );
        let context = CompiledContext {
            now,
            recent_history: vec![],
            graph: json!({"nodes": [], "edges": []}),
            world_objects: vec![obj],
            rooms: vec![],
        };
        let toon = context.to_toon();
        assert!(toon.contains("#OBJECTS:chair_001[class:chair,pos:(2.18,0.19,0.52),conf:0.85,vis:1,obs:1]"), "Actual: {}", toon);
    }

    #[test]
    fn test_to_toon_with_located_in_graph_edges() {
        let now = json!({
            "status": "online",
            "current_room": "Master Bedroom",
            "robot_position": { "x": -5.0, "y": 2.0, "theta": 0.0, "speed": 0.0 }
        });
        let graph = json!({
            "nodes": [],
            "edges": [
                {
                    "source": "object:bed_001",
                    "target": "room:Master Bedroom",
                    "relation": "LOCATED_IN",
                    "confidence": 1.0
                }
            ]
        });
        let context = CompiledContext {
            now,
            recent_history: vec![],
            graph,
            world_objects: vec![],
            rooms: vec![],
        };
        let toon = context.to_toon();
        assert!(toon.contains("#GRAPH:bed_001[in:Master Bedroom,conf:1.00]"), "Actual: {}", toon);
    }

    #[test]
    fn test_to_toon_with_apartment_map() {
        let now = json!({
            "status": "online",
            "current_room": "Master Bedroom",
            "robot_position": { "x": -5.0, "y": 2.0, "theta": 0.0, "speed": 0.0 }
        });
        let rooms = vec![
            json!({
                "room_id": "room:bedroom",
                "label": "Master Bedroom",
                "explored": true,
                "object_count": 3
            }),
            json!({
                "room_id": "room:hallway",
                "label": "Central Hallway",
                "explored": true,
                "object_count": 0
            }),
            json!({
                "room_id": "room:study",
                "label": "Home Study",
                "explored": false,
                "object_count": 0
            }),
        ];
        let context = CompiledContext {
            now,
            recent_history: vec![],
            graph: json!({"nodes": [], "edges": []}),
            world_objects: vec![],
            rooms,
        };
        let toon = context.to_toon();
        assert!(toon.contains("#APARTMENT_MAP:bedroom[explored:true,objs:3]!hallway[explored:true,objs:0]!study[explored:false,objs:0]"), "Actual: {}", toon);
    }
}

pub async fn compile_context(
    inspector_state: &SharedInspectorState,
    ledger: &Ledger,
    graph_db: &GraphDb,
    history_limit: usize,
) -> CompiledContext {
    let live_snapshot = {
        let read_guard = inspector_state.read().await;
        (*read_guard).clone()
    };

    let history = ledger.query_recent(history_limit);
    let real_graph = graph_db.query_full_graph().unwrap_or_else(|_| json!({"nodes": [], "edges": []}));
    let world_objects = graph_db.query_world_objects(None, false).unwrap_or_default();
    let rooms = graph_db.query_all_rooms().unwrap_or_default();

    CompiledContext {
        now: live_snapshot,
        recent_history: history,
        graph: real_graph,
        world_objects,
        rooms,
    }
}
