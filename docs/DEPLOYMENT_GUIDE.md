# GRaCEmo ViRa — Production Deployment Guide
**Target System:** Physical Differential Robot Platform (REV-C-PHYSICAL) & Simulation  
**OS Target:** Ubuntu 24.04 LTS (x86_64 / aarch64) with ROS 2 Jazzy Jalisco  

---

## 1. Prerequisites & Environment Setup

### System Packages
```bash
sudo apt-get update && sudo apt-get install -y \
  ros-jazzy-ros-base \
  ros-jazzy-nav2-bringup \
  ros-jazzy-navigation2 \
  ros-jazzy-robot-localization \
  python3-pip \
  python3-venv \
  libasound2-dev \
  portaudio19-dev
```

### Python Virtual Environment
```bash
cd /opt/vira
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Hardware Udev Rules & Device Mappings

Create `/etc/udev/rules.d/99-gracemo-vira.rules` to ensure deterministic device symlinks:

```udev
# RPLiDAR A2M8 / A3
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666", SYMLINK+="rplidar"

# Motor Controller MCU (Teensy / STM32 USB CDC)
KERNEL=="ttyACM*", ATTRS{idVendor}=="16c0", ATTRS{idProduct}=="0483", MODE="0666", SYMLINK+="vira_motor"

# Intel RealSense D435
SUBSYSTEM=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b07", MODE="0666", GROUP="plugdev"
```

Apply and reload rules:
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

## 3. Configuration Freeze Verification

Before running production bringup, execute configuration integrity checks:
```bash
./scripts/verify_release_manifest.sh
```
This script computes SHA-256 hashes of:
- `config/nav2_params_physical.yaml`
- `description/urdf/gracemo_vira.urdf.xacro`
- `config/places.json`

and halts if any hash differs from [`docs/RELEASE_MANIFEST.md`](file:///Users/samdavi/projects/VIRA/docs/RELEASE_MANIFEST.md).

---

## 4. Systemd Service Deployment

Install systemd units to manage lifecycle and clean process restart:

```ini
# /etc/systemd/system/vira-bridge.service
[Unit]
Description=GRaCEmo ViRa Robot Bridge and EventBus
After=network.target ros2.service
Requires=ros2.service

[Service]
Type=simple
User=vira
WorkingDirectory=/opt/vira
Environment="VIRA_MODE=hardware"
Environment="PYTHONPATH=/opt/vira"
ExecStart=/opt/vira/.venv/bin/python3 -m adapters.robot-bridge.gracemo_bridge.main
Restart=on-failure
RestartSec=3s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vira-bridge.service
sudo systemctl start vira-bridge.service
```

---

## 5. Pre-Deployment Acceptance Run

Before turning over the robot to operators:
1. Place the robot in a safe testing pen or elevate drive wheels.
2. Run full regression test suite:
   ```bash
   .venv/bin/python3 -m unittest discover -s tests -p "test_*.py"
   ```
3. Run preflight verification:
   ```bash
   .venv/bin/python3 -c "from adapters.robot_bridge.gracemo_bridge.preflight import run_preflight; print(run_preflight())"
   ```
4. Confirm `all_passed: true` and current state is `IDLE`.
