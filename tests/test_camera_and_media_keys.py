import sys
import types

import pytest

from core import camera


class _FakeCv2:
    CAP_ANY = 0
    CAP_DSHOW = 700
    CAP_AVFOUNDATION = 1200
    CAP_V4L2 = 200
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self, working=None):
        self.working = working  # set of (index, backend) that open
        self.opened = []

    def VideoCapture(self, idx, backend=0):
        outer = self

        class Cap:
            def isOpened(self):
                return (idx, backend) in outer.working

            def read(self):
                return True, object()

            def set(self, *a):
                pass

            def release(self):
                pass

        outer.opened.append((idx, backend))
        return Cap()


@pytest.mark.parametrize(
    "platform,expected_first",
    [("win32", 700), ("darwin", 1200), ("linux", 200)],
)
def test_backend_order_per_platform(monkeypatch, platform, expected_first):
    monkeypatch.setattr(sys, "platform", platform)
    backends = camera.camera_backends(_FakeCv2())
    assert backends[0] == expected_first
    assert backends[-1] == 0


def test_open_camera_falls_back_to_any(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    fake = _FakeCv2(working={(0, 0)})
    cap = camera.open_camera(0, cv2_module=fake)
    assert cap is not None
    assert fake.opened == [(0, 1200), (0, 0)]


def test_open_camera_returns_none_when_nothing_opens(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert camera.open_camera(indexes=(0, 1), cv2_module=_FakeCv2(working=set())) is None


def _run_media_key(monkeypatch, platform, key):
    from actions import spotify_controller as sc

    calls = []
    monkeypatch.setattr(sc.sys, "platform", platform)
    monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/" + name)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(sc.subprocess, "run", fake_run)
    # Force the no-pyobjc path on macOS regardless of what is installed.
    monkeypatch.setitem(sys.modules, "Quartz", None)
    return sc._press_media_key(key), calls


def test_mac_media_keys_fall_back_to_osascript(monkeypatch):
    ok, calls = _run_media_key(monkeypatch, "darwin", "volumeup")
    assert ok and calls[0][0] == "osascript"
    ok, calls = _run_media_key(monkeypatch, "darwin", "playpause")
    assert ok and "playpause" in calls[0][-1]


def test_linux_media_keys_use_playerctl_and_pactl(monkeypatch):
    ok, calls = _run_media_key(monkeypatch, "linux", "nexttrack")
    assert ok and calls[0] == ["playerctl", "next"]
    ok, calls = _run_media_key(monkeypatch, "linux", "volumedown")
    assert ok and calls[0][0] == "pactl"


def test_media_keys_module_exports():
    from actions import media_keys

    for name in ("volume_up", "volume_down", "volume_mute", "volume_set",
                 "media_play_pause", "media_next", "media_previous"):
        assert callable(getattr(media_keys, name))
