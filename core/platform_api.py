"""
core/platform_api.py
====================

Cross-platform desktop API layer for Brahma AI Evo.

Replaces scattered Win32 ctypes / winreg / os.startfile / platform-specific
subprocess calls with a single, platform-agnostic interface:

    Windows   -> ctypes.windll, winreg, pycaw, powershell
    macOS     -> AppleScript (osascript), subprocess, Quartz (via pyautogui)
    Linux     -> xdg-open, wmctrl, gsettings, pactl/brightnessctl

Every function degrades gracefully (returns False / empty / None) when the
underlying capability is unavailable on the current OS, so callers never need
to `#if` around platform checks.

Usage:
    from core.platform_api import platform_api
    platform_api.lock_workstation()
    platform_api.open_file("/path/to/file")
    info = platform_api.get_foreground_window()
"""

from __future__ import annotations

import ctypes
import os
import platform as _platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_OS = _platform.system()  # "Windows" | "Darwin" | "Linux"

# Windows-only modules (imported lazily so the package loads on any OS).
_winreg: Any = None
if _OS == "Windows":
    try:
        import winreg as _winreg  # type: ignore
    except Exception:  # pragma: no cover
        _winreg = None


# ═════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════


def _run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run a command, hiding the console window on Windows."""
    if _OS == "Windows":
        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _osascript(script: str) -> subprocess.CompletedProcess:
    """Execute AppleScript on macOS; a no-op elsewhere."""
    if _OS != "Darwin":
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    return _run(["osascript", "-e", script], timeout=10)


# ═════════════════════════════════════════════════════════════════════════
# Window / foreground info
# ═════════════════════════════════════════════════════════════════════════


class PlatformAPI:
    """Singleton facade exposing one API for every desktop OS."""

    # ── window / screen ─────────────────────────────────────────────

    def get_foreground_window(self) -> Dict[str, Any]:
        """Metadata for the currently focused window (title, process, bounds, pid)."""
        if _OS == "Windows":
            return self._win_foreground_window()
        if _OS == "Darwin":
            return self._mac_foreground_window()
        return self._linux_foreground_window()

    # -- Windows implementation ------------------------------------
    def _win_foreground_window(self) -> Dict[str, Any]:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {"title": "", "class_name": "", "hwnd": 0, "rect": (0, 0, 0, 0), "pid": 0}

            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()

            class_buff = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buff, 256)
            class_name = class_buff.value.strip()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = max(0, rect.right - rect.left)
            h = max(0, rect.bottom - rect.top)
            return {
                "title": title,
                "class_name": class_name,
                "hwnd": hwnd,
                "rect": (rect.left, rect.top, w, h),
                "bbox": (rect.left, rect.top, rect.right, rect.bottom),
                "pid": pid.value,
            }
        except Exception:
            return {"title": "", "class_name": "error", "hwnd": 0, "rect": (0, 0, 0, 0), "pid": 0}

    # -- macOS implementation --------------------------------------
    def _mac_foreground_window(self) -> Dict[str, Any]:
        script = (
            'tell application "System Events"\n'
            "  set frontProc to first process whose frontmost is true\n"
            "  set procName to name of frontProc\n"
            "  try\n    set winTitle to name of front window of frontProc\n  end try\n"
            "  try\n"
            "    set winPos to position of front window of frontProc\n"
            "    set winSize to size of front window of frontProc\n"
            "  end try\n"
            "end tell\n"
            "return procName & \\t\\t & (winTitle as string) & \\t\\t & "
            "(item 1 of winPos as string) & \\t\\t & (item 2 of winPos as string) & "
            "\\t\\t & (item 1 of winSize as string) & \\t\\t & (item 2 of winSize as string)"
        )
        try:
            res = _run(["osascript", "-e", script], timeout=6)
            if res.returncode != 0:
                return {}
            parts = res.stdout.strip().split("\t\t")
            if len(parts) < 6:
                return {}
            proc_name, title = parts[0], parts[1]
            try:
                x, y, w, h = (int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5]))
            except Exception:
                x = y = w = h = 0
            pid_script = 'tell application "System Events" to unix id of (first process whose frontmost is true)'
            pid = 0
            try:
                pr = _run(["osascript", "-e", pid_script], timeout=6)
                pid = int(pr.stdout.strip()) if pr.stdout.strip().isdigit() else 0
            except Exception:
                pass
            return {
                "title": title or "",
                "class_name": proc_name or "unknown",
                "hwnd": 0,
                "rect": (x, y, w, h),
                "bbox": (x, y, x + w, y + h),
                "pid": pid,
            }
        except Exception:
            return {}

    # -- Linux implementation --------------------------------------
    def _linux_foreground_window(self) -> Dict[str, Any]:
        try:
            res = _run(["xdotool", "getactivewindow", "getwindowname"], timeout=4)
            title = res.stdout.strip() if res.returncode == 0 else ""
            pid_res = _run(["xdotool", "getactivewindow", "getwindowpid"], timeout=4)
            pid = int(pid_res.stdout.strip()) if pid_res.stdout.strip().isdigit() else 0
            return {"title": title, "class_name": "", "hwnd": 0, "rect": (0, 0, 0, 0), "pid": pid}
        except Exception:
            return {}

    def minimize_windows_by_name(self, process_names: List[str]) -> int:
        """Minimize all visible windows whose process name matches. Returns count minimized."""
        if _OS == "Windows":
            return self._win_minimize_by_name(process_names)
        if _OS == "Darwin":
            return self._mac_minimize_by_name(process_names)
        return self._linux_minimize_by_name(process_names)

    def _win_minimize_by_name(self, process_names: List[str]) -> int:
        import ctypes
        import psutil

        user32 = ctypes.windll.user32
        lowered = {n.lower() for n in process_names}
        count = 0

        def callback(hwnd, extra):
            nonlocal count
            if user32.IsWindowVisible(hwnd):
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    if psutil.Process(pid.value).name().lower() in lowered:
                        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                        count += 1
                except Exception:
                    pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return count

    def _mac_minimize_by_name(self, process_names: List[str]) -> int:
        names_json = '", "'.join(process_names)
        script = (
            'tell application "System Events" to set minimized of every window '
            f'of every process whose name is in {{"{names_json}"}} to true'
        )
        try:
            res = _osascript(script)
            return len(process_names) if res.returncode == 0 else 0
        except Exception:
            return 0

    def _linux_minimize_by_name(self, process_names: List[str]) -> int:
        return 0

    def get_screen_size(self) -> Tuple[int, int]:
        """Primary screen resolution (width, height)."""
        try:
            import pyautogui

            w, h = pyautogui.size()
            return int(w), int(h)
        except Exception:
            return 0, 0

    # ── system control ─────────────────────────────────────────────

    def lock_workstation(self) -> bool:
        """Lock the session / show the login screen."""
        if _OS == "Windows":
            try:
                ctypes.windll.user32.LockWorkStation()
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            try:
                _run([
                    "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                    "-suspend",
                ], timeout=5)
                return True
            except Exception:
                return False
        return False

    def mute_system_audio(self, muted: bool = True) -> bool:
        """Mute or unmute master audio."""
        if _OS == "Windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                VK_VOLUME_MUTE = 0xAD
                KEYEVENTF_KEYUP = 0x0002
                user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
                user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            try:
                script = "set volume with output muted" if muted else "set volume without output muted"
                res = _osascript(script)
                return res.returncode == 0
            except Exception:
                return False
        try:
            _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0"])
            return True
        except Exception:
            return False

    def set_volume(self, percent: int) -> bool:
        """Set master volume 0-100."""
        percent = max(0, min(100, int(percent)))
        if _OS == "Windows":
            try:
                import math
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol = cast(interface, POINTER(IAudioEndpointVolume))
                vol_db = -65.25 if percent == 0 else max(-65.25, 20 * math.log10(percent / 100))
                vol.SetMasterVolumeLevel(vol_db, None)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            res = _run(["osascript", "-e", f"set volume output volume {percent}"], timeout=5)
            return res.returncode == 0
        try:
            _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"])
            return True
        except Exception:
            return False

    def get_volume(self) -> Optional[int]:
        """Current master volume 0-100, or None if unreadable."""
        if _OS == "Windows":
            try:
                import math
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                vol = cast(interface, POINTER(IAudioEndpointVolume))
                db = vol.GetMasterVolumeLevel()
                if db <= -65.0:
                    return 0
                return max(0, min(100, round(10 ** (db / 20) * 100)))
            except Exception:
                return None
        if _OS == "Darwin":
            try:
                res = _run(["osascript", "-e", "output volume of (get volume settings)"], timeout=5)
                return max(0, min(100, int(res.stdout.strip())))
            except Exception:
                return None
        try:
            res = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], timeout=5)
            import re
            m = re.search(r"(\d+)%", res.stdout)
            return max(0, min(100, int(m.group(1)))) if m else None
        except Exception:
            return None

    def set_brightness(self, percent: int) -> bool:
        """Set screen brightness 0-100."""
        percent = max(0, min(100, int(percent)))
        if _OS == "Windows":
            try:
                _run([
                    "powershell", "-Command",
                    f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                    f".WmiSetBrightness(1, {percent})",
                ], timeout=5)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            # macOS has no public CLI for brightness; best-effort via private framework not available.
            return False
        try:
            _run(["brightnessctl", "set", f"{percent}%"])
            return True
        except Exception:
            return False

    def get_brightness(self) -> Optional[int]:
        """Current brightness 0-100, or None."""
        if _OS == "Windows":
            try:
                res = _run([
                    "powershell", "-Command",
                    "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness",
                ], timeout=5)
                return max(0, min(100, int(res.stdout.strip())))
            except Exception:
                return None
        if _OS == "Linux":
            try:
                cur = int(_run(["brightnessctl", "get"], timeout=5).stdout.strip())
                mx = int(_run(["brightnessctl", "max"], timeout=5).stdout.strip())
                return max(0, min(100, round(cur * 100 / mx))) if mx else None
            except Exception:
                return None
        return None

    def dark_mode_toggle(self) -> bool:
        """Toggle system dark/light theme."""
        if _OS == "Windows":
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
                current, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                new_val = 1 - current
                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_val)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_val)
                winreg.CloseKey(key)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            script = ('tell app "System Events" to tell appearance preferences '
                      'to set dark mode to not dark mode')
            res = _osascript(script)
            return res.returncode == 0
        try:
            res = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], text=True)
            current = res.stdout.strip()
            new_scheme = "'default'" if "dark" in current else "'prefer-dark'"
            _run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", new_scheme])
            return True
        except Exception:
            return False

    def toggle_wifi(self) -> bool:
        """Toggle Wi-Fi on/off."""
        if _OS == "Windows":
            try:
                _run([
                    "powershell", "-Command",
                    "$adapter = Get-NetAdapter | Where-Object {$_.PhysicalMediaType -eq 'Native 802.11'};"
                    "if ($adapter.Status -eq 'Up') { Disable-NetAdapter -Name $adapter.Name -Confirm:$false }"
                    "else { Enable-NetAdapter -Name $adapter.Name -Confirm:$false }",
                ], timeout=10)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            try:
                # Detect interface then flip power.
                list_res = _run(["networksetup", "-listallhardwareports"], timeout=5)
                iface = "en0"
                for i, line in enumerate(list_res.stdout.splitlines()):
                    if "Wi-Fi" in line or "AirPort" in line:
                        for j in range(i, min(i + 4, len(list_res.stdout.splitlines()))):
                            if list_res.stdout.splitlines()[j].startswith("Device:"):
                                iface = list_res.stdout.splitlines()[j].split(":", 1)[1].strip()
                                break
                        break
                get_res = _run(["networksetup", "-getairportpower", iface], timeout=5)
                state = "off" if "On" in get_res.stdout else "on"
                _run(["networksetup", "-setairportpower", iface, state], timeout=5)
                return True
            except Exception:
                return False
        try:
            res = _run(["nmcli", "radio", "wifi"], timeout=5)
            state = "off" if "enabled" in res.stdout else "on"
            _run(["nmcli", "radio", "wifi", state], timeout=5)
            return True
        except Exception:
            return False

    # ── power / session ────────────────────────────────────────────

    def shutdown(self, timeout: int = 10) -> bool:
        if _OS == "Windows":
            return _run(["shutdown", "/s", "/t", str(timeout)]).returncode == 0
        if _OS == "Darwin":
            return _run(["osascript", "-e", 'tell application "System Events" to shut down']).returncode == 0
        return _run(["systemctl", "poweroff"]).returncode == 0

    def restart(self, timeout: int = 10) -> bool:
        if _OS == "Windows":
            return _run(["shutdown", "/r", "/t", str(timeout)]).returncode == 0
        if _OS == "Darwin":
            return _run(["osascript", "-e", 'tell application "System Events" to restart']).returncode == 0
        return _run(["systemctl", "reboot"]).returncode == 0

    def sleep_display(self) -> bool:
        if _OS == "Windows":
            try:
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
                return True
            except Exception:
                return False
        if _OS == "Darwin":
            return _run(["pmset", "displaysleepnow"]).returncode == 0
        return _run(["xset", "dpms", "force", "off"]).returncode == 0

    # ── file / folder ──────────────────────────────────────────────

    def open_file(self, path: str) -> bool:
        """Open a file with its default application."""
        try:
            p = str(path)
            if _OS == "Windows":
                os.startfile(p)
            elif _OS == "Darwin":
                _run(["open", p])
            else:
                _run(["xdg-open", p])
            return True
        except Exception:
            return False

    def reveal_file(self, path: str) -> bool:
        """Reveal a file/folder in the system file browser."""
        try:
            p = Path(path)
            target = str(p if p.exists() else p.parent)
            if _OS == "Windows":
                _run(["explorer", f"/select,{target}"])
            elif _OS == "Darwin":
                _run(["open", "-R", target])
            else:
                _run(["xdg-open", str(Path(target).parent)])
            return True
        except Exception:
            return False

    def open_folder(self, path: str) -> bool:
        """Open a folder in the file browser."""
        try:
            p = str(path)
            if _OS == "Windows":
                os.startfile(p)
            elif _OS == "Darwin":
                _run(["open", p])
            else:
                _run(["xdg-open", p])
            return True
        except Exception:
            return False

    def open_settings(self) -> bool:
        if _OS == "Windows":
            return _run(["explorer", "ms-settings:"]).returncode == 0
        if _OS == "Darwin":
            return _run(["open", "-a", "System Settings"]).returncode == 0
        try:
            _run(["gnome-control-center"])
            return True
        except Exception:
            return False

    def open_task_manager(self) -> bool:
        if _OS == "Windows":
            import pyautogui
            pyautogui.hotkey("ctrl", "shift", "esc")
            return True
        if _OS == "Darwin":
            return _run(["open", "-a", "Activity Monitor"]).returncode == 0
        for cmd in (["gnome-system-monitor"], ["xfce4-taskmanager"], ["htop"]):
            if _run(["which", cmd[0]]).returncode == 0:
                _run(cmd)
                return True
        return False

    # ── idle / input ───────────────────────────────────────────────

    def get_idle_seconds(self) -> float:
        """Seconds since last mouse/keyboard input."""
        if _OS == "Windows":
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                lii = ctypes.Structure()
                lii._fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
                lii.cbSize = ctypes.sizeof(lii)
                if user32.GetLastInputInfo(ctypes.byref(lii)):
                    millis = kernel32.GetTickCount() - lii.dwTime
                    return max(0.0, millis / 1000.0)
            except Exception:
                return 0.0
        if _OS == "Darwin":
            try:
                res = _run(["ioreg", "-c", "IOHIDSystem"], timeout=5)
                for line in res.stdout.splitlines():
                    if "HIDIdleTime" in line:
                        parts = line.split("=")
                        if len(parts) == 2:
                            nanos = int(parts[1].strip())
                            return max(0.0, nanos / 1_000_000_000.0)
            except Exception:
                return 0.0
        return 0.0

    def take_screenshot(self) -> Optional[bytes]:
        """JPEG bytes of the whole screen."""
        try:
            from PIL import ImageGrab
            import io

            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        except Exception:
            return None

    # ── trash / recycle bin ────────────────────────────────────────

    def get_trash_stats(self) -> Tuple[int, int]:
        """(size_bytes, item_count) for the OS trash."""
        if _OS == "Windows":
            try:
                import ctypes
                from ctypes import wintypes

                class SHQUERYRBINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("i64Size", ctypes.c_int64),
                        ("i64NumItems", ctypes.c_int64),
                    ]

                shell32 = ctypes.windll.shell32
                rb_info = SHQUERYRBINFO()
                rb_info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
                drive = os.environ.get("SystemDrive", "C:") + "\\"
                if shell32.SHQueryRecycleBinW(drive, ctypes.byref(rb_info)) == 0:
                    return int(rb_info.i64Size), int(rb_info.i64NumItems)
            except Exception:
                pass
        home = Path.home()
        total_size = 0
        total_items = 0
        trash_dirs = [home / ".Trash", home / ".local" / "share" / "Trash" / "files"]
        for td in trash_dirs:
            if td.exists():
                try:
                    for root, _, files in os.walk(td):
                        for f in files:
                            try:
                                fp = os.path.join(root, f)
                                total_size += os.path.getsize(fp)
                                total_items += 1
                            except Exception:
                                continue
                except Exception:
                    pass
        return total_size, total_items

    def empty_trash(self) -> bool:
        if _OS == "Windows":
            try:
                shell32 = ctypes.windll.shell32
                flags = 0x00000001 | 0x00000002 | 0x00000004  # noconfirm|noprogress|nosound
                res = shell32.SHEmptyRecycleBinW(None, None, flags)
                return res in (0, -2147418113)
            except Exception:
                return False
        home = Path.home()
        trash_dirs = [
            home / ".Trash",
            home / ".local" / "share" / "Trash" / "files",
            home / ".local" / "share" / "Trash" / "info",
        ]
        cleared = False
        for td in trash_dirs:
            if td.exists():
                try:
                    for entry in os.scandir(td):
                        try:
                            if entry.is_file(follow_symlinks=False):
                                os.remove(entry.path)
                            elif entry.is_dir(follow_symlinks=False):
                                import shutil
                                shutil.rmtree(entry.path, ignore_errors=True)
                            cleared = True
                        except Exception:
                            pass
                except Exception:
                    pass
        return cleared

    # ── startup / shortcuts ────────────────────────────────────────

    def is_startup_enabled(self, app_name: str = "Nexus Core") -> bool:
        if _OS != "Windows" or _winreg is None:
            return False
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, app_name)
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def set_startup(self, enabled: bool, app_name: str = "Nexus Core",
                    target_path: Optional[str] = None) -> bool:
        """Add/remove the app from the user's startup run key (Windows)."""
        if _OS != "Windows" or _winreg is None:
            return False
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    path = target_path or sys.executable
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{path}"')
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    # ── environment paths ──────────────────────────────────────────

    def get_data_dir(self) -> str:
        """Platform-appropriate application data directory (with NexusCore subdir)."""
        if _OS == "Windows":
            base = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
        elif _OS == "Darwin":
            base = str(Path(os.path.expanduser("~")) / "Library" / "Application Support")
        else:
            base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        return str(Path(base) / "NexusCore")


# Singleton instance
platform_api = PlatformAPI()
