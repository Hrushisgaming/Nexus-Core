"""
core/clipboard_compat.py
Make pyperclip thread-safe on macOS.

pyperclip auto-selects an AppKit/NSPasteboard backend whenever pyobjc is
installed (it is bundled in the macOS build). NSPasteboard must not be touched
from Python worker threads - doing so crashes with EXC_BAD_ACCESS inside
-[NSPasteboard _updateTypeCacheIfNeeded]. Force the pbcopy/pbpaste backend,
which just spawns a subprocess and is safe from any thread.

Call apply() before the first pyperclip.copy()/paste(). It is idempotent.
"""
import sys

_applied = False


def apply() -> None:
    global _applied
    if _applied or sys.platform != "darwin":
        return
    try:
        import pyperclip
        pyperclip.set_clipboard("pbcopy")
    except Exception:
        pass
    _applied = True
