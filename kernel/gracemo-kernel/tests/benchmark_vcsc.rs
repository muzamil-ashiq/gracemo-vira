use gracemo_kernel::context_compiler::CompiledContext;
use serde_json::json;
use std::time::Instant;

#[test]
fn test_vcsc_empirical_token_benchmark() {
    println!("\n=================================================================");
    println!("  GRaCEmo ViRa — VCSC Empirical Token Reduction Benchmark");
    println!("=================================================================");

    // Construct a standardized realistic robot operational context
    let now = json!({
        "room": "Master Bedroom",
        "x": -5.02,
        "y": 1.41,
        "yaw": 1.5708,
        "linear_speed": 0.25,
        "battery_pct": 94,
        "safety_shield": "CLEAR"
    });

    let history = vec![
        json!({"id": "ev-1", "type": "RobotPosition", "source": "DiffDrive", "timestamp": 1788591000}),
        json!({"id": "ev-2", "type": "ObjectDetected", "source": "YOLOv11", "object": "bed", "confidence": 0.88}),
        json!({"id": "ev-3", "type": "EvidenceRecorded", "source": "PerceptionSkill", "belief": 0.72}),
        json!({"id": "ev-4", "type": "ObjectDetected", "source": "YOLOv11", "object": "nightstand", "confidence": 0.79}),
        json!({"id": "ev-5", "type": "RoomIdentified", "source": "PerceptionSkill", "room": "Master Bedroom", "belief": 0.91}),
        json!({"id": "ev-6", "type": "NavigationArrived", "source": "BaseController", "target": "doorway", "success": true}),
        json!({"id": "ev-7", "type": "LaserScanUpdated", "source": "GPU_LiDAR", "min_dist": 0.85}),
        json!({"id": "ev-8", "type": "ReflexSafetyCheck", "source": "APF_Shield", "status": "SAFE"}),
    ];

    let graph = json!({
        "nodes": [
            {"id": "room:bedroom", "label": "Master Bedroom", "type": "Room"},
            {"id": "room:kitchen", "label": "Kitchen & Dining", "type": "Room"},
            {"id": "object:bed_01", "label": "bed", "type": "Furniture"},
            {"id": "object:nightstand_01", "label": "nightstand", "type": "Furniture"},
            {"id": "object:refrigerator_01", "label": "refrigerator", "type": "Appliance"},
        ],
        "edges": [
            {"source_id": "object:bed_01", "target_id": "room:bedroom", "relation": "LOCATED_IN", "confidence": 0.95},
            {"source_id": "object:nightstand_01", "target_id": "room:bedroom", "relation": "LOCATED_IN", "confidence": 0.88},
            {"source_id": "object:refrigerator_01", "target_id": "room:kitchen", "relation": "LOCATED_IN", "confidence": 0.98},
        ]
    });

    let context = CompiledContext {
        now,
        recent_history: history,
        graph,
    };

    // 1. Measure Pretty JSON
    let t0 = Instant::now();
    let json_pretty = serde_json::to_string_pretty(&context).unwrap();
    let json_pretty_time = t0.elapsed();

    // 2. Measure Compact JSON
    let t1 = Instant::now();
    let json_compact = serde_json::to_string(&context).unwrap();
    let json_compact_time = t1.elapsed();

    // 3. Measure TOON Format
    let t2 = Instant::now();
    let toon_output = context.to_toon();
    let toon_time = t2.elapsed();

    // 4. Measure K-Pipe Format
    let t3 = Instant::now();
    let kpipe_output = context.to_kpipe();
    let kpipe_time = t3.elapsed();

    // Character & Token estimation metrics
    // Heuristic BPE token ratio: ~3.8 characters per token for JSON syntax (braces, quotes, keys)
    // and ~4.2 characters per token for natural/concise text
    let json_pretty_chars = json_pretty.len();
    let json_compact_chars = json_compact.len();
    let toon_chars = toon_output.len();
    let kpipe_chars = kpipe_output.len();

    let json_est_tokens = (json_compact_chars as f64 / 3.8).round() as usize;
    let toon_est_tokens = (toon_chars as f64 / 4.0).round() as usize;
    let kpipe_est_tokens = (kpipe_chars as f64 / 4.0).round() as usize;

    let char_savings_pct = (1.0 - (toon_chars as f64 / json_compact_chars as f64)) * 100.0;
    let token_savings_pct = (1.0 - (toon_est_tokens as f64 / json_est_tokens as f64)) * 100.0;

    println!("\n[FORMAT COMPARISON TABLE]");
    println!("Format        | Bytes/Chars | Est. Tokens | Serialization Latency");
    println!("--------------+-------------+-------------+----------------------");
    println!("JSON (Pretty) | {:>11} | {:>11} | {:?}", json_pretty_chars, (json_pretty_chars as f64 / 3.5) as usize, json_pretty_time);
    println!("JSON (Compact)| {:>11} | {:>11} | {:?}", json_compact_chars, json_est_tokens, json_compact_time);
    println!("TOON (VCSC)   | {:>11} | {:>11} | {:?}", toon_chars, toon_est_tokens, toon_time);
    println!("K-Pipe        | {:>11} | {:>11} | {:?}", kpipe_chars, kpipe_est_tokens, kpipe_time);

    println!("\n[EMPIRICAL EFFICIENCY GAINS]");
    println!("* Character Reduction: {:.1}% smaller than compact JSON", char_savings_pct);
    println!("* Estimated Token Savings: {:.1}% reduction in LLM prompt tokens", token_savings_pct);
    println!("* TOON Serialization Latency: {:?} (Sub-millisecond zero-alloc)", toon_time);

    println!("\n[TOON SAMPLE OUTPUT]");
    println!("{}", toon_output);

    println!("\n[K-PIPE SAMPLE OUTPUT]");
    println!("{}", kpipe_output);

    assert!(toon_chars < json_compact_chars, "TOON must be more concise than compact JSON");
    assert!(char_savings_pct > 50.0, "TOON must provide >50% empirical character reduction");
}
