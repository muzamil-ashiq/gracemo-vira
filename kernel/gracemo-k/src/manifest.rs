use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum TargetLayer {
    Level3MNSE,
    Level2Skill,
    Level1Spine,
}

#[derive(Debug, Clone)]
pub struct StageDefinition {
    pub noun: String,
    pub verb: String,
    pub target_layer: TargetLayer,
    pub required_args: Vec<String>,
    pub optional_args: Vec<String>,
    pub output_type: String,
}

pub struct CapabilityManifest {
    stages: HashMap<String, StageDefinition>,
}

impl CapabilityManifest {
    pub fn new() -> Self {
        let mut manifest = Self {
            stages: HashMap::new(),
        };
        manifest.register_defaults();
        manifest
    }

    pub fn register(&mut self, def: StageDefinition) {
        let key = format!("{}::{}", def.noun, def.verb);
        self.stages.insert(key, def);
    }

    pub fn get(&self, noun: &str, verb: &str) -> Option<&StageDefinition> {
        let key = format!("{}::{}", noun, verb);
        self.stages.get(&key)
    }

    fn register_defaults(&mut self) {
        // Level 3 MNSE stages
        self.register(StageDefinition {
            noun: "graph".into(),
            verb: "locate".into(),
            target_layer: TargetLayer::Level3MNSE,
            required_args: vec!["entity".into()],
            optional_args: vec!["max_distance".into()],
            output_type: "SpatialEntity".into(),
        });

        self.register(StageDefinition {
            noun: "graph".into(),
            verb: "query".into(),
            target_layer: TargetLayer::Level3MNSE,
            required_args: vec!["query".into()],
            optional_args: vec![],
            output_type: "GraphResultSet".into(),
        });

        self.register(StageDefinition {
            noun: "memory".into(),
            verb: "recall".into(),
            target_layer: TargetLayer::Level3MNSE,
            required_args: vec!["query".into()],
            optional_args: vec!["limit".into()],
            output_type: "LedgerRecords".into(),
        });

        // Level 2 Embodied Skills
        self.register(StageDefinition {
            noun: "nav".into(),
            verb: "reach".into(),
            target_layer: TargetLayer::Level2Skill,
            required_args: vec![], // Can inherit target from upstream pipe or explicit arg
            optional_args: vec!["target".into(), "clearance".into(), "timeout".into()],
            output_type: "NavResult".into(),
        });

        self.register(StageDefinition {
            noun: "nav".into(),
            verb: "goto_pose".into(),
            target_layer: TargetLayer::Level2Skill,
            required_args: vec!["x".into(), "y".into()],
            optional_args: vec!["yaw".into()],
            output_type: "NavResult".into(),
        });

        self.register(StageDefinition {
            noun: "vision".into(),
            verb: "scan".into(),
            target_layer: TargetLayer::Level2Skill,
            required_args: vec![],
            optional_args: vec!["target".into(), "timeout".into()],
            output_type: "VisualDetections".into(),
        });

        self.register(StageDefinition {
            noun: "arm".into(),
            verb: "grasp".into(),
            target_layer: TargetLayer::Level2Skill,
            required_args: vec![],
            optional_args: vec!["object_id".into(), "effort".into()],
            output_type: "GraspResult".into(),
        });
    }
}

impl Default for CapabilityManifest {
    fn default() -> Self {
        Self::new()
    }
}
