import os
import sys
import subprocess
from pathlib import Path
import threading
import time
import requests
from PyQt6.QtCore import QObject, pyqtSignal

_BASE_DIR = Path(__file__).resolve().parent.parent


class UpdateChecker(QObject):
    update_available_sig = pyqtSignal(str)

    def __init__(self, repo_owner="Hrushisgaming", repo_name="Nexus-Core", branch="main"):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self._stop_event = threading.Event()
        self._check_thread = None

    def start(self):
        if self._check_thread is None:
            self._check_thread = threading.Thread(target=self._check_loop, daemon=True, name="updater-thread")
            self._check_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._check_thread:
            self._check_thread.join(timeout=1.0)

    def _get_local_hash(self):
        # Only a git checkout can self-update; a packaged app has no .git folder.
        if not (_BASE_DIR / ".git").exists():
            return None
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=_BASE_DIR, stderr=subprocess.DEVNULL
            )
            return output.decode("utf-8").strip()
        except Exception:
            return None

    def _remote_is_ahead(self, local_hash):
        """True only if the remote branch has commits that local_hash lacks.

        Comparing hashes for plain inequality would also fire when the local
        checkout is ahead of GitHub (unpushed work) or the repo has no remote.
        """
        url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
            f"/compare/{local_hash}...{self.branch}"
        )
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get("status") == "ahead"
        except Exception as e:
            print(f"[Updater] Error comparing with remote: {e}")
        return False

    def _get_remote_hash(self):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/commits/{self.branch}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("sha")
        except Exception as e:
            print(f"[Updater] Error fetching remote hash: {e}")
        return None

    def _check_loop(self):
        while not self._stop_event.is_set():
            local_hash = self._get_local_hash()
            remote_hash = self._get_remote_hash()

            if local_hash and remote_hash and local_hash != remote_hash and self._remote_is_ahead(local_hash):
                print(f"[Updater] Update detected! Local: {local_hash[:7]}, Remote: {remote_hash[:7]}")
                self.update_available_sig.emit(remote_hash)
                break # Stop checking once an update is detected

            # Check every hour
            for _ in range(3600):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

def apply_update_and_restart():
    print("[Updater] Applying update...")
    try:
        # Never touch a checkout that has local edits.
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=_BASE_DIR,
            capture_output=True, text=True, timeout=30,
        )
        if status.returncode != 0 or status.stdout.strip():
            print("[Updater] Local changes found; not updating. Commit or stash them first.")
            return
        subprocess.check_call(["git", "fetch", "origin", "main"], cwd=_BASE_DIR,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Fast-forward only: this can never discard local commits (the old
        # `reset --hard` could).
        subprocess.check_call(["git", "merge", "--ff-only", "origin/main"], cwd=_BASE_DIR,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("[Updater] Update applied successfully. Restarting application...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"[Updater] Failed to apply update: {e}")
