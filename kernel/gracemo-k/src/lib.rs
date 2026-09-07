pub mod ast;
pub mod lexer;
pub mod manifest;
pub mod parser;
pub mod planner;
pub mod runtime;

pub use ast::{KPipeline, KStage, KValue};
pub use lexer::{Lexer, Token};
pub use manifest::{CapabilityManifest, TargetLayer};
pub use parser::Parser;
pub use planner::{KPlan, Planner};
pub use runtime::{ExecutionSummary, KRuntime, RuntimeError, StageResult};

/// Convenience top-level evaluation of a K pipeline string
pub fn execute_k_expression(input: &str) -> Result<ExecutionSummary, String> {
    let pipeline = Parser::parse_str(input)?;
    let manifest = CapabilityManifest::new();
    let planner = Planner::new(&manifest);
    let plan = planner.plan(&pipeline).map_err(|e| e.to_string())?;
    let runtime = KRuntime::new();
    runtime.execute(&plan).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_end_to_end_k_execution() {
        let input = r#"graph::locate[entity: "Coke"] | nav::reach"#;
        let summary = execute_k_expression(input).unwrap();
        assert_eq!(summary.total_stages, 2);
        assert_eq!(summary.completed_stages, 2);
        assert!(summary.success);
    }
}
