# GRaCEmo ViRa — Real-Time Requirements & Latency Specification
**Phase 1 Deliverable — Real-Time Robot Development Mode**  
**Document ID:** `VIRA-PERF-P1-007`  
**System Version:** v0.0.3  

---

## 1. Real-Time Engineering Targets

The following measurable performance budgets define acceptance criteria for production interactive robotics. These targets apply across Apple Silicon (macOS) development, Linux workstation environments, and physical embedded robot compute.

```
Total End-to-End Latency Pipeline:
[Speech End] ──► [VAD Cutoff] ──► [STT] ──► [Intent/Brain] ──► [TTS First Audio Byte] ──► [Ear Hears Audio]
    0 ms            +450 ms       +350 ms       +650 ms              +250 ms               ≈ 1700 ms
```

---

## 2. Latency Benchmarks Specification Table

| Stage / Metric | P50 (Median) | P95 | P99 | Maximum Allowed | Target Failure Rate | Timeout Threshold |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **VAD Cutoff Latency** | $350\text{ ms}$ | $500\text{ ms}$ | $650\text{ ms}$ | $900\text{ ms}$ | $< 0.1\%$ | $1200\text{ ms}$ |
| **STT Cloud (Groq Whisper)** | $280\text{ ms}$ | $450\text{ ms}$ | $600\text{ ms}$ | $1000\text{ ms}$ | $< 0.5\%$ | $2000\text{ ms}$ |
| **STT Local (Faster-Whisper)**| $450\text{ ms}$ | $750\text{ ms}$ | $950\text{ ms}$ | $1400\text{ ms}$ | $< 0.05\%$| $2500\text{ ms}$ |
| **Fast-Path Intent Match** | $2\text{ ms}$ | $8\text{ ms}$ | $15\text{ ms}$ | $30\text{ ms}$ | $0.0\%$ | $50\text{ ms}$ |
| **Local LLM (Qwen 2.5 MLX)** | $380\text{ ms}$ | $650\text{ ms}$ | $850\text{ ms}$ | $1200\text{ ms}$ | $< 0.1\%$ | $2000\text{ ms}$ |
| **Cloud LLM (Groq / Gemini)** | $450\text{ ms}$ | $850\text{ ms}$ | $1200\text{ ms}$| $1800\text{ ms}$ | $< 1.0\%$ | $3000\text{ ms}$ |
| **Kernel EventBus Dispatch** | $0.4\text{ ms}$ | $1.2\text{ ms}$ | $2.5\text{ ms}$ | $5.0\text{ ms}$ | $0.0\%$ | $10.0\text{ ms}$ |
| **Safety Gate Validation** | $1.5\text{ ms}$ | $4.0\text{ ms}$ | $8.0\text{ ms}$ | $15.0\text{ ms}$ | $0.0\%$ | $25.0\text{ ms}$ |
| **TTS Startup (First Byte)** | $180\text{ ms}$ | $320\text{ ms}$ | $450\text{ ms}$ | $700\text{ ms}$ | $< 0.2\%$ | $1200\text{ ms}$ |
| **Robot Motor Setpoint (/cmd_vel)**| $8\text{ ms}$| $18\text{ ms}$ | $28\text{ ms}$ | $50\text{ ms}$ | $< 0.01\%$| $100\text{ ms}$ |
| **End-to-End Dialogue Turn** | $1450\text{ ms}$| $2100\text{ ms}$| $2800\text{ ms}$| $3500\text{ ms}$ | $< 1.0\%$ | $4000\text{ ms}$ |
| **EMERGENCY STOP LATENCY** | **$18\text{ ms}$**| **$35\text{ ms}$**| **$48\text{ ms}$**| **$65\text{ ms}$** | **$0.0\%$**| **$80\text{ ms}$** |

---

## 3. Real-Time Resource Budget

### 3.1 Memory Footprint (RAM)
- `kernel` (Rust Axum + SQLite): $< 35\text{ MB}$ RSS
- `graceemo_interaction` (Pygame + Edge-TTS): $< 150\text{ MB}$ RSS
- Local Qwen 2.5 3B 4-bit (Apple Silicon unified memory): $\approx 1.85\text{ GB}$ VRAM
- `kernel_bridge` (ROS 2 Humble / rclpy): $< 85\text{ MB}$ RSS
- Gazebo Sim Harmonic (Headless simulation): $< 650\text{ MB}$ RSS

### 3.2 Compute (CPU / GPU)
- Audio capture & VAD: $< 3\%$ of 1 CPU core at 16 kHz.
- Local Qwen 2.5 MLX generation: $> 45\text{ tokens/sec}$ on Apple Silicon M-series GPU.
- Pygame Expression avatar: 60 FPS rendering utilizing $< 4\%$ GPU.
- EventBus throughput capacity: $> 50,000\text{ events/sec}$ with zero packet loss.
