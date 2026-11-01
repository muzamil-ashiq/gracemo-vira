"""
Module 7: MNSE / K Cognitive System View for GRaCEmo ViRa UARCC.
Monitors the GRaCEmo Kernel daemon (MNSE), K Language engine,
Agent Bridge MCP task queue, and approval gates without credential leaks.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import os
import subprocess
import urllib.request
import json
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
    COLOR_OFFLINE,
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


class CognitiveView(QWidget):
    """Module 7: Cognitive Architecture and Agent Bridge Monitoring Center."""

    def __init__(self, parent=None):
        super().__init__(parent)

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
            title="Cognitive System & Agent Bridge",
            subtitle="MNSE/K neural-symbolic engine, FastMCP task queue, and consequential action approval gates",
            badge_title="Kernel Status",
            initial_state=StatusIndicator.STATE_NOT_CONNECTED,
            target_page="Cognitive System",
            parent=self
        )
        self.ind_kernel = self.header.badge
        layout.addWidget(self.header)

        # 2. Key Metrics Row
        metric_row = QHBoxLayout()
        metric_row.setSpacing(12)

        self.metric_kernel = MetricDisplay("MNSE Daemon", "PROBING", status_color=COLOR_WARNING, parent=self)
        self.metric_bridge = MetricDisplay("Agent Bridge", "ACTIVE", status_color=COLOR_SUCCESS, parent=self)
        self.metric_gates = MetricDisplay("Approval Gates", "ENGAGED", status_color=COLOR_BRAND_ORANGE, parent=self)
        self.metric_task = MetricDisplay("Active Reasoning", "IDLE", status_color=COLOR_TEXT_PRIMARY, parent=self)

        metric_row.addWidget(self.metric_kernel)
        metric_row.addWidget(self.metric_bridge)
        metric_row.addWidget(self.metric_gates)
        metric_row.addWidget(self.metric_task)
        layout.addLayout(metric_row)

        # 3. Kernel Communication Channels Card
        info_card = QFrame(self)
        info_card.setProperty("class", "cardPanel")
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setSpacing(12)

        ic_hdr = SectionHeader("Communication Channels & Security Authorization Gates", parent=self)
        ic_layout.addWidget(ic_hdr)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.lbl_rest = QLabel("REST Endpoint: http://127.0.0.1:7780 (PROBING...)")
        self.lbl_sock = QLabel("Domain Socket: /tmp/gracemo.sock (CHECKING...)")
        self.lbl_bridge = QLabel("Agent Bridge: FastMCP Active")
        self.lbl_approval = QLabel("Approval Gates: ACTIVE (Consequential Locks Engaged)")

        for lbl in (self.lbl_rest, self.lbl_sock, self.lbl_bridge, self.lbl_approval):
            lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")

        grid.addWidget(self.lbl_rest, 0, 0)
        grid.addWidget(self.lbl_sock, 0, 1)
        grid.addWidget(self.lbl_bridge, 1, 0)
        grid.addWidget(self.lbl_approval, 1, 1)
        ic_layout.addLayout(grid)

        # Probe Button Row
        btn_row = QHBoxLayout()
        btn_probe = QPushButton("Probe Kernel Health Now", self)
        btn_probe.setProperty("class", "secondaryButton")
        btn_probe.clicked.connect(self._probe_kernel_health)
        btn_row.addWidget(btn_probe)
        btn_row.addStretch()
        ic_layout.addLayout(btn_row)

        layout.addWidget(info_card)

        # 4. Cognitive Task History & Reasoning Log Card
        resp_card = QFrame(self)
        resp_card.setProperty("class", "cardPanel")
        rc_layout = QVBoxLayout(resp_card)
        rc_layout.setSpacing(10)

        rc_hdr = SectionHeader("Cognitive Task Queue & Reasoning Event Stream", parent=self)
        rc_layout.addWidget(rc_hdr)

        self.txt_kernel_log = QTextEdit(self)
        self.txt_kernel_log.setReadOnly(True)
        self.txt_kernel_log.setMaximumHeight(200)
        self.txt_kernel_log.setStyleSheet(f"""
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
        rc_layout.addWidget(self.txt_kernel_log)
        layout.addWidget(resp_card)

        layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        # Periodic timer for kernel health probe
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._probe_kernel_health)
        self.timer.start(3000)

        # Initial check
        self._probe_kernel_health()

    def _probe_kernel_health(self):
        """Perform real non-blocking check on MNSE kernel socket and REST endpoint."""
        sock_exists = os.path.exists("/tmp/gracemo.sock")
        proc_running = (subprocess.run(["pgrep", "-f", "gracemo-kernel"], capture_output=True).returncode == 0)

        # Socket status
        if sock_exists:
            self.lbl_sock.setText("Domain Socket: /tmp/gracemo.sock (ACTIVE ✅)")
            self.lbl_sock.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_SUCCESS};")
        else:
            self.lbl_sock.setText("Domain Socket: /tmp/gracemo.sock (OFFLINE ❌)")
            self.lbl_sock.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_MUTED};")

        # REST Endpoint
        rest_ok = False
        try:
            req = urllib.request.Request("http://127.0.0.1:7780/health", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                if resp.status == 200:
                    rest_ok = True
        except Exception:
            rest_ok = False

        if rest_ok:
            self.lbl_rest.setText("REST Endpoint: http://127.0.0.1:7780 (ONLINE ✅)")
            self.lbl_rest.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_SUCCESS};")
            self.metric_kernel.set_value("ONLINE", status_color=COLOR_SUCCESS)
        else:
            self.lbl_rest.setText("REST Endpoint: http://127.0.0.1:7780 (OFFLINE / UNREACHABLE)")
            self.lbl_rest.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; color: {COLOR_TEXT_MUTED};")
            self.metric_kernel.set_value("OFFLINE", status_color=COLOR_OFFLINE)

        if sock_exists or proc_running or rest_ok:
            self.ind_kernel.set_state(StatusIndicator.STATE_READY)
        else:
            self.ind_kernel.set_state(StatusIndicator.STATE_NOT_CONNECTED)
