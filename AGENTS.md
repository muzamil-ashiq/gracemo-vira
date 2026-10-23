# Agent Bridge Operational Rules for GRaCEmo ViRa

These rules govern how AI agents (including Antigravity) interact with the VIRA project via the Agent Bridge MCP Server.

---

## 1. Task Queue Workflow

1. **Discovery & Polling:**
   - Call `list_pending_tasks()` to discover available work items.
   - Inspect priority and category to select the most appropriate task.
2. **Inspection:**
   - Call `read_task(task_id)` to retrieve complete instructions, constraints, and payload parameters.
3. **Execution & Evidence Recording:**
   - Execute the requested work strictly within the project boundaries.
   - Collect evidence (log files, test outputs, generated artifacts, diffs).
4. **Publishing Outcomes:**
   - Call `publish_execution_result(task_id, status, summary, metrics_json, evidence_files_json)` upon completion or failure.
   - Always record concrete metrics (e.g. test counts, execution time, artifact hashes).

---

## 2. Consequential Action Authorization Gates

Actions classified as consequential include:
- Physical robot locomotion or navigation goals
- Motor driver parameter modifications
- Arm and head servo actuation
- External announcements or broad broadcasts
- Overwriting production datasets or golden model weights

### Strict Protocol:
1. Consequential tasks **MUST** have `requires_approval: true`.
2. Before performing any consequential step, call `check_approval_status(task_id)`.
3. If status is `pending` or `rejected`, the agent **MUST NOT** proceed. It must record the awaiting state and notify the human operator.
4. Only when `check_approval_status` returns `status: "approved"` may the action proceed.

---

## 3. Prohibited Actions & Safety Boundaries

Under no circumstances may an agent:
- Attempt to disable obstacle avoidance sensors.
- Attempt to bypass physical or software emergency stops.
- Expose unrestricted shell access or arbitrary write permissions outside the sandbox.
- Read or leak private credentials, tokens, or environment keys.
