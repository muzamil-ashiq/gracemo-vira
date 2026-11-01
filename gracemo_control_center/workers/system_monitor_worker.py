"""
Host System & GPU Telemetry Monitor Worker for GRaCEmo ViRa UARCC.
Runs on a dedicated QThread at 1 Hz sampling CPU, RAM,
and NVIDIA GeForce RTX 5060 Laptop GPU metrics.
"""

from PySide6.QtCore import QThread, Signal
import time
import subprocess
import psutil

from ..core.event_bus import bus


class SystemMonitorWorker(QThread):
    """Background worker gathering host workstation and GPU metrics."""

    def __init__(self, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.interval_sec = interval_ms / 1000.0
        self._running = True

    def run(self):
        while self._running:
            try:
                # 1. CPU & Memory
                cpu_pct = psutil.cpu_percent(interval=None)
                vm = psutil.virtual_memory()
                ram_pct = vm.percent
                ram_used_gb = vm.used / (1024.0 ** 3)
                ram_total_gb = vm.total / (1024.0 ** 3)

                # 2. NVIDIA GPU Telemetry via nvidia-smi
                gpu_util = 0.0
                vram_used_mb = 0.0
                vram_total_mb = 8151.0
                gpu_temp = 45

                try:
                    smi_res = subprocess.run(
                        [
                            "nvidia-smi",
                            "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                            "--format=csv,noheader,nounits"
                        ],
                        capture_output=True, text=True, timeout=0.8
                    )
                    if smi_res.returncode == 0 and smi_res.stdout.strip():
                        parts = [p.strip() for p in smi_res.stdout.strip().split(",")]
                        if len(parts) >= 4:
                            gpu_util = float(parts[0])
                            vram_used_mb = float(parts[1])
                            vram_total_mb = float(parts[2])
                            gpu_temp = int(parts[3])
                except Exception:
                    pass

                metrics = {
                    "cpu_percent": cpu_pct,
                    "ram_percent": ram_pct,
                    "ram_used_gb": ram_used_gb,
                    "ram_total_gb": ram_total_gb,
                    "gpu_util_percent": gpu_util,
                    "vram_used_mb": vram_used_mb,
                    "vram_total_mb": vram_total_mb,
                    "gpu_temp_c": gpu_temp,
                    "timestamp": time.time()
                }

                # Emit to UI
                bus.system_metrics_ready.emit(metrics)

            except Exception as e:
                pass

            # Sleep in small increments for clean thread cancellation
            slept = 0.0
            while self._running and slept < self.interval_sec:
                time.sleep(0.1)
                slept += 0.1

    def stop(self):
        self._running = False
        self.wait(1500)
