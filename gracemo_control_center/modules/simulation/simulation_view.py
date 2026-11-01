"""
Module 2: Gazebo Simulation View for GRaCEmo ViRa UARCC.
Monitors Gazebo Harmonic simulation clock, model state, bridge status,
and provides external Gazebo viewer launcher without duplicate instances.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import subprocess
import os
import time

from ...resources.styles.tokens import (
    COLOR_BG_MAIN,
    COLOR_SURFACE,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
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
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)
from ...widgets.status_indicator import StatusIndicator
from ...widgets.common_components import PageHeader, SectionHeader, MetricDisplay, AlertBanner
from ...core.event_bus import bus


class SimulationView(QWidget):
    """Module 2: Gazebo Harmonic simulation monitoring & GUI controls."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.sim_time = 0.0
        self.last_clock_receipt = 0.0
        self.gz_running = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Page Header
        self.header = PageHeader(
            title="Simulation Management",
            subtitle="Gazebo Harmonic physics clock synchronization, bridge health, and external viewer controls",
            badge_title="Simulation Status",
            initial_state=StatusIndicator.STATE_NOT_CONNECTED,
            target_page="Simulation",
            parent=self
        )
        self.ind_gz_status = self.header.badge
        layout.addWidget(self.header)

        # 2. Key Telemetry Metrics
        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)

        self.metric_clock = MetricDisplay("Sim Clock", "0.000 s", status_color=COLOR_ACCENT_PRIMARY, parent=self)
        self.metric_rtf = MetricDisplay("Real-Time Factor", "1.00x", status_color=COLOR_SUCCESS, parent=self)
        self.metric_bridge = MetricDisplay("ros_gz_bridge", "DISCONNECTED", status_color=COLOR_WARNING, parent=self)
        self.metric_world = MetricDisplay("Active World", "Apartment", status_color=COLOR_TEXT_PRIMARY, parent=self)

        metric_row.addWidget(self.metric_clock)
        metric_row.addWidget(self.metric_rtf)
        metric_row.addWidget(self.metric_bridge)
        metric_row.addWidget(self.metric_world)
        layout.addLayout(metric_row)

        # 3. Environment & Bridge Details Card
        clock_card = QFrame(self)
        clock_card.setProperty("class", "cardPanel")
        c_layout = QVBoxLayout(clock_card)
        c_layout.setSpacing(12)

        c_hdr = SectionHeader("Simulation Environment & Bridge Details", parent=self)
        c_layout.addWidget(c_hdr)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.lbl_clock = QLabel("Sim Time: 0.000 s")
        self.lbl_rtf = QLabel("Real-Time Factor: 1.00x")
        self.lbl_bridge = QLabel("ros_gz_bridge: NOT CONNECTED")
        self.lbl_model = QLabel("Model Entity: gracemo_vira")
        self.lbl_world = QLabel("World: gracemo_apartment.world")
        self.lbl_partition = QLabel("GZ_PARTITION: gracemo")

        for lbl in (self.lbl_clock, self.lbl_rtf, self.lbl_bridge, self.lbl_model, self.lbl_world, self.lbl_partition):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")

        grid.addWidget(self.lbl_clock, 0, 0)
        grid.addWidget(self.lbl_rtf, 0, 1)
        grid.addWidget(self.lbl_bridge, 1, 0)
        grid.addWidget(self.lbl_model, 1, 1)
        grid.addWidget(self.lbl_world, 2, 0)
        grid.addWidget(self.lbl_partition, 2, 1)
        c_layout.addLayout(grid)
        layout.addWidget(clock_card)

        # 4. Gazebo Controls Card
        ctrl_card = QFrame(self)
        ctrl_card.setProperty("class", "cardPanel")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setSpacing(12)

        ctrl_hdr = SectionHeader("Gazebo 3D Visualization Controls", parent=self)
        ctrl_layout.addWidget(ctrl_hdr)

        note_lbl = QLabel(
            "Native embedded rendering in Qt can lead to OpenGL context collisions with Gazebo Harmonic.\n"
            "This control center manages and attaches external Gazebo clients to the existing 'gracemo' partition with zero process duplication."
        )
        note_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px; line-height: 1.4;")
        ctrl_layout.addWidget(note_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_launch_gz_gui = QPushButton("Launch Gazebo 3D Window (gz sim -g)", self)
        self.btn_launch_gz_gui.setProperty("class", "primaryButton")
        self.btn_launch_gz_gui.clicked.connect(self._launch_gz_gui)
        btn_row.addWidget(self.btn_launch_gz_gui)

        self.btn_check_processes = QPushButton("Inspect Active Processes", self)
        self.btn_check_processes.setProperty("class", "secondaryButton")
        self.btn_check_processes.clicked.connect(self._inspect_processes)
        btn_row.addWidget(self.btn_check_processes)

        btn_row.addStretch()
        ctrl_layout.addLayout(btn_row)
        layout.addWidget(ctrl_card)

        # 5. Diagnostic Output Console Card
        diag_card = QFrame(self)
        diag_card.setProperty("class", "cardPanel")
        dc_layout = QVBoxLayout(diag_card)
        dc_layout.setSpacing(8)

        dc_hdr = SectionHeader("Simulation Process Telemetry", parent=self)
        dc_layout.addWidget(dc_hdr)

        self.txt_diag = QTextEdit(self)
        self.txt_diag.setReadOnly(True)
        self.txt_diag.setMaximumHeight(160)
        self.txt_diag.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLOR_PANEL_SECONDARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_SM}px;
                color: {COLOR_TEXT_PRIMARY};
                font-family: {FONT_FAMILY_MONO};
                font-size: 11px;
                padding: 8px;
            }}
        """)
        self.txt_diag.setPlaceholderText("Process status and simulation diagnostics will appear here...")
        dc_layout.addWidget(self.txt_diag)
        layout.addWidget(diag_card)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        # Connect bus signals
        bus.sim_clock_updated.connect(self._on_sim_clock)
        bus.gazebo_connected.connect(self._on_gazebo_status)

        # Periodic check for Gazebo process state
        self.proc_timer = QTimer(self)
        self.proc_timer.timeout.connect(self._periodic_check)
        self.proc_timer.start(2000)

    def _on_sim_clock(self, clock_sec: float):
        self.sim_time = clock_sec
        self.last_clock_receipt = time.time()
        self.lbl_clock.setText(f"Sim Time: {clock_sec:.3f} s")
        self.metric_clock.set_value(f"{clock_sec:.2f} s")
        self.lbl_bridge.setText("ros_gz_bridge: CONNECTED & STREAMING")
        self.lbl_bridge.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_SUCCESS};")
        self.metric_bridge.set_value("CONNECTED", status_color=COLOR_SUCCESS)
        self.ind_gz_status.set_state(StatusIndicator.STATE_READY)

    def _on_gazebo_status(self, connected: bool):
        self.gz_running = connected
        st = StatusIndicator.STATE_READY if connected else StatusIndicator.STATE_NOT_CONNECTED
        self.ind_gz_status.set_state(st)
        if not connected:
            self.metric_bridge.set_value("OFFLINE", status_color=COLOR_WARNING)

    def _launch_gz_gui(self):
        """Safely attach Gazebo GUI to existing server partition without creating duplicate instances."""
        try:
            chk = subprocess.run(["pgrep", "-f", "gz sim gui"], capture_output=True, text=True)
            if chk.returncode == 0:
                self.txt_diag.append(f"[INFO] Gazebo GUI client is already running (PID: {chk.stdout.strip()})")
                return

            env = os.environ.copy()
            env["GZ_PARTITION"] = "gracemo"
            env["GZ_IP"] = "127.0.0.1"
            subprocess.Popen(["gz", "sim", "-g"], env=env)
            self.txt_diag.append("🚀 Attached external Gazebo Harmonic GUI client to partition 'gracemo'.")
        except Exception as e:
            self.txt_diag.append(f"[ERROR] Failed to launch Gazebo GUI: {e}")

    def _inspect_processes(self):
        """Query active Gazebo and ROS simulation processes."""
        try:
            res = subprocess.run(
                "ps aux | grep -E 'gz sim|ros_gz_bridge|prototype.launch.py' | grep -v grep",
                shell=True, capture_output=True, text=True
            )
            output = res.stdout.strip()
            if output:
                self.txt_diag.setPlainText(f"--- ACTIVE SIMULATION PROCESSES ---\n{output}")
            else:
                self.txt_diag.setPlainText("Zero simulation processes detected in process table.")
        except Exception as e:
            self.txt_diag.setPlainText(f"Error querying processes: {e}")

    def _periodic_check(self):
        # Watchdog for stale clock (>2s without /clock tick)
        if self.last_clock_receipt > 0 and (time.time() - self.last_clock_receipt > 2.0):
            self.lbl_bridge.setText("ros_gz_bridge: STALE CLOCK")
            self.lbl_bridge.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_WARNING};")
            self.metric_bridge.set_value("STALE", status_color=COLOR_WARNING)
            self.ind_gz_status.set_state(StatusIndicator.STATE_STALE)
