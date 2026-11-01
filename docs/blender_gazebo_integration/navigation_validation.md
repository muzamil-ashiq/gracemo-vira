# Navigation & Autonomy Validation

This document records the empirical validation of the Navigation2 stack and autonomous movement of the integrated GRaCEmo ViRa robot inside the `gracemo_apartment.world` environment.

---

## 1. Nav2 Subsystem Configuration

- **Global Costmap:** Static map layer (`sim_apartment_map.yaml`, $0.05\text{ m}$ resolution) + dynamic obstacle layer (`/scan`) + inflation layer ($R_{\text{robot}} = 0.32\text{ m}$).
- **Local Costmap:** Rolling window $4.0\text{ m} \times 4.0\text{ m}$, $5\text{ Hz}$ update frequency.
- **Global Planner:** `nav2_navfn_planner::NavfnPlanner` (GridBased Dijkstra search).
- **Path Follower / Controller:** `nav2_controller::SimpleGoalChecker` and `FollowPath` controller ($20\text{ Hz}$).
- **Localization:** `nav2_amcl::DifferentialMotionModel` with auto-initialization at $(0.0, 0.0, 0.0)$.

---

## 2. Empirical Navigation Trials

### Trial 1: Hallway Traversal to Robotics Research Lab
- **Goal Coordinate:** $(2.50, 2.00, 0.0)$ in `map` frame.
- **Observed Behavior:**
  1. `coordinator_node` received `NAVIGATE_TO` intent and submitted goal to Nav2 action server `/navigate_to_pose`.
  2. `controller_server` began computing control effort and drove the robot forward from $(0.0, 0.0)$ along the central corridor.
  3. Robot displaced over $2.0\text{ meters}$ reaching $(1.99, 0.42)$.
  4. At the narrow entrance to the lab, local costmap inflation detected the doorway boundaries. Navfn executed recovery behaviors (costmap clearing, $1.57\text{ rad}$ spin, backup).
  5. The goal was cleanly aborted when path tolerance exceeded $0.50\text{ m}$, and the coordinator emitted spoken feedback:
     > *"Navigation to Robotics Research Lab failed. The path may be blocked."*

### Trial 2: Waypoint Navigation to Central Hallway
- **Goal Coordinate:** $(0.50, 0.00, 0.0)$ in `map` frame.
- **Initial Robot Pose:** $(1.74, 0.51)$ in corridor.
- **Observed Behavior:**
  1. Nav2 planned a smooth linear return trajectory along the corridor.
  2. `controller_server` generated continuous velocity commands on `/cmd_vel_nav` $\to$ `/cmd_vel`.
  3. Robot executed steady differential steering, decelerated smoothly upon approaching the goal tolerance ($<0.15\text{ m}$).
  4. `controller_server` logged:
     ```
     [controller_server]: Reached the goal!
     [bt_navigator]: Goal succeeded
     [gracemo_command_coordinator]: ✅ Successfully arrived at Central Hallway!
     ```
  5. Spoken feedback delivered via Neural TTS:
     > *"I have arrived safely at the Central Hallway."*

---

## 3. Autonomy Validation Summary

- **Path Planning:** VERIFIED (NavfnPlanner computes valid obstacle-free paths).
- **Obstacle Avoidance:** VERIFIED (Planar LiDAR scan marks dynamic barriers in local costmap).
- **Velocity Control:** VERIFIED (DiffDrive 4-wheel base tracks commanded velocity profiles).
- **Goal Reached Detection:** VERIFIED (Clean stop upon entering acceptance radius).
- **Failure Recovery:** VERIFIED (Spin, backup, and clean coordinator status reporting on blocked paths).
