"""
MCP Server Interface for the VIRA Agent Bridge.
Exposes validated, narrowly scoped tools over MCP stdio transport:
- get_project_status
- list_pending_tasks
- list_tasks
- claim_task
- update_task_status
- read_task
- create_task
- publish_execution_result
- read_latest_result
- check_approval_status
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure VIRA root is in sys.path
VIRA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VIRA_ROOT))

from mcp.server.mcpserver import MCPServer
from agent_bridge.storage import BridgeStorage
from agent_bridge.models import (
    TaskCreateRequest,
    TaskCategory,
    TaskPriority,
    ResultStatus,
    ExecutionResultCreateRequest,
    TaskStatus
)
from agent_bridge.config import validate_task_id, BridgeValidationError, BridgePathSafetyError

server = MCPServer('vira-agent-bridge')
storage = BridgeStorage()

@server.tool(name='get_project_status', description='Retrieve current VIRA repository status, git branch, task counts, and bridge storage metrics.')
def get_project_status() -> str:
    """Returns project and task queue summary in JSON format."""
    try:
        status = storage.get_project_status()
        return json.dumps(status, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='list_pending_tasks', description='List all tasks currently in pending status awaiting execution.')
def list_pending_tasks(category: Optional[str] = None, priority: Optional[str] = None) -> str:
    """Lists pending tasks, optionally filtered by category or priority (backward-compatible)."""
    try:
        tasks = storage.list_tasks(status=TaskStatus.PENDING.value, category=category, priority=priority)
        records = [t.model_dump() for t in tasks]
        return json.dumps({'count': len(records), 'tasks': records}, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='list_tasks', description='List tasks with validated status, category, or priority filters, bounded by limit.')
def list_tasks(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50
) -> str:
    """Lists tasks with validated status filters and bounded output."""
    status_val = None
    if status is not None:
        try:
            status_val = TaskStatus(status.lower()).value
        except ValueError:
            return json.dumps({
                'error': f'Invalid status "{status}". Valid: {[s.value for s in TaskStatus]}',
                'status': 'invalid_status'
            })

    cat_val = None
    if category is not None:
        try:
            cat_val = TaskCategory(category.lower()).value
        except ValueError:
            return json.dumps({
                'error': f'Invalid category "{category}". Valid: {[c.value for c in TaskCategory]}',
                'status': 'invalid_category'
            })

    prio_val = None
    if priority is not None:
        try:
            prio_val = TaskPriority(priority.lower()).value
        except ValueError:
            return json.dumps({
                'error': f'Invalid priority "{priority}". Valid: {[p.value for p in TaskPriority]}',
                'status': 'invalid_priority'
            })

    try:
        bounded_limit = min(max(1, int(limit)), 100)
    except (ValueError, TypeError):
        bounded_limit = 50

    try:
        tasks = storage.list_tasks(status=status_val, category=cat_val, priority=prio_val, limit=bounded_limit)
        records = [t.model_dump() for t in tasks]
        return json.dumps({'count': len(records), 'tasks': records}, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='claim_task', description='Atomically claim an eligible pending task for execution.')
def claim_task(task_id: str, agent_id: str = 'agent') -> str:
    """Atomically claims an eligible pending task."""
    try:
        clean_id = validate_task_id(task_id)
        clean_agent = agent_id.strip() if agent_id and isinstance(agent_id, str) else 'agent'
        success, message, task = storage.claim_task(clean_id, clean_agent)
        if not success:
            return json.dumps({
                'status': 'claim_rejected',
                'task_id': task_id,
                'message': message,
                'task': task.model_dump() if task else None
            }, indent=2)
        return json.dumps({
            'status': 'claimed',
            'task_id': clean_id,
            'message': message,
            'task': task.model_dump() if task else None
        }, indent=2)
    except (BridgeValidationError, BridgePathSafetyError) as e:
        return json.dumps({'error': str(e), 'status': 'invalid_request'})
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='update_task_status', description='Update active task status enforcing validated transitions and approval boundaries.')
def update_task_status(task_id: str, target_status: str, reason: Optional[str] = None) -> str:
    """Updates active task status."""
    try:
        status_enum = TaskStatus(target_status.lower())
    except ValueError:
        return json.dumps({
            'error': f'Invalid target status "{target_status}". Valid: {[s.value for s in TaskStatus]}',
            'status': 'invalid_status'
        })

    try:
        clean_id = validate_task_id(task_id)
        success, message, task = storage.update_task_status(clean_id, status_enum, reason)
        if not success:
            return json.dumps({
                'status': 'transition_rejected',
                'task_id': task_id,
                'message': message,
                'task': task.model_dump() if task else None
            }, indent=2)
        return json.dumps({
            'status': 'updated',
            'task_id': clean_id,
            'message': message,
            'task': task.model_dump() if task else None
        }, indent=2)
    except (BridgeValidationError, BridgePathSafetyError) as e:
        return json.dumps({'error': str(e), 'status': 'invalid_request'})
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='read_task', description='Retrieve complete details for a specific task by task ID.')
def read_task(task_id: str) -> str:
    """Reads task details by ID."""
    try:
        clean_id = validate_task_id(task_id)
        task = storage.get_task(clean_id)
        if not task:
            return json.dumps({'error': f'Task {task_id} not found.', 'status': 'not_found'})
        return task.model_dump_json(indent=2)
    except (BridgeValidationError, BridgePathSafetyError) as e:
        return json.dumps({'error': str(e), 'status': 'invalid_request'})
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='create_task', description='Create a new task in the VIRA agent bridge queue. Consequential tasks must have requires_approval=True.')
def create_task(
    title: str,
    description: str,
    category: str = 'research',
    priority: str = 'normal',
    requires_approval: bool = False,
    payload_json: Optional[str] = None
) -> str:
    """Creates a new task."""
    try:
        cat_enum = TaskCategory(category.lower())
    except ValueError:
        return json.dumps({'error': f'Invalid category "{category}". Valid: {[c.value for c in TaskCategory]}', 'status': 'invalid_category'})

    try:
        prio_enum = TaskPriority(priority.lower())
    except ValueError:
        return json.dumps({'error': f'Invalid priority "{priority}". Valid: {[p.value for p in TaskPriority]}', 'status': 'invalid_priority'})

    payload_dict = {}
    if payload_json:
        try:
            payload_dict = json.loads(payload_json)
        except json.JSONDecodeError:
            return json.dumps({'error': 'payload_json must be valid JSON.', 'status': 'invalid_payload'})

    try:
        req = TaskCreateRequest(
            title=title,
            description=description,
            category=cat_enum,
            priority=prio_enum,
            requires_approval=requires_approval,
            payload=payload_dict
        )
        task = storage.create_task(req, creator='mcp_client')
        return json.dumps({'status': 'created', 'task_id': task.id, 'task': task.model_dump()}, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='publish_execution_result', description='Publish outcomes, metrics, and evidence files for a completed or failed task.')
def publish_execution_result(
    task_id: str,
    status: str = 'success',
    summary: str = '',
    metrics_json: Optional[str] = None,
    evidence_files_json: Optional[str] = None,
    operator_notes: Optional[str] = None
) -> str:
    """Publishes task execution result."""
    try:
        res_status = ResultStatus(status.lower())
    except ValueError:
        return json.dumps({'error': f'Invalid status "{status}". Valid: {[s.value for s in ResultStatus]}', 'status': 'invalid_status'})

    metrics = {}
    if metrics_json:
        try:
            metrics = json.loads(metrics_json)
        except json.JSONDecodeError:
            return json.dumps({'error': 'metrics_json must be valid JSON.', 'status': 'invalid_metrics'})

    evidence_files = []
    if evidence_files_json:
        try:
            evidence_files = json.loads(evidence_files_json)
            if not isinstance(evidence_files, list):
                return json.dumps({'error': 'evidence_files_json must be a JSON array of filepaths.', 'status': 'invalid_evidence'})
        except json.JSONDecodeError:
            return json.dumps({'error': 'evidence_files_json must be valid JSON.', 'status': 'invalid_evidence'})

    try:
        clean_id = validate_task_id(task_id)
        req = ExecutionResultCreateRequest(
            task_id=clean_id,
            status=res_status,
            summary=summary or 'Task execution completed.',
            metrics=metrics,
            evidence_files=evidence_files,
            operator_notes=operator_notes
        )
        result = storage.publish_result(req)
        return json.dumps({'status': 'published', 'result_id': result.result_id, 'result': result.model_dump()}, indent=2)
    except (BridgeValidationError, BridgePathSafetyError) as e:
        return json.dumps({'error': str(e), 'status': 'validation_error'})
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='read_latest_result', description='Read the most recent task execution result across the bridge, or for a specific task ID.')
def read_latest_result(task_id: Optional[str] = None) -> str:
    """Reads latest execution result."""
    try:
        clean_id = validate_task_id(task_id) if task_id else None
        res = storage.get_latest_result(clean_id)
        if not res:
            return json.dumps({'status': 'not_found', 'message': f'No execution result found for task_id={task_id}'})
        return res.model_dump_json(indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

@server.tool(name='check_approval_status', description='Check the human operator approval status for a consequential task.')
def check_approval_status(task_id: str) -> str:
    """Reads approval record for a consequential task."""
    try:
        clean_id = validate_task_id(task_id)
        approval = storage.check_approval(clean_id)
        if not approval:
            task = storage.get_task(clean_id)
            if not task:
                return json.dumps({'status': 'not_found', 'message': f'Task {task_id} not found.'})
            return json.dumps({
                'task_id': clean_id,
                'status': 'not_required',
                'message': 'This task does not require explicit approval.'
            })
        return approval.model_dump_json(indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'status': 'failed'})

def main():
    """Main server entry point over stdio transport."""
    server.run(transport='stdio')

if __name__ == '__main__':
    main()
