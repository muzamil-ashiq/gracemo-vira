"""
Pydantic data models and schemas for the VIRA Agent Bridge.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class TaskCategory(str, Enum):
    RESEARCH = 'research'
    DATA_INGESTION = 'data_ingestion'
    RAG_PIPELINE = 'rag_pipeline'
    MODEL_TRAINING = 'model_training'
    EVALUATION = 'evaluation'
    ROBOTICS_INTEGRATION = 'robotics_integration'
    SYSTEM_ADMIN = 'system_admin'

class TaskPriority(str, Enum):
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'

class TaskStatus(str, Enum):
    PENDING = 'pending'
    CLAIMED = 'claimed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    BLOCKED = 'blocked'
    AWAITING_APPROVAL = 'awaiting_approval'

class ApprovalStatus(str, Enum):
    NOT_REQUIRED = 'not_required'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description='Concise task title')
    description: str = Field(..., min_length=5, max_length=10000, description='Detailed task instructions and constraints')
    category: TaskCategory = Field(default=TaskCategory.RESEARCH, description='Domain category')
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description='Task priority level')
    requires_approval: bool = Field(default=False, description='True if consequential action requiring operator approval')
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description='Arbitrary task parameters and configuration')

class TaskRecord(BaseModel):
    id: str
    title: str
    description: str
    category: TaskCategory
    priority: TaskPriority
    status: TaskStatus
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = 'agent'
    assigned_to: Optional[str] = None
    requires_approval: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    payload: Dict[str, Any] = Field(default_factory=dict)

class ResultStatus(str, Enum):
    SUCCESS = 'success'
    FAILURE = 'failure'
    PARTIAL = 'partial'

class ExecutionResultCreateRequest(BaseModel):
    task_id: str
    status: ResultStatus = ResultStatus.SUCCESS
    summary: str = Field(..., min_length=5, max_length=5000, description='Summary of execution outcomes')
    metrics: Dict[str, Any] = Field(default_factory=dict, description='Measured numeric and categorical metrics')
    evidence_files: List[str] = Field(default_factory=list, description='Relative filepaths to logs, diffs, or generated reports')
    operator_notes: Optional[str] = Field(default=None, max_length=2000, description='Optional operator observations')

class ExecutionResultRecord(BaseModel):
    result_id: str
    task_id: str
    status: ResultStatus
    summary: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    evidence_files: List[str] = Field(default_factory=list)
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_notes: Optional[str] = None

class ApprovalRecord(BaseModel):
    task_id: str
    action_description: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: Optional[str] = None
    reviewer: Optional[str] = None
    notes: Optional[str] = None
