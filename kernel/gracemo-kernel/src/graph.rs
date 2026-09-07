use anyhow::Result;
use chrono::Utc;
use gracemo_types::{Event, EventType};
use rusqlite::{params, Connection};
use serde_json::{json, Value};
use std::path::Path;
use std::sync::{Arc, Mutex};
use tracing::info;

#[derive(Clone)]
pub struct GraphDb {
    conn: Arc<Mutex<Connection>>,
}

impl GraphDb {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let conn = Connection::open(path)?;

        // WAL mode for maximum concurrency and durability
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "NORMAL")?;
        conn.pragma_update(None, "foreign_keys", "ON")?;

        let db = Self {
            conn: Arc::new(Mutex::new(conn)),
        };
        db.migrate()?;
        db.init_apartment_rooms()?;

        Ok(db)
    }

    fn migrate(&self) -> Result<()> {
        let conn = self.conn.lock().unwrap();

        // 1. Nodes table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                properties JSON,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )",
            [],
        )?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)",
            [],
        )?;

        // 2. Edges table (Relational spatial & causal truth)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight INTEGER DEFAULT 1,
                confidence REAL DEFAULT 1.0,
                properties JSON,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (source_id, target_id, relation),
                FOREIGN KEY(source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY(target_id) REFERENCES nodes(id) ON DELETE CASCADE
            )",
            [],
        )?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)",
            [],
        )?;
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)",
            [],
        )?;

        Ok(())
    }

    /// Seed the canonical physical apartment topology
    fn init_apartment_rooms(&self) -> Result<()> {
        let rooms = vec![
            ("room:bedroom", "Room", "Master Bedroom", json!({
                "x_min": -9.0, "x_max": 0.0, "y_min": 1.0, "y_max": 7.0,
                "portal_id": "portal:bedroom", "target_x": -5.0, "target_y": 2.8,
                "provenance": "seeded_topology"
            })),
            ("room:study",   "Room", "Home Study", json!({
                "x_min": 0.0, "x_max": 9.0, "y_min": 1.0, "y_max": 7.0,
                "portal_id": "portal:study", "target_x": 4.0, "target_y": 3.8,
                "provenance": "seeded_topology"
            })),
            ("room:kitchen", "Room", "Kitchen & Dining", json!({
                "x_min": -9.0, "x_max": 0.0, "y_min": -7.0, "y_max": -1.0,
                "portal_id": "portal:kitchen", "target_x": -4.5, "target_y": -2.5,
                "provenance": "seeded_topology"
            })),
            ("room:living",  "Room", "Living Room", json!({
                "x_min": 0.0, "x_max": 9.0, "y_min": -7.0, "y_max": -1.0,
                "portal_id": "portal:living", "target_x": 4.0, "target_y": -2.5,
                "provenance": "seeded_topology"
            })),
            ("room:hallway", "Room", "Central Hallway", json!({
                "x_min": -9.0, "x_max": 9.0, "y_min": -1.0, "y_max": 1.0,
                "target_x": 0.0, "target_y": 0.0,
                "provenance": "seeded_topology"
            })),
        ];

        for (id, node_type, label, props) in rooms {
            self.upsert_node(id, node_type, label, Some(props))?;
        }

        // Topological Doorway Portals derived from verified apartment_floor.world geometry
        let portals = vec![
            ("portal:bedroom", "Portal", "Bedroom Doorway", json!({
                "door_x": -5.0, "door_y": 1.0, "width": 1.2,
                "approach_x": -5.0, "approach_y": 0.0, "approach_yaw": 1.5708,
                "threshold_x": -5.0, "threshold_y": 1.4, "threshold_yaw": 1.5708,
                "target_x": -5.0, "target_y": 2.8,
                "connects_from": "room:hallway", "connects_to": "room:bedroom",
                "provenance": "seeded_topology"
            })),
            ("portal:study", "Portal", "Study Doorway", json!({
                "door_x": 5.0, "door_y": 1.0, "width": 1.2,
                "approach_x": 5.0, "approach_y": 0.0, "approach_yaw": 1.5708,
                "threshold_x": 5.0, "threshold_y": 1.4, "threshold_yaw": 1.5708,
                "target_x": 4.0, "target_y": 3.8,
                "connects_from": "room:hallway", "connects_to": "room:study",
                "provenance": "seeded_topology"
            })),
            ("portal:kitchen", "Portal", "Kitchen Doorway", json!({
                "door_x": -5.0, "door_y": -1.0, "width": 1.2,
                "approach_x": -5.0, "approach_y": 0.0, "approach_yaw": -1.5708,
                "threshold_x": -5.0, "threshold_y": -1.4, "threshold_yaw": -1.5708,
                "target_x": -4.5, "target_y": -2.5,
                "connects_from": "room:hallway", "connects_to": "room:kitchen",
                "provenance": "seeded_topology"
            })),
            ("portal:living", "Portal", "Living Room Doorway", json!({
                "door_x": 5.0, "door_y": -1.0, "width": 1.2,
                "approach_x": 5.0, "approach_y": 0.0, "approach_yaw": -1.5708,
                "threshold_x": 5.0, "threshold_y": -1.4, "threshold_yaw": -1.5708,
                "target_x": 4.0, "target_y": -2.5,
                "connects_from": "room:hallway", "connects_to": "room:living",
                "provenance": "seeded_topology"
            })),
        ];

        for (id, node_type, label, props) in portals {
            self.upsert_node(id, node_type, label, Some(props.clone()))?;
            let from_room = props["connects_from"].as_str().unwrap();
            let to_room = props["connects_to"].as_str().unwrap();
            self.add_edge(from_room, id, "CONNECTS", 1.0, Some(json!({"provenance": "seeded_topology"})))?;
            self.add_edge(id, to_room, "LEADS_TO", 1.0, Some(json!({"provenance": "seeded_topology"})))?;
        }

        // Add Robot self-node
        self.upsert_node("robot:vira", "Robot", "GRaCEmo ViRa", Some(json!({"height": 1.45, "type": "Humanoid Service Robot"})))?;

        Ok(())
    }

    pub fn upsert_node(
        &self,
        id: &str,
        node_type: &str,
        label: &str,
        properties: Option<Value>,
    ) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let now = Utc::now().timestamp();
        let props_str = properties.unwrap_or_else(|| json!({})).to_string();

        conn.execute(
            "INSERT INTO nodes (id, type, label, properties, created_at, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?5)
             ON CONFLICT(id) DO UPDATE SET
                type = excluded.type,
                label = excluded.label,
                properties = excluded.properties,
                updated_at = excluded.updated_at",
            params![id, node_type, label, props_str, now],
        )?;

        Ok(())
    }

    pub fn add_edge(
        &self,
        source_id: &str,
        target_id: &str,
        relation: &str,
        confidence: f32,
        properties: Option<Value>,
    ) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        let now = Utc::now().timestamp();
        let props_str = properties.unwrap_or_else(|| json!({})).to_string();

        conn.execute(
            "INSERT INTO edges (source_id, target_id, relation, weight, confidence, properties, created_at, updated_at)
             VALUES (?1, ?2, ?3, 1, ?4, ?5, ?6, ?6)
             ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                weight = weight + 1,
                confidence = excluded.confidence,
                properties = excluded.properties,
                updated_at = excluded.updated_at",
            params![source_id, target_id, relation, confidence, props_str, now],
        )?;

        Ok(())
    }

    pub fn query_full_graph(&self) -> Result<Value> {
        let conn = self.conn.lock().unwrap();

        let mut nodes_stmt = conn.prepare("SELECT id, type, label, properties, updated_at FROM nodes")?;
        let nodes: Vec<Value> = nodes_stmt
            .query_map([], |row| {
                let props_str: String = row.get(3)?;
                let props: Value = serde_json::from_str(&props_str).unwrap_or(json!({}));
                Ok(json!({
                    "id": row.get::<_, String>(0)?,
                    "type": row.get::<_, String>(1)?,
                    "label": row.get::<_, String>(2)?,
                    "properties": props,
                    "updated_at": row.get::<_, i64>(4)?,
                }))
            })?
            .filter_map(Result::ok)
            .collect();

        let mut edges_stmt = conn.prepare(
            "SELECT source_id, target_id, relation, weight, confidence, properties, updated_at FROM edges"
        )?;
        let edges: Vec<Value> = edges_stmt
            .query_map([], |row| {
                let props_str: String = row.get(5)?;
                let props: Value = serde_json::from_str(&props_str).unwrap_or(json!({}));
                Ok(json!({
                    "source": row.get::<_, String>(0)?,
                    "target": row.get::<_, String>(1)?,
                    "relation": row.get::<_, String>(2)?,
                    "weight": row.get::<_, i32>(3)?,
                    "confidence": row.get::<_, f64>(4)?,
                    "properties": props,
                    "updated_at": row.get::<_, i64>(6)?,
                }))
            })?
            .filter_map(Result::ok)
            .collect();

        Ok(json!({
            "nodes": nodes,
            "edges": edges,
            "node_count": nodes.len(),
            "edge_count": edges.len(),
        }))
    }

    /// Fast lookup: Where is an object located in the apartment?
    pub fn query_object_location(&self, object_name: &str) -> Result<Option<Value>> {
        let conn = self.conn.lock().unwrap();
        let target_node_id = format!("object:{}", object_name.to_lowercase().trim());

        let mut stmt = conn.prepare(
            "SELECT n.label, e.relation, r.label, e.confidence, e.properties, e.updated_at
             FROM edges e
             JOIN nodes n ON e.source_id = n.id
             JOIN nodes r ON e.target_id = r.id
             WHERE e.source_id = ?1
             ORDER BY e.updated_at DESC LIMIT 1"
        )?;

        let result = stmt.query_row(params![target_node_id], |row| {
            let props_str: String = row.get(4)?;
            let props: Value = serde_json::from_str(&props_str).unwrap_or(json!({}));
            Ok(json!({
                "object": row.get::<_, String>(0)?,
                "relation": row.get::<_, String>(1)?,
                "location": row.get::<_, String>(2)?,
                "confidence": row.get::<_, f64>(3)?,
                "properties": props,
                "timestamp": row.get::<_, i64>(5)?,
            }))
        });

        match result {
            Ok(val) => Ok(Some(val)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(anyhow::anyhow!(e)),
        }
    }

fn canonical_room_id(room: &str) -> &'static str {
    let lower = room.to_lowercase();
    if lower.contains("bed") {
        "room:bedroom"
    } else if lower.contains("kitch") {
        "room:kitchen"
    } else if lower.contains("study") {
        "room:study"
    } else if lower.contains("living") {
        "room:living"
    } else {
        "room:hallway"
    }
}

    /// Process live events and build the knowledge graph deterministically
    pub fn process_event(&self, event: &Event, current_room: &str) -> Result<()> {
        match &event.event_type {
            // Real YOLOv11 Visual Detections from Gazebo
            EventType::ObjectDetected { class_name, confidence, x, y } => {
                let obj_id = format!("object:{}", class_name.to_lowercase().trim());
                let room_id = Self::canonical_room_id(current_room);

                // 1. Upsert the object node
                self.upsert_node(
                    &obj_id,
                    "Object",
                    class_name,
                    Some(json!({"x": x, "y": y, "source": "YOLOv11"})),
                )?;

                // 2. Link Object -> LOCATED_IN -> Room
                self.add_edge(
                    &obj_id,
                    room_id,
                    "LOCATED_IN",
                    *confidence,
                    Some(json!({"observed_at": event.timestamp, "x": x, "y": y})),
                )?;

                info!("🕸️ Graph updated: ({}) -[LOCATED_IN]-> ({}) [conf: {:.2}]", class_name, room_id, confidence);
            }

            // Real Odometry / Navigation Arrived
            EventType::NavigationArrived { destination, success } => {
                if *success {
                    let room_id = Self::canonical_room_id(destination);
                    self.add_edge("robot:vira", room_id, "LOCATED_IN", 1.0, Some(json!({"arrived_at": event.timestamp})))?;
                    info!("🕸️ Graph updated: (robot:vira) -[LOCATED_IN]-> ({})", room_id);
                }
            }

            // Human Presence Visible
            EventType::PersonVisible { identity, confidence, distance } => {
                let person_id = format!("person:{}", identity.to_lowercase().trim());
                let room_id = format!("room:{}", current_room.to_lowercase().replace(' ', "_").replace('&', "and").trim());

                self.upsert_node(&person_id, "Person", identity, Some(json!({"distance": distance})))?;
                self.add_edge(&person_id, &room_id, "PRESENT_IN", *confidence, Some(json!({"time": event.timestamp})))?;
            }

            // Custom Facts Remembered via K CLI
            EventType::Custom { name, payload } => {
                if name == "FactRemembered" {
                    if let Some(fact) = payload.get("fact").and_then(|f| f.as_str()) {
                        let fact_id = format!("fact:{}", &event.id.to_string()[..8]);
                        self.upsert_node(&fact_id, "Fact", fact, Some(payload.clone()))?;
                        self.add_edge(&fact_id, "robot:vira", "REMEMBERS", 1.0, None)?;
                    }
                }
            }

            _ => {}
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_seeded_doorway_portals() {
        let db = GraphDb::open(":memory:").expect("Failed to create in-memory db");
        let full = db.query_full_graph().expect("Failed to query graph");
        let nodes = full["nodes"].as_array().expect("nodes must be array");
        let edges = full["edges"].as_array().expect("edges must be array");

        let bedroom_portal = nodes.iter().find(|n| n["id"] == "portal:bedroom").expect("Bedroom portal missing");
        let props = &bedroom_portal["properties"];
        assert_eq!(props["door_x"], -5.0);
        assert_eq!(props["door_y"], 1.0);
        assert_eq!(props["approach_x"], -5.0);
        assert_eq!(props["approach_y"], 0.0);
        assert_eq!(props["threshold_x"], -5.0);
        assert_eq!(props["threshold_y"], 1.4);

        let kitchen_portal = nodes.iter().find(|n| n["id"] == "portal:kitchen").expect("Kitchen portal missing");
        assert_eq!(kitchen_portal["properties"]["door_x"], -5.0);
        assert_eq!(kitchen_portal["properties"]["door_y"], -1.0);

        let study_portal = nodes.iter().find(|n| n["id"] == "portal:study").expect("Study portal missing");
        assert_eq!(study_portal["properties"]["door_x"], 5.0);
        assert_eq!(study_portal["properties"]["door_y"], 1.0);

        let living_portal = nodes.iter().find(|n| n["id"] == "portal:living").expect("Living portal missing");
        assert_eq!(living_portal["properties"]["door_x"], 5.0);
        assert_eq!(living_portal["properties"]["door_y"], -1.0);

        // Verify topological edges
        let connects = edges.iter().find(|e| e["source"] == "room:hallway" && e["target"] == "portal:bedroom" && e["relation"] == "CONNECTS");
        assert!(connects.is_some(), "room:hallway must CONNECT portal:bedroom");

        let leads_to = edges.iter().find(|e| e["source"] == "portal:bedroom" && e["target"] == "room:bedroom" && e["relation"] == "LEADS_TO");
        assert!(leads_to.is_some(), "portal:bedroom must LEAD_TO room:bedroom");
    }
}
