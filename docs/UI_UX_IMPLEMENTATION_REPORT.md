# GRaCEmo ViRa UARCC — Professional UI/UX Implementation Report

**Document Reference:** `docs/UI_UX_IMPLEMENTATION_REPORT.md`  
**Application:** GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC)  
**Framework:** PySide6 (Qt for Python) / ROS 2 Jazzy / Gazebo Harmonic  
**Status:** Complete & Fully Validated (30/30 Comprehensive Integration Tests Passed)

---

## 1. Executive Summary

The GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC) desktop application was transformed from an overly technical, dark, cluttered dashboard into a clean, minimal, modern, and professional engineering workstation application.

The redesigned interface eliminates all AI-generated aesthetics, neon glow, futuristic HUD clutter, and visual fragmentation. In their place is an intentional, ergonomic, three-pane engineering interface constructed with a disciplined light-surface palette (`#F5F6F8` canvas, `#FFFFFF` panels, `#17212B` sidebar) and restrained GRaCEmo brand orange accents (`#E65100`).

### Core Accomplishments
1. **Unified Design System:** Implemented a single source of truth for color tokens ([tokens.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/resources/styles/tokens.py)), master Qt stylesheet ([dark_theme.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/resources/styles/dark_theme.py)), and reusable component primitives ([common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py)).
2. **Three-Pane Workstation Architecture:**
   - **Left Sidebar:** Structured 3-group navigation (`WORKSPACE`, `ROBOT SYSTEMS`, `ENGINEERING`) with brand header and persistent hardware safety lock status.
   - **Top Application Bar:** Live breadcrumb title and description, subsystem status pills (`ROS 2`, `Gazebo`, `Robot`, `Localization`, `E-Stop`), and high-precision monospace simulation clock (`Sim Time: X.XXX s`).
   - **Main Content Canvas:** Responsive layout using standardized `PageHeader`, `SectionHeader`, `MetricDisplay`, and clean card surfaces.
3. **Complete 11-Module Redesign:** Redesigned all 11 modules to adhere strictly to the design system with zero loss of underlying ROS 2 telemetry or control capabilities.
4. **Safety Invariants Uncompromised:** Actuation hardware remains strictly disabled (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`). All collision and terrain safety watchdogs remain fully active.
5. **Quality Assurance & Verification:** 100% test pass rate across 30 comprehensive unit and integration tests; headless offscreen screenshot capture verified across all four desktop resolutions (1280×720, 1366×768, 1600×900, 1920×1080).

---

## 2. Before-and-After Observations

| Architectural Dimension | Prior Baseline Implementation | Redesigned Professional Workstation |
| :--- | :--- | :--- |
| **Visual Hierarchy & Palette** | Pitch-black background (`#0A0E14`), high-contrast neon borders (`#00FFCC`, `#FF8800`), dense text blocks, unconstrained card nesting. | Minimal light workstation palette (`#F5F6F8` canvas, `#FFFFFF` cards, `#E3E7EB` borders) with a deep slate sidebar (`#17212B`) and restrained brand accent (`#E65100`). |
| **Navigation Structure** | Flat list of 11 buttons without grouping or logical categorization; no active indicator; inconsistent widths. | Structured 3-tier sidebar: `WORKSPACE` (Overview, Simulation, Sensors, Navigation), `ROBOT SYSTEMS` (Localization, Voice & Interaction, Cognitive System), and `ENGINEERING` (Safety, Diagnostics, System Logs, Settings). |
| **Top Application Bar** | Unorganized, crowded metrics; unaligned status text; lack of context regarding the active page. | Unified bar displaying active page title, purpose description, small status pills with soft background fills, and simulation clock badge. |
| **Component Consistency** | Ad-hoc inline CSS on individual labels and buttons; multiple conflicting button styles; unstyled tables. | Standardized component suite (`PageHeader`, `SectionHeader`, `MetricDisplay`, `EmptyState`, `AlertBanner`, `StatusBadge`, `DataTable`, `PrimaryButton`, `SecondaryButton`). |
| **Information Density** | Critical data obscured by raw JSON logs, redundant numerical tables, and debug prints. | 5-second situational awareness: top-level metric counters, visual status indicators, and clean cards with secondary details accessible via tabs and expandable sections. |
| **Window Responsiveness** | Fixed-dimension containers that clipped or created horizontal scrollbars below 1600px width. | Fluid layouts using responsive splitters, column spans, and scroll areas; verified without clipping across 1280×720, 1366×768, 1600×900, and 1920×1080. |

---

## 3. Redesigned Modules Walkthrough

### Module 1: Overview (`modules/overview/overview_view.py`)
- **Purpose:** Primary landing page delivering full robot operational awareness within 5 seconds.
- **Key Features:**
  - 4 key metrics: Active Navigation State, E-Stop Watchdog, Collision Monitor bubble, and Localization status.
  - Two-column responsive layout:
    - *Left Column:* Live robot state card with active destination, coordinates, linear/angular velocity, and a live mini camera preview (160×120).
    - *Right Column:* Complete Subsystem Health Matrix (ROS 2 Core, Gazebo Simulation, 360° Planar LiDAR, Depth Camera, Navigation Coordinator, Hardware Safety Lock).
  - Bottom card displaying recent operational logs with clear severity distinction.

### Module 2: Simulation (`modules/simulation/simulation_view.py`)
- **Purpose:** Gazebo Harmonic simulation environment management without fake viewports.
- **Key Features:**
  - Metric counters: Sim Time, Real-Time Factor (RTF), Physics Step Rate (Hz), and Active Model Count.
  - External Gazebo management panel with launch action, connection state, world parameters (`empty_world.sdf`), and spawn status.
  - Process monitor inspecting local `ruby`, `gz-sim`, and `ign gazebo` daemons.

### Module 3: Sensors (`modules/sensors/sensors_view.py`)
- **Purpose:** Centralized sensor telemetry inspection across optical, depth, lidar, and inertial modalities.
- **Key Features:**
  - Tabbed organization:
    - *Vision & Depth:* Side-by-side [CameraViewWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/camera_view.py) (RGB stream) and [DepthViewWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/depth_view.py) (turbo colormapped depth stream with min/max distance probes).
    - *360° Planar LiDAR:* Integrated [LidarViewWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/lidar_view.py) with polar range rings, Cartesian obstacle projection, and obstacle safety bubble.
    - *IMU & Odometry:* 3-axis acceleration, angular rate gyroscopes, Euler orientation (Roll/Pitch/Yaw), and odometric velocities.

### Module 4: Navigation (`modules/navigation/navigation_view.py`)
- **Purpose:** Intuitive autonomous navigation dispatch and live tracking using Nav2.
- **Key Features:**
  - Full-screen capable 2D Occupancy Grid map viewer ([MapViewWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/map_view.py)) with interactive pan and zoom.
  - 6-destination quick selector loaded from `config/destinations.json` (Charging Station, Lab Workbench, Inspection Bay, Corridor A, Kitchen, Living Room).
  - Coordinator control card with "Dispatch Goal", "Cancel Goal", and "Immediate Safe Stop" actions.
  - Real-time navigation telemetry well displaying active goal, distance to goal, arrival confirmation, and execution duration.

### Module 5: Localization (`modules/localization/localization_view.py`)
- **Purpose:** AMCL probabilistic pose estimation and TF transform hierarchy verification.
- **Key Features:**
  - Metric displays: Global AMCL X/Y coordinates, Heading Yaw (° / rad), and AMCL Status.
  - Integrated [RobotPoseWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/robot_pose_widget.py) with directional compass needle and covariance matrix bounds.
  - TF Transform Tree health card verifying frame continuity (`map` → `odom` → `base_footprint` → `base_link` → `lidar_link`).

### Module 6: Voice & Interaction (`modules/interaction/interaction_view.py`)
- **Purpose:** Client monitoring interface for the existing Pygame voice and avatar engine.
- **Key Features:**
  - Strict preservation of the external Pygame engine ([vira_interaction/model.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/model.py)) without duplicate audio capture.
  - Metrics: Voice Engine Status, STT State, TTS Speech Output, and Grounding Engine.
  - Dialogue stream table rendering timestamps, speaker origin, recognized text, and intent classification.
  - Clean text-command input field with "Send Command" dispatch.

### Module 7: Cognitive System (`modules/cognitive/cognitive_view.py`)
- **Purpose:** MNSE neural-symbolic engine and Agent Bridge FastMCP task queue monitoring.
- **Key Features:**
  - Daemon probe for `/tmp/gracemo.sock` and REST endpoint `http://127.0.0.1:7780/health`.
  - Consequential action authorization gate status with strict protocol enforcement.
  - Real-time cognitive event and reasoning stream text display.

### Module 8: Safety (`modules/safety/safety_view.py`)
- **Purpose:** Authoritative safety command center prioritizing system and personnel protection.
- **Key Features:**
  - Authoritative Emergency Stop card with clear visual warning indicator, reason readout, and separate "ENGAGE E-STOP" and "RESET E-STOP" controls.
  - Collision Monitor card displaying 3-zone polygon safety bubbles (Warning, Slowdown, Stop).
  - Terrain Monitor card tracking pitch, roll, and ground roughness.
  - Single-owner velocity chain status guaranteeing zero competing `/cmd_vel` publishers.
  - Permanent hardware lockout confirmation banner.

### Module 9: Diagnostics (`modules/diagnostics/diagnostics_view.py`)
- **Purpose:** Host hardware metrics and ROS 2 middleware health inspection.
- **Key Features:**
  - Hardware resource meters: CPU utilization, System RAM usage, and GPU acceleration status.
  - ROS 2 Active Topic Table displaying topic names, message types, publication frequencies, and health indicators.
  - Active ROS 2 node registry table.

### Module 10: System Logs (`modules/logs/logs_view.py`)
- **Purpose:** Professional logging workbench for operational and diagnostic analysis.
- **Key Features:**
  - Integrated [LogViewerWidget](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/log_viewer.py) with real-time log ingestion.
  - Filter controls: text search input, severity selector (`ALL`, `INFO`, `WARNING`, `ERROR`), and node/component filter.
  - Auto-scroll toggle and "Export Log to File" action.
  - Color-coded severity badges for rapid scannability.

### Module 11: Settings (`modules/settings/settings_view.py`)
- **Purpose:** Centralized, structured configuration workbench.
- **Key Features:**
  - Categorized configuration sections: General Application, ROS 2 Middleware, Simulation & Gazebo, Display & Layout, Diagnostics, Interaction, and Safety Locks.
  - Clear explanations for every configuration toggle.
  - Read-only safety lock indicators preventing accidental physical motor enablement.

---

## 4. Reusable Component Inventory

| Component Name | File Location | Purpose & Styling |
| :--- | :--- | :--- |
| `PageHeader` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Standardized page title, descriptive subtitle, and contextual status badge. |
| `SectionHeader` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Section title with subtle bottom separator line. |
| `MetricDisplay` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Large metric readout (`22-26px`), uppercase label, and optional unit. |
| `StatusIndicator` | [status_indicator.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/status_indicator.py) | Pill-style status badge with anti-aliased dot and colored background. |
| `EmptyState` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Informative placeholder with icon, message, and descriptive text. |
| `AlertBanner` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Prominent notification banner for warnings, errors, and system states. |
| `ConfirmationDialog` | [common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) | Modal dialog for high-consequence operations (e.g. E-Stop reset). |
| `CameraViewWidget` | [camera_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/camera_view.py) | Optical video stream renderer with FPS and resolution overlays. |
| `DepthViewWidget` | [depth_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/depth_view.py) | Colormapped depth image viewer with distance probes. |
| `LidarViewWidget` | [lidar_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/lidar_view.py) | 360° polar radar viewer with Cartesian obstacle projection. |
| `MapViewWidget` | [map_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/map_view.py) | Interactive 2D Nav2 map viewer with zoom, pan, and waypoint rendering. |
| `RobotPoseWidget` | [robot_pose_widget.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/robot_pose_widget.py) | Coordinate grid, velocity readouts, and directional compass dial. |
| `LogViewerWidget` | [log_viewer.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/log_viewer.py) | Filterable, auto-scrolling system log table. |

---

## 5. Responsiveness & Resolution Validation

The application was rendered and visually verified at four standard desktop workstation resolutions:

1. **1280 × 720 (HD):** Compact workstation layout. Sidebar maintains readable category headers; main content adapts via vertical scrollbars without horizontal overflow or widget clipping.
2. **1366 × 768 (Standard Laptop):** Balanced layout with generous margin spacing. Cards span evenly across columns.
3. **1600 × 900 (Widescreen Workstation):** Optimum engineering density. Two-column layouts on Overview and Safety operate side-by-side without vertical scrolling.
4. **1920 × 1080 (Full HD Desktop):** Full workstation view. Map and sensor views expand cleanly to fill available viewport space with high readability.

### Visual Quality Assurance Artifacts
High-resolution offscreen PNG screenshots of all 11 modules and multi-resolution views are saved in [docs/screenshots/](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/screenshots/):

- `1920x1080_01_overview.png`
- `1920x1080_02_simulation.png`
- `1920x1080_03_sensors.png`
- `1920x1080_04_navigation.png`
- `1920x1080_05_localization.png`
- `1920x1080_06_interaction.png`
- `1920x1080_07_cognitive.png`
- `1920x1080_08_safety.png`
- `1920x1080_09_diagnostics.png`
- `1920x1080_10_logs.png`
- `1920x1080_11_settings.png`
- `1280x720_01_overview.png`, `1280x720_04_navigation.png`, `1280x720_08_safety.png`
- `1366x768_01_overview.png`, `1366x768_04_navigation.png`, `1366x768_08_safety.png`
- `1600x900_01_overview.png`, `1600x900_04_navigation.png`, `1600x900_08_safety.png`

---

## 6. Integration & Safety Verification Test Results

Comprehensive verification was executed against the active ROS 2 Jazzy environment using the unified test suite ([test_uarcc_comprehensive.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/tests/test_uarcc_comprehensive.py)).

### Test Execution Summary
- **Test Command:** `pytest -v gracemo_control_center/tests/test_uarcc_comprehensive.py`
- **Total Tests:** 30
- **Passed:** 30 (100%)
- **Failed:** 0
- **Duration:** 2.41 seconds

```
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_01_application_startup PASSED [  3%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_02_application_shutdown PASSED [  6%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_03_ros_connection PASSED [ 10%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_04_ros_disconnection_and_reconnection PASSED [ 13%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_05_sensor_freshness PASSED [ 16%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_06_camera_image_delivery PASSED [ 20%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_07_depth_image_delivery PASSED [ 23%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_08_lidar_coordinate_conversion PASSED [ 26%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_09_imu_parsing PASSED [ 30%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_10_odometry_parsing PASSED [ 33%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_11_map_rendering PASSED [ 36%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_12_robot_pose_rendering PASSED [ 40%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_13_destination_loading PASSED [ 43%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_14_navigation_action_dispatch PASSED [ 46%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_15_navigation_cancellation PASSED [ 50%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_16_navigation_result_handling PASSED [ 53%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_17_arrival_status_display PASSED [ 56%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_18_emergency_stop_interface PASSED [ 60%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_19_collision_monitor_status PASSED [ 63%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_20_terrain_monitor_status PASSED [ 66%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_21_voice_event_display PASSED [ 70%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_22_mnse_offline_handling PASSED [ 73%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_23_log_filtering PASSED [ 76%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_24_diagnostics_refresh PASSED [ 80%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_25_gui_closure_during_navigation PASSED [ 83%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_26_gui_restart_during_navigation PASSED [ 86%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_27_pygame_independent_operation PASSED [ 90%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_28_gazebo_disconnection_handling PASSED [ 93%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_29_no_duplicate_ros_nodes PASSED [ 96%]
gracemo_control_center/tests/test_uarcc_comprehensive.py::test_30_hardware_safety_invariant_preservation PASSED [100%]
```

---

## 7. Modified & Created Files Summary

### Design System & Documentation
- [docs/UI_UX_AUDIT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/UI_UX_AUDIT.md) — Comprehensive architectural and UI/UX audit of the baseline application.
- [docs/UI_DESIGN_SYSTEM.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/UI_DESIGN_SYSTEM.md) — Design system specification (colors, typography, geometry, component tokens).
- [docs/UI_UX_IMPLEMENTATION_REPORT.md](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/UI_UX_IMPLEMENTATION_REPORT.md) — This implementation report.
- [docs/screenshots/](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/docs/screenshots/) — 20 verification screenshot PNGs.

### Styles & Common Widgets
- [gracemo_control_center/resources/styles/tokens.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/resources/styles/tokens.py) — Design tokens definition.
- [gracemo_control_center/resources/styles/dark_theme.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/resources/styles/dark_theme.py) — Master QSS generator.
- [gracemo_control_center/widgets/common_components.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/common_components.py) — Reusable component library.
- [gracemo_control_center/widgets/status_indicator.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/status_indicator.py) — Redesigned status badge with colored background and dot.
- [gracemo_control_center/widgets/camera_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/camera_view.py) — Optical camera viewer.
- [gracemo_control_center/widgets/depth_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/depth_view.py) — Colormapped depth viewer.
- [gracemo_control_center/widgets/lidar_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/lidar_view.py) — 360° LiDAR radar widget.
- [gracemo_control_center/widgets/map_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/map_view.py) — 2D occupancy grid navigation widget.
- [gracemo_control_center/widgets/robot_pose_widget.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/robot_pose_widget.py) — Pose, odometry velocity, covariance, and compass widget.
- [gracemo_control_center/widgets/log_viewer.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/widgets/log_viewer.py) — Filterable log viewer widget.

### Application Shell & Modules
- [gracemo_control_center/app.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/app.py) — Main application window, 3-group sidebar, top bar, and bottom notification bar.
- [gracemo_control_center/modules/overview/overview_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/overview/overview_view.py) — Module 1: Overview.
- [gracemo_control_center/modules/simulation/simulation_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/simulation/simulation_view.py) — Module 2: Simulation.
- [gracemo_control_center/modules/sensors/sensors_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/sensors/sensors_view.py) — Module 3: Sensors.
- [gracemo_control_center/modules/navigation/navigation_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/navigation/navigation_view.py) — Module 4: Navigation.
- [gracemo_control_center/modules/localization/localization_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/localization/localization_view.py) — Module 5: Localization.
- [gracemo_control_center/modules/interaction/interaction_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/interaction/interaction_view.py) — Module 6: Voice & Interaction.
- [gracemo_control_center/modules/cognitive/cognitive_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/cognitive/cognitive_view.py) — Module 7: Cognitive System.
- [gracemo_control_center/modules/safety/safety_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/safety/safety_view.py) — Module 8: Safety.
- [gracemo_control_center/modules/diagnostics/diagnostics_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/diagnostics/diagnostics_view.py) — Module 9: Diagnostics.
- [gracemo_control_center/modules/logs/logs_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/logs/logs_view.py) — Module 10: System Logs.
- [gracemo_control_center/modules/settings/settings_view.py](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/gracemo_control_center/modules/settings/settings_view.py) — Module 11: Settings.

---

## 8. Verification & Launch Instructions

To launch the newly transformed GRaCEmo ViRa UARCC application on any robotics engineering workstation:

```bash
# 1. Source ROS 2 Jazzy workspace
source /opt/ros/jazzy/setup.bash

# 2. Launch the UARCC desktop application
bash scripts/run_control_center.sh
```

To re-run the complete test suite:
```bash
source /opt/ros/jazzy/setup.bash
pytest -v gracemo_control_center/tests/test_uarcc_comprehensive.py
```

To re-capture all verification screenshots across all resolutions:
```bash
source /opt/ros/jazzy/setup.bash
PYTHONPATH=. python3 scripts/capture_uarcc_screenshots.py
```
