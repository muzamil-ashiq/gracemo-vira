# GRaCEmo ViRa UARCC — Phase 2: Professional UI/UX Design System

**Document:** `docs/UI_DESIGN_SYSTEM.md`  
**Date:** November 2026  
**System:** GRaCEmo ViRa Unified Autonomous Robotics Control Center (UARCC V1.0)  
**Standard:** Enterprise Robotics Engineering Workstation Design Specification  

---

## 1. Design Philosophy & Guidelines

The GRaCEmo ViRa UARCC interface is engineered for real-world robotics development, operational supervision, and hardware-in-the-loop validation.

### Core Principles
1. **Clarity Over Novelty:** Prioritize high-contrast readability, clean typography, and predictable navigation over sci-fi HUD graphics, glowing borders, or artificial gradients.
2. **Restrained Engineering Palette:** Professional light-canvas workspace (`#F5F6F8`) with crisp white surfaces (`#FFFFFF`), anchored by a deep slate navigation sidebar (`#17212B`) and purposeful accent colors.
3. **Structured Information Hierarchy:** Important health and navigation states must be discernible within five seconds. Advanced diagnostic trees and raw ROS message inspection remain accessible via secondary drill-down panels without crowding the primary interface.
4. **Resilience & Honesty:** Display real status, real timestamps, and real data. Never fabricate placeholder measurements. Disconnected states are treated as first-class UI conditions with clear diagnostic feedback.
5. **Deterministic Responsiveness:** Fluid adaptation across standard 16:9 and 16:10 engineering displays (1280×720, 1366×768, 1600×900, 1920×1080) without content truncation or double scrollbars.

---

## 2. Color System & Semantic Tokens

### 2.1 Foundational Palette

```
Surface & Structure:
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ Main Canvas: #F5F6F8 │ Content Card: #FFFFFF│ Nav Sidebar: #17212B │
└──────────────────────┴──────────────────────┴──────────────────────┘
Text & Borders:
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ Primary Text: #202B36│ Second Text: #687583 │ Subtle Border: #E3E7EB
└──────────────────────┴──────────────────────┴──────────────────────┘
Semantic Accents:
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ Primary: #2463A6     │ Success: #23865B     │ Warning: #D99A2B     │
│ Error:   #C74747     │ Brand Accent: #E65100│ Muted/Offline: #8896A4
└──────────────────────┴──────────────────────┴──────────────────────┘
```

### 2.2 Semantic Token Mapping

| Token Name | Hex Code | Usage |
| :--- | :--- | :--- |
| `COLOR_BG_MAIN` | `#F5F6F8` | Primary desktop application canvas background |
| `COLOR_SURFACE` | `#FFFFFF` | Main content cards, table containers, and inspect panels |
| `COLOR_SURFACE_ALT` | `#F0F3F6` | Secondary input backgrounds, table header bars, and inner wells |
| `COLOR_SIDEBAR_BG` | `#17212B` | Persistent left navigation sidebar background |
| `COLOR_SIDEBAR_ACTIVE` | `#233241` | Active navigation menu item background |
| `COLOR_SIDEBAR_HOVER` | `#1D2A37` | Hovered navigation menu item background |
| `COLOR_TEXT_PRIMARY` | `#202B36` | Headings, primary metrics, active values, button labels |
| `COLOR_TEXT_SECONDARY`| `#687583` | Subtitles, field labels, metadata, inactive items |
| `COLOR_TEXT_MUTED` | `#9AA6B2` | Placeholders, disabled actions, minor captions |
| `COLOR_TEXT_SIDEBAR` | `#D6E0EA` | Primary navigation item text on dark sidebar |
| `COLOR_BORDER` | `#E3E7EB` | Standard divider and card outline border |
| `COLOR_BORDER_FOCUS` | `#2463A6` | Focused inputs, selected items, active tabs |
| `COLOR_ACCENT_PRIMARY`| `#2463A6` | Primary action buttons, active indicators, tab highlights |
| `COLOR_ACCENT_HOVER` | `#1B4E85` | Hover state for primary action buttons |
| `COLOR_BRAND_ORANGE` | `#E65100` | GRaCEmo brand highlight, robot identity tag, safety badge |
| `COLOR_SUCCESS` | `#23865B` | Healthy subsystems, active nodes, normal navigation, arrival |
| `COLOR_SUCCESS_BG` | `#EBF5F0` | Soft background tint for successful status pills |
| `COLOR_WARNING` | `#D99A2B` | Stale sensor data, low covariance, high temperature |
| `COLOR_WARNING_BG` | `#FBF4E8` | Soft background tint for warning status pills |
| `COLOR_ERROR` | `#C74747` | Emergency stop asserted, node crash, sensor disconnect |
| `COLOR_ERROR_BG` | `#FAECEC` | Soft background tint for error status pills and alerts |
| `COLOR_OFFLINE` | `#8896A4` | Disconnected sensors, uninitialized nodes, offline daemon |
| `COLOR_OFFLINE_BG` | `#EDF0F3` | Soft background tint for offline status pills |

---

## 3. Typography Hierarchy

Primary Font: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`  
Monospace Font: `"JetBrains Mono", "Fira Code", "DejaVu Sans Mono", Consolas, monospace`

| Level | Size / Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- |
| **Page Title** | 22–24 px / 700 (Bold) | 28 px | Main view header (e.g. "System Overview", "Navigation") |
| **Section Title** | 15–16 px / 600 (Semibold) | 22 px | Group headings, card titles, table headers |
| **Subsection / Label** | 12–13 px / 600 (Semibold) | 18 px | Form labels, metric descriptors (uppercase tracking: 0.5px) |
| **Body Text** | 13–14 px / 400 (Regular) | 20 px | General descriptions, descriptions, dialogue messages |
| **Secondary Caption** | 11–12 px / 400 (Regular) | 16 px | Subtitles, timestamp strings, hints |
| **Primary Telemetry** | 22–28 px / 700 (Bold Mono) | 32 px | High-visibility values (speed, battery, covariance, pose) |
| **Monospace Data** | 12 px / 500 (Medium Mono) | 18 px | ROS topics, coordinate tuples, frame names, logs |

---

## 4. Spacing, Geometry & Layout System

### 4.1 Spacing Scale
- `SPACING_XS` = 4 px (Micro-gap between indicator dot and label)
- `SPACING_SM` = 8 px (Standard row element gap, button inner padding)
- `SPACING_MD` = 12 px (Gap between metric cards, container inner margins)
- `SPACING_LG` = 16 px (Page margins, major panel separation)
- `SPACING_XL` = 24 px (Section division, top-level layout gaps)

### 4.2 Elevation & Geometry
- **Border Radius:**
  - `RADIUS_SM` = 4 px (Pills, small buttons, input fields)
  - `RADIUS_MD` = 6 px (Standard content cards, tables, panels)
  - `RADIUS_LG` = 8 px (Modal dialogs, major view containers)
- **Shadows:** No heavy drop-shadows. Clean 1px solid borders (`#E3E7EB`) provide sharp, precise distinction.

---

## 5. Standardized Reusable UI Components

### 5.1 PageHeader
Standardized header for every module view:
- **Title:** Bold 22px heading.
- **Description:** 12px secondary text explaining the functional scope.
- **Context Badge:** High-level status pill (e.g., "SIMULATION READY", "AUTONOMOUS IDLE").
- **Header Actions:** Optional primary action button (e.g., "Focus Gazebo", "Clear E-Stop", "Export Logs").

### 5.2 SectionHeader
Standardized group header:
- Semibold 15px title with optional subtitle or badge counter.
- Subtle bottom divider or clean margin separation.

### 5.3 StatusBadge
Refined status indicator with subtle colored background tint, solid LED dot, and semantic text:
- **States:** `READY`, `INITIALIZING`, `STALE DATA`, `ERROR`, `NOT CONNECTED`.
- Hover behavior: Subtle border highlight if configured as a navigation link.

### 5.4 MetricDisplay
Compact engineering value card:
- Top: Uppercase 11px label (`X POSITION`, `LINEAR VELOCITY`).
- Middle: Large 22px value with monospace formatting (`+1.450 m/s`).
- Bottom: Optional sub-label or trend description (`Confidence: 99.4%`).

### 5.5 SensorPanel
Container for visual streams (RGB Camera, Depth, LiDAR):
- Top bar with sensor frame name, update frequency, and full-view toggle.
- Clean display canvas with automatic aspect ratio scaling.
- Integrated `EmptyState` when the sensor feed is offline or uninitialized.

### 5.6 EmptyState
Standardized message container displayed when a subsystem or data source is inactive:
- Clean monochrome SVG/vector icon.
- Concise headline (e.g. "No Live Camera Stream").
- Helpful resolution tip (e.g. "Ensure Gazebo simulation is running and ros_gz_bridge is active").

### 5.7 AlertBanner
Full-width notification banner for consequential events:
- Distinct color-coded left border (4px) and soft background tint.
- Critical priority for E-Stop and safety gate events.

### 5.8 Buttons Hierarchy
- **Primary Action (`PrimaryButton`):** Filled `#2463A6`, white text, 600 weight. Used for primary user commands (e.g., "Dispatch Goal").
- **Secondary Action (`SecondaryButton`):** Clean surface `#FFFFFF` with `#E3E7EB` border, `#202B36` text. Used for cancellations, refreshes, filters.
- **Danger Action (`DangerButton`):** High-contrast `#C74747` with white text. Reserved strictly for E-Stop engagement and critical aborts.

### 5.9 ConfirmationDialog
Two-step confirmation modal for consequential operations:
- Clear headline outlining the exact consequence.
- Explicit confirmation requirement before proceeding.

---

## 6. Application Shell Layout

### 6.1 Layout Overview
```
┌────────────────────────────────────────────────────────────────────────┐
│ TOP BAR: [Brand] [Page Title] | [ROS 2] [GZ] [Robot] [E-Stop] | [Clock]│
├───────────────┬────────────────────────────────────────────────────────┤
│ SIDEBAR       │ MAIN CONTENT AREA                                      │
│               │                                                        │
│ WORKSPACE     │ [Page Header: Title + Description + Status Badge]     │
│  Overview     │ ────────────────────────────────────────────────────── │
│  Simulation   │                                                        │
│  Navigation   │ [Structured Content Area: Cards, Maps, Tables, Feeds]  │
│  Sensors      │                                                        │
│               │                                                        │
│ ROBOT SYSTEMS │                                                        │
│  Localization │                                                        │
│  Voice & Int. │                                                        │
│  Cognitive    │                                                        │
│               │                                                        │
│ ENGINEERING   │                                                        │
│  Safety       │                                                        │
│  Diagnostics  │                                                        │
│  System Logs  │                                                        │
│  Settings     │                                                        │
│               │                                                        │
│ [Safety Lock] │                                                        │
├───────────────┴────────────────────────────────────────────────────────┤
│ BOTTOM BAR: [System Notification Stream]             [DDS / Partition] │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Responsive Behavior Matrix
- **1280 × 720 (Compact HD):** Sidebar compresses to compact mode (180px); 2-column layouts wrap into single-column vertical stacks; map and camera viewports maintain minimum 320px heights.
- **1366 × 768 (Standard Laptop):** Sidebar 200px; 2-column layouts comfortable; telemetry cards arranged in 3-column grids.
- **1600 × 900 (Widescreen):** Sidebar 220px; side-by-side map and navigation column; sensor tabs display dual-stream 640px feeds.
- **1920 × 1080 (Full HD Workstation):** Sidebar 240px; generous whitespace; simultaneous dual-view inspection enabled.
