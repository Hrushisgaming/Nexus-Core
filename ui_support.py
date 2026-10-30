"""Platform, path, styling, and settings helpers for the Qt UI facade."""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from core.user_paths import get_user_data_dir
from ui_cards import C, qcol

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = get_user_data_dir() / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
APP_SETTINGS_FILE = CONFIG_DIR / "app_settings.json"
DISCORD_SETTINGS_FILE = CONFIG_DIR / "discord_bot.json"
LOGO_FILE  = BASE_DIR / "assets" / "nexus_core_logo.png"
LOGO_ICO   = BASE_DIR / "assets" / "nexus_lite_logo.ico"
APP_ICON_PNG = BASE_DIR / "assets" / "nexus_app_icon.png"
BACKGROUND_IMAGE_FILE = BASE_DIR / "assets" / "nexus_background.png"
MODEL_DOWNLOAD_URL = "https://storage.googleapis.com/mediapipe-assets/hand_landmarker.task"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 160
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"



try:
    if APP_SETTINGS_FILE.exists():
        with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
            _global_settings = json.load(f)
            C.load_theme(_global_settings.get("app_theme", "#ffffff"))
except Exception:
    pass

# Patch setStyleSheet to dynamically replace legacy colors with Nexus Core theme
_old_setStyleSheet = QWidget.setStyleSheet
def _new_setStyleSheet(self, style):
    if style:
        # Legacy cyan/gold -> Nexus bright teal
        style = style.replace("#00e5ff", getattr(C, "ACC", "#2FD1D9"))
        style = style.replace("#80ffff", getattr(C, "ACC2", "#1FA3A8"))
        style = style.replace("#ffd700", getattr(C, "ACC", "#2FD1D9"))
        style = style.replace("#d4af37", getattr(C, "ACC", "#2FD1D9"))
        style = style.replace("#00b4d8", getattr(C, "ACC", "#2FD1D9"))
        style = style.replace("#0099cc", getattr(C, "ICE_DIM", "#A8CBD9"))
        # Legacy rgb gold -> bright teal
        style = style.replace("255, 179, 0", "47, 209, 217")
        style = style.replace("255,179,0", "47,209,217")
        style = style.replace("255, 190, 26", "47, 209, 217")
        style = style.replace("244, 180, 0", "47, 209, 217")
        # Legacy dark backgrounds -> Nexus deep space
        style = style.replace("#020305", getattr(C, "BG", "#0B0A14"))
        style = style.replace("#07080b", getattr(C, "PANEL", "#141224"))
        style = style.replace("#0d0f14", getattr(C, "PANEL2", "#1C1A33"))
        style = style.replace("#222222", getattr(C, "BAR_BG", "#141224"))
        # Legacy white text -> Nexus primary text
        style = style.replace("#ffffff", getattr(C, "PRI", "#E8EEF5"))
        style = style.replace("#f4f6f8", getattr(C, "PRI", "#E8EEF5"))
        style = style.replace("#e2e8f0", getattr(C, "PRI_DIM", "#8A93A6"))
        style = style.replace("#8e949d", getattr(C, "TEXT_DIM", "#8A93A6"))
        style = style.replace("#c5cad2", getattr(C, "TEXT_MED", "#B8C4D0"))
        # Legacy red -> Nexus warm amber (error)
        style = style.replace("#ff3b30", getattr(C, "RED", "#D97A4B"))
        style = style.replace("#ff5555", getattr(C, "RED", "#D97A4B"))
        style = style.replace("#ff6b6b", getattr(C, "RED", "#D97A4B"))
        # Legacy green -> Nexus bright teal
        style = style.replace("#37ff5f", getattr(C, "GREEN", "#2FD1D9"))
        style = style.replace("#1dcc43", getattr(C, "GREEN_D", "#1FA3A8"))
        # Legacy borders -> Nexus slate/ice
        style = style.replace("rgba(0, 229, 255, 0.16)", getattr(C, "BORDER", "rgba(43, 35, 71, 0.5)"))
        style = style.replace("rgba(0, 229, 255, 0.35)", getattr(C, "BORDER_B", "rgba(43, 35, 71, 0.8)"))
        style = style.replace("rgba(255, 255, 255, 0.20)", getattr(C, "BORDER_A", "rgba(217, 243, 251, 0.3)"))
        style = style.replace("rgba(0, 229, 255, 0.15)", getattr(C, "ICE_GHO", "rgba(217, 243, 251, 0.15)"))
        style = style.replace("rgba(0, 229, 255, 0.05)", "rgba(47, 209, 217, 0.05)")
        style = style.replace("rgba(0, 229, 255, 0.08)", "rgba(47, 209, 217, 0.08)")
        style = style.replace("rgba(255, 255, 255, 0.03)", "rgba(28, 26, 51, 0.7)")
        style = style.replace("rgba(255, 255, 255, 0.06)", "rgba(43, 35, 71, 0.4)")
        style = style.replace("rgba(255, 255, 255, 0.05)", "rgba(43, 35, 71, 0.5)")
        style = style.replace("rgba(255, 60, 60, 0.08)", "rgba(217, 122, 75, 0.08)")
        style = style.replace("rgba(255, 60, 60, 0.2)", "rgba(217, 122, 75, 0.2)")
        style = style.replace("rgba(55,255,95,20)", "rgba(47, 209, 217, 0.2)")
        style = style.replace("rgba(0, 229, 255,28)", "rgba(47, 209, 217, 0.28)")
        style = style.replace("rgba(10, 12, 18, 250)", "rgba(11, 10, 20, 250)")
        style = style.replace("rgba(0, 0, 0, 0.45)", "rgba(11, 10, 20, 0.45)")
        style = style.replace("rgba(0, 0, 0, 0.4)", "rgba(11, 10, 20, 0.4)")
    _old_setStyleSheet(self, style)
QWidget.setStyleSheet = _new_setStyleSheet


def _logo_icon() -> QIcon:
    candidates = [APP_ICON_PNG, LOGO_FILE, LOGO_ICO]
    if sys.platform == "darwin":
        # macOS expects ~10% transparent padding around the artwork; the full-bleed
        # PNG renders noticeably larger than other Dock icons.
        candidates.insert(0, BASE_DIR / "assets" / "nexus_app_icon_mac.png")
    for candidate in candidates:
        if candidate.exists():
            icon = QIcon(str(candidate))
            if not icon.isNull():
                return icon
    return QIcon()


def _logo_pixmap(size: int) -> QPixmap:
    pix = QPixmap(str(LOGO_FILE))
    if pix.isNull():
        return QPixmap(size, size)
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _framed_logo(size: int, icon_size: int | None = None, *, bg: str = "rgba(18,18,18,240)",
                 border: str = None, radius: int | None = None, inset: int = 6) -> QFrame:
    border = border or C.BORDER_B
    radius = radius if radius is not None else max(10, size // 4)
    icon_size = icon_size or max(8, size - inset * 2)
    frame = QFrame()
    frame.setFixedSize(size, size)
    frame.setStyleSheet(
        f"background: {bg}; border: 1px solid {border}; border-radius: {radius}px;"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(inset, inset, inset, inset)
    lay.setSpacing(0)
    lbl = QLabel()
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setPixmap(_logo_pixmap(icon_size))
    lbl.setStyleSheet("background: transparent; border: none;")
    lay.addWidget(lbl)
    return frame


def _icon_pixmap(kind: str, size: int = 18) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(qcol(C.WHITE), max(2.2, size * 0.14), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "attach":
        # More readable paperclip shape
        p.drawArc(QRectF(size*0.22, size*0.14, size*0.42, size*0.58), 35*16, 290*16)
        p.drawArc(QRectF(size*0.42, size*0.24, size*0.28, size*0.44), 35*16, 290*16)
        p.drawLine(QPointF(size*0.28, size*0.56), QPointF(size*0.38, size*0.66))
    elif kind == "mic":
        # Clearer microphone silhouette
        p.drawRoundedRect(QRectF(size*0.31, size*0.14, size*0.38, size*0.48), size*0.16, size*0.16)
        p.drawLine(QPointF(size*0.50, size*0.62), QPointF(size*0.50, size*0.83))
        p.drawLine(QPointF(size*0.36, size*0.83), QPointF(size*0.64, size*0.83))
        p.drawLine(QPointF(size*0.42, size*0.70), QPointF(size*0.58, size*0.70))
    elif kind == "send":
        p.drawLine(QPointF(size*0.20, size*0.50), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.30), QPointF(size*0.70, size*0.50))
        p.drawLine(QPointF(size*0.48, size*0.70), QPointF(size*0.70, size*0.50))

    p.end()
    return px


def _attach_pulse_glow(widget: QWidget, *, color: str = C.WHITE, blur_min: float = 12.0,
                       blur_max: float = 28.0, alpha: int = 180, period_ms: int = 2400) -> None:
    # Intentionally disabled for performance. Kept as a no-op so existing calls
    # do not need to change across the UI.
    return


def _quiet_run(*args, **kwargs):
    if _OS == "Windows":
        kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(*args, **kwargs)


def _quote_cmd_arg(path: str) -> str:
    return f'"{path}"'


def _get_pythonw_path() -> Path | None:
    venv_pythonw = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.exists():
        return venv_pythonw
    sibling_pythonw = Path(sys.executable).parent / "pythonw.exe"
    if sibling_pythonw.exists():
        return sibling_pythonw
    which_pythonw = shutil.which("pythonw")
    if which_pythonw:
        return Path(which_pythonw)
    return None


def _hidden_launch_args(*extra_args: str) -> list[str]:
    pythonw = _get_pythonw_path()
    python = Path(sys.executable)
    main_py = BASE_DIR / "main.py"
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return [str(exe), *extra_args]
    if pythonw and pythonw.exists():
        return [str(pythonw), str(main_py), *extra_args]
    return [str(python), str(main_py), *extra_args]

def _startup_run_value() -> str:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'{_quote_cmd_arg(str(exe))} --startup'
    main_py = BASE_DIR / "main.py"
    pythonw = _get_pythonw_path()
    if pythonw and pythonw.exists():
        return f'{_quote_cmd_arg(str(pythonw))} {_quote_cmd_arg(str(main_py))} --startup'
    return f'{_quote_cmd_arg(sys.executable)} {_quote_cmd_arg(str(main_py))} --startup'


def _startup_registry_key():
    if platform.system() != "Windows":
        return None
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def _current_boot_stamp() -> int:
    try:
        return int(psutil.boot_time())
    except Exception:
        return int(time.time())


def _launched_from_windows_startup() -> bool:
    return any(str(arg).strip().lower() == "--startup" for arg in sys.argv[1:])


def _default_app_settings() -> dict:
    return {
        "startup_animation_enabled": True,
        "last_boot_stamp": 0,
        "boot_sequence_played": True,
        "show_workspace_on_startup": False,
        "launcher_pos": None,
        "launch_minimized": False,
        "check_updates_on_startup": True,
        "default_ai_provider": "Gemini",
        "auto_provider_switch": True,
        "attention_message_prompts": True,
        "attention_call_prompts": True,
        "developer_mode_enabled": False,
        "developer_mode_workspace": "",
        # STT Engine Settings
        "stt_engine": "moonshine",
        "stt_autocorrect": True,
        # TTS Engine Settings
        "tts_engine": "elevenlabs",
        "tts_voice_id": "pNInz6obpgDQGcFmaJgB",
        # Search Engine Settings
        "search_engine": "tavily",
        # Image Generation Settings
        "image_engine": "pollinations",
        "image_model": "community/scriptsnsenses-sys/flux-2-dev-free",
        # Advanced AI Settings
        "advanced_ai_enabled": False,
        "first_run_diagnostics_complete": False,
    }


def _read_json_dict(path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_settings_files(settings: dict) -> None:
    """Write app_settings.json and api_keys.json without ever dropping saved keys.

    api_keys.json is merged on top of what is already stored, so a settings save
    that does not carry the API keys (most of them) cannot wipe the Gemini key or
    os_system and send the user back to first-run setup.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    APP_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")
    try:
        merged = _read_json_dict(API_FILE)
        merged.update(settings)
        if not merged.get("os_system"):
            merged["os_system"] = platform.system()
        API_FILE.write_text(json.dumps(merged, indent=4), encoding="utf-8")
    except Exception:
        pass


_PROVIDER_KEY_FIELDS = ("gemini_api_key", "openrouter_api_key", "anthropic_api_key",
                        "nvidia_api_key", "groq_api_key", "custom_ai_api_key")


def _default_discord_settings() -> dict:
    return {
        "bot_token": "",
        "enabled": False,
        "channel_id": "",
    }

class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass
