# GRaCEmo ViRa UARCC — Phase 1: Comprehensive UI/UX Audit

**Document:** `docs/UI_UX_AUDIT.md`  
**Date:** November 2026  
**System:** GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC V1.0)  
**Author:** Senior Product Designer & Principal UI/UX Architect  

---

## 1. Executive Summary

The GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC) provides critical real-time observability and operator control over an autonomous mobile manipulator platform integrating ROS 2 Jazzy, Gazebo Harmonic, Nav2, AMCL, multimodal perception (RGB-D + LiDAR), Whisper interaction, and the MNSE/K cognitive architecture.

While the existing backend integration and telemetry routing are functionally sound, the user interface currently exhibits severe usability, aesthetic, and architectural shortcomings:
- **Visual Over-Engineering ("Bordered-Card Hell"):** Every panel, status metric, and group box is enclosed in heavy, dark-bordered cards with arbitrary nested borders (`#2E4150` / `#3E576B`), creating visual fatigue and high cognitive load.
- **Unstructured Navigation:** All 11 functional modules are presented in a flat, unorganized list with miscellaneous emojis (`📊 Overview`, `🌐 Simulation`, `📡 Sensors`...) without semantic grouping.
- **Inconsistent Design Language:** Module views construct independent header frames, status rows, and telemetry tables with ad-hoc font sizes, inline `setStyleSheet()` blocks, and hardcoded colors rather than consuming unified design tokens.
- **Overwhelming Technical Clutter:** High-frequency raw numerical data is exposed uniformly across all screens. The primary Overview page fails to answer the operator's primary question (*"What is the overall state of the robot right now?"*) within five seconds.
- **Responsiveness Limitations:** Fixed-width sidebars (220px) and inflexible column ratios cause clipping and awkward horizontal scrolling on common engineering laptop resolutions (1280×720 and 1366×768).

This audit documents the complete baseline state, catalogs all components and dependencies, and establishes the blueprint for the professional UI/UX transformation.

---

## 2. Architecture & Component Inventory

### 2.1 File & Module Structure

| Path | Primary Purpose | Lines | UI Elements / Dependencies |
| :--- | :--- | :--- | :--- |
| `gracemo_control_center/app.py` | Main window orchestrator | 278 | Top bar, 220px Sidebar, StackedWidget (11 views), Bottom notification bar |
| `gracemo_control_center/resources/styles/tokens.py` | Theme tokens | 46 | Legacy dark palette tokens (`#101820`, `#17232D`, `#F28C28`) |
| `gracemo_control_center/resources/styles/dark_theme.py` | QSS Stylesheet generator | 317 | Global QSS rules, cardPanel, navButton, button classes |
| `gracemo_control_center/widgets/status_indicator.py` | Status pill with LED dot | 115 | Clickable indicator with 5 states (NOT CONNECTED, INITIALIZING, READY, STALE, ERROR) |
| `gracemo_control_center/widgets/camera_view.py` | RGB camera renderer | 134 | QPainter image rendering, FPS/Resolution overlay |
| `gracemo_control_center/widgets/depth_view.py` | Depth sensor renderer | 138 | Colormapped depth map, min/max metric ranges |
| `gracemo_control_center/widgets/lidar_view.py` | Planar LiDAR polar-Cartesian display | 158 | Polar grid, 0.35m safety zone ring, range rings |
| `gracemo_control_center/widgets/map_view.py` | 2D Occupancy Grid map | 224 | Coordinate transforms, robot marker, destination waypoints |
| `gracemo_control_center/widgets/robot_pose_widget.py` | Odometry & AMCL pose | 138 | Compass heading widget, X/Y/Yaw coordinates, velocity readouts |
| `gracemo_control_center/widgets/log_viewer.py` | Unified log table | 148 | Severity filtering, search query matching, table row styling |
| `gracemo_control_center/modules/overview/overview_view.py` | Module 1: Overview Dashboard | 248 | 9-indicator health matrix, pose widget, camera preview, coordinator status |
| `gracemo_control_center/modules/simulation/simulation_view.py` | Module 2: Gazebo Integration | 209 | Clock telemetry, RTF, external Gazebo launcher |
| `gracemo_control_center/modules/navigation/navigation_view.py` | Module 3: Nav2 Command Center | 278 | Map view, 6-destination selector, coordinator action dispatch, cancel action |
| `gracemo_control_center/modules/sensors/sensors_view.py` | Module 4: Sensor Telemetry | 170 | Tabbed views (Vision, LiDAR, Inertial/Odometry) |
| `gracemo_control_center/modules/localization/localization_view.py` | Module 5: AMCL & TF Monitor | 172 | TF chain (`map->odom->base_footprint`), AMCL covariance |
| `gracemo_control_center/modules/interaction/interaction_view.py` | Module 6: Voice & Interaction | 151 | Whisper transcripts, spoken responses, text command input |
| `gracemo_control_center/modules/cognitive/cognitive_view.py` | Module 7: MNSE/K Cognitive | 168 | Kernel HTTP socket probe, Agent Bridge FastMCP status |
| `gracemo_control_center/modules/safety/safety_view.py` | Module 8: Safety & E-Stop | 194 | E-Stop button, single-owner velocity chain, collision/terrain gates |
| `gracemo_control_center/modules/diagnostics/diagnostics_view.py` | Module 9: System Diagnostics | 205 | Host CPU/RAM/GPU telemetry, ROS 2 node & topic table |
| `gracemo_control_center/modules/logs/logs_view.py` | Module 10: System Logs View | 62 | Wraps LogViewerWidget with header card |
| `gracemo_control_center/modules/settings/settings_view.py` | Module 11: Application Settings | 156 | UI update rates, sensor visualizer toggles, safety locks |

### 2.2 Event Bus & Coupling

All modules communicate asynchronously via the centralized `bus` singleton (`core/event_bus.py`).
Key signals:
- **Middleware Lifecycle:** `ros_connected(bool)`, `gazebo_connected(bool)`, `sim_clock_updated(float)`
- **Perception:** `camera_frame_ready`, `depth_image_ready`, `lidar_scan_ready`, `imu_data_ready`, `odometry_ready`
- **Navigation & Localization:** `amcl_pose_ready`, `map_received`, `nav_path_received`, `navigation_goal_dispatched`, `navigation_cancel_requested`, `coordinator_feedback_ready`
- **Interaction:** `user_input_received`, `spoken_feedback_received`
- **Safety & Arbitration:** `emergency_stop_state(bool, str)`, `collision_event_detected`, `terrain_state_updated`
- **Host Metrics:** `system_metrics_updated(dict)`, `log_event_emitted(dict)`, `request_page_navigation(str)`

---

## 3. UI/UX Problem Analysis

### 3.1 Visual Aesthetics & Styling
1. **Dark High-Contrast Harshness:**
   - The dark palette (`#101820` / `#17232D`) makes prolonged viewing taxing under standard indoor office lighting.
   - Text contrast is erratic: some labels use `#AAB8C2` (low contrast on elevated cards), while headers shout in bright `#F28C28` or pure `#FFFFFF`.
2. **Excessive Border Density ("Bordered-Card Hell"):**
   - Almost every widget creates an inner `QFrame` with `border: 1px solid #2E4150` and `border-radius: 6px`.
   - On the Overview and Simulation screens, 4–6 nested bordered boxes compete for visual attention with no whitespace breathing room.
3. **Overuse of Generic Emojis:**
   - The navigation sidebar relies on colored unicode emojis (`📊`, `🌐`, `📡`, `🗺️`, `📍`, `🎙️`, `🧠`, `🛡️`, `💻`, `📜`, `⚙️`). These render inconsistently across Linux distributions and look like an amateur dashboard rather than an aerospace/robotics workstation.

### 3.2 Navigation & Information Architecture
1. **Flat Sidebar Navigation:**
   - 11 buttons stacked vertically with no categorical grouping. An operator looking for "Safety" or "Diagnostics" must scan down a single unsegmented list.
   - Master Prompt requirement: Reorganize into **WORKSPACE**, **ROBOT SYSTEMS**, and **ENGINEERING** sections.
2. **Top Application Bar Inefficiencies:**
   - Status indicators in the top bar have uneven spacing and lack clear labeling of the current page title and overall robot operating state.
   - The simulation clock is visually prominent with harsh orange borders even when the simulation is paused or disconnected.

### 3.3 Module-by-Module Assessment

| Module | Current Flaws | Required Redesign Focus |
| :--- | :--- | :--- |
| **1. Overview** | Overloaded with 9 large indicator cards, cramped camera preview, lack of quick 5-second status assessment. | Primary landing page: Robot readiness summary, mini camera preview, current waypoint, navigation status, recent events, safety badge. |
| **2. Simulation** | Raw text readouts for RTF and model entities; cluttered launcher buttons. | Clean Gazebo Harmonic control, clear world details, connection heartbeat, launch/focus external Gazebo viewer button. |
| **3. Navigation** | Map view and control column have harsh contrast; destination dropdown mixes names and coordinates awkwardly. | Modern 2D map canvas with smooth controls, clear destination pills, goal progress tracker, safe-stop action, expandable advanced details. |
| **4. Sensors** | Tabs are basic; disconnected states look blank rather than informative; fixed heights clip on low-res screens. | Clean sensor arrangement (RGB, Depth, LiDAR, IMU/Odometry), clear disconnected/empty states, full-view expansion. |
| **5. Localization** | Cluttered covariance matrix; TF chain is a horizontal row of bulky pills. | Visual TF tree representation, AMCL particle filter confidence gauge, clean pose & heading card. |
| **6. Voice & Interaction** | Terminal-style black text box with crude text append; text input looks like a raw code input. | Modern conversation log stream with operator vs. robot message bubbles, intent status badge, clean command input bar. |
| **7. Cognitive System** | Probing relies on text readouts; looks like an unfinished placeholder. | MNSE/K status card, Agent Bridge MCP connection state, active task summary, reasoning stage progress, event audit list. |
| **8. Safety** | Dark red background with bright red button (`#201214`); looks alarming even in normal state. | High-visibility authoritative E-Stop banner with 2-step confirmation, clear collision/terrain safe envelopes, immutable hardware lock indicator. |
| **9. Diagnostics** | Progress bars have generic styling; ROS 2 node table has fixed column widths that truncate text. | Sleek system telemetry (CPU, RAM, RTX 5060 GPU/VRAM), searchable ROS 2 active nodes and topic health table. |
| **10. System Logs** | Encapsulated in nested cards; export functionality is not exposed in the header. | Modern engineering log table with timestamp, severity badges (INFO, WARN, ERROR), search query box, severity filters, auto-scroll, export CSV action. |
| **11. Settings** | Inline spinboxes with dark theme styling; no visual grouping of settings categories. | Structured configuration sections (Application, ROS 2, Gazebo, Display, Diagnostics, Interaction, Advanced) with clear descriptions. |

---

## 4. Design & Component Opportunities

To eliminate redundant code and achieve visual consistency, the following reusable UI components must be established:
1. `PageHeader` — Standardized header displaying the section title, breadcrumb description, and contextual status badge or action button.
2. `SectionHeader` — Clean subsection typography with optional counter or metadata.
3. `StatusBadge` — Minimalist status indicator (pill format) with soft background tint, color-coded dot, and crisp typography.
4. `MetricDisplay` — High-visibility value and unit readout for telemetry (speed, sim time, covariance, frequency).
5. `SensorPanel` — Clean frame for video feeds and LiDAR canvases with overlay telemetry and enlargement button.
6. `EmptyState` — Polished placeholder for disconnected sensors or empty log tables explaining current status and recovery action.
7. `AlertBanner` — High-priority notification banner (for E-Stop assertion, hardware safety locks, or lost localization).
8. `PrimaryButton`, `SecondaryButton`, `DangerButton` — Consistent interactive buttons with defined states (hover, pressed, disabled).
9. `ConfirmationDialog` — Clean modal dialog for consequential actions (E-Stop reset, simulation reset).

---

## 5. Technical Safeguards & Invariants

During the transformation, all existing technical and safety invariants must be preserved:
1. **Safety Enforcement:**
   - Physical actuation remains locked: `SAFETY_MOTOR_OUTPUT_ENABLED = 0`, `SAFETY_HARDWARE_PROTOCOL_CONFIRMED = False`.
   - Single-owner `/cmd_vel` publisher pipeline through `safety_gate` remains intact.
2. **ROS 2 & Gazebo Integration:**
   - Single node instance: `ControlCenterNode` (`gracemo_control_center_node`).
   - Zero duplicate publishers or competing subscriber loops.
3. **Pygame Voice Interface:**
   - Preserves `vira_interaction/model.py` independence; UARCC only monitors and submits text commands via `/interaction/user_input`.
4. **Test Suite Compatibility:**
   - All 30 test cases in `test_uarcc_comprehensive.py` must continue to pass without regression.

---

## 6. Phase Roadmap

- **Phase 2:** Implement Design System (`docs/UI_DESIGN_SYSTEM.md`, `tokens.py`, master theme, reusable components).
- **Phase 3:** Redesign Application Shell (`app.py`, 3-group sidebar, top bar, breadcrumb routing).
- **Phase 4:** Redesign all 11 modules systematically.
- **Phase 5:** Verify ROS 2, Gazebo, and EventBus integration.
- **Phase 6:** Run full test suite across window resolutions (1280×720 up to 1920×1080).
- **Phase 7:** Visual QA, screenshots, and completion report (`docs/UI_UX_IMPLEMENTATION_REPORT.md`).
