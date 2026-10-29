import os
import sys
from pathlib import Path


def get_user_data_dir() -> Path:
    """Return the platform-appropriate user data directory for Nexus Core.

    * Windows:   %LOCALAPPDATA%\\NexusCore
    * macOS:     ~/Library/Application Support/NexusCore
    * Linux:     ~/.local/share/NexusCore  (or $XDG_DATA_HOME/NexusCore)
    """
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = Path(os.path.expanduser("~")) / "Library" / "Application Support"
    else:
        base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    d = Path(base) / "NexusCore"
    d.mkdir(parents=True, exist_ok=True)
    return d
