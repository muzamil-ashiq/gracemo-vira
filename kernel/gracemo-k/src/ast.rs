use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Literal value in K expressions
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum KValue {
    String(String),
    Number(f64),
    Bool(bool),
    Coordinates { x: f64, y: f64, z: Option<f64> },
    List(Vec<KValue>),
    Map(HashMap<String, KValue>),
}

impl From<String> for KValue {
    fn from(s: String) -> Self {
        KValue::String(s)
    }
}

impl From<&str> for KValue {
    fn from(s: &str) -> Self {
        KValue::String(s.to_string())
    }
}

impl From<f64> for KValue {
    fn from(n: f64) -> Self {
        KValue::Number(n)
    }
}

impl From<bool> for KValue {
    fn from(b: bool) -> Self {
        KValue::Bool(b)
    }
}

/// A single stage invocation in a K pipeline: `noun::verb[arg1: val1, arg2: val2]`
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KStage {
    pub noun: String,
    pub verb: String,
    pub args: HashMap<String, KValue>,
}

impl KStage {
    pub fn new(noun: impl Into<String>, verb: impl Into<String>) -> Self {
        Self {
            noun: noun.into(),
            verb: verb.into(),
            args: HashMap::new(),
        }
    }

    pub fn with_arg(mut self, key: impl Into<String>, val: impl Into<KValue>) -> Self {
        self.args.insert(key.into(), val.into());
        self
    }
}

/// An executable K pipeline comprising chained stages: `stage1 | stage2 | stage3`
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KPipeline {
    pub stages: Vec<KStage>,
}

impl KPipeline {
    pub fn new() -> Self {
        Self { stages: Vec::new() }
    }

    pub fn pipe(mut self, stage: KStage) -> Self {
        self.stages.push(stage);
        self
    }
}

impl Default for KPipeline {
    fn default() -> Self {
        Self::new()
    }
}
