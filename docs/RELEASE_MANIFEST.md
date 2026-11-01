# GRaCEmo ViRa — Production Release Manifest
**Version:** 1.0.0-rc1 (Production Candidate Freeze)  
**Classification:** READY FOR SUPERVISED AUTONOMOUS NAVIGATION  
**Date:** 2026-10-05  

---

## 1. System Identity & Provenance

| Component | Identifier / Version | Description |
|:---|:---|:---|
| **Git Commit SHA** | `cd6af65677e6195b2cd499e1251787f332690f5e` | Production acceptance tag commit |
| **Software Version** | `1.0.0-rc1` | GRaCEmo ViRa Core & Bridge |
| **Hardware Revision** | `REV-C-PHYSICAL` | Differential-drive base with LiDAR & Intel RealSense D435 |
| **Firmware Version** | `2.4.1-rc3` | Motor Controller MCU / Low-Level Real-Time Driver |
| **ROS 2 Version** | `Jazzy Jalisco` (LTS) | Communication middleware & lifecycle nodes |
| **Nav2 Version** | `1.3.1 (Jazzy)` | Nav2 navigation stack (BT Navigator, Costmap2D, DWB) |
| **Python Runtime** | `3.11.10` | CPython 64-bit on aarch64 / Darwin |

---

## 2. Configuration Artifact Hashes (SHA-256)

Every configuration file governing physical robot behavior is frozen. No runtime parameter modifications may be applied without updating and re-qualifying these hashes.

| Artifact | File Path | SHA-256 Digest |
|:---|:---|:---|
| **Physical Nav2 Config** | `config/nav2_params_physical.yaml` | `85464ab9eb6d59812eca4f004c3166794c9ebc1839347a9296de77b60a056b45` |
| **URDF / Xacro Model** | `description/urdf/gracemo_vira.urdf.xacro` | `dd757339ad748dba86e07f5cf78c21b15724283b205db5ee44795798f3f89f36` |
| **Campus Places Graph** | `config/places.json` | `5a4d9f0aa442ffbd9c885dabe54c2d2e6007aef4d9b5b9d8b9025c1068ef25c1` |

---

## 3. Subsystem Configurations

### A. Speech-to-Text (STT) & Wake Word
- **Engine:** Vosk Offline Kaldi-based STT (Model: `vosk-model-small-en-us-0.15`)
- **Wake Word:** Local energy-based and phonetic detector for `"vira"` / `"gracemo"`
- **VAD Threshold:** 500 ms silence timeout, 48 kHz / 16-bit mono input
- **Fallback:** Offline local keyword matcher for high-confidence intents (`STOP`, `STATUS`, `GREET`)

### B. Text-to-Speech (TTS) & Audio Output
- **Primary Engine:** Piper Neural TTS (`en-us-lessac-medium.onnx`)
- **Fallback Engine:** System `espeak-ng` / `pyttsx3`
- **Output Channel:** Bounded audio sink, 22.05 kHz 16-bit PCM
- **Subordination:** Voice synthesis immediately muted on any emergency stop or operator intervention

### C. EventBus Configuration
- **Bus Implementation:** In-memory async event broker with priority queues
- **Priorities:** `EMERGENCY` (0), `HIGH` (1), `NORMAL` (2), `LOW` (3)
- **Trace Propagation:** W3C TraceContext compliant `trace_id` attached to every event envelope
- **Queue Limits:** Max buffer depth 1,000 events, drop policy: drop-oldest only for telemetry; emergency events never dropped

### D. Safety Configuration & Limits
- **Max Linear Velocity:** `0.35 m/s` (Hardware Test Mode: `0.30 m/s`, Hardware Safe Mode: `0.0 m/s`)
- **Max Angular Velocity:** `0.60 rad/s` (Hardware Test Mode: `0.50 rad/s`)
- **Watchdog Timeout:** `300 ms` strict hardware heartbeat; motors automatically halt if tick expires
- **Battery Safety Thresholds:** Warning at `11.1 V`, Safe Hold at `10.8 V`, Critical Stop at `10.5 V`
- **E-Stop Latency:** `< 5 ms` in software SafetyGate, hardware latch active low
- **Zero Auto-Resume:** Mandatory operator clearance required following any emergency stop or sensor trip

---

## 4. Runtime Dependencies & Environment

```text
rclpy==0.11.0
PyYAML>=6.0.1
pydantic>=2.8.2
numpy>=1.26.0
sounddevice>=0.4.6
vosk>=0.3.45
requests>=2.31.0
```

---

## 5. Frozen Production Baseline

- **Phase 5 Verification:** 106/106 passing tests
- **Phase 6 Verification:** 123/123 passing tests
- **Phase 7 Acceptance:** 13/13 production qualification tests passing (136/136 total tests across full suite)
- **Deployment Designation:** READY FOR SUPERVISED AUTONOMOUS NAVIGATION
