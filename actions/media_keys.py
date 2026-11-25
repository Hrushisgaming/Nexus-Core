"""Cross-platform volume and media transport helpers (Windows, macOS, Linux)."""
from __future__ import annotations

from core.platform_api import platform_api


def _press(key: str) -> bool:
    from actions.spotify_controller import _press_media_key
    return _press_media_key(key)


def volume_up(steps: int = 3) -> bool:
    ok = False
    for _ in range(max(1, int(steps))):
        ok = _press("volumeup") or ok
    return ok


def volume_down(steps: int = 3) -> bool:
    ok = False
    for _ in range(max(1, int(steps))):
        ok = _press("volumedown") or ok
    return ok


def volume_mute() -> bool:
    return _press("volumemute")


def volume_set(percent: int) -> bool:
    return platform_api.set_volume(int(percent))


def media_play_pause() -> bool:
    return _press("playpause")


def media_next() -> bool:
    return _press("nexttrack")


def media_previous() -> bool:
    return _press("prevtrack")
