"""
Configuration, path safety, and validation primitives for the VIRA Agent Bridge.
"""

import os
import re
from pathlib import Path
from typing import Union

# Authoritative Bridge Root
VIRA_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_ROOT = VIRA_PROJECT_ROOT / 'agent_bridge'

# Dedicated subdirectories
TASKS_DIR = BRIDGE_ROOT / 'tasks'
INBOX_DIR = BRIDGE_ROOT / 'inbox'
RESULTS_DIR = BRIDGE_ROOT / 'results'
APPROVALS_DIR = BRIDGE_ROOT / 'approvals'
LOGS_DIR = BRIDGE_ROOT / 'logs'

# Security & Validation Constraints
TASK_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
MAX_PAYLOAD_BYTES = 512 * 1024  # 512 KB
MAX_EVIDENCE_FILES = 20

class BridgePathSafetyError(ValueError):
    """Raised when a path violates the agent bridge directory boundary."""
    pass

class BridgeValidationError(ValueError):
    """Raised when input payload or task ID fails validation."""
    pass

def ensure_bridge_directories():
    """Ensures all required bridge directories exist."""
    for d in [TASKS_DIR, INBOX_DIR, RESULTS_DIR, APPROVALS_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def safe_bridge_path(subpath: Union[str, Path], base_dir: Path = BRIDGE_ROOT) -> Path:
    """
    Resolves subpath within base_dir. Rejects traversal, null bytes, and symlink escapes.
    """
    subpath_str = str(subpath)
    if '\0' in subpath_str:
        raise BridgePathSafetyError('Null byte detected in path.')

    base_resolved = base_dir.resolve()
    target = (base_resolved / subpath).resolve()

    # Verify containment
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise BridgePathSafetyError(
            f'Path traversal violation: target {target} escapes base directory {base_resolved}'
        )

    return target

def validate_task_id(task_id: str) -> str:
    """Validates task ID format and length."""
    if not task_id or not isinstance(task_id, str):
        raise BridgeValidationError('Task ID must be a non-empty string.')
    clean_id = task_id.strip()
    if not TASK_ID_REGEX.match(clean_id):
        raise BridgeValidationError(
            f'Invalid task ID "{task_id}". Must match ^[A-Za-z0-9_-]{{4,64}}$'
        )
    return clean_id

def atomic_write_json(target_path: Path, content: str) -> None:
    """
    Safely and atomically writes string content to target_path using a temporary file.
    """
    target_path = safe_bridge_path(target_path, BRIDGE_ROOT)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = target_path.with_suffix(f'.tmp_{os.getpid()}_{os.urandom(4).hex()}')
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, target_path)
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
