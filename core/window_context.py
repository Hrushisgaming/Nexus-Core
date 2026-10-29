"""
Active Window & Foreground Application Context for Brahma AI.
Cross-platform: delegates to core.platform_api so the same call works on
Windows (Win32), macOS (AppleScript/System Events), and Linux.
"""

from typing import Optional, Dict, Any

from core.platform_api import platform_api


def get_foreground_window_info() -> Dict[str, Any]:
    """
    Returns metadata about the currently active foreground window:
    - title: Window title string
    - class_name: Executable or window class name
    - hwnd: Window handle (0 on non-Windows)
    - rect: (x, y, w, h)
    - pid: Process id
    """
    return platform_api.get_foreground_window()


def capture_active_window_screenshot() -> Optional[bytes]:
    """
    Captures a high-resolution JPEG screenshot of the current foreground window.
    """
    info = get_foreground_window_info()
    bbox = info.get("bbox")
    if not bbox or info.get("rect", (0, 0, 0, 0))[2] < 10:
        return None

    try:
        from PIL import ImageGrab
        import io

        x, y, w, h = info["rect"]
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None
