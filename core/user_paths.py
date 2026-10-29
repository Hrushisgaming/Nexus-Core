import os
import sys
from pathlib import Path


def get_user_data_dir() -> Path:
    """Return the platform-appropriate user data directory for Brahma AI.

    * Windows:   %LOCALAPPDATA%\\BrahmaAI
    * macOS:     ~/Library/Application Support/BrahmaAI
    * Linux:     ~/.local/share/BrahmaAI  (or $XDG_DATA_HOME/BrahmaAI)
    """
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = Path(os.path.expanduser("~")) / "Library" / "Application Support"
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    d = Path(base) / "BrahmaAI"
    d.mkdir(parents=True, exist_ok=True)
    return d
