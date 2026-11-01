# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 05: Configuration and Dependency Audit

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Objective:** Identification of conflicting parameter values, duplicate configuration files, multiple sources of truth, and unaligned dependencies.

---

## 1. Physical Parameter Inconsistencies & Conflicts

The audit identified **eight major configuration divergence points** across kinematic, dimensional, and operational parameters:

| Parameter | Source A | Value A | Source B | Value B | Source C | Value C | Operational Impact & Conflict Description | Severity |
| :--- | :--- | :---: | :--- | :---: | :--- | :---: | :--- | :---: |
| **Wheel Separation (Wheelbase)** | `config/robot.yaml` (line 10) | **0.32 m** | `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml` (line 14) | **0.34 m** | `ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro` (line 11) | **0.34 m** | **Systematic Odometry Drift:** A 20 mm discrepancy causes the robot to calculate erroneous heading angles during rotation. Caliper measurement required. | **CRITICAL** |
| **Robot Collision Radius** | `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` | **0.22 m** | `prototypes/.../gracemo_navigation/config/nav2_params.yaml` | **0.23 m** | `ros2_ws/src/gracemo_description/` base footprint | $\sim 0.225\text{ m}$ | **Costmap Inconsistency:** Nav2 local and global costmap inflation radii differ by 10 mm depending on which package's parameter file is sourced. | **HIGH** |
| **Max Linear Velocity** | `config/robot.yaml` | **0.80 m/s** | `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` | **0.65 m/s** | `ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_transport.py` | **0.35 m/s** (clamp) | **Uncoordinated Motion Limits:** Simulation plans for $0.65\text{ m/s}$, robot config claims $0.80\text{ m/s}$, but serial hardware clamps commands to $0.35\text{ m/s}$. | **HIGH** |
| **Max Angular Velocity** | `config/robot.yaml` | **1.50 rad/s** | `ros2_ws/src/gracemo_nav2/config/nav2_params.yaml` | **1.00 rad/s** | `prototypes/.../nav2_params.yaml` | **1.20 rad/s** | **Trajectory Tracking Lag:** Path planner generates paths assuming 1.0 rad/s, but velocity smoother may clamp or amplify turn rate. | **MEDIUM** |
| **Wheel Radius** | `ros2_ws/src/gracemo_hardware/config/hardware_params.yaml` | **0.065 m** | `ros2_ws/src/gracemo_description/urdf/gracemo_vira.urdf.xacro` | **0.065 m** | `tests/integration/test_drive_diagnostics.py` calculation | **0.066 m** ($R=0.066$) | **Linear Displacement Scale Error:** A 1 mm radius error produces a 1.5% accumulated distance estimation error over 10 meters of travel. | **MEDIUM** |
| **Room Destination Schema** | `config/destinations.json` | **JSON Dict** (with `name`, `x`, `y`, `yaw`, `aliases`) | `config/places.json` & `vira_interaction/config/places.json` | **JSON List** (`[x, y, name, yaw]`) | UARCC destinations registry | **JSON Dict** | **Schema Incompatibility:** Code reading `places.json` indexes `[0], [1]`, while code reading `destinations.json` accesses `['x'], ['y']`. | **HIGH** |
| **Kernel Domain Socket Path** | `gracemo_control_center/modules/cognitive/cognitive_view.py` | `/tmp/gracemo.sock` | `kernel/gracemo-kernel/src/main.rs` | `/tmp/gracemo.sock` | `scripts/start_kernel.sh` legacy argument | `/tmp/kernel.sock` | **IPC Connection Failure:** If kernel is started with legacy script argument, UARCC marks kernel OFFLINE. | **MEDIUM** |
| **Cognitive REST API Port** | `gracemo_control_center/modules/cognitive/cognitive_view.py` | **Port 7780** | `kernel/gracemo-kernel/src/main.rs` | **Port 7780** | `adapters/sdk/gracemo_sdk/config.py` default | **Port 7777** | **SDK Client Disconnect:** SDK default configuration fails to connect to running kernel unless explicitly overridden. | **HIGH** |

---

## 2. Duplicate Configuration Files & Redundancy

```
Configuration Duplication Map:
├── Destinations & Places:
│   ├── config/destinations.json ──[EXACT DUPLICATE]──> prototypes/.../config/destinations.json
│   ├── config/places.json ─────────[EXACT DUPLICATE]──> vira_interaction/config/places.json
│   └── (Schema conflict between destinations.json and places.json)
├── Nav2 Parameter Files:
│   ├── ros2_ws/src/gracemo_nav2/config/nav2_params.yaml (radius: 0.22, max_v: 0.65)
│   ├── ros2_ws/src/gracemo_nav2/config/nav2_physical_params.yaml (use_sim_time: False)
│   ├── prototypes/.../gracemo_navigation/config/nav2_params.yaml (radius: 0.23, max_v: 0.50)
│   └── prototypes/.../config/nav2_params.yaml (duplicate copy in config/)
└── Hardware & LiDAR Parameters:
    ├── ros2_ws/src/gracemo_hardware/config/hardware_params.yaml ──[EXACT]──> prototypes/.../hardware_params.yaml
    └── ros2_ws/src/gracemo_hardware/config/lidar_params.yaml ────────[EXACT]──> prototypes/.../lidar_params.yaml
```

---

## 3. Dependency & Environment Audit

### 3.1 Python Package Manager Fragmentation

The repository exhibits competing dependency definitions across four separate package specification formats:

1. **`requirements/` Directory:**
   - `requirements/dev.txt`
   - `requirements/simulation.txt`
   - `requirements/hardware.txt`
2. **Component `requirements.txt` Files:**
   - `gracemo_control_center/requirements.txt` (`PySide6>=6.5.0`, `numpy>=1.24.0`, `psutil>=5.9.0`)
   - `vira_interaction/requirements.txt` (`pygame>=2.5.0`, `pyttsx3>=2.90`, `groq>=0.4.0`)
   - `prototypes/gracemo_integrated_v1/unified_control_center/requirements.txt`
3. **`pyproject.toml` in `adapters/` (Poetry / Flit):**
   - `adapters/pyproject.toml`
   - `adapters/brain/pyproject.toml`
   - `adapters/robot-bridge/pyproject.toml`
   - `adapters/sdk/pyproject.toml`
   - `adapters/vision/pyproject.toml`
   - `adapters/voice/pyproject.toml`
4. **ROS 2 `package.xml` `<depend>` Tags:**
   - Declares system dependencies for `rclpy`, `sensor_msgs`, `nav2_msgs`, `geometry_msgs`, `tf2_ros`.

### 3.2 Key Dependency Version Conflicts

| Library | Defined in `requirements/` | Defined in `adapters/pyproject.toml` | Defined in `vira_interaction/` | Risk Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **`numpy`** | `numpy>=1.24.0,<2.0.0` | `numpy^1.26.0` | Unpinned | **Medium:** NumPy 2.0 breaking changes can disrupt C-extensions (`cv2`, PySide6). |
| **`PySide6`** | Not declared | Not declared | Not declared (uses Pygame) | **Low:** Declared only in `gracemo_control_center`. |
| **`torch` / `torchvision`** | `torch==2.1.2` (in `requirements/hardware.txt`) | Optional dependency in `vision` | Not declared | **High:** PyTorch is required only for local YOLO/Whisper inference. On Jetson Orin, PyTorch must use NVIDIA JetPack pre-built wheel, not PyPI. |
| **`pydantic`** | `pydantic>=2.4.0` | `pydantic>=2.0.0` | `pydantic>=2.5.0` | **Low:** Consistent on v2. |
