# GRaCEmo ViRa — Live Sensor Integration Status

**Document ID:** `VIRA-STATUS-SENS-001`  
**Classification:** Subsystem Integration & Readiness Audit  
**Date:** 2026-10-28  

---

## 1. Executive Summary

This document details the software integration and physical verification status for all primary sensor subsystems:
1. **RGB-D / Monocular Camera**
2. **Microphone Array & Audio Ingestion**
3. **2D Safety LiDAR**
4. **Inertial Measurement Unit (IMU)**
5. **Wheel Quadrature Encoders**

---

## 2. Sensor Integration Subsystem Matrix

| Subsystem | Driver / Adapter Class | Hardware Interface | ROS 2 Topic / Contract | Test Coverage | Physical Verification Status | Remaining Blockers / Dependencies |
|---|---|---|---|---|---|---|
| **Camera** | [`OpenCVCameraDriver`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/camera_driver.py) & [`MockCameraDriver`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/camera_driver.py) | USB / MIPI CSI (`/dev/video0`) | `CameraFrame` / `/camera/image_raw` (`sensor_msgs/Image`) | Unit tested in [`test_live_sensor_pipeline.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/unit/test_live_sensor_pipeline.py) | **NOT QUALIFIED** (Simulated & mock tested only) | Physical camera optical mount calibration; TensorRT YOLOv8 inference optimization. |
| **Microphone** | [`PyAudioDriver`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/audio_driver.py) & [`MockAudioDriver`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/vira_interaction/core/audio_driver.py) | USB Audio / ALSA (`plughw:1,0`) | `AudioChunk` / 16 kHz 16-bit PCM | Unit tested in [`test_live_sensor_pipeline.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/unit/test_live_sensor_pipeline.py) | **NOT QUALIFIED** (Mock speech injection tested) | Physical microphone array selection; far-field acoustic noise cancellation and wake word tuning. |
| **LiDAR** | Generic ROS 2 2D LiDAR driver / Gazebo GPU LiDAR plugin | USB-UART (`/dev/ttyUSB1`) or Ethernet | `/scan` (`sensor_msgs/LaserScan`, 360 beams, 15 Hz) | 30 tests in [`test_hardware_hal.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/hardware/test_hardware_hal.py) (profile switching, bounds) | **NOT QUALIFIED** (Simulated scans in Gazebo & mock profiles) | Sensor model identification (RPLiDAR A2/S2 vs YDLIDAR); port separation and baud rate confirmation. |
| **IMU** | `gracemo_hardware_status` / Gazebo IMU sensor | I2C / SPI on STM32 or USB-UART on Jetson | `/imu/data` (`sensor_msgs/Imu`) | Stale data detection tested in `test_hardware_hal.py` | **NOT QUALIFIED** (Simulation only) | IMU 6-DOF sensor model confirmation (e.g. BNO055 / MPU6050); coordinate frame calibration. |
| **Wheel Encoders** | STM32 Hardware Timer Counter / Firmware Telemetry | Quadrature channels A, B per wheel | `TELEM` serial frame (`ticksL`, `ticksR`) | Verified in [`test_mcu_protocol_engine.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/tests/unit/test_mcu_protocol_engine.py) & firmware parser | **NOT QUALIFIED** (Synthetic counts only; pins disabled) | Physical encoder CPR and gearbox ratio measurement; timer input pin mapping (`TIM2`/`TIM3`/`TIM4`). |

---

## 3. Subsystem Detailed Analysis

### 3.1 Camera Subsystem
- **Software Implementation:**
  - Standardized frame encapsulation via `CameraFrame(data, width, height, timestamp, is_mock)`.
  - OpenCV capture interface with configurable resolution ($640\times 480$ default) and FPS throttling.
  - Person detection bounding box extraction with distance estimation heuristic based on vertical box extent ($d \approx f \times H_{person} / h_{pixels}$).
  - Full mock adapter allowing deterministic injection of detection candidates for automated testing.
- **Hardware Blockers:**
  - Physical camera mount geometry: extrinsic transformation from `base_link` to `camera_link` must be confirmed on real robot.
  - Exposure and white-balance tuning for indoor hospital/educational corridor lighting.

### 3.2 Audio & Speech Subsystem
- **Software Implementation:**
  - Standardized `AudioChunk(raw_data, sample_rate, channels, timestamp, is_mock)`.
  - Non-blocking PyAudio reader capturing 16-bit PCM chunks at 16,000 Hz.
  - `VoiceCommandParser` enforcing strict keyword matching and prioritizing STOP over any motion command.
  - Ambiguous or unrecognized speech automatically falls back to safe zero-velocity UNKNOWN.
- **Hardware Blockers:**
  - Ambient acoustic noise calibration: reverberation in corridors requires microphone gain and threshold tuning.
  - Hardware microphone ALSA device index locking via udev rules.

### 3.3 LiDAR Subsystem
- **Software Implementation:**
  - Profile validator in [`hardware_adapter.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/adapters/robot-bridge/gracemo_bridge/hardware_adapter.py) supporting standard profiles (360 samples, min range $0.15\text{ m}$, max range $12.0\text{ m}$, $15\text{ Hz}$).
  - Device path separation: guarantees that LiDAR serial device (`/dev/ttyUSB1`) cannot collide with MCU serial bridge (`/dev/ttyUSB0` or `/dev/ttyACM0`).
  - Stale scan watchdog: halts autonomous navigation if `/scan` age exceeds $2.0\text{ s}$.
- **Hardware Blockers:**
  - Exact physical LiDAR unit model confirmation (RPLiDAR A1/A2/A3 vs YDLIDAR X4/G4).
  - Physical mounting orientation and scan angle inversion (clockwise vs counter-clockwise).

### 3.4 Encoders & Odometry
- **Software Implementation:**
  - Serial protocol conveys 32-bit signed pulse counts (`ticksL`, `ticksR`) and integrated odometry coordinates (`x, y, yaw`).
  - Forward kinematics model verified in [`mcu_transport.py`](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py#L324).
- **Hardware Blockers:**
  - Physical line count (CPR) and gearbox reduction ratio tag inspection.
  - Verification of channel A/B phase sequence to ensure positive count increase during forward roll.
