# Changelog

All notable changes to the **GRaCEmo ViRa** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.0.1] - 2026-08-25 (Project Skeleton & Architecture Baseline) 🏗️

### Added
- **Core Repository Skeleton**: Established modular layout separating `kernel/` (Rust), `adapters/` (Python), `simulation/` (ROS2/Gazebo), and `config/`.
- **Rust Kernel Workspace**: Set up workspace root with `gracemo-types`, `gracemo-kernel`, `gracemo-ledger`, and `gracemo-graph` crate stubs.
- **Unified Event Schema**: Drafted foundational `EventType` definitions in `gracemo-types` encompassing robot telemetry, navigation status, vision detections, and voice commands.
- **Python Adapter SDK**: Created shared `gracemo_sdk` client providing standardized `/emit` and SSE action subscription capabilities.
- **Documentation & Standards**: Added root `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, and `.editorconfig`.
