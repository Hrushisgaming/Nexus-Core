"""
core/atomic_io.py
Crash-safe config I/O and a hard-exit watchdog.

* atomic_write_text  - temp file + fsync + os.replace, keeps the previous good
                       copy as <name>.bak. A force-quit mid-save can never
                       leave a truncated api_keys.json / app_settings.json.
* read_json_dict     - tolerant reader: if the file is missing/corrupt it falls
                       back to <name>.bak instead of silently returning {}.
* install_exit_watchdog - after Qt starts quitting, make sure the process really
                       exits (kills helper subprocesses, then os._exit) so the
                       app can never sit "not responding" on close.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

PROTECTED_PIDS: set[int] = set()   # e.g. the new instance spawned by Restart


def atomic_write_text(path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # keep the last good copy so a bad write is always recoverable
        try:
            if path.exists() and path.stat().st_size > 2:
                json.loads(path.read_text(encoding=encoding)) if path.suffix == ".json" else None
                shutil.copy2(path, str(path) + ".bak")
        except Exception:
            pass
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, data, indent: int = 4) -> None:
    atomic_write_text(path, json.dumps(data, indent=indent))


def read_json_dict(path) -> dict:
    """Read a JSON object; fall back to <path>.bak if the file is corrupt."""
    for candidate in (Path(path), Path(str(path) + ".bak")):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _kill_children() -> None:
    try:
        import psutil
        me = psutil.Process()
        kids = [c for c in me.children(recursive=True) if c.pid not in PROTECTED_PIDS]
        for c in kids:
            try:
                c.terminate()
            except Exception:
                pass
        psutil.wait_procs(kids, timeout=1.0)
        for c in kids:
            try:
                if c.is_running():
                    c.kill()
            except Exception:
                pass
    except Exception:
        pass


def install_exit_watchdog(app, grace_seconds: float = 4.0) -> None:
    """Guarantee the process exits shortly after the Qt event loop stops."""
    def _on_quit():
        def _reaper():
            time.sleep(grace_seconds)
            _kill_children()
            os._exit(0)
        threading.Thread(target=_reaper, daemon=True, name="exit-watchdog").start()
        _kill_children()
    try:
        app.aboutToQuit.connect(_on_quit)
    except Exception:
        pass
