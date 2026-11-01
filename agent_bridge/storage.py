"""
Storage and concurrency-safe persistence layer for the VIRA Agent Bridge.
"""

import os
import json
import fcntl
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from agent_bridge.config import (
    BRIDGE_ROOT,
    VIRA_PROJECT_ROOT,
    TASKS_DIR,
    INBOX_DIR,
    RESULTS_DIR,
    APPROVALS_DIR,
    LOGS_DIR,
    MAX_PAYLOAD_BYTES,
    safe_bridge_path,
    validate_task_id,
    atomic_write_json,
    ensure_bridge_directories,
    BridgeValidationError,
    BridgePathSafetyError
)
from agent_bridge.models import (
    TaskCategory,
    TaskPriority,
    TaskStatus,
    ApprovalStatus,
    ResultStatus,
    TaskCreateRequest,
    TaskRecord,
    ExecutionResultCreateRequest,
    ExecutionResultRecord,
    ApprovalRecord
)

class BridgeStorage:
    """Local file-backed persistence engine with atomic writes and concurrency safety."""

    def __init__(self):
        ensure_bridge_directories()

    def create_task(self, req: TaskCreateRequest, creator: str = 'agent') -> TaskRecord:
        """Creates and persists a new task record atomically."""
        ts = datetime.now(timezone.utc)
        rand_suffix = os.urandom(3).hex().upper()
        task_id = f'TASK-{ts.strftime("%Y%m%d%H%M%S")}-{rand_suffix}'
        validate_task_id(task_id)

        requires_approval = req.requires_approval
        initial_status = TaskStatus.AWAITING_APPROVAL if requires_approval else TaskStatus.PENDING
        initial_approval = ApprovalStatus.PENDING if requires_approval else ApprovalStatus.NOT_REQUIRED

        record = TaskRecord(
            id=task_id,
            title=req.title,
            description=req.description,
            category=req.category,
            priority=req.priority,
            status=initial_status,
            created_at=ts.isoformat(),
            updated_at=ts.isoformat(),
            created_by=creator,
            requires_approval=requires_approval,
            approval_status=initial_approval,
            payload=req.payload or {}
        )

        task_path = TASKS_DIR / f'{task_id}.json'
        payload_str = record.model_dump_json(indent=2)
        if len(payload_str.encode('utf-8')) > MAX_PAYLOAD_BYTES:
            raise BridgeValidationError(f'Payload exceeds maximum limit of {MAX_PAYLOAD_BYTES} bytes.')

        atomic_write_json(task_path, payload_str)

        # If pending, also place marker in inbox for rapid queue polling
        if initial_status == TaskStatus.PENDING:
            inbox_path = INBOX_DIR / f'{task_id}.json'
            atomic_write_json(inbox_path, json.dumps({'task_id': task_id, 'added_at': ts.isoformat()}))

        # If requires approval, create approval record
        if requires_approval:
            approval_path = APPROVALS_DIR / f'{task_id}.json'
            approval_record = ApprovalRecord(
                task_id=task_id,
                action_description=req.title,
                status=ApprovalStatus.PENDING,
                requested_at=ts.isoformat()
            )
            atomic_write_json(approval_path, approval_record.model_dump_json(indent=2))

        return record

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Reads and parses a task by ID."""
        clean_id = validate_task_id(task_id)
        task_path = safe_bridge_path(f'tasks/{clean_id}.json', BRIDGE_ROOT)
        if not task_path.exists():
            return None
        with open(task_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return TaskRecord(**data)

    def list_tasks(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[TaskRecord]:
        """Lists tasks matching optional filter parameters with bounded output."""
        records = []
        for file in sorted(TASKS_DIR.glob('TASK-*.json'), reverse=True):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                rec = TaskRecord(**data)
                if status and rec.status.value != status:
                    continue
                if category and rec.category.value != category:
                    continue
                if priority and rec.priority.value != priority:
                    continue
                records.append(rec)
                if limit and len(records) >= limit:
                    break
            except Exception:
                continue
        return records

    def claim_task(self, task_id: str, agent_id: str = 'agent') -> Tuple[bool, str, Optional[TaskRecord]]:
        """Concurrency-safe task claiming via file locking."""
        clean_id = validate_task_id(task_id)
        task_path = safe_bridge_path(f'tasks/{clean_id}.json', BRIDGE_ROOT)
        lock_path = safe_bridge_path(f'tasks/{clean_id}.lock', BRIDGE_ROOT)

        if not task_path.exists():
            return False, f'Task {task_id} not found', None

        # Lock file descriptor
        lock_fd = open(lock_path, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            lock_fd.close()
            return False, f'Task {task_id} is currently locked by another worker.', None

        try:
            with open(task_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rec = TaskRecord(**data)

            # Prevent claiming tasks that require approval if not yet approved
            if rec.requires_approval and rec.approval_status != ApprovalStatus.APPROVED:
                return False, f'Task {task_id} requires operator approval before claiming (current approval status: {rec.approval_status.value}).', rec

            if rec.status != TaskStatus.PENDING:
                return False, f'Task {task_id} is not in pending state (current: {rec.status.value}).', rec

            rec.status = TaskStatus.CLAIMED
            rec.assigned_to = agent_id
            rec.updated_at = datetime.now(timezone.utc).isoformat()

            atomic_write_json(task_path, rec.model_dump_json(indent=2))

            # Remove from inbox
            inbox_path = INBOX_DIR / f'{clean_id}.json'
            if inbox_path.exists():
                try:
                    inbox_path.unlink()
                except OSError:
                    pass

            return True, f'Task {task_id} claimed successfully by {agent_id}.', rec
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def update_task_status(
        self,
        task_id: str,
        target_status: TaskStatus,
        reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[TaskRecord]]:
        """
        Validated status transition for active tasks.
        Enforces state machine rules and preserves approval boundaries.
        """
        clean_id = validate_task_id(task_id)
        task_path = safe_bridge_path(f'tasks/{clean_id}.json', BRIDGE_ROOT)
        lock_path = safe_bridge_path(f'tasks/{clean_id}.lock', BRIDGE_ROOT)

        if not task_path.exists():
            return False, f'Task {task_id} not found', None

        lock_fd = open(lock_path, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            lock_fd.close()
            return False, f'Task {task_id} is currently locked by another worker.', None

        try:
            with open(task_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rec = TaskRecord(**data)

            # Approval enforcement
            if rec.requires_approval and rec.approval_status != ApprovalStatus.APPROVED:
                if target_status in (TaskStatus.CLAIMED, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED):
                    return False, f'Task {task_id} requires operator approval before execution (approval status: {rec.approval_status.value}).', rec

            # Terminal state immutability
            if rec.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return False, f'Cannot transition task {task_id} from terminal state {rec.status.value}.', rec

            allowed_transitions = {
                TaskStatus.PENDING: {TaskStatus.CLAIMED},
                TaskStatus.CLAIMED: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
                TaskStatus.IN_PROGRESS: {TaskStatus.BLOCKED, TaskStatus.CLAIMED},
                TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS, TaskStatus.CLAIMED},
                TaskStatus.AWAITING_APPROVAL: set(),
            }

            if target_status not in allowed_transitions.get(rec.status, set()):
                return False, f'Invalid status transition from {rec.status.value} to {target_status.value}.', rec

            rec.status = target_status
            rec.updated_at = datetime.now(timezone.utc).isoformat()
            if reason:
                rec.payload["_last_transition_reason"] = reason

            atomic_write_json(task_path, rec.model_dump_json(indent=2))
            return True, f'Task {task_id} transitioned from {data["status"]} to {target_status.value}.', rec
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def approve_task(
        self,
        task_id: str,
        reviewer: str,
        approved: bool = True,
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[TaskRecord]]:
        """
        Record operator approval decision and transition task from awaiting_approval to pending.
        """
        clean_id = validate_task_id(task_id)
        task_path = safe_bridge_path(f'tasks/{clean_id}.json', BRIDGE_ROOT)
        approval_path = safe_bridge_path(f'approvals/{clean_id}.json', BRIDGE_ROOT)
        lock_path = safe_bridge_path(f'tasks/{clean_id}.lock', BRIDGE_ROOT)

        if not task_path.exists():
            return False, f'Task {task_id} not found', None

        lock_fd = open(lock_path, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            lock_fd.close()
            return False, f'Task {task_id} is currently locked.', None

        try:
            with open(task_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rec = TaskRecord(**data)

            if rec.status != TaskStatus.AWAITING_APPROVAL:
                return False, f'Task {task_id} is not awaiting approval (current: {rec.status.value}).', rec

            ts = datetime.now(timezone.utc).isoformat()
            new_approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            rec.approval_status = new_approval_status
            rec.status = TaskStatus.PENDING if approved else TaskStatus.BLOCKED
            rec.updated_at = ts

            atomic_write_json(task_path, rec.model_dump_json(indent=2))

            approval_record = ApprovalRecord(
                task_id=clean_id,
                action_description=rec.title,
                status=new_approval_status,
                requested_at=rec.created_at,
                reviewed_at=ts,
                reviewer=reviewer,
                notes=notes
            )
            atomic_write_json(approval_path, approval_record.model_dump_json(indent=2))

            if approved:
                inbox_path = INBOX_DIR / f'{clean_id}.json'
                atomic_write_json(inbox_path, json.dumps({'task_id': clean_id, 'added_at': ts}))

            decision_str = 'approved' if approved else 'rejected'
            return True, f'Task {task_id} {decision_str} by {reviewer}.', rec
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def publish_result(self, req: ExecutionResultCreateRequest) -> ExecutionResultRecord:
        """Publishes task execution outcome and updates task record."""
        clean_id = validate_task_id(req.task_id)
        task = self.get_task(clean_id)
        if not task:
            raise BridgeValidationError(f'Task {req.task_id} does not exist.')

        # Enforce approval boundaries
        if task.requires_approval and task.approval_status != ApprovalStatus.APPROVED:
            raise BridgeValidationError(
                f'Task {clean_id} requires operator approval before execution results can be published (current approval status: {task.approval_status.value}).'
            )

        # Enforce terminal state immutability
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            raise BridgeValidationError(
                f'Task {clean_id} is already in terminal state {task.status.value}.'
            )

        ts = datetime.now(timezone.utc)
        result_id = f'RES-{clean_id}'
        result_record = ExecutionResultRecord(
            result_id=result_id,
            task_id=clean_id,
            status=req.status,
            summary=req.summary,
            metrics=req.metrics,
            evidence_files=req.evidence_files,
            completed_at=ts.isoformat(),
            operator_notes=req.operator_notes
        )

        result_path = safe_bridge_path(f'results/{clean_id}_result.json', BRIDGE_ROOT)
        atomic_write_json(result_path, result_record.model_dump_json(indent=2))

        # Update task status
        task.status = TaskStatus.COMPLETED if req.status == ResultStatus.SUCCESS else TaskStatus.FAILED
        task.updated_at = ts.isoformat()
        task_path = safe_bridge_path(f'tasks/{clean_id}.json', BRIDGE_ROOT)
        atomic_write_json(task_path, task.model_dump_json(indent=2))

        # Ensure cleared from inbox
        inbox_path = INBOX_DIR / f'{clean_id}.json'
        if inbox_path.exists():
            try:
                inbox_path.unlink()
            except OSError:
                pass

        return result_record

    def get_latest_result(self, task_id: Optional[str] = None) -> Optional[ExecutionResultRecord]:
        """Retrieves the latest execution result or the result for a specific task."""
        if task_id:
            clean_id = validate_task_id(task_id)
            res_path = safe_bridge_path(f'results/{clean_id}_result.json', BRIDGE_ROOT)
            if not res_path.exists():
                return None
            with open(res_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ExecutionResultRecord(**data)

        # Find latest across all result files
        res_files = sorted(RESULTS_DIR.glob('*_result.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not res_files:
            return None

        with open(res_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ExecutionResultRecord(**data)

    def check_approval(self, task_id: str) -> Optional[ApprovalRecord]:
        """Reads approval record for a task."""
        clean_id = validate_task_id(task_id)
        approval_path = safe_bridge_path(f'approvals/{clean_id}.json', BRIDGE_ROOT)
        if not approval_path.exists():
            return None
        with open(approval_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ApprovalRecord(**data)

    def get_project_status(self) -> Dict[str, Any]:
        """Aggregates Git state, directory stats, and task counts."""
        branch = 'unknown'
        untracked_count = 0
        modified_count = 0
        try:
            res_branch = subprocess.run(
                ['git', '-C', str(VIRA_PROJECT_ROOT), 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, timeout=5
            )
            if res_branch.returncode == 0:
                branch = res_branch.stdout.strip()

            res_status = subprocess.run(
                ['git', '-C', str(VIRA_PROJECT_ROOT), 'status', '--porcelain'],
                capture_output=True, text=True, timeout=5
            )
            if res_status.returncode == 0:
                lines = [l for l in res_status.stdout.splitlines() if l.strip()]
                untracked_count = sum(1 for l in lines if l.startswith('??'))
                modified_count = len(lines) - untracked_count
        except Exception:
            pass

        tasks = self.list_tasks()
        counts = {
            'total': len(tasks),
            'pending': sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            'claimed': sum(1 for t in tasks if t.status == TaskStatus.CLAIMED),
            'in_progress': sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
            'completed': sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            'failed': sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            'awaiting_approval': sum(1 for t in tasks if t.status == TaskStatus.AWAITING_APPROVAL)
        }

        total_bytes = 0
        for p in BRIDGE_ROOT.rglob('*'):
            if p.is_file():
                total_bytes += p.stat().st_size

        return {
            'system_name': 'GRaCEmo ViRa Agent Bridge',
            'git_root': str(VIRA_PROJECT_ROOT),
            'current_branch': branch,
            'git_summary': {
                'untracked_files_count': untracked_count,
                'modified_files_count': modified_count
            },
            'task_counts': counts,
            'bridge_disk_usage_kb': round(total_bytes / 1024, 2),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
