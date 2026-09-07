use crate::ast::{KPipeline, KStage};
use crate::manifest::{CapabilityManifest, TargetLayer};
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum PlannerError {
    #[error("Unknown stage: {0}::{1}")]
    UnknownStage(String, String),
    #[error("Missing required argument '{0}' for stage {1}::{2}")]
    MissingRequiredArg(String, String, String),
}

#[derive(Debug, Clone)]
pub struct PlannedStage {
    pub stage: KStage,
    pub target_layer: TargetLayer,
    pub output_type: String,
}

#[derive(Debug, Clone)]
pub struct KPlan {
    pub stages: Vec<PlannedStage>,
}

pub struct Planner<'a> {
    manifest: &'a CapabilityManifest,
}

impl<'a> Planner<'a> {
    pub fn new(manifest: &'a CapabilityManifest) -> Self {
        Self { manifest }
    }

    pub fn plan(&self, pipeline: &KPipeline) -> Result<KPlan, PlannerError> {
        let mut planned_stages = Vec::new();

        for stage in &pipeline.stages {
            let def = self
                .manifest
                .get(&stage.noun, &stage.verb)
                .ok_or_else(|| PlannerError::UnknownStage(stage.noun.clone(), stage.verb.clone()))?;

            // Validate required args
            for req in &def.required_args {
                if !stage.args.contains_key(req) {
                    return Err(PlannerError::MissingRequiredArg(
                        req.clone(),
                        stage.noun.clone(),
                        stage.verb.clone(),
                    ));
                }
            }

            planned_stages.push(PlannedStage {
                stage: stage.clone(),
                target_layer: def.target_layer.clone(),
                output_type: def.output_type.clone(),
            });
        }

        Ok(KPlan { stages: planned_stages })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::Parser;

    #[test]
    fn test_planner_valid_plan() {
        let manifest = CapabilityManifest::new();
        let planner = Planner::new(&manifest);

        let pipeline = Parser::parse_str(r#"graph::locate[entity: "Coke"] | nav::reach"#).unwrap();
        let plan = planner.plan(&pipeline).unwrap();

        assert_eq!(plan.stages.len(), 2);
        assert_eq!(plan.stages[0].target_layer, TargetLayer::Level3MNSE);
        assert_eq!(plan.stages[1].target_layer, TargetLayer::Level2Skill);
    }

    #[test]
    fn test_planner_missing_arg() {
        let manifest = CapabilityManifest::new();
        let planner = Planner::new(&manifest);

        let pipeline = Parser::parse_str(r#"graph::locate"#).unwrap();
        let err = planner.plan(&pipeline).unwrap_err();
        assert_eq!(
            err,
            PlannerError::MissingRequiredArg("entity".into(), "graph".into(), "locate".into())
        );
    }
}
