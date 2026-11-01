#!/usr/bin/env python3
"""
Offscreen Visual Quality Assurance & Screenshot Capture for GRaCEmo ViRa UARCC.
Renders all 11 modules across standard desktop resolutions (1280x720, 1366x768, 1600x900, 1920x1080)
and saves high-resolution verification artifacts to docs/screenshots/.
"""

import os
import sys
import time

# Ensure offscreen rendering
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QPainter

from gracemo_control_center.config.settings import Settings
from gracemo_control_center.app import MainWindow
from gracemo_control_center.core.event_bus import bus
from gracemo_control_center.widgets.status_indicator import StatusIndicator

def main():
    app = QApplication(sys.argv)
    settings = Settings()
    window = MainWindow(settings)
    window.show()

    # Populate realistic sample telemetry for screenshots
    bus.ros_connected.emit(True)
    bus.gazebo_connected.emit(True)
    bus.sim_clock_updated.emit(42.158)
    bus.odom_data_ready.emit({"x": 1.240, "y": -0.450, "yaw": 0.085, "vx": 0.250, "vy": 0.0, "wz": 0.045, "timestamp": 42.158})
    bus.amcl_pose_ready.emit(1.240, -0.450, 0.085, 0.012, 0.015, 0.004)
    bus.system_metrics_ready.emit({"cpu": 24.5, "ram": 41.2, "gpu_util": 18.0})
    bus.coordinator_feedback_ready.emit("NAVIGATING", "Navigating to Kitchen", {}, 42.158)

    # Add sample log entry
    bus.log_event_emitted.emit({"timestamp": 42.158, "level": "INFO", "source": "Nav2Controller", "message": "Path plan computed successfully with 84 waypoints."})
    bus.log_event_emitted.emit({"timestamp": 42.160, "level": "INFO", "source": "CollisionMonitor", "message": "Polygon safety bubble clear: 0.85m to nearest obstacle."})

    modules = [
        ("01_overview", "Overview"),
        ("02_simulation", "Simulation"),
        ("03_sensors", "Sensors"),
        ("04_navigation", "Navigation"),
        ("05_localization", "Localization"),
        ("06_interaction", "Voice & Interaction"),
        ("07_cognitive", "Cognitive System"),
        ("08_safety", "Safety"),
        ("09_diagnostics", "Diagnostics"),
        ("10_logs", "System Logs"),
        ("11_settings", "Settings"),
    ]

    resolutions = [
        (1280, 720, "1280x720"),
        (1366, 768, "1366x768"),
        (1600, 900, "1600x900"),
        (1920, 1080, "1920x1080"),
    ]

    out_dir = os.path.abspath("docs/screenshots")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Capturing screenshots to {out_dir}...")

    # Primary capture at 1920x1080 for all 11 modules
    res_w, res_h, res_label = 1920, 1080, "1920x1080"
    window.resize(res_w, res_h)
    app.processEvents()

    for mod_file_name, page_name in modules:
        window.switch_to_page(page_name)
        app.processEvents()
        time.sleep(0.05)

        pixmap = QPixmap(window.size())
        window.render(pixmap)
        path = os.path.join(out_dir, f"{res_label}_{mod_file_name}.png")
        pixmap.save(path, "PNG")
        print(f"Saved: {path}")

    # Capture responsive overview, navigation, and safety checks at smaller desktop resolutions
    for res_w, res_h, res_label in resolutions[:-1]:
        window.resize(res_w, res_h)
        app.processEvents()
        for mod_file_name, page_name in [("01_overview", "Overview"), ("04_navigation", "Navigation"), ("08_safety", "Safety")]:
            window.switch_to_page(page_name)
            app.processEvents()
            time.sleep(0.05)

            pixmap = QPixmap(window.size())
            window.render(pixmap)
            path = os.path.join(out_dir, f"{res_label}_{mod_file_name}.png")
            pixmap.save(path, "PNG")
            print(f"Saved: {path}")

    print("All verification screenshots successfully captured.")

if __name__ == "__main__":
    main()
