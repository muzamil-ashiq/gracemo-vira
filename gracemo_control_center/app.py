"""
GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC).
Main Window Orchestrator with Professional 3-Group Sidebar, Top Status Bar,
Bottom Notification Bar, and Stacked Multi-Module View Routing.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QStackedWidget, QButtonGroup
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon

from .resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_SIDEBAR_BG,
    COLOR_SIDEBAR_ACTIVE,
    COLOR_SIDEBAR_HOVER,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_BRAND_ORANGE,
    COLOR_ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SIDEBAR,
    COLOR_TEXT_SIDEBAR_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)
from .resources.styles.dark_theme import get_application_stylesheet
from .widgets.status_indicator import StatusIndicator
from .config.settings import Settings
from .core.event_bus import bus

# Import All 11 Module Views
from .modules.overview.overview_view import OverviewView
from .modules.simulation.simulation_view import SimulationView
from .modules.sensors.sensors_view import SensorsView
from .modules.navigation.navigation_view import NavigationView
from .modules.localization.localization_view import LocalizationView
from .modules.interaction.interaction_view import InteractionView
from .modules.cognitive.cognitive_view import CognitiveView
from .modules.safety.safety_view import SafetyView
from .modules.diagnostics.diagnostics_view import DiagnosticsView
from .modules.logs.logs_view import LogsView
from .modules.settings.settings_view import SettingsView


class MainWindow(QMainWindow):
    """Primary UARCC Engineering Desktop Application Window."""

    # Categorized 3-Group Navigation Structure
    NAVIGATION_GROUPS = [
        ("WORKSPACE", [
            ("Overview", "Overview"),
            ("Simulation", "Simulation"),
            ("Navigation", "Navigation"),
            ("Sensors", "Sensors"),
        ]),
        ("ROBOT SYSTEMS", [
            ("Localization", "Localization"),
            ("Voice & Interaction", "Voice & Interaction"),
            ("Cognitive System", "Cognitive System"),
        ]),
        ("ENGINEERING", [
            ("Safety", "Safety"),
            ("Diagnostics", "Diagnostics"),
            ("System Logs", "System Logs"),
            ("Settings", "Settings"),
        ])
    ]

    MODULE_NAMES = [
        ("Overview", ""),
        ("Simulation", ""),
        ("Sensors", ""),
        ("Navigation", ""),
        ("Localization", ""),
        ("Voice & Interaction", ""),
        ("Cognitive System", ""),
        ("Safety", ""),
        ("Diagnostics", ""),
        ("System Logs", ""),
        ("Settings", "")
    ]

    MODULE_DESCRIPTIONS = {
        "Overview": "Operational readiness, subsystem health matrix, and live pose telemetry",
        "Simulation": "Gazebo Harmonic environment, physics clock, and simulation runtime control",
        "Navigation": "2D Occupancy Grid map, destination waypoint dispatch, and route tracking",
        "Sensors": "Multi-modal vision feeds, 360° planar LiDAR, IMU attitude, and odometry",
        "Localization": "AMCL particle filter covariance and authoritative TF coordinate tree",
        "Voice & Interaction": "Whisper speech-to-text, spoken TTS responses, and dialogue grounding",
        "Cognitive System": "MNSE/K cognitive kernel, Agent Bridge task queue, and approval gates",
        "Safety": "Authoritative E-Stop gate, collision monitor, terrain limits, and hardware safety locks",
        "Diagnostics": "ROS 2 Jazzy node graph health, topic telemetry, and host CPU/RAM/GPU metrics",
        "System Logs": "Unified multi-source event logging, severity filtering, and export tools",
        "Settings": "Application refresh rates, sensor visualization tolerances, and preferences",
    }

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("GRaCEmo ViRa — Unified Autonomous Robotics Control Center V1.0")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 720)

        # Apply global professional engineering stylesheet
        self.setStyleSheet(get_application_stylesheet())

        # Central Container
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Status Bar
        self.top_status_bar = self._create_top_status_bar()
        main_layout.addWidget(self.top_status_bar)

        # 2. Body Layout (Categorized Sidebar + Central Stacked Content)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Sidebar Navigation
        self.sidebar = self._create_sidebar()
        body_layout.addWidget(self.sidebar)

        # Stacked Views Container
        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet(f"background-color: {COLOR_BG_MAIN};")
        self._instantiate_module_views()
        body_layout.addWidget(self.stack, stretch=1)

        main_layout.addLayout(body_layout)

        # 3. Persistent Bottom Status & Notification Area
        self.bottom_bar = self._create_bottom_bar()
        main_layout.addWidget(self.bottom_bar)

        # Connect Navigation routing signal
        bus.request_page_navigation.connect(self.switch_to_page)

        # Select Overview by default
        self.switch_to_page("Overview")

    def _create_top_status_bar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("topStatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        # Left: Active Page Header Breadcrumb
        page_box = QVBoxLayout()
        page_box.setSpacing(1)

        self.lbl_top_page_title = QLabel("Overview", self)
        self.lbl_top_page_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLOR_TEXT_PRIMARY};")
        page_box.addWidget(self.lbl_top_page_title)

        self.lbl_top_page_desc = QLabel(self.MODULE_DESCRIPTIONS.get("Overview", ""), self)
        self.lbl_top_page_desc.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY};")
        page_box.addWidget(self.lbl_top_page_desc)

        layout.addLayout(page_box)
        layout.addSpacing(16)
        layout.addStretch()

        # Center/Right: Key Subsystem Status Indicators
        self.top_ind_ros = StatusIndicator("ROS 2", StatusIndicator.STATE_NOT_CONNECTED, "Diagnostics")
        self.top_ind_gz = StatusIndicator("Gazebo", StatusIndicator.STATE_NOT_CONNECTED, "Simulation")
        self.top_ind_fsm = StatusIndicator("Robot State", StatusIndicator.STATE_READY, "Navigation")
        self.top_ind_loc = StatusIndicator("Localization", StatusIndicator.STATE_NOT_CONNECTED, "Localization")
        self.top_ind_estop = StatusIndicator("E-Stop", StatusIndicator.STATE_READY, "Safety")

        for ind in (self.top_ind_ros, self.top_ind_gz, self.top_ind_fsm, self.top_ind_loc, self.top_ind_estop):
            ind.clicked.connect(self.switch_to_page)
            layout.addWidget(ind)

        layout.addSpacing(10)

        # Simulation Time Clock Display (Clean Monospace Badge)
        self.lbl_top_clock = QLabel("Sim Time: 0.000 s", self)
        self.lbl_top_clock.setStyleSheet(f"""
            font-family: {FONT_FAMILY_MONO};
            font-size: 11px;
            font-weight: 600;
            color: {COLOR_TEXT_PRIMARY};
            background-color: {COLOR_SURFACE_ALT};
            padding: 4px 10px;
            border-radius: {BORDER_RADIUS_SM}px;
            border: 1px solid {COLOR_BORDER};
        """)
        layout.addWidget(self.lbl_top_clock)

        # Connect top status bar signals
        bus.ros_connected.connect(lambda ok: self.top_ind_ros.set_state(StatusIndicator.STATE_READY if ok else StatusIndicator.STATE_NOT_CONNECTED))
        bus.gazebo_connected.connect(lambda ok: self.top_ind_gz.set_state(StatusIndicator.STATE_READY if ok else StatusIndicator.STATE_NOT_CONNECTED))
        bus.amcl_pose_ready.connect(lambda *_: self.top_ind_loc.set_state(StatusIndicator.STATE_READY))
        bus.sim_clock_updated.connect(lambda t: self.lbl_top_clock.setText(f"Sim Time: {t:.3f} s"))
        bus.emergency_stop_state.connect(self._on_estop_state_top)
        bus.coordinator_feedback_ready.connect(self._on_coordinator_feedback_top)

        return bar

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame(self)
        sidebar.setObjectName("sidebarPanel")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(0)

        # Brand Header
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(16, 0, 16, 16)
        brand_box.setSpacing(2)

        lbl_brand = QLabel("GRaCEmo ViRa", sidebar)
        lbl_brand.setProperty("class", "sidebarBrandTitle")
        brand_box.addWidget(lbl_brand)

        lbl_sub = QLabel("CONTROL CENTER", sidebar)
        lbl_sub.setProperty("class", "sidebarBrandSubtitle")
        brand_box.addWidget(lbl_sub)

        layout.addLayout(brand_box)

        # Navigation Button Group
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.nav_buttons = {}

        # 3 Structured Categories: WORKSPACE, ROBOT SYSTEMS, ENGINEERING
        current_stack_idx = 0
        for cat_name, items in self.NAVIGATION_GROUPS:
            cat_lbl = QLabel(cat_name, sidebar)
            cat_lbl.setProperty("class", "sidebarCategoryHeader")
            layout.addWidget(cat_lbl)

            for label, mod_name in items:
                btn = QPushButton(f"  {label}", sidebar)
                btn.setProperty("class", "navButton")
                btn.setCheckable(True)
                btn.clicked.connect(lambda checked, name=mod_name: self.switch_to_page(name))
                self.btn_group.addButton(btn)
                self.nav_buttons[mod_name] = btn
                layout.addWidget(btn)

            layout.addSpacing(6)

        layout.addStretch()

        # Persistent Hardware Safety Lock Footer
        hw_box = QFrame(sidebar)
        hw_box.setStyleSheet(f"""
            background-color: #121A22;
            border-top: 1px solid #233241;
            padding: 12px 16px;
        """)
        hw_layout = QVBoxLayout(hw_box)
        hw_layout.setContentsMargins(0, 0, 0, 0)
        hw_layout.setSpacing(3)

        hw_lbl1 = QLabel("🔒 HARDWARE LOCKED", hw_box)
        hw_lbl1.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLOR_BRAND_ORANGE}; letter-spacing: 0.5px;")
        hw_layout.addWidget(hw_lbl1)

        hw_lbl2 = QLabel("Physical Actuation Disabled", hw_box)
        hw_lbl2.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SIDEBAR_MUTED};")
        hw_layout.addWidget(hw_lbl2)

        layout.addWidget(hw_box)
        return sidebar

    def _instantiate_module_views(self):
        """Create and register all 11 functional views in canonical order."""
        self.view_overview = OverviewView(self)
        self.view_overview.request_page.connect(self.switch_to_page)
        self.stack.addWidget(self.view_overview) # 0

        self.view_simulation = SimulationView(self)
        self.stack.addWidget(self.view_simulation) # 1

        self.view_sensors = SensorsView(self)
        self.stack.addWidget(self.view_sensors) # 2

        self.view_navigation = NavigationView(self.settings, self)
        self.stack.addWidget(self.view_navigation) # 3

        self.view_localization = LocalizationView(self)
        self.stack.addWidget(self.view_localization) # 4

        self.view_interaction = InteractionView(self)
        self.stack.addWidget(self.view_interaction) # 5

        self.view_cognitive = CognitiveView(self)
        self.stack.addWidget(self.view_cognitive) # 6

        self.view_safety = SafetyView(self)
        self.stack.addWidget(self.view_safety) # 7

        self.view_diagnostics = DiagnosticsView(self)
        self.stack.addWidget(self.view_diagnostics) # 8

        self.view_logs = LogsView(self)
        self.stack.addWidget(self.view_logs) # 9

        self.view_settings = SettingsView(self.settings, self)
        self.stack.addWidget(self.view_settings) # 10

    def _create_bottom_bar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("bottomNotificationBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 5, 16, 5)
        layout.setSpacing(12)

        self.lbl_bottom_status = QLabel("System Status: All subsystems initialized. Ready for operation.", self)
        self.lbl_bottom_status.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SECONDARY};")
        layout.addWidget(self.lbl_bottom_status)

        layout.addStretch()

        self.lbl_dds_info = QLabel("ROS Discovery: LOCALHOST  |  GZ Partition: gracemo", self)
        self.lbl_dds_info.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; color: {COLOR_TEXT_MUTED};")
        layout.addWidget(self.lbl_dds_info)

        # Connect feedback to bottom bar
        bus.spoken_feedback_received.connect(lambda text, st: self.set_notification(f"GRaCEmo: {text}"))
        bus.coordinator_feedback_ready.connect(lambda st, speech, *_: self.set_notification(f"Coordinator [{st}]: {speech}"))

        return bar

    def set_notification(self, text: str):
        self.lbl_bottom_status.setText(text)

    def switch_to_page(self, page_name: str):
        """Programmatic page switching via signal or button click."""
        canonical_map = {
            "overview": (0, "Overview"),
            "simulation": (1, "Simulation"),
            "sensors": (2, "Sensors"),
            "navigation": (3, "Navigation"),
            "localization": (4, "Localization"),
            "voice": (5, "Voice & Interaction"),
            "voice & interaction": (5, "Voice & Interaction"),
            "interaction": (5, "Voice & Interaction"),
            "cognitive": (6, "Cognitive System"),
            "cognitive system": (6, "Cognitive System"),
            "safety": (7, "Safety"),
            "diagnostics": (8, "Diagnostics"),
            "logs": (9, "System Logs"),
            "system logs": (9, "System Logs"),
            "settings": (10, "Settings"),
        }

        key = page_name.lower().strip()
        target = canonical_map.get(key)
        if not target:
            # Fuzzy match
            for k, val in canonical_map.items():
                if k in key or key in k:
                    target = val
                    break

        if target:
            idx, canonical_name = target
            self.stack.setCurrentIndex(idx)
            if canonical_name in self.nav_buttons:
                self.nav_buttons[canonical_name].setChecked(True)
            self.lbl_top_page_title.setText(canonical_name)
            self.lbl_top_page_desc.setText(self.MODULE_DESCRIPTIONS.get(canonical_name, ""))

    def _on_estop_state_top(self, is_active: bool, source: str):
        if is_active:
            self.top_ind_estop.set_state(StatusIndicator.STATE_ERROR)
            self.set_notification(f"🚨 EMERGENCY STOP ASSERTED by {source}!")
        else:
            self.top_ind_estop.set_state(StatusIndicator.STATE_READY)
            self.set_notification("Emergency Stop cleared. System operational.")

    def _on_coordinator_feedback_top(self, status: str, speech: str, details: dict, timestamp: float):
        if status in ("NAVIGATING", "EXECUTING"):
            self.top_ind_fsm.set_state(StatusIndicator.STATE_READY, f"State: {status}")
        elif status == "SUCCEEDED":
            self.top_ind_fsm.set_state(StatusIndicator.STATE_READY, "Arrived at destination")
        elif status in ("FAILED", "CANCELED"):
            self.top_ind_fsm.set_state(StatusIndicator.STATE_WARNING, f"State: {status}")
