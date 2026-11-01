"""
core/api_keys.py
Single place to resolve provider API keys.

Order: explicit value -> environment variable -> saved settings
(api_keys.json / app_settings.json in the user data dir).

The Settings UI saves keys to the JSON files, never to the environment, so
provider classes that only read os.environ always reported "not configured".
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def get_api_key(setting_name: str, env_var: Optional[str] = None, explicit: Optional[str] = None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    if env_var:
        v = (os.environ.get(env_var) or "").strip()
        if v:
            return v
    try:
        from core.user_paths import get_user_data_dir
        cfg_dir = get_user_data_dir() / "config"
        for name in ("api_keys.json", "app_settings.json"):
            path = cfg_dir / name
            if path.exists() or Path(str(path) + ".bak").exists():
                from core.atomic_io import read_json_dict
                data = read_json_dict(path)
                v = str(data.get(setting_name, "") or "").strip()
                if v:
                    return v
    except Exception:
        pass
    return ""
