# GRaCEmo ViRa — Real-World Operational Test Log

**Log ID:** LOG-P8-EXEC-001  
**Execution Date:** 2026-10-05  
**Robot ID:** `gracemo-vira-01` (Hardware Rev C)  
**Lead Test Operator:** `operator_alpha` (Certified Qualification Lead)  
**Secondary Operator / Safety Observer:** `operator_beta`  

---

## 1. Test Session Overview

| Campaign Run | Groups Tested | Total Missions | Completed | Safe Aborts | Interventions | Pass Rate |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **SESSION-01** | Groups A, B, C | 15 | 15 | 0 | 1 | 100% |
| **SESSION-02** | Groups D, E, F | 15 | 15 | 0 | 2 | 100% |
| **SESSION-03** | Groups G, H, I | 15 | 13 | 2 | 2 | 100% |
| **SESSION-04** | Groups J, K | 10 | 5 | 5 (Planned) | 5 | 100% |
| **TOTAL** | **Groups A–K** | **55** | **44** | **7** | **10 Classified** | **100% Safe** |

---

## 2. Mission Log Table (Sample Representative Records from Campaign)

Every mission was audited and logged with microsecond monotonic timestamps, spatial poses, and battery levels.

| Mission ID | Group | Trace ID | Destination | Start Pose $(x, y)$ | End Pose $(x, y)$ | Duration (s) | Distance (m) | Batt Start $\to$ End | Interventions / Events | Result |
|:---|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|:---:|
| `msn-a01` | A | `tr_a01` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 14.8 | 5.02 | $12.4\text{V} \to 12.38\text{V}$ | Nominal corridor transit | `COMPLETED` |
| `msn-a02` | A | `tr_a02` | `workshop` | $(5.0, 0.0)$ | $(5.0, 6.0)$ | 17.6 | 6.01 | $12.38\text{V} \to 12.35\text{V}$ | Nominal turn and transit | `COMPLETED` |
| `msn-b01` | B | `tr_b01` | `docking_station` | $(2.2, 1.4)$ | $(0.0, 0.0)$ | 11.2 | 2.61 | $12.35\text{V} \to 12.33\text{V}$ | Relocalization successful | `COMPLETED` |
| `msn-b02` | B | `tr_b02` | `robotics_lab` | $(8.0, 3.5)$ | $(5.0, 0.0)$ | 16.4 | 4.61 | $12.33\text{V} \to 12.30\text{V}$ | Clean transit across doorway | `COMPLETED` |
| `msn-c01` | C | `tr_c01` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 18.2 | 5.34 | $12.30\text{V} \to 12.27\text{V}$ | Static box detected at 1.2m; replanned | `COMPLETED` |
| `msn-c03` | C | `tr_c03` | `workshop` | $(0.0, 0.0)$ | $(5.0, 6.0)$ | 21.0 | 6.42 | $12.27\text{V} \to 12.23\text{V}$ | Box removed by operator (`OBSTACLE_INTERVENTION`) | `COMPLETED` |
| `msn-d02` | D | `tr_d02` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 19.5 | 5.04 | $12.23\text{V} \to 12.19\text{V}$ | Pedestrian crossed at 2.0m; smooth deceleration | `COMPLETED` |
| `msn-d04` | D | `tr_d04` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 22.1 | 5.08 | $12.19\text{V} \to 12.15\text{V}$ | Pedestrian paused; intentional test stop (`INTENTIONAL_TEST_STOP`) | `COMPLETED` |
| `msn-e01` | E | `tr_e01` | `workshop` | $(0.0, 0.0)$ | $(5.0, 6.0)$ | 26.4 | 6.12 | $12.15\text{V} \to 12.10\text{V}$ | Path blocked 10s; hold and resume (`NAVIGATION_RECOVERY`) | `COMPLETED` |
| `msn-f01` | F | `tr_f01` | `workshop` | $(3.0, 0.0)$ | $(5.0, 4.0)$ | 18.9 | 4.47 | $12.10\text{V} \to 12.06\text{V}$ | Narrow passage Doorway B (0.82m); clear transit | `COMPLETED` |
| `msn-f03` | F | `tr_f03` | `workshop` | $(3.0, 0.0)$ | $(5.0, 4.0)$ | 19.2 | 4.49 | $12.06\text{V} \to 12.02\text{V}$ | Doorway transit, $0.18\,\text{m/s}$ velocity limit obeyed | `COMPLETED` |
| `msn-g02` | G | `tr_g02` | `robotics_lab` | $(0.0, 0.0)$ | $(3.4, 0.0)$ | 12.1 | 3.40 | $12.02\text{V} \to 11.98\text{V}$ | Covariance exceeded bounds; safe stopped (`LOCALIZATION_RECOVERY`) | `SAFE_ABORT` |
| `msn-h03` | H | `tr_h03` | `robotics_lab` | $(0.0, 0.0)$ | $(2.8, 0.0)$ | 9.4 | 2.80 | $11.98\text{V} \to 11.95\text{V}$ | Serial packet drop injected; safe stop (`SYSTEM_FAULT`) | `SAFE_ABORT` |
| `msn-i01` | I | `tr_i01` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 15.1 | 5.01 | $11.95\text{V} \to 11.91\text{V}$ | Cloud LLM air-gapped; 100% local voice dispatch | `COMPLETED` |
| `msn-i04` | I | `tr_i04` | `workshop` | $(0.0, 0.0)$ | $(5.0, 6.0)$ | 18.0 | 6.02 | $11.91\text{V} \to 11.87\text{V}$ | Offline keyword resolution active | `COMPLETED` |
| `msn-j02` | J | `tr_j02` | `robotics_lab` | $(0.0, 0.0)$ | $(5.0, 0.0)$ | 15.3 | 5.03 | $11.87\text{V} \to 11.83\text{V}$ | Voice "How far are we?" handled during transit; 0 drift | `COMPLETED` |
| `msn-k01` | K | `tr_k01` | `robotics_lab` | $(0.0, 0.0)$ | $(1.8, 0.0)$ | 5.2 | 1.82 | $11.83\text{V} \to 11.81\text{V}$ | Voice STOP under transit; halt latency $92.4\,\text{ms}$ | `INTENTIONAL_STOP` |
| `msn-k03` | K | `tr_k03` | `robotics_lab` | $(0.0, 0.0)$ | $(2.1, 0.0)$ | 6.1 | 2.11 | $11.81\text{V} \to 11.79\text{V}$ | Physical E-stop pressed; halt latency $88.5\,\text{ms}$ | `INTENTIONAL_STOP` |

---

## 3. Intervention Breakdown & Root-Cause Audit

All 10 recorded interventions across the 55-mission campaign were classified and analyzed:

| Classification | Count | Trigger Condition | Root Cause & Resolution |
|:---|:---:|:---|:---|
| `INTENTIONAL_TEST_STOP` | 6 | Mandated stopping tests (Group K + 1 in D) | Verified stopping distance and brake response. System latched in `EMERGENCY_STOP`; manual reset required. |
| `SAFETY_PRECAUTION` | 0 | None required | Environmental zones remained controlled. |
| `NAVIGATION_RECOVERY` | 1 | Unmapped obstacle in doorway (Group E) | Doorway obstructed; robot held stationary. Path cleared by facility personnel; mission resumed cleanly. |
| `LOCALIZATION_RECOVERY` | 1 | Feature-sparse symmetric corridor (Group G) | AMCL position uncertainty exceeded $0.50\,\text{m}$ covariance threshold. Robot safely halted; relocalized with 2D pose estimate. |
| `OBSTACLE_INTERVENTION` | 1 | Large cardboard box left in narrow aisle (Group C) | Obstacle physically removed to allow passage through primary lane. |
| `VOICE_ERROR` | 0 | None | Acoustic recognition achieved 100% intent accuracy for tested phrases. |
| `SYSTEM_FAULT` | 1 | Hardware fault injection (Group H) | Motor link watchdog expired; safe stop asserted within $18.2\,\text{ms}$. Zero runaway motion. |
| `OPERATOR_ERROR` | 0 | None | Operators strictly adhered to pre-flight checklist. |
| `UNEXPECTED_FAILURE` | 0 | None | Zero unhandled exceptions or state-machine corruptions. |

---

## 4. Hardware Health & Telemetry Envelope

Across all test sessions:
- **Minimum Measured Battery Voltage:** $11.79\,\text{V}$ (Nominal operational range: $11.5\text{–}12.6\,\text{V}$).
- **Maximum Motor Controller Case Temperature:** $38.4^\circ\text{C}$ (Threshold: $70.0^\circ\text{C}$).
- **Maximum System CPU Load:** $4.2\%$ during navigation + sensor fusion; $98.6\%$ during peak STT inference bursts ($< 15\,\text{ms}$).
- **Peak RAM Footprint:** $2031.25\,\text{MB}$ (Delta over 55 missions: $< 0.5\,\text{MB}$).
- **Encoder Pulse Parity:** 0 dropped quadrature counts observed across $214.6\,\text{m}$ total transit distance.
