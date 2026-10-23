"""
Tests for the VIRA Agent Bridge persistence layer, models, and MCP tools.
"""

import os
import json
import pytest
import asyncio
from pathlib import Path

from agent_bridge.config import (
    BRIDGE_ROOT,
    TASKS_DIR,
    INBOX_DIR,
    RESULTS_DIR,
    APPROVALS_DIR,
    safe_bridge_path,
    validate_task_id,
    BridgePathSafetyError,
    BridgeValidationError
)
from agent_bridge.models import (
    TaskCreateRequest,
    TaskRecord,
    TaskCategory,
    TaskPriority,
    TaskStatus,
    ApprovalStatus,
    ResultStatus,
    ExecutionResultCreateRequest
)
from agent_bridge.storage import BridgeStorage
from agent_bridge.server import (
    server,
    get_project_status,
    list_pending_tasks,
    list_tasks,
    claim_task,
    update_task_status,
    read_task,
    create_task,
    publish_execution_result,
    read_latest_result,
    check_approval_status
)

@pytest.fixture
def storage():
    st = BridgeStorage()
    created_task_ids = []
    original_create_task = st.create_task

    def tracked_create(req, creator="agent"):
        rec = original_create_task(req, creator=creator)
        created_task_ids.append(rec.id)
        return rec

    st.create_task = tracked_create
    yield st

    # Clean up test tasks created during test to preserve existing production bridge tasks
    for tid in created_task_ids:
        for d in [TASKS_DIR, INBOX_DIR, RESULTS_DIR, APPROVALS_DIR]:
            for f in d.glob(f"*{tid}*"):
                try:
                    f.unlink()
                except OSError:
                    pass

class TestBridgePathSafety:
    def test_safe_path_valid(self):
        p = safe_bridge_path("tasks/test.json", BRIDGE_ROOT)
        assert p == (BRIDGE_ROOT / "tasks/test.json").resolve()

    def test_safe_path_rejects_parent_traversal(self):
        with pytest.raises(BridgePathSafetyError):
            safe_bridge_path("../../etc/passwd", BRIDGE_ROOT)

    def test_safe_path_rejects_deep_traversal(self):
        with pytest.raises(BridgePathSafetyError):
            safe_bridge_path("tasks/../../secret.txt", BRIDGE_ROOT)

    def test_safe_path_rejects_null_byte(self):
        with pytest.raises(BridgePathSafetyError):
            safe_bridge_path("tasks/test\0.json", BRIDGE_ROOT)

class TestTaskValidation:
    def test_valid_task_ids(self):
        assert validate_task_id("TASK-1234") == "TASK-1234"
        assert validate_task_id("TASK_20261023_ABCD") == "TASK_20261023_ABCD"
        assert validate_task_id("task-abcd-1234") == "task-abcd-1234"

    def test_invalid_task_ids(self):
        with pytest.raises(BridgeValidationError):
            validate_task_id("../task")
        with pytest.raises(BridgeValidationError):
            validate_task_id("task with spaces")
        with pytest.raises(BridgeValidationError):
            validate_task_id("")
        with pytest.raises(BridgeValidationError):
            validate_task_id("sh")

class TestTaskLifecycleAndPersistence:
    def test_create_and_read_task(self, storage):
        req = TaskCreateRequest(
            title="Audit LPU RAG Pipeline",
            description="Verify semantic chunking and retrieval precision across 20 test queries.",
            category=TaskCategory.RAG_PIPELINE,
            priority=TaskPriority.HIGH,
            requires_approval=False,
            payload={"min_confidence": 0.35}
        )
        task = storage.create_task(req, creator="test_agent")
        assert task.id.startswith("TASK-")
        assert task.status == TaskStatus.PENDING

        loaded = storage.get_task(task.id)
        assert loaded is not None
        assert loaded.id == task.id
        assert loaded.title == req.title
        assert loaded.payload["min_confidence"] == 0.35

        inbox_file = INBOX_DIR / f"{task.id}.json"
        assert inbox_file.exists()

    def test_list_tasks_filtering(self, storage):
        req1 = TaskCreateRequest(
            title="Filter Test Research Task",
            description="Testing list filtering",
            category=TaskCategory.RESEARCH,
            priority=TaskPriority.LOW
        )
        t1 = storage.create_task(req1)
        tasks = storage.list_tasks(category="research", priority="low")
        assert any(t.id == t1.id for t in tasks)

    def test_list_tasks_bounded_limit(self, storage):
        for i in range(5):
            storage.create_task(TaskCreateRequest(
                title=f"Batch Task {i}",
                description="Testing bounded limits in task listing",
                category=TaskCategory.RESEARCH
            ))
        limited = storage.list_tasks(limit=3)
        assert len(limited) <= 3

class TestConcurrencySafeTaskClaiming:
    def test_claim_pending_task_succeeds(self, storage):
        req = TaskCreateRequest(
            title="Concurrency Claim Test Task",
            description="Testing task claiming mechanism",
            category=TaskCategory.EVALUATION
        )
        task = storage.create_task(req)
        success, msg, claimed = storage.claim_task(task.id, agent_id="worker_alpha")
        assert success is True
        assert claimed.status == TaskStatus.CLAIMED
        assert claimed.assigned_to == "worker_alpha"

        assert not (INBOX_DIR / f"{task.id}.json").exists()

        # Second claim attempt must fail
        success2, msg2, claimed2 = storage.claim_task(task.id, agent_id="worker_beta")
        assert success2 is False
        assert "not in pending state" in msg2

    def test_claim_unapproved_task_fails(self, storage):
        req = TaskCreateRequest(
            title="Unapproved Claim Test",
            description="Consequential action requiring approval",
            category=TaskCategory.ROBOTICS_INTEGRATION,
            requires_approval=True
        )
        task = storage.create_task(req)
        success, msg, res = storage.claim_task(task.id, agent_id="worker_rogue")
        assert success is False
        assert "requires operator approval" in msg

class TestStatusTransitionsAndStateMachine:
    def test_valid_status_transitions(self, storage):
        req = TaskCreateRequest(
            title="State Machine Transition Test",
            description="Testing valid task state transitions",
            category=TaskCategory.EVALUATION
        )
        task = storage.create_task(req)
        s1, m1, rec1 = storage.claim_task(task.id, agent_id="worker_one")
        assert s1 is True
        assert rec1.status == TaskStatus.CLAIMED

        s2, m2, rec2 = storage.update_task_status(task.id, TaskStatus.IN_PROGRESS, reason="Starting benchmark run")
        assert s2 is True
        assert rec2.status == TaskStatus.IN_PROGRESS

        s3, m3, rec3 = storage.update_task_status(task.id, TaskStatus.BLOCKED, reason="Awaiting test data")
        assert s3 is True
        assert rec3.status == TaskStatus.BLOCKED

        s4, m4, rec4 = storage.update_task_status(task.id, TaskStatus.IN_PROGRESS, reason="Resuming")
        assert s4 is True
        assert rec4.status == TaskStatus.IN_PROGRESS

    def test_invalid_status_transitions(self, storage):
        req = TaskCreateRequest(
            title="Invalid Transition Test",
            description="Testing invalid task state transitions",
            category=TaskCategory.RESEARCH
        )
        task = storage.create_task(req)
        s, m, r = storage.update_task_status(task.id, TaskStatus.IN_PROGRESS)
        assert s is False
        assert "Invalid status transition" in m

class TestExecutionResultPublishing:
    def test_publish_result_completes_task(self, storage):
        req = TaskCreateRequest(
            title="Result Publishing Test Task",
            description="Testing result lifecycle",
            category=TaskCategory.DATA_INGESTION
        )
        task = storage.create_task(req)
        storage.claim_task(task.id, agent_id="worker_gamma")

        res_req = ExecutionResultCreateRequest(
            task_id=task.id,
            status=ResultStatus.SUCCESS,
            summary="Successfully extracted 113 LPU documents.",
            metrics={"extracted_documents": 113, "total_chunks": 2688},
            evidence_files=["data/lpu/manifests/dataset_manifest.json"]
        )
        result = storage.publish_result(res_req)
        assert result.result_id == f"RES-{task.id}"
        assert result.status == ResultStatus.SUCCESS

        updated_task = storage.get_task(task.id)
        assert updated_task.status == TaskStatus.COMPLETED

        latest = storage.get_latest_result(task.id)
        assert latest is not None
        assert latest.result_id == result.result_id

    def test_cannot_publish_result_for_terminal_task(self, storage):
        req = TaskCreateRequest(
            title="Terminal Task Re-publish Test",
            description="Testing terminal state protection",
            category=TaskCategory.EVALUATION
        )
        task = storage.create_task(req)
        storage.claim_task(task.id, agent_id="worker_term")
        res_req = ExecutionResultCreateRequest(
            task_id=task.id,
            status=ResultStatus.SUCCESS,
            summary="First run completed."
        )
        storage.publish_result(res_req)

        with pytest.raises(BridgeValidationError) as exc:
            storage.publish_result(res_req)
        assert "terminal state" in str(exc.value)

class TestApprovalBoundaries:
    def test_consequential_task_awaits_approval(self, storage):
        req = TaskCreateRequest(
            title="Deploy Motor Firmware to Physical Robot",
            description="Consequential task modifying hardware registers",
            category=TaskCategory.ROBOTICS_INTEGRATION,
            requires_approval=True
        )
        task = storage.create_task(req)
        assert task.status == TaskStatus.AWAITING_APPROVAL
        assert task.approval_status == ApprovalStatus.PENDING

        approval = storage.check_approval(task.id)
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING

        assert not (INBOX_DIR / f"{task.id}.json").exists()

    def test_unapproved_task_cannot_publish_result(self, storage):
        req = TaskCreateRequest(
            title="Bypass Approval Test",
            description="Attempting to publish result without approval",
            category=TaskCategory.ROBOTICS_INTEGRATION,
            requires_approval=True
        )
        task = storage.create_task(req)
        res_req = ExecutionResultCreateRequest(
            task_id=task.id,
            status=ResultStatus.SUCCESS,
            summary="Bypassed execution attempt"
        )
        with pytest.raises(BridgeValidationError) as exc:
            storage.publish_result(res_req)
        assert "requires operator approval" in str(exc.value)

    def test_approved_task_can_be_claimed_and_completed(self, storage):
        req = TaskCreateRequest(
            title="Safe Consequential Action",
            description="Action requiring formal operator review",
            category=TaskCategory.SYSTEM_ADMIN,
            requires_approval=True
        )
        task = storage.create_task(req)
        ok, msg, approved_task = storage.approve_task(task.id, reviewer="lead_operator", approved=True, notes="Verified safe")
        assert ok is True
        assert approved_task.approval_status == ApprovalStatus.APPROVED
        assert approved_task.status == TaskStatus.PENDING

        ok_claim, msg_claim, claimed_task = storage.claim_task(task.id, agent_id="worker_approved")
        assert ok_claim is True
        assert claimed_task.status == TaskStatus.CLAIMED

        res_req = ExecutionResultCreateRequest(
            task_id=task.id,
            status=ResultStatus.SUCCESS,
            summary="Authorized execution completed safely."
        )
        res = storage.publish_result(res_req)
        assert res.status == ResultStatus.SUCCESS

class TestMCPServerTools:
    def test_server_discovery(self):
        async def check():
            tools = await server.list_tools()
            names = [t.name for t in tools]
            expected = [
                "get_project_status",
                "list_pending_tasks",
                "list_tasks",
                "claim_task",
                "update_task_status",
                "read_task",
                "create_task",
                "publish_execution_result",
                "read_latest_result",
                "check_approval_status"
            ]
            for exp in expected:
                assert exp in names
        asyncio.run(check())

    def test_mcp_tool_functions_directly(self):
        status_json = get_project_status()
        status_data = json.loads(status_json)
        assert "git_root" in status_data
        assert "task_counts" in status_data

        create_res = create_task(
            title="MCP Tool Integration Probe",
            description="Verifying MCP create_task endpoint",
            category="evaluation",
            priority="normal",
            requires_approval=False
        )
        create_data = json.loads(create_res)
        assert create_data["status"] == "created"
        t_id = create_data["task_id"]

        try:
            list_res = list_tasks(status="pending", limit=10)
            list_data = json.loads(list_res)
            assert "tasks" in list_data
            assert any(t["id"] == t_id for t in list_data["tasks"])

            inv_res = list_tasks(status="nonexistent_status")
            inv_data = json.loads(inv_res)
            assert inv_data["status"] == "invalid_status"

            claim_res = claim_task(task_id=t_id, agent_id="mcp_runner")
            claim_data = json.loads(claim_res)
            assert claim_data["status"] == "claimed"

            dup_res = claim_task(task_id=t_id, agent_id="mcp_runner_2")
            dup_data = json.loads(dup_res)
            assert dup_data["status"] == "claim_rejected"

            up_res = update_task_status(task_id=t_id, target_status="in_progress", reason="Running via MCP")
            up_data = json.loads(up_res)
            assert up_data["status"] == "updated"

            read_res = read_task(t_id)
            read_data = json.loads(read_res)
            assert read_data["id"] == t_id
            assert read_data["status"] == "in_progress"

            pub_res = publish_execution_result(
                task_id=t_id,
                status="success",
                summary="MCP probe execution passed",
                metrics_json=json.dumps({"probe_status": "ok"})
            )
            pub_data = json.loads(pub_res)
            assert pub_data["status"] == "published"

            latest_res = read_latest_result(t_id)
            latest_data = json.loads(latest_res)
            assert latest_data["task_id"] == t_id

            app_res = check_approval_status(t_id)
            app_data = json.loads(app_res)
            assert app_data["status"] == "not_required"
        finally:
            for d in [TASKS_DIR, INBOX_DIR, RESULTS_DIR, APPROVALS_DIR]:
                for f in d.glob(f"*{t_id}*"):
                    try:
                        f.unlink()
                    except OSError:
                        pass
