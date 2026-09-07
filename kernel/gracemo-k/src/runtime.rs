use crate::ast::KValue;
use crate::manifest::TargetLayer;
use crate::planner::KPlan;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum RuntimeError {
    #[error("Stage execution failed: {0}")]
    StageFailed(String),
    #[error("Timeout during stage {0}::{1}")]
    Timeout(String, String),
    #[error("Dispatcher error: {0}")]
    DispatcherError(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StageResult {
    pub stage_index: usize,
    pub noun: String,
    pub verb: String,
    pub success: bool,
    pub output: Option<KValue>,
    pub execution_time_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionSummary {
    pub total_stages: usize,
    pub completed_stages: usize,
    pub success: bool,
    pub stage_results: Vec<StageResult>,
}

pub struct ExecutionContext {
    pub variables: HashMap<String, KValue>,
    pub pipe_context: Option<KValue>,
}

impl ExecutionContext {
    pub fn new() -> Self {
        Self {
            variables: HashMap::new(),
            pipe_context: None,
        }
    }
}

impl Default for ExecutionContext {
    fn default() -> Self {
        Self::new()
    }
}

pub struct KRuntime;

impl KRuntime {
    pub fn new() -> Self {
        Self
    }

    /// Executes a planned pipeline deterministically
    pub fn execute(&self, plan: &KPlan) -> Result<ExecutionSummary, RuntimeError> {
        let mut ctx = ExecutionContext::new();
        let mut results = Vec::new();

        for (idx, planned_stage) in plan.stages.iter().enumerate() {
            let stage = &planned_stage.stage;
            let start = std::time::Instant::now();

            // Mock/Local deterministic execution of recognized primitives
            let stage_output = match planned_stage.target_layer {
                TargetLayer::Level3MNSE => {
                    // Query MNSE Graph or Memory
                    if stage.noun == "graph" && stage.verb == "locate" {
                        let _entity = stage.args.get("entity").and_then(|v| match v {
                            KValue::String(s) => Some(s.clone()),
                            _ => None,
                        }).unwrap_or_else(|| "unknown".into());

                        // Returns simulated spatial entity coordinate
                        Some(KValue::Coordinates { x: -5.0, y: 1.4, z: None })
                    } else {
                        Some(KValue::String("ok".into()))
                    }
                }
                TargetLayer::Level2Skill => {
                    // Skill dispatch
                    Some(KValue::String("completed".into()))
                }
                TargetLayer::Level1Spine => {
                    Some(KValue::String("applied".into()))
                }
            };

            let duration = start.elapsed().as_millis() as u64;
            ctx.pipe_context = stage_output.clone();

            results.push(StageResult {
                stage_index: idx,
                noun: stage.noun.clone(),
                verb: stage.verb.clone(),
                success: true,
                output: stage_output,
                execution_time_ms: duration,
            });
        }

        Ok(ExecutionSummary {
            total_stages: plan.stages.len(),
            completed_stages: results.len(),
            success: true,
            stage_results: results,
        })
    }
}

impl Default for KRuntime {
    fn default() -> Self {
        Self::new()
    }
}
