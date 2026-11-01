"""
High-Performance Filterable Log Viewer Widget for GRaCEmo ViRa.
Features multi-level severity filtering, full-text search,
follow-latest autoscroll, and log export.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor, QFont

import os
import json
import time
from typing import List, Dict, Any

from ..resources.styles.tokens import (
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_PANEL_MAIN,
    COLOR_PANEL_SECONDARY,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO,
    BORDER_RADIUS_SM,
    BORDER_RADIUS_MD,
)


class LogViewerWidget(QFrame):
    """Unified system log and event history table."""

    LEVEL_COLORS = {
        "DEBUG": COLOR_TEXT_MUTED,
        "INFO": COLOR_SUCCESS,
        "WARN": COLOR_WARNING,
        "WARNING": COLOR_WARNING,
        "ERROR": COLOR_ERROR,
        "CRITICAL": "#B91C1C",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: {BORDER_RADIUS_MD}px;
            }}
        """)

        self.all_logs: List[Dict[str, Any]] = []
        self.auto_scroll = True

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Controls Bar (Search + Filters + Actions)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)

        # Search Bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search log message or component...")
        self.search_input.textChanged.connect(self._apply_filters)
        ctrl_layout.addWidget(self.search_input, stretch=2)

        # Severity Filter Dropdown
        self.level_filter = QComboBox(self)
        self.level_filter.addItems(["All Severities", "INFO", "WARN", "ERROR", "CRITICAL"])
        self.level_filter.currentTextChanged.connect(self._apply_filters)
        ctrl_layout.addWidget(self.level_filter, stretch=1)

        # Component Filter Dropdown
        self.component_filter = QComboBox(self)
        self.component_filter.addItems([
            "All Components", "Navigation", "Localization", "Safety",
            "Voice", "Cognitive", "Gazebo", "ROS 2", "Coordinator"
        ])
        self.component_filter.currentTextChanged.connect(self._apply_filters)
        ctrl_layout.addWidget(self.component_filter, stretch=1)

        # Auto-scroll Toggle
        self.chk_autoscroll = QCheckBox("Follow Latest", self)
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.toggled.connect(self._toggle_autoscroll)
        ctrl_layout.addWidget(self.chk_autoscroll)

        # Clear Button
        self.btn_clear = QPushButton("Clear", self)
        self.btn_clear.setProperty("class", "secondaryButton")
        self.btn_clear.clicked.connect(self.clear_logs)
        ctrl_layout.addWidget(self.btn_clear)

        # Export Button
        self.btn_export = QPushButton("Export...", self)
        self.btn_export.setProperty("class", "secondaryButton")
        self.btn_export.clicked.connect(self.export_logs)
        ctrl_layout.addWidget(self.btn_export)

        main_layout.addLayout(ctrl_layout)

        # Table Widget
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["TIMESTAMP", "LEVEL", "COMPONENT", "SOURCE", "MESSAGE"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table)

    def add_log(self, level: str, component: str, source: str, message: str, timestamp: float = None):
        """Append a new log record."""
        ts = timestamp or time.time()
        time_str = QDateTime.fromSecsSinceEpoch(int(ts)).toString("hh:mm:ss.zzz")

        entry = {
            "timestamp": ts,
            "time_str": time_str,
            "level": level.upper(),
            "component": component,
            "source": source,
            "message": message
        }
        self.all_logs.append(entry)

        if self._matches_filter(entry):
            self._insert_table_row(entry)

    def _matches_filter(self, entry: Dict[str, Any]) -> bool:
        search_query = self.search_input.text().lower()
        if search_query:
            combined = f"{entry['component']} {entry['source']} {entry['message']}".lower()
            if search_query not in combined:
                return False

        lvl_filter = self.level_filter.currentText()
        if lvl_filter != "All Severities":
            if lvl_filter == "WARN" and entry["level"] in ("WARN", "WARNING"):
                pass
            elif entry["level"] != lvl_filter:
                return False

        comp_filter = self.component_filter.currentText()
        if comp_filter != "All Components":
            if comp_filter.lower() not in entry["component"].lower():
                return False

        return True

    def _insert_table_row(self, entry: Dict[str, Any]):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 0. Timestamp
        it_time = QTableWidgetItem(entry["time_str"])
        it_time.setFont(QFont(FONT_FAMILY_MONO, 10))
        it_time.setForeground(QColor(COLOR_TEXT_SECONDARY))
        self.table.setItem(row, 0, it_time)

        # 1. Level
        it_lvl = QTableWidgetItem(entry["level"])
        it_lvl.setFont(QFont(FONT_FAMILY_MONO, 10, QFont.Bold))
        color = self.LEVEL_COLORS.get(entry["level"], COLOR_TEXT_PRIMARY)
        it_lvl.setForeground(QColor(color))
        self.table.setItem(row, 1, it_lvl)

        # 2. Component
        it_comp = QTableWidgetItem(entry["component"])
        it_comp.setFont(QFont(FONT_FAMILY_PRIMARY, 10, QFont.DemiBold))
        self.table.setItem(row, 2, it_comp)

        # 3. Source
        it_src = QTableWidgetItem(entry["source"])
        it_src.setFont(QFont(FONT_FAMILY_MONO, 9))
        it_src.setForeground(QColor(COLOR_TEXT_MUTED))
        self.table.setItem(row, 3, it_src)

        # 4. Message
        it_msg = QTableWidgetItem(entry["message"])
        it_msg.setFont(QFont(FONT_FAMILY_PRIMARY, 11))
        self.table.setItem(row, 4, it_msg)

        if self.auto_scroll:
            self.table.scrollToBottom()

    def _apply_filters(self):
        self.table.setRowCount(0)
        for entry in self.all_logs:
            if self._matches_filter(entry):
                self._insert_table_row(entry)

    def _toggle_autoscroll(self, checked: bool):
        self.auto_scroll = checked
        if checked:
            self.table.scrollToBottom()

    def clear_logs(self):
        self.all_logs.clear()
        self.table.setRowCount(0)

    def export_logs(self):
        """Export logs to text/JSON file."""
        path, _ = QFileDialog.getSaveFileName(self, "Export Log Records", "gracemo_system_logs.json", "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.all_logs, f, indent=2)
        except Exception as e:
            pass
