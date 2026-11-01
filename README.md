# GRaCEmo ViRa — Unified Documentation Repository

> **Dedicated Native Documentation Branch (`DOCS_`) for GRaCEmo ViRa Autonomous AI Robotics**

Welcome to the unified documentation branch for **GRaCEmo ViRa**. This branch is dedicated exclusively to system architecture, engineering specifications, validation reports, hardware manuals, simulation integration guides, and operational standards.

---

## 📚 Master Documentation Index

### 1. System Architecture & Protocols
- [System Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) — End-to-end architecture: Kernel, adapters, nervous system, and hardware bridges.
- [Universal Substrate](docs/architecture/UNIVERSAL_SUBSTRATE.md) — Substrate event model and cross-layer state integration.
- [Adapter Executor Protocol](docs/architecture/ADAPTER_EXECUTOR_PROTOCOL.md) — Protocol specifications for asynchronous adapters.
- [Event Protocol Specification](docs/architecture/EVENT_PROTOCOL.md) — Canonical schema and serialization contracts for all events.
- [K Operational Language Specification](docs/architecture/K_OPERATIONAL_LANGUAGE.md) — Declarative robotics DSL and mission control logic.
- [Roadmap Phases](docs/architecture/ROADMAP_PHASES.md) — Strategic execution phases and milestones.
- [Robot Integration Architecture](docs/robot_integration_architecture.md) — Physical and simulation stack integration architecture.
- [Robot Bridge Specification](docs/ROBOT_BRIDGE.md) — ROS2 / micro-ROS hardware abstraction layer.
- [Robot State Machine](docs/ROBOT_STATE_MACHINE.md) — Core operational states, transitions, and failsafes.
- [ROS2 Integration Guide](docs/ROS2_INTEGRATION.md) — ROS2 Jazzy package interfaces, topic contracts, and transforms.
- [VIRA Production Architecture](docs/VIRA_PRODUCTION_ARCHITECTURE.md) — Hardened multi-node production deployment layout.
- [VIRA Robot Interface Spec](docs/VIRA_ROBOT_INTERFACE.md) — Concrete hardware APIs, service definitions, and action goals.
- [VIRA Event Contracts](docs/VIRA_EVENT_CONTRACTS.md) — Event contracts for perception, navigation, and manipulation.
- [GRaCEmo UARCC Architecture Report](docs/GRACEMO_UARCC_ARCHITECTURE_REPORT.md) — Unified Autonomous Robot Control Center design and telemetry.

### 2. Safety, Operations & Recovery
- [Safety Operations & Protocols](docs/SAFETY_OPERATIONS.md) — Emergency stop mechanisms, boundary compliance, and operator handoffs.
- [VIRA Safety Architecture](docs/VIRA_SAFETY_ARCHITECTURE.md) — Layered hardware and software reflex safety envelopes.
- [VIRA Realtime Requirements](docs/VIRA_REALTIME_REQUIREMENTS.md) — Jitter bounds, deterministic latency guarantees, and timing budgets.
- [Fault Recovery Manual](docs/FAULT_RECOVERY_MANUAL.md) — Automated recovery runbooks, unstick routines, and exception trees.
- [Operator Manual](docs/OPERATOR_MANUAL.md) — User and field operator guide for system commissioning and control.
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) — Deployment instructions for physical robots and workstations.
- [Hardware Deployment Guide](docs/HARDWARE_DEPLOYMENT.md) — Step-by-step physical deployment and bringup checklist.
- [Navigation Flow](docs/NAVIGATION_FLOW.md) — Nav2 planner/controller orchestration and dynamic obstacle routing.

### 3. Engineering Acceptance & Qualification Reports
- [Autonomous Lifecycle Acceptance Report](docs/AUTONOMOUS_LIFECYCLE_ACCEPTANCE_REPORT.md) — End-to-end lifecycle verification and endurance results.
- [Autonomous Navigation Acceptance Report](docs/AUTONOMOUS_NAVIGATION_ACCEPTANCE_REPORT.md) — Benchmark navigation trials and waypoint reach tests.
- [Final Engineering Acceptance Report](docs/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md) — Comprehensive sign-off on autonomous capabilities.
- [Final Engineering Handoff](docs/FINAL_ENGINEERING_HANDOFF.md) — Deliverables, repository handoff notes, and operation instructions.
- [Gap Closure Test Report](docs/gap_closure_test_report.md) — Validation testing closing architectural and functional gaps.
- [GRaCEmo Gap Analysis](docs/gracemo_gap_analysis.md) — Baseline audit comparing expected vs. actual performance.
- [GRaCEmo Gap Closure Roadmap](docs/gracemo_gap_closure_roadmap.md) — Actionable milestone plan for full capability closure.
- [Living Room & Bedroom Acceptance Report](docs/LIVING_ROOM_AND_BEDROOM_ACCEPTANCE_REPORT.md) — Multi-room navigation and obstacle avoidance validation.
- [Localization and TF Repair Report](docs/LOCALIZATION_AND_TF_REPAIR_REPORT.md) — Root cause analysis and resolution of transform tree latency.
- [Mission Reliability Report](docs/MISSION_RELIABILITY_REPORT.md) — Long-run stress tests, MTBF, and mission completion statistics.
- [Operator Acceptance Report](docs/OPERATOR_ACCEPTANCE_REPORT.md) — Operator testing and usability sign-off.
- [Phase 4 Validation Report](docs/PHASE4_VALIDATION_REPORT.md) — Closed-loop sensor-actuator validation.
- [Phase 5 Hardware Report](docs/PHASE5_HARDWARE_REPORT.md) — Jetson Orin Nano + STM32 embedded qualification.
- [Phase 6 Autonomous Test Report](docs/PHASE6_AUTONOMOUS_TEST_REPORT.md) — Autonomous wander, exploration, and slam verification.
- [Phase 7 Acceptance Report](docs/PHASE7_ACCEPTANCE_REPORT.md) — Multi-room autonomy and vision-guided pick/stow acceptance.
- [Phase 8 Final Report](docs/PHASE8_FINAL_REPORT.md) — Complete Phase 8 milestone sign-off.
- [Phase 8 Operational Qualification](docs/PHASE8_OPERATIONAL_QUALIFICATION.md) — Environmental boundary tests and qualification metrics.
- [Physical Latency Report](docs/PHYSICAL_LATENCY_REPORT.md) — End-to-end latency benchmarks (sensor-to-motor loop).
- [Production Readiness Report](docs/PRODUCTION_READINESS_REPORT.md) — Checklist and sign-off for real-world deployments.
- [Real World Test Log](docs/REAL_WORLD_TEST_LOG.md) — Execution logs from hardware trials on physical robot.
- [Real World Test Plan](docs/REAL_WORLD_TEST_PLAN.md) — Protocol for physical robot validation runs.
- [Release Manifest](docs/RELEASE_MANIFEST.md) — Inventory of tested software packages and hardware revisions.
- [Simulation Hardware Parity](docs/SIMULATION_HARDWARE_PARITY.md) — Digital twin fidelity and sim-to-real transfer validation.
- [UARCC V1 Baseline Audit](docs/UARCC_V1_BASELINE_AUDIT.md) — Unified Control Center baseline capabilities audit.
- [VIRA Interaction Audit](docs/VIRA_INTERACTION_AUDIT.md) — Human-robot interaction response and latency audit.
- [VIRA Interaction Spec](docs/VIRA_INTERACTION_SPEC.md) — Multimodal voice and spatial dialogue contracts.
- [VIRA Observability Spec](docs/VIRA_OBSERVABILITY_SPEC.md) — Metrics, tracing, and health monitoring architecture.
- [VIRA Test Architecture](docs/VIRA_TEST_ARCHITECTURE.md) — Unit, integration, and HIL test harness architecture.

### 4. Hardware Verification & Embedded Firmware Protocols
- [Hardware Activation Gates](docs/hardware_activation_gates.md) — Prerequisite safety checks prior to energizing actuators.
- [Hardware Verification Checklist](docs/hardware_verification_checklist.md) — Component-level physical checkout procedures.
- [Hardware Test Log](docs/HARDWARE_TEST_LOG.md) — Hardware testing history, voltages, and thermal measurements.
- [Live Sensor Integration Status](docs/live_sensor_integration_status.md) — Realtime health of LiDAR, depth cameras, and IMU.
- [STM32-Jetson Protocol Proposal](docs/stm32_jetson_protocol_proposal.md) — UART packet frames, CRC checks, and command structure.
- [STM32 Protocol Compatibility Audit](docs/stm32_protocol_compatibility_audit.md) — Analysis of firmware command set compatibility.
- [GRaCEmo ViRa Master Database](docs/GRaCEmo_ViRa_Master_Database.xlsx) — Hardware BOM, pinout mapping, and calibration constants.

### 5. Blender & Gazebo Simulation Integration
- [Gazebo Integration Guide](docs/GAZEBO_INTEGRATION.md) — Gazebo Harmonic world configurations, sensors, and plugins.
- [Simulation Architecture](docs/blender_gazebo_integration/architecture.md) — High-level pipeline from 3D assets to physics engine.
- [Baseline Audit](docs/blender_gazebo_integration/baseline_audit.md) — Initial simulation assets and physics evaluation.
- [Blender Model Audit](docs/blender_gazebo_integration/blender_model_audit.md) — Mesh topology, joint hierarchies, and visual meshes.
- [Coordinate Frames](docs/blender_gazebo_integration/coordinate_frames.md) — Complete transform tree (`base_link`, `odom`, `map`).
- [Final Acceptance Report](docs/blender_gazebo_integration/FINAL_ENGINEERING_ACCEPTANCE_REPORT.md) — Digital twin acceptance criteria.
- [Integration Report](docs/blender_gazebo_integration/integration_report.md) — Assembly and testing report for simulated environment.
- [Material Palette](docs/blender_gazebo_integration/material_palette.md) — Surface friction, PBR materials, and sensor reflectance.
- [Navigation Validation](docs/blender_gazebo_integration/navigation_validation.md) — Gazebo simulated Nav2 route validation.
- [Physics & Collisions](docs/blender_gazebo_integration/physics_and_collisions.md) — Collision geometry, inertia tensors, and mass distribution.
- [Sensor Configuration](docs/blender_gazebo_integration/sensor_configuration.md) — Noise models, update rates, and field-of-view settings.
- [Simulation Launch](docs/blender_gazebo_integration/simulation_launch.md) — Step-by-step instructions to run headless and GUI simulations.
- [Test Results](docs/blender_gazebo_integration/test_results.md) — Automated simulation run results.
- [Troubleshooting Guide](docs/blender_gazebo_integration/troubleshooting.md) — Common Gazebo/ROS2 issues and solutions.

### 6. Components, Kernel & Research
- [Context Compilers](docs/components/CONTEXT_COMPILERS.md) — Fast LLM context compilation and grounding.
- [Event Ledger](docs/components/EVENT_LEDGER.md) — Append-only persistent SQLite event ledger.
- [Inspector State](docs/components/INSPECTOR_STATE.md) — Live telemetry inspection and introspective debugging.
- [K Trust Model](docs/research/K_TRUST_MODEL.md) — Security boundaries and verification of autonomous actions.
- [Lessons Learned (MNSE)](docs/lessons_learned_mnse.md) — Retrospective on multimodal nervous system engineering.
