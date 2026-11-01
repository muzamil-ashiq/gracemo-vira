# Troubleshooting & Diagnostics Guide

This document catalogs observed diagnostics, warnings, failure modes, root causes, and verified solutions encountered during the Gazebo Harmonic and ROS 2 Jazzy integration on Ubuntu 24.04 LTS.

---

## 1. NVIDIA RTX 5060 Laptop GPU & EGL Diagnostic Warnings

### Symptom:
When starting Gazebo Sim (`gz sim`), the terminal logs:
```
libEGL warning: pci id for fd 143: 10de:2d19, driver (null)
libEGL warning: egl: failed to create dri2 screen
```

### Root Cause Analysis:
The host development laptop is equipped with an AMD Ryzen CPU with integrated graphics and an NVIDIA GeForce RTX 5060 Laptop GPU running proprietary driver `595.99.02`.
- When Mesa's `libEGL` initializes, it probes device file descriptors for DRI2 support.
- File descriptor 143 corresponds to PCI ID `10de:2d19` (NVIDIA Corporation vendor `0x10de`).
- Because NVIDIA's proprietary driver implements direct EGL dispatch (`libEGL_nvidia.so.0`) rather than Mesa's open-source DRI2 interface, Mesa outputs an informational warning and falls back to the NVIDIA direct EGL loader.
- **Impact:** Non-fatal. Camera rendering, depth projection, and OpenGL 4.6 context remain fully hardware accelerated by the NVIDIA RTX 5060 GPU.

---

## 2. Nav2 AMCL Initial Pose & Lifecycle Manager Timeout

### Symptom:
`lifecycle_manager_navigation` aborts bringup with:
```
[global_costmap]: Failed to activate global_costmap because transform from base_footprint to map did not become available before timeout
[lifecycle_manager]: Failed to change state for node: planner_server. Aborting bringup.
```

### Root Cause:
By default, Nav2's AMCL node waits for an operator to publish an initial pose estimate on `/initialpose`. Because the global costmap requires a valid `map` $\to$ `odom` transform to transition to `ACTIVE`, the lifecycle manager times out after 40 seconds.

### Solution:
Configured inside `nav2_params.yaml`:
```yaml
amcl:
  ros__parameters:
    set_initial_pose: true
    initial_pose:
      x: 0.0
      y: 0.0
      z: 0.0
      yaw: 0.0
```
Upon startup, AMCL immediately seeds its particle distribution around the world spawn origin $(0, 0, 0)$, broadcasts the transform, and allows all Nav2 nodes to activate automatically.

---

## 3. Resolving `package://` and `model://` URI Lookups

### Symptom:
Gazebo server logs:
```
Msg: Unable to find uri[package://gracemo_robot_description/meshes/base_link_visual.obj]
```

### Root Cause:
Gazebo Harmonic uses `GZ_SIM_RESOURCE_PATH` to resolve URI prefixes. When ROS 2 launches Gazebo, it must expose the parent share directory where package meshes reside.

### Solution:
The launch files (`simulation.launch.py` and `sim.launch.py`) dynamically inject the package share directories into the process environment:
```python
package_share_parent = os.path.dirname(pkg_share)
current_resource_path = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
os.environ["GZ_SIM_RESOURCE_PATH"] = f"{package_share_parent}:{current_resource_path}"
```

---

## 4. Recovering from Stale Simulator Daemons

If a launch is abruptly killed (e.g. `Ctrl+C` or terminal crash), background Ruby or Gazebo processes can lock the simulation port or hold socket locks.
Run the cleanup sequence:
```bash
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "gz-sim" 2>/dev/null || true
pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
pkill -9 -f "robot_state_publisher" 2>/dev/null || true
pkill -9 -f "nav2" 2>/dev/null || true
```
Verify that `ps aux | grep gz` returns zero processes before relaunching.
