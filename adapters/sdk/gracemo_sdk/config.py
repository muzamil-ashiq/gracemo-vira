"""
GRaCEmo ViRa — Unified Configuration Loader
Supports YAML/TOML configs, environment overrides, type-safety, and fallback defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigDict(dict):
    """A dictionary that allows dot-notation access to its keys."""

    def __getattr__(self, key: str) -> Any:
        try:
            val = self[key]
            if isinstance(val, dict) and not isinstance(val, ConfigDict):
                val = ConfigDict(val)
                self[key] = val
            return val
        except KeyError:
            return None

    def __setattr__(self, key: str, value: Any):
        self[key] = value

    def __delattr__(self, key: str):
        try:
            del self[key]
        except KeyError:
            pass

    def get_nested(self, path: str, default: Any = None) -> Any:
        """Get a value from a dot-separated path (e.g. 'stt.model_size')."""
        keys = path.split(".")
        curr = self
        for k in keys:
            if isinstance(curr, dict) and k in curr:
                curr = curr[k]
            else:
                return default
        return curr


class ConfigLoader:
    @staticmethod
    def get_project_root() -> Path:
        """Find the root directory of gracemo-vira."""
        curr = Path(__file__).resolve()
        for parent in [curr] + list(curr.parents):
            if (parent / "config").is_dir() and ((parent / "kernel").is_dir() or (parent / "adapters").is_dir()):
                return parent
        # Fallback to standard project location
        return Path("/home/mab/Applications/lpu-project/gracemo-vira")

    @classmethod
    def load(cls, config_name: str, custom_path: Optional[str] = None) -> ConfigDict:
        """
        Load a YAML config file by name (e.g. 'voice', 'perception', 'brain', 'robot')
        or from a custom file path.
        """
        if custom_path and os.path.exists(custom_path):
            file_path = Path(custom_path)
        else:
            root = cls.get_project_root()
            if not config_name.endswith(".yaml") and not config_name.endswith(".yml"):
                config_name = f"{config_name}.yaml"
            file_path = root / "config" / config_name

        data: Dict[str, Any] = {}
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception as e:
                print(f"[ConfigLoader] Warning: Failed to parse {file_path}: {e}")

        # Apply environment variable overrides (e.g., GRACEMO_VOICE_TTS_ENGINE="kokoro")
        prefix = f"GRACEMO_{file_path.stem.upper()}_"
        for env_k, env_v in os.environ.items():
            if env_k.startswith(prefix):
                sub_key = env_k[len(prefix):].lower().replace("__", ".")
                cls._set_nested_value(data, sub_key, env_v)

        return ConfigDict(cls._wrap_dict(data))

    @staticmethod
    def _wrap_dict(d: Any) -> Any:
        if isinstance(d, dict):
            return ConfigDict({k: ConfigLoader._wrap_dict(v) for k, v in d.items()})
        elif isinstance(d, list):
            return [ConfigLoader._wrap_dict(item) for item in d]
        return d

    @staticmethod
    def _set_nested_value(d: dict, path: str, val: Any):
        keys = path.split(".")
        curr = d
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        # Attempt type inference for boolean / integer env vars
        if str(val).lower() in ("true", "1", "yes"):
            val = True
        elif str(val).lower() in ("false", "0", "no"):
            val = False
        else:
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
        curr[keys[-1]] = val
