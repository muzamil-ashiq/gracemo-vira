"""
GRACEEMO-01 — Hardware Manifest Loader
Loads and parses docs/hardware/graceemo_hardware_manifest.yaml (or .json fallback).
Zero external dependency fallback.
"""

import os
import sys
import json

MANIFEST_YAML = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "docs", "hardware", "graceemo_hardware_manifest.yaml"
)
MANIFEST_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "docs", "hardware", "graceemo_hardware_manifest.json"
)

def load_manifest(path=None):
    """Load hardware manifest using JSON or YAML."""
    json_path = os.path.abspath(MANIFEST_JSON)
    yaml_path = path or os.path.abspath(MANIFEST_YAML)

    # 1. Prefer JSON mirror if available (built-in, no dependencies)
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            return json.load(f)

    # 2. Try importing yaml, with .venv fallback
    try:
        import yaml
    except ImportError:
        venv_sp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".venv", "lib", "python3.11", "site-packages"))
        if os.path.exists(venv_sp) and venv_sp not in sys.path:
            sys.path.insert(0, venv_sp)
        import yaml

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    # Write out JSON mirror for future dependency-free access
    try:
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    return data

def get_component(comp_id, manifest=None):
    """Get single component record by component_id."""
    data = manifest or load_manifest()
    for c in data.get("components", []):
        if c.get("component_id") == comp_id:
            return c
    return None

def get_components_by_category(category, manifest=None):
    """Get all components under a given category."""
    data = manifest or load_manifest()
    return [c for c in data.get("components", []) if c.get("category") == category]
