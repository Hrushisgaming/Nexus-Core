"""
core/single_instance.py
Single-instance guard for macOS / Linux (Windows uses a named mutex in main.py).

Uses an advisory flock() on a file in the user data dir. The OS drops the lock
the instant the process dies - including a force-quit - so it can never go
stale. A freshly restarted instance retries for a few seconds so it doesn't
lose the race against the old instance that is still shutting down.
"""
from __future__ import annotations

import os
import sys
import time

_lock_fd = None


def acquire(wait_seconds: float = 12.0) -> bool:
    """Return True if this process now owns the instance lock."""
    global _lock_fd
    if os.name == "nt":
        return True
    try:
        import fcntl
        from core.user_paths import get_user_data_dir
        path = get_user_data_dir() / "nexus_core.lock"
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        deadline = time.time() + max(0.0, wait_seconds)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    os.close(fd)
                    return False
                time.sleep(0.3)
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        _lock_fd = fd  # keep open for the life of the process
        return True
    except Exception:
        # Never block startup because the guard itself failed.
        return True


def notify_already_running() -> None:
    msg = "Nexus Core is already running. If it is not responding, Force Quit it and reopen."
    print(f"[NEXUS CORE] {msg}")
    if sys.platform == "darwin":
        try:
            import subprocess
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{msg}" with title "Nexus Core"'],
                timeout=5, check=False,
            )
        except Exception:
            pass
