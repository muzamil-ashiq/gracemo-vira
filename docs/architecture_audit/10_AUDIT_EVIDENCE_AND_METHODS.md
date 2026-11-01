# GRaCEmo ViRa — Codebase Duplication and Redundancy Audit
# Document 10: Audit Evidence and Methods

**Audit Date:** November 2026  
**System:** GRaCEmo ViRa — Autonomous Robotics System  
**Auditor:** Principal Robotics Software Architect & Systems Safety Engineer  
**Audit Type:** Automated Static Analysis, Cryptographic Hashing, AST Parsing, and Semantic Diffing.

---

## 1. Audit Methodology & Procedures

The audit was executed without modifying, moving, or deleting any repository files, ensuring strict preservation of all existing code, configurations, and git branches.

### 1.1 Step 1: Inventory & Artifact Categorization
- Scanned all directory trees recursively using `os.walk(followlinks=False)`.
- Separated maintained source files from generated build outputs (`build/`, `install/`, `log/`, `kernel/target/`, `__pycache__`, `.venv`).
- Tracked file extensions, sizes, and file permissions.

### 1.2 Step 2: Cryptographic SHA-256 Duplication Hashing
- Computed SHA-256 digests over all maintained files with size $> 0$ bytes (excluding large binaries $> 20\text{ MB}$).
- Clustered identical hashes across workspace root and prototype directories.
- Identified 56 clusters comprising 138 identical files.

### 1.3 Step 3: Python Abstract Syntax Tree (AST) Extraction
- Parsed 334 maintained Python source files using Python's standard `ast` module.
- Extracted class definitions, base classes, function signatures, and method counts.
- Mapped ROS 2 entity instantiations:
  - `Node("node_name")` and `super().__init__("node_name")`
  - `create_publisher(MsgType, 'topic', qos)`
  - `create_subscription(MsgType, 'topic', callback, qos)`
  - `create_client(SrvType, 'service')`
  - `ActionClient(self, ActionType, 'action_name')`

### 1.4 Step 4: ROS 2 Launch Pipeline & Dependency Mapping
- Analyzed all `.launch.py` and `.launch` files using AST and regular expression parsers.
- Traced `IncludeLaunchDescription` trees to map parent-child launch hierarchies.
- Cross-referenced published topics against subscription graphs to identify single points of failure, multi-publisher contention, and rogue `/cmd_vel` publishers.

### 1.5 Step 5: Configuration Value Diffing & Cross-Referencing
- Loaded all YAML (`*.yaml`, `*.yml`), JSON (`*.json`), and TOML (`*.toml`) configuration files.
- Extracted kinematic parameters (`wheel_separation_m`, `wheel_radius_m`, `max_vel_x`, `robot_radius`).
- Highlighted divergent parameter definitions between simulation configs, hardware params, and URDF Xacro models.

---

## 2. Reproducibility Scripts & Exact Commands

### Script A: Full Inventory and Duplicate Hash Scanner
Location: `scratch/audit_investigator.py`  
Command to reproduce:
```bash
python3 scratch/audit_investigator.py
```
Output artifact: `scratch/audit_raw.json`

### Script B: ROS 2 Entity & Publisher Extraction
Command to reproduce:
```bash
python3 -c "
import os, re
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', '__pycache__', 'build', 'install', 'log', 'target', '.venv']): continue
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', errors='ignore') as fp: txt = fp.read()
            pubs = re.findall(r'create_publisher\(\s*([A-Za-z0-9_]+)\s*,\s*[\'\"]([^\'\"]+)[\'\"]', txt)
            if pubs: print(f'{p}: {pubs}')
"
```

### Script C: Exact SHA-256 Verification Check
Command to verify any candidate duplicate pair:
```bash
sha256sum \
  ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_bridge_node.py \
  /home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_bridge_node.py
```
Expected output:
```
8952bc765955fe4600236a2826cf941a3a270db6cf1b0ff4efd73bf9adad9b16  ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_bridge_node.py
8952bc765955fe4600236a2826cf941a3a270db6cf1b0ff4efd73bf9adad9b16  /home/sabarishchandrasekaran/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_hardware/gracemo_hardware/mcu_bridge_node.py
```

---

## 3. Evidence Log Artifacts

The following raw evidence files were generated during this audit and persist in the repository:

- `scratch/audit_raw.json` — 108 KB structured JSON file containing the inventory counts, 56 SHA-256 duplicate clusters with complete file paths, and AST analysis of 334 Python files.
- `docs/architecture_audit/` — The complete 11-part architectural audit documentation suite:
  - `00_EXECUTIVE_SUMMARY.md`
  - `01_COMPLETE_FILE_INVENTORY.md`
  - `02_EXACT_DUPLICATES.md`
  - `03_FUNCTIONAL_DUPLICATES.md`
  - `04_ROS2_ARCHITECTURE_AUDIT.md`
  - `05_CONFIGURATION_AND_DEPENDENCY_AUDIT.md`
  - `06_ENTRY_POINTS_AND_EXECUTION_MAP.md`
  - `07_LEGACY_UNUSED_AND_ORPHANED_CODE.md`
  - `08_RISK_AND_IMPACT_ASSESSMENT.md`
  - `09_RECOMMENDED_CONSOLIDATION_PLAN.md`
  - `10_AUDIT_EVIDENCE_AND_METHODS.md`

---

## 4. Audit Verification Sign-Off

- **Audit Completion Date:** November 1, 2026
- **Safety Standard Maintained:** Physical hardware remained completely disabled (`MOTOR_OUTPUT_ENABLED = 0`, `SerialMCUTransport.PROTOCOL_CONFIRMED = False`).
- **Repository Integrity:** Zero existing source files, launch files, or configurations were modified, moved, or deleted during this investigation.
- **Next Action:** Awaiting human engineering review and consolidation decision on Document 09.
