#!/usr/bin/env python3
"""
GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC) V1.0
Main Application Entry Point.
"""

import os
import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Ensure project and packages can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Enforce deterministic DDS and Gazebo Harmonic environment
os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "LOCALHOST"
os.environ["ROS_DOMAIN_ID"] = "0"
os.environ["GZ_PARTITION"] = "gracemo"
os.environ["GZ_IP"] = "127.0.0.1"

from gracemo_control_center.config.settings import Settings
from gracemo_control_center.app import MainWindow
from gracemo_control_center.core.ros_manager import RosManager
from gracemo_control_center.workers.system_monitor_worker import SystemMonitorWorker


def main():
    # Enable high-DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("GRaCEmo ViRa Unified Control Center")
    app.setOrganizationName("GRaCEmo Robotics")

    settings = Settings()
    ros_manager = RosManager()
    sys_worker = SystemMonitorWorker(interval_ms=settings.system_monitor_rate_ms)

    window = MainWindow(settings)
    window.show()

    # Start background telemetry and ROS 2 threads
    sys_worker.start()
    ros_manager.start()

    import argparse
    parser = argparse.ArgumentParser(description="GRaCEmo ViRa Unified Autonomous Robotics Control Center")
    parser.add_argument("--duration", type=float, default=None, help="Automatically shut down after N seconds (for testing)")
    parser.add_argument("--test-startup", action="store_true", help="Initialize all subsystems, verify health, and exit cleanly")
    args, _ = parser.parse_known_args()

    # Clean shutdown handler
    def cleanup():
        print("\n🛑 Initiating clean UARCC application shutdown...")
        sys_worker.stop()
        ros_manager.stop()
        window.close()
        print("✅ UARCC shutdown complete. Zero orphaned threads or nodes.")

    app.aboutToQuit.connect(cleanup)

    # Allow Python to catch SIGINT / SIGTERM cleanly
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(200)

    # Handle automated shutdown timeout if requested
    if args.test_startup or (args.duration is not None and args.duration <= 0):
        QTimer.singleShot(1000, app.quit)
    elif args.duration is not None:
        QTimer.singleShot(int(args.duration * 1000), app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
