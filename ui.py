from __future__ import annotations
from core.user_paths import get_user_data_dir

import asyncio
import json
import shutil
import subprocess
import traceback
import html as html_lib
import math
import os

import sys
import platform

# Hardware acceleration & WebGL flags for smooth 180fps+ rendering across Windows, macOS, and Linux
_base_chromium_flags = (
    "--enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist "
    "--enable-accelerated-2d-canvas --enable-webgl --enable-webgl2-compute-context "
    "--disable-frame-rate-limit --disable-gpu-vsync --num-raster-threads=4 --disable-gpu-driver-bug-workarounds"
)
if sys.platform == "win32":
    _base_chromium_flags += " --use-angle=d3d11"
elif sys.platform.startswith("linux"):
    _base_chromium_flags += " --no-sandbox --disable-dev-shm-usage"
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", _base_chromium_flags)
import random
import re
import sys
import threading
import time
from collections import deque
from typing import Any
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QPoint, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, QPropertyAnimation, pyqtSignal, QCoreApplication,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QDragEnterEvent, QDropEvent, QFont,
    QIcon, QImage, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider, QTextEdit,
    QGraphicsDropShadowEffect,
    QStyle, QSystemTrayIcon, QVBoxLayout, QWidget, QProgressBar,
    QStackedWidget, QInputDialog, QMessageBox,
)

try:
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception:
    pass

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except Exception:
    WEB_ENGINE_AVAILABLE = False

from discord_bot import DiscordBotService
from gesture_utils import estimate_gesture_state, GestureTracker
from smart_home import SmartHomeService
from smart_home_page_new import BrahmaHomePage, _DeviceTile
from core.local_brain import local_brain
from workspace_store import store as workspace_store
from core.identity import identity
from core.moonshine_stt import get_available_stt_engines, is_moonshine_available
from core.stt_providers import get_available_stt_engines as get_stt_engines_list
from core.tts_providers import get_available_tts_providers
from core.search_providers import get_available_search_providers
from core.image_providers import get_available_image_providers
from sound_manager import sound_mgr
from ui_cards import (
    C, qcol, MetricBar, MessageCard, TaskCard, AttachmentCard, EventCard, ArtifactCard,
)
from ui_conversation import (
    _fmt_time_stamp, _markdown_to_html, _split_markdown_code_blocks,
    CodeBlockWidget, ChatBubble, HistoryConversationItem, ConversationFeed,
)
from ui_diagnostics import FirstRunDiagnosticsDialog

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

class LauncherControlPanel(QDialog):
    def __init__(self, *, startup_workspace: bool = False, on_open=None, on_close=None,
                 on_toggle_startup=None, on_hide_icon=None, on_restart=None, on_quit=None,
                 on_open_app=None,
                 on_show_icon=None,
                 on_open_dev=None,
                 parent=None):
        super().__init__(parent)
        self._on_open = on_open
        self._on_close = on_close
        self._on_toggle_startup = on_toggle_startup
        self._on_hide_icon = on_hide_icon
        self._on_restart = on_restart
        self._on_quit = on_quit
        self._on_open_app = on_open_app
        self._on_show_icon = on_show_icon
        self._on_open_dev = on_open_dev

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(15,15,20,235);
                border: 1px solid rgba(0,191,255,60);
                border-radius: 18px;
            }
        """)
        root.addWidget(frame)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("NEXUS EVO CONTROL")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; background: transparent; letter-spacing: 1px;")
        lay.addWidget(title)

        sub = QLabel("Desktop launcher controls")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        lay.addWidget(sub)

        def mk_btn(text: str, *, checkable: bool = False, checked: bool = False) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(checkable)
            btn.setChecked(checked)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.05);
                    color: #FFFFFF;
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 12px;
                    padding: 6px 12px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(0,191,255,0.10);
                    border: 1px solid rgba(0,191,255,0.45);
                }
                QPushButton:checked {
                    background: rgba(0,191,255,0.16);
                    border: 1px solid rgba(0,191,255,0.60);
                }
            """)
            return btn

        self._open_btn = mk_btn("Open Workspace")
        self._close_btn = mk_btn("Close Workspace")
        self._startup_btn = mk_btn("Show Workspace On Startup", checkable=True, checked=bool(startup_workspace))
        self._show_icon_btn = mk_btn("Show Floating Icon")
        self._hide_icon_btn = mk_btn("Hide Floating Icon")
        self._restart_btn = mk_btn("Restart Nexus Core")
        self._quit_btn = mk_btn("Quit Nexus Core")
        self._open_app_btn = mk_btn("Open App")
        self._open_dev_btn = mk_btn("Open Developer Mode")

        self._open_btn.clicked.connect(lambda: self._invoke(self._on_open))
        self._close_btn.clicked.connect(lambda: self._invoke(self._on_close))
        self._startup_btn.clicked.connect(lambda: self._invoke(self._on_toggle_startup, self._startup_btn.isChecked()))
        self._show_icon_btn.clicked.connect(lambda: self._invoke(self._on_show_icon))
        self._hide_icon_btn.clicked.connect(self._hide_icon_confirm)
        self._restart_btn.clicked.connect(lambda: self._invoke(self._on_restart))
        self._quit_btn.clicked.connect(lambda: self._invoke(self._on_quit))
        self._open_app_btn.clicked.connect(lambda: self._invoke(self._on_open_app))
        self._open_dev_btn.clicked.connect(lambda: self._invoke(self._on_open_dev))

        for btn in (
            self._open_app_btn, self._open_btn, self._close_btn, self._startup_btn,
            self._show_icon_btn, self._hide_icon_btn, self._open_dev_btn,
            self._restart_btn, self._quit_btn
        ):
            lay.addWidget(btn)

        self.adjustSize()

    def _invoke(self, fn, *args):
        if fn:
            try:
                fn(*args)
            except Exception:
                pass
        self.close()

    def _hide_icon_confirm(self):
        box = QDialog(self)
        box.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        box.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: rgba(15,15,20,240); border: 1px solid rgba(0,191,255,60); border-radius: 16px; }")
        lay.addWidget(frame)
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(18, 16, 18, 16)
        flay.setSpacing(10)
        lbl = QLabel("Hide Nexus Core icon?")
        lbl.setStyleSheet("color: #FFFFFF; background: transparent; font: 700 11pt 'Segoe UI';")
        sub = QLabel("You can restore it from the system tray.")
        sub.setStyleSheet("color: rgba(255,255,255,0.65); background: transparent;")
        flay.addWidget(lbl)
        flay.addWidget(sub)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        hide = QPushButton("Hide")
        for btn in (cancel, hide):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; } QPushButton:hover { border: 1px solid #00BFFF; }")
        cancel.clicked.connect(box.reject)
        hide.clicked.connect(box.accept)
        row.addWidget(cancel)
        row.addWidget(hide)
        flay.addLayout(row)
        box.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        box.move(screen.center().x() - box.width() // 2, screen.center().y() - box.height() // 2)
        if box.exec():
            self._invoke(self._on_hide_icon)

    def set_startup_workspace(self, enabled: bool):
        self._startup_btn.setChecked(bool(enabled))


class SmallPanelCard(QFrame):
    def __init__(self, title: str, body: str, *, accent: str = C.WHITE, parent=None):
        super().__init__(parent)
        self.setObjectName("SmallPanelCard")
        self.setStyleSheet(
            f"""
            QFrame#SmallPanelCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 18, 24, 230),
                    stop:1 rgba(9, 11, 15, 210));
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 14px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        t = QLabel(title.upper())
        t.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; letter-spacing: 1px;")
        lay.addWidget(t)

        self._body_lbl = QLabel(body)
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._body_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
        lay.addWidget(self._body_lbl)

class BrahmaTelemetryWing(QFrame):
    """
    Nexus Right Wing: Live Operations, Research Streams, and Sources.
    Auto-dismisses in 10 seconds unless pinned or hovered.
    Adapts dynamically to the active theme color (Amber Gold by default).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BrahmaTelemetryWing")
        self.setFixedWidth(310)
        self.setMinimumHeight(320)
        self.setMaximumHeight(520)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)
        self._pinned = False
        self._paused = False
        self._total_duration_ms = 10000
        self._remaining_ms = 10000
        self._sources_list = []
        self._theme_pri = "#00e5ff"
        self._theme_rgb = (0, 229, 255)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        # Header Row: [⚡ OPERATIONS] + Tool Tag + Pin + Close
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self._hud_tag = QLabel("⚡ [OPERATIONS]")
        self._hud_tag.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        header_row.addWidget(self._hud_tag)

        self._tool_tag = QLabel("TELEMETRY")
        self._tool_tag.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        header_row.addWidget(self._tool_tag)
        header_row.addStretch()

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(26, 26)
        self._pin_btn.setToolTip("Pin card (prevent auto-dismiss)")
        self._pin_btn.clicked.connect(self.toggle_pin)
        header_row.addWidget(self._pin_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setToolTip("Dismiss")
        self._close_btn.clicked.connect(self.dismiss)
        header_row.addWidget(self._close_btn)
        lay.addLayout(header_row)

        # Operation Title
        self._title_lbl = QLabel("LIVE TASK EXECUTION")
        self._title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet("color: #ffffff;")
        self._title_lbl.setWordWrap(True)
        lay.addWidget(self._title_lbl)

        # Active Step Box
        self._step_box = QFrame()
        step_lay = QVBoxLayout(self._step_box)
        step_lay.setContentsMargins(12, 9, 12, 9)
        step_lay.setSpacing(4)

        step_hdr = QHBoxLayout()
        self._pulse_dot = QLabel("◉")
        self._pulse_dot.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        step_hdr.addWidget(self._pulse_dot)
        self._step_status_lbl = QLabel("ACTIVE STEP")
        self._step_status_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        step_hdr.addWidget(self._step_status_lbl)
        step_hdr.addStretch()
        step_lay.addLayout(step_hdr)

        self._step_text_lbl = QLabel("Initializing operation...")
        self._step_text_lbl.setFont(QFont("Segoe UI", 9))
        self._step_text_lbl.setStyleSheet("color: #E2E8F0;")
        self._step_text_lbl.setWordWrap(True)
        step_lay.addWidget(self._step_text_lbl)
        lay.addWidget(self._step_box)

        # Sources / References List
        self._sources_hdr = QLabel("LIVE SOURCES & CHANNELS")
        self._sources_hdr.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        lay.addWidget(self._sources_hdr)

        self._sources_container = QWidget()
        self._sources_container.setStyleSheet("background: transparent;")
        self._sources_lay = QVBoxLayout(self._sources_container)
        self._sources_lay.setContentsMargins(0, 0, 0, 0)
        self._sources_lay.setSpacing(5)
        lay.addWidget(self._sources_container)

        lay.addStretch()

        # Bottom 10-Second Fuse
        fuse_row = QHBoxLayout()
        self._fuse_lbl = QLabel("10s")
        self._fuse_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        fuse_row.addWidget(self._fuse_lbl)
        self._fuse_bar = QProgressBar()
        self._fuse_bar.setRange(0, 100)
        self._fuse_bar.setValue(100)
        self._fuse_bar.setTextVisible(False)
        self._fuse_bar.setFixedHeight(4)
        fuse_row.addWidget(self._fuse_bar, stretch=1)
        lay.addLayout(fuse_row)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_tick)

        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._anim = QPropertyAnimation(self._opacity_fx, b"opacity", self)

        self.apply_theme()
        if hasattr(C, "register_listener"):
            C.register_listener(self.apply_theme)

        self.hide()

    def apply_theme(self):
        pri = getattr(C, "PRI", "#00e5ff") or "#00e5ff"
        try:
            r = int(pri[1:3], 16)
            g = int(pri[3:5], 16)
            b = int(pri[5:7], 16)
        except Exception:
            pri = "#00e5ff"
            r, g, b = 0, 229, 255

        self._theme_pri = pri
        self._theme_rgb = (r, g, b)

        self.setStyleSheet(f"""
            QFrame#BrahmaTelemetryWing {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(10, 15, 24, 238),
                    stop:0.6 rgba(6, 10, 18, 222),
                    stop:1 rgba(3, 5, 12, 212));
                border: 1px solid rgba({r}, {g}, {b}, 0.45);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba({r}, {g}, {b}, 0.10);
                border: 1px solid rgba({r}, {g}, {b}, 0.28);
                border-radius: 6px;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background: rgba({r}, {g}, {b}, 0.26);
                border: 1px solid {pri};
                color: {pri};
            }}
        """)

        self._hud_tag.setStyleSheet(f"color: {pri}; letter-spacing: 1px; font-weight: bold;")
        self._tool_tag.setStyleSheet(f"""
            background: rgba({r}, {g}, {b}, 0.14);
            color: {pri};
            border: 1px solid rgba({r}, {g}, {b}, 0.38);
            border-radius: 9px;
            padding: 1px 7px;
            font-weight: bold;
        """)
        self._step_box.setStyleSheet(f"""
            background: rgba({r}, {g}, {b}, 0.07);
            border: 1px solid rgba({r}, {g}, {b}, 0.22);
            border-radius: 10px;
        """)
        self._pulse_dot.setStyleSheet(f"color: {pri}; font-weight: bold;")
        self._step_status_lbl.setStyleSheet(f"color: rgba({r}, {g}, {b}, 0.85); font-weight: bold;")
        self._sources_hdr.setStyleSheet("color: rgba(255, 255, 255, 0.60); letter-spacing: 0.5px; font-weight: bold;")
        self._fuse_lbl.setStyleSheet(f"color: rgba({r}, {g}, {b}, 0.75); font-weight: bold;")
        self._fuse_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {pri};
                border-radius: 2px;
            }}
        """)
        if self._pinned:
            self._pin_btn.setStyleSheet(f"background: rgba({r}, {g}, {b}, 0.35); border: 1px solid {pri}; color: {pri};")
        else:
            self._pin_btn.setStyleSheet("")

    def enterEvent(self, event):
        super().enterEvent(event)
        self._paused = True

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._paused = False

    def toggle_pin(self):
        self._pinned = not self._pinned
        r, g, b = self._theme_rgb
        pri = self._theme_pri
        self._pin_btn.setStyleSheet(f"background: rgba({r}, {g}, {b}, 0.35); border: 1px solid {pri}; color: {pri};" if self._pinned else "")
        if self._pinned:
            self._fuse_lbl.setText("PINNED")
            self._fuse_bar.setValue(100)
        else:
            self._fuse_lbl.setText("10s")

    def show_operation(self, title: str, step: str, sources: list = None, tool: str = None):
        self.apply_theme()
        r, g, b = self._theme_rgb
        pri = self._theme_pri
        self._title_lbl.setText(title or "LIVE TASK EXECUTION")
        self._step_text_lbl.setText(step or "Running operation...")
        if tool:
            self._tool_tag.setText(str(tool).upper()[:14])

        # Clear and repopulate sources
        while self._sources_lay.count():
            item = self._sources_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sources = sources or []
        if not sources:
            default_item = QLabel("• System core processing data")
            default_item.setFont(QFont("Segoe UI", 8))
            default_item.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
            self._sources_lay.addWidget(default_item)
        else:
            for s in sources[:4]:
                s_str = str(s).strip()
                if s_str.startswith("http"):
                    import urllib.parse
                    domain = urllib.parse.urlparse(s_str).netloc or s_str[:25]
                    text = f"🌐 {domain}"
                else:
                    text = f"📄 {s_str[:32]}"
                pill = QLabel(text)
                pill.setFont(QFont("Segoe UI", 8))
                pill.setStyleSheet(f"""
                    background: rgba(255, 255, 255, 0.05);
                    color: #E2E8F0;
                    border: 1px solid rgba({r}, {g}, {b}, 0.25);
                    border-radius: 6px;
                    padding: 3px 7px;
                """)
                self._sources_lay.addWidget(pill)

        self._remaining_ms = self._total_duration_ms
        self._paused = False
        if not self._pinned:
            self._timer.start()

        # Fade-in animation
        was_visible = self.isVisible()
        self.show()
        if not was_visible:
            sound_mgr.play_deploy_whoosh()
        else:
            sound_mgr.play_telemetry_chirp()
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except Exception:
            pass
        self._anim.setDuration(250)
        self._anim.setStartValue(self._opacity_fx.opacity())
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _on_tick(self):
        if self._pinned or self._paused:
            return
        self._remaining_ms -= 100
        pct = max(0, int((self._remaining_ms / self._total_duration_ms) * 100))
        self._fuse_bar.setValue(pct)
        sec_left = max(0, int(math.ceil(self._remaining_ms / 1000.0)))
        self._fuse_lbl.setText(f"{sec_left}s")
        if self._remaining_ms <= 0:
            self._timer.stop()
            self.dismiss()

    def set_body(self, text: str):
        if hasattr(self, "_step_lbl") and text:
            self._step_lbl.setText(str(text))
            sound_mgr.play_telemetry_chirp()

    def dismiss(self):
        self._timer.stop()
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except Exception:
            pass
        self._anim.setDuration(250)
        self._anim.setStartValue(self._opacity_fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()


class BrahmaResultWing(QFrame):
    """
    Nexus Left Wing: Final Results, Generated Deliverables (PDF/Word/Media/Code),
    Executive Summary Bullets, and Quick Action Buttons.
    Auto-dismisses in 10 seconds unless pinned or hovered.
    Adapts dynamically to the active theme color (Amber Gold by default).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BrahmaResultWing")
        self.setFixedWidth(310)
        self.setMinimumHeight(320)
        self.setMaximumHeight(540)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)
        self._pinned = False
        self._paused = False
        self._total_duration_ms = 10000
        self._remaining_ms = 10000
        self._active_file_path = None
        self._theme_pri = "#00e5ff"
        self._theme_rgb = (0, 229, 255)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        # Header: [✨ DELIVERABLE] + Status Badge + Pin + Close
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self._hud_tag = QLabel("✨ [DELIVERABLE]")
        self._hud_tag.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        header_row.addWidget(self._hud_tag)

        self._status_badge = QLabel("COMPLETED")
        self._status_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        header_row.addWidget(self._status_badge)
        header_row.addStretch()

        self._pin_btn = QPushButton("📌")
        self._pin_btn.setFixedSize(26, 26)
        self._pin_btn.setToolTip("Pin card (prevent auto-dismiss)")
        self._pin_btn.clicked.connect(self.toggle_pin)
        header_row.addWidget(self._pin_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setToolTip("Dismiss")
        self._close_btn.clicked.connect(self.dismiss)
        header_row.addWidget(self._close_btn)
        lay.addLayout(header_row)

        # Title Label
        self._title_lbl = QLabel("MISSION RESULT")
        self._title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet("color: #ffffff;")
        self._title_lbl.setWordWrap(True)
        lay.addWidget(self._title_lbl)

        # File Card Section (Visible when deliverable is a file)
        self._file_card = QFrame()
        file_lay = QHBoxLayout(self._file_card)
        file_lay.setContentsMargins(12, 8, 12, 8)
        file_lay.setSpacing(10)

        self._file_icon_lbl = QLabel("📄")
        self._file_icon_lbl.setFont(QFont("Segoe UI", 16))
        file_lay.addWidget(self._file_icon_lbl)

        file_info_lay = QVBoxLayout()
        file_info_lay.setSpacing(2)
        self._file_name_lbl = QLabel("document.pdf")
        self._file_name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._file_name_lbl.setStyleSheet("color: #ffffff;")
        self._file_name_lbl.setWordWrap(True)
        file_info_lay.addWidget(self._file_name_lbl)

        self._file_size_lbl = QLabel("Ready to open")
        self._file_size_lbl.setFont(QFont("Segoe UI", 8))
        self._file_size_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        file_info_lay.addWidget(self._file_size_lbl)
        file_lay.addLayout(file_info_lay, stretch=1)

        self._btn_open_file = QPushButton("Open")
        self._btn_open_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_file.clicked.connect(self._on_open_file_clicked)
        file_lay.addWidget(self._btn_open_file)

        lay.addWidget(self._file_card)
        self._file_card.hide()

        # Summary / Bullets Scroll Area
        self._bullets_scroll = QScrollArea()
        self._bullets_scroll.setWidgetResizable(True)
        self._bullets_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._bullets_scroll.setStyleSheet("background: transparent; border: none;")
        self._bullets_container = QWidget()
        self._bullets_container.setStyleSheet("background: transparent;")
        self._bullets_lay = QVBoxLayout(self._bullets_container)
        self._bullets_lay.setContentsMargins(0, 0, 4, 0)
        self._bullets_lay.setSpacing(5)
        self._bullets_scroll.setWidget(self._bullets_container)
        lay.addWidget(self._bullets_scroll, stretch=1)

        # Actions Row: [Reveal in Folder] [Copy Result]
        self._actions_row = QHBoxLayout()
        self._actions_row.setSpacing(8)

        self._btn_explorer = QPushButton("📁 Reveal in Folder")
        self._btn_explorer.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_explorer.clicked.connect(self._on_reveal_clicked)
        self._actions_row.addWidget(self._btn_explorer)

        self._btn_copy = QPushButton("📋 Copy Result")
        self._btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy.clicked.connect(self._on_copy_clicked)
        self._actions_row.addWidget(self._btn_copy)
        lay.addLayout(self._actions_row)

        # Bottom 10-Second Fuse
        fuse_row = QHBoxLayout()
        self._fuse_lbl = QLabel("10s")
        self._fuse_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        fuse_row.addWidget(self._fuse_lbl)
        self._fuse_bar = QProgressBar()
        self._fuse_bar.setRange(0, 100)
        self._fuse_bar.setValue(100)
        self._fuse_bar.setTextVisible(False)
        self._fuse_bar.setFixedHeight(4)
        fuse_row.addWidget(self._fuse_bar, stretch=1)
        lay.addLayout(fuse_row)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_tick)

        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._anim = QPropertyAnimation(self._opacity_fx, b"opacity", self)
        self._raw_result_text = ""

        self.apply_theme()
        if hasattr(C, "register_listener"):
            C.register_listener(self.apply_theme)

        self.hide()

    def apply_theme(self):
        pri = getattr(C, "PRI", "#00e5ff") or "#00e5ff"
        try:
            r = int(pri[1:3], 16)
            g = int(pri[3:5], 16)
            b = int(pri[5:7], 16)
        except Exception:
            pri = "#00e5ff"
            r, g, b = 0, 229, 255

        self._theme_pri = pri
        self._theme_rgb = (r, g, b)

        self.setStyleSheet(f"""
            QFrame#BrahmaResultWing {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(14, 18, 26, 240),
                    stop:0.6 rgba(9, 13, 20, 225),
                    stop:1 rgba(4, 7, 12, 215));
                border: 1px solid rgba({r}, {g}, {b}, 0.45);
                border-radius: 18px;
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: rgba({r}, {g}, {b}, 0.10);
                border: 1px solid rgba({r}, {g}, {b}, 0.28);
                border-radius: 6px;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background: rgba({r}, {g}, {b}, 0.26);
                border: 1px solid {pri};
                color: {pri};
            }}
        """)

        self._hud_tag.setStyleSheet(f"color: {pri}; letter-spacing: 1px; font-weight: bold;")
        self._status_badge.setStyleSheet(f"""
            background: rgba({r}, {g}, {b}, 0.15);
            color: {pri};
            border: 1px solid rgba({r}, {g}, {b}, 0.40);
            border-radius: 9px;
            padding: 1px 7px;
            font-weight: bold;
        """)
        self._file_card.setStyleSheet(f"""
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba({r}, {g}, {b}, 0.25);
            border-radius: 10px;
        """)
        self._fuse_lbl.setStyleSheet(f"color: rgba({r}, {g}, {b}, 0.75); font-weight: bold;")
        self._fuse_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {pri};
                border-radius: 2px;
            }}
        """)
        if self._pinned:
            self._pin_btn.setStyleSheet(f"background: rgba({r}, {g}, {b}, 0.35); border: 1px solid {pri}; color: {pri};")
        else:
            self._pin_btn.setStyleSheet("")

    def enterEvent(self, event):
        super().enterEvent(event)
        self._paused = True

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._paused = False

    def toggle_pin(self):
        self._pinned = not self._pinned
        r, g, b = self._theme_rgb
        pri = self._theme_pri
        self._pin_btn.setStyleSheet(f"background: rgba({r}, {g}, {b}, 0.35); border: 1px solid {pri}; color: {pri};" if self._pinned else "")
        if self._pinned:
            self._fuse_lbl.setText("PINNED")
            self._fuse_bar.setValue(100)
        else:
            self._fuse_lbl.setText("10s")

    def show_deliverable(self, title: str, summary: str = "", bullets: list = None,
                         file_path: str = None, kind: str = "result", actions: list = None, data: dict = None):
        self.apply_theme()
        self._title_lbl.setText(title or "MISSION RESULT")
        self._active_file_path = file_path
        self._raw_result_text = summary or "\n".join(bullets or [])

        # File card handling
        if file_path and Path(file_path).exists():
            p = Path(file_path)
            self._file_name_lbl.setText(p.name)
            suf = p.suffix.lower()
            icon_map = {
                ".pdf": ("📄", "PDF Document"),
                ".docx": ("📝", "Word Document"),
                ".xlsx": ("📊", "Spreadsheet"),
                ".pptx": ("📈", "Slide Presentation"),
                ".mp4": ("🎬", "Video File"),
                ".py": ("💻", "Python Script"),
                ".png": ("🖼️", "Image"),
                ".jpg": ("🖼️", "Image"),
            }
            icon, ftype = icon_map.get(suf, ("📁", "File"))
            self._file_icon_lbl.setText(icon)
            try:
                sz_mb = p.stat().st_size / (1024 * 1024)
                if sz_mb >= 0.1:
                    self._file_size_lbl.setText(f"{ftype} • {sz_mb:.1f} MB")
                else:
                    sz_kb = p.stat().st_size / 1024
                    self._file_size_lbl.setText(f"{ftype} • {sz_kb:.0f} KB")
            except Exception:
                self._file_size_lbl.setText(ftype)
            self._file_card.show()
            self._btn_explorer.show()
        else:
            self._file_card.hide()
            self._btn_explorer.hide()

        # Clear and repopulate bullets
        while self._bullets_lay.count():
            item = self._bullets_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bullets = bullets or []
        if not bullets and summary:
            for sent in summary.split(". "):
                clean_s = sent.strip()
                if clean_s and len(clean_s) > 10:
                    bullets.append(clean_s + ("." if not clean_s.endswith(".") else ""))

        for b in bullets[:6]:
            b_lbl = QLabel(f"• {b}")
            b_lbl.setFont(QFont("Segoe UI", 9))
            b_lbl.setStyleSheet("color: #E2E8F0;")
            b_lbl.setWordWrap(True)
            self._bullets_lay.addWidget(b_lbl)

        self._remaining_ms = self._total_duration_ms
        self._paused = False
        if not self._pinned:
            self._timer.start()

        # Fade-in animation
        self.show()
        if kind == "deliverable" or file_path:
            sound_mgr.play_mission_complete()
        else:
            sound_mgr.play_deploy_whoosh()
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except Exception:
            pass
        self._anim.setDuration(250)
        self._anim.setStartValue(self._opacity_fx.opacity())
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _on_tick(self):
        if self._pinned or self._paused:
            return
        self._remaining_ms -= 100
        pct = max(0, int((self._remaining_ms / self._total_duration_ms) * 100))
        self._fuse_bar.setValue(pct)
        sec_left = max(0, int(math.ceil(self._remaining_ms / 1000.0)))
        self._fuse_lbl.setText(f"{sec_left}s")
        if self._remaining_ms <= 0:
            self._timer.stop()
            self.dismiss()

    def dismiss(self):
        self._timer.stop()
        self._anim.stop()
        try:
            self._anim.finished.disconnect()
        except Exception:
            pass
        self._anim.setDuration(250)
        self._anim.setStartValue(self._opacity_fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _on_open_file_clicked(self):
        if self._active_file_path:
            p = Path(self._active_file_path).resolve()
            if p.exists():
                try:
                    import subprocess
                    if sys.platform == "win32":
                        os.startfile(str(p))
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(p)])
                    else:
                        subprocess.Popen(["xdg-open", str(p)])
                except Exception as e:
                    print(f"[BrahmaResultWing] Open file error: {e}")

    def _on_reveal_clicked(self):
        if self._active_file_path:
            p = Path(self._active_file_path).resolve()
            try:
                import subprocess
                if sys.platform == "win32":
                    if p.exists():
                        subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
                    elif p.parent.exists():
                        subprocess.Popen(["explorer.exe", str(p.parent)])
                elif sys.platform == "darwin":
                    target = p if p.exists() else p.parent
                    subprocess.Popen(["open", "-R", str(target)])
                else:
                    subprocess.Popen(["xdg-open", str(p.parent)])
            except Exception as e:
                print(f"[BrahmaResultWing] Reveal error: {e}")

    def set_body(self, text: str):
        if hasattr(self, "_summary_lbl") and text:
            self._summary_lbl.setText(str(text))

    def _on_copy_clicked(self):
        if self._raw_result_text:
            try:
                import pyperclip
                pyperclip.copy(self._raw_result_text)
                self._btn_copy.setText("✓ Copied!")
                QTimer.singleShot(1500, lambda: self._btn_copy.setText("📋 Copy Result"))
            except Exception:
                pass


class StatCard(QFrame):
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            f"""
            QFrame#StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(18, 20, 26, 240),
                    stop:1 rgba(8, 10, 14, 220));
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 16px;
            }}
            """
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        lbl = QLabel(label.upper())
        lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._detail_lbl = QLabel("")
        self._detail_lbl.setFont(QFont("Segoe UI", 7))
        self._detail_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: rgba(255,255,255,0.05);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {C.WHITE};
                border-radius: 2px;
            }}
            """
        )
        lay.addWidget(lbl)
        lay.addWidget(val)
        lay.addWidget(self._detail_lbl)
        lay.addWidget(self._bar)
        self._value_lbl = val

    def set_value(self, value: str, level: int | None = None, detail: str | None = None):
        self._value_lbl.setText(value)
        if detail is not None:
            self._detail_lbl.setText(detail)
        if level is not None:
            self._bar.setValue(max(0, min(100, int(level))))


class LogWidget(QScrollArea):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                border: none;
                margin: 6px 0 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 24px;
            }}
            """
        )
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)

        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        role, name, body = self._parse(text)
        stamp = time.strftime("%H:%M")

        card = MessageCard(role, name, body, stamp)
        self._layout.insertWidget(self._layout.count() - 1, card)
        QTimer.singleShot(0, self._scroll_bottom)

    def _scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _parse(self, text: str) -> tuple[str, str, str]:
        raw = (text or "").strip()
        tl = raw.lower()
        if tl.startswith("you:"):
            return "user", "You", raw[4:].strip()
        if tl.startswith("nexus core:"):
            return "assistant", "Nexus Core", raw[len("Nexus Core:"):].strip()
        if tl.startswith("nexus core:"):
            return "assistant", "Nexus Core", raw[len("Nexus Core:"):].strip()
        if tl.startswith("file:"):
            return "file", "File", raw[5:].strip()
        if tl.startswith("err:"):
            return "error", "System", raw[4:].strip()
        if tl.startswith("sys:"):
            return "system", "System", raw[4:].strip()
        return "system", "System", raw

_FILE_ICONS = {
    "image":   ("ðŸ-¼", "#00d4ff"), "video":   ("ðŸŽ¬", "#ff6b00"),
    "audio":   ("ðŸŽµ", "#cc44ff"), "pdf":     ("ðŸ“„", "#ff4444"),
    "word":    ("ðŸ“", "#4488ff"), "excel":   ("ðŸ“Š", "#44bb44"),
    "code":    ("ðŸ’»", "#ffcc00"), "archive": ("ðŸ“¦", "#ff8844"),
    "pptx":    ("ðŸ“Š", "#ff6622"), "text":    ("ðŸ“ƒ", "#aaaaaa"),
    "data":    ("ðŸ”§", "#88ddff"), "unknown": ("ðŸ“Ž", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._screen_capture_result = b""
        import threading
        self._screen_capture_event = threading.Event()
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for Nexus Core", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✖")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class APIKeySettingsDialog(QDialog):
    """Dialog to edit all API provider keys at once."""

    def __init__(self, defaults: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Keys — API Provider Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0c14, stop:1 #080a10);
                color: #e8eef5;
            }
            QLabel { color: #e8eef5; background: transparent; border: none; }
            QLineEdit {
                background: rgba(0, 229, 255, 0.08);
                color: #e8eef5;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 8px;
                padding: 8px 12px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 229, 255, 0.6);
                background: rgba(0, 229, 255, 0.12);
            }
            QPushButton {
                background: rgba(0, 229, 255, 0.12);
                color: #e8eef5;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.22);
                border: 1px solid #00e5ff;
            }
            QPushButton:pressed {
                background: rgba(0, 229, 255, 0.05);
            }
            QGroupBox {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 12px;
                margin-top: 10px;
                font-weight: bold;
                color: #00e5ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 4px;
                color: #00e5ff;
            }
        """)
        self._fields: dict[str, QLineEdit] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 25, 30, 25)
        lay.setSpacing(18)

        title = QLabel("API Provider Keys")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        lay.addWidget(title)

        sub = QLabel("Enter your API keys for each provider. Leave blank to disable.")
        sub.setStyleSheet("color: #8a93a6; background: transparent; border: none; font-size: 11px;")
        lay.addWidget(sub)
        lay.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(0, 0, 0, 0)
        scroll_lay.setSpacing(12)

        defaults = defaults or {}

        fields_spec = [
            ("gemini_api_key", "Google Gemini", "Gemini API Key"),
            ("openrouter_api_key", "OpenRouter", "OpenRouter API Key"),
            ("nvidia_api_key", "NVIDIA NIM", "NVIDIA API Key"),
            ("groq_api_key", "Groq", "Groq API Key"),
            ("custom_ai_api_key", "Custom OpenAI-Compatible", "Custom API Key"),
            ("tavily_api_key", "Tavily Search", "Tavily API Key"),
            ("firecrawl_api_key", "Firecrawl", "Firecrawl API Key"),
            ("serpapi_api_key", "SerpAPI", "SerpAPI API Key"),
            ("anthropic_api_key", "Anthropic Claude", "Anthropic API Key"),
            ("pollinations_api_key", "Pollinations (Images)", "Pollinations API Key (sk_...)"),
            ("elevenlabs_api_key", "ElevenLabs (Voice)", "ElevenLabs API Key"),
            ("fish_audio_api_key", "Fish Audio (Voice)", "Fish Audio API Key"),
            ("cloudflare_api_key", "Cloudflare (Images)", "Cloudflare API Token"),
            ("cloudflare_account_id", "Cloudflare Account ID", "Cloudflare Account ID"),
        ]

        for key_id, label, placeholder in fields_spec:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)

            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #e8eef5; background: transparent; border: none;")
            lbl.setMinimumWidth(150)
            row.addWidget(lbl)

            edit = QLineEdit()
            edit.setText((defaults.get(key_id) or "").strip())
            edit.setPlaceholderText(placeholder)
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            row.addWidget(edit, 1)

            scroll_lay.addLayout(row)
            self._fields[key_id] = edit

        scroll.setWidget(scroll_content)
        lay.addWidget(scroll, 1)

        btn_lay = QHBoxLayout()
        btn_lay.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #8a93a6;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton("Save API Keys")
        btn_cancel.setFixedWidth(100)
        btn_save.setFixedWidth(130)
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00e5ff, stop:1 #00a3a8);
                color: #0a0c14;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00a3a8, stop:1 #00e5ff); }
        """)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)
        lay.addLayout(btn_lay)

    def get_settings(self) -> dict:
        result = {}
        for key_id, edit in self._fields.items():
            result[key_id] = edit.text().strip()
        return result


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)

    def __init__(self, parent=None, defaults: dict | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._defaults = defaults or {}
        self._detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = self._defaults.get("os_system", self._detected)

        self._stack = QStackedWidget(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._stack)

        self._build_stage1()
        self._build_stage_identity()
        self._build_stage_owner()
        self._build_stage_behavior()
        self._build_stage_shared()
        self._build_stage2()
        self._build_stage3()
        self._build_stage4()

        self._stack.setCurrentIndex(0)
        QTimer.singleShot(1000, self._start_stage1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Heavy dark overlay to completely hide dashboard UI and make a full faded background
        painter.fillRect(self.rect(), QColor(3, 5, 8, 245))

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0

        # Add a subtle gold vignette ring over the full faded background
        ring_grad = QRadialGradient(cx, cy, 320.0)
        ring_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        ring_grad.setColorAt(0.7, QColor(0, 0, 0, 0))
        ring_grad.setColorAt(0.85, QColor(0, 229, 255, 12))
        ring_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(ring_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 320.0, 320.0)

    def _call_js(self, func_call):
        try:
            p = self.parentWidget()
            while p is not None:
                if hasattr(p, '_background'):
                    p._background.page().runJavaScript(func_call)
                    return
                p = p.parentWidget()
        except Exception:
            pass

    # ── STAGE 1: System Check ──────────────────────────────────────
    def _build_stage1(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        # Push text to the bottom half (below reactor)
        lay.addStretch(3)

        self._s1_container = QFrame()
        self._s1_container.setStyleSheet("""
            QFrame {
                background: rgba(5, 8, 12, 180);
                border: 1px solid rgba(0, 229, 255, 0.08);
                border-radius: 16px;
            }
        """)
        self._s1_container.setFixedWidth(420)
        clay = QVBoxLayout(self._s1_container)
        clay.setContentsMargins(30, 24, 30, 24)
        clay.setSpacing(0)

        self._s1_lbl = QLabel("")
        self._s1_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._s1_lbl.setFont(QFont("Consolas", 12))
        self._s1_lbl.setStyleSheet("color: rgba(0, 229, 255, 0.9); background: transparent; border: none;")
        self._s1_lbl.setWordWrap(True)
        clay.addWidget(self._s1_lbl)

        lay.addWidget(self._s1_container, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        self._stack.addWidget(page)

    def _start_stage1(self):
        self._s1_lines = [
            ("Scanning local configuration...", "#00e5ff", False),
            ("✓  " + self._detected.capitalize() + " detected", "#37ff5f", False),
            ("✓  GPU acceleration enabled", "#37ff5f", False),
            ("✓  Network online", "#37ff5f", False),
            ("Looking for AI provider...", "#00e5ff", False),
            ("✕  No provider configured", "#ff3b30", True),
            ("", "", False),
            ("One final step is required\nbefore I can think.", "#ffffff", True),
        ]
        self._s1_idx = 0
        self._s1_text_parts = []
        self._s1_timer = QTimer(self)
        self._s1_timer.timeout.connect(self._s1_tick)
        self._s1_timer.start(900)
        self._s1_tick()

    def _s1_tick(self):
        if self._s1_idx < len(self._s1_lines):
            line_text, color, is_special = self._s1_lines[self._s1_idx]

            if line_text == "":
                self._s1_idx += 1
                return

            if is_special and "✕" in line_text:
                self._call_js("if(window.losePower) window.losePower();")
            elif is_special and "final step" in line_text:
                self._call_js("if(window.triggerPulse) window.triggerPulse();")

            size = "14px" if is_special and "final" in line_text else "12px"
            weight = "bold" if is_special else "normal"
            spacing = "margin-top: 16px;" if is_special and "final" in line_text else "margin-top: 4px;"

            self._s1_text_parts.append(
                f'<div style="color:{color}; font-size:{size}; font-weight:{weight}; font-family:Consolas; {spacing}">{line_text}</div>'
            )
            self._s1_lbl.setText("".join(self._s1_text_parts))

            self._s1_idx += 1
        else:
            self._s1_timer.stop()
            QTimer.singleShot(2500, self._finish_stage1)

    # ── STAGE 2: Provider Selection ────────────────────────────────

    # ── STAGE 1.1: Assistant Identity ────────────────────────────────
    def _build_stage_identity(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(2)

        title = QLabel("DEFINE YOUR ASSISTANT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent; letter-spacing: 2px;")
        lay.addWidget(title)
        
        sub = QLabel("Every assistant needs an identity.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        lay.addWidget(sub)
        lay.addSpacing(20)

        form_lay = QGridLayout()
        form_lay.setSpacing(16)
        
        lbl_ast = QLabel("Assistant Name")
        lbl_ast.setStyleSheet("color: #ffaa30;")
        self._inp_ast = QLineEdit(identity.get_assistant_name())
        self._inp_ast.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        form_lay.addWidget(lbl_ast, 0, 0)
        form_lay.addWidget(self._inp_ast, 0, 1)

        lbl_app = QLabel("Application Name")
        lbl_app.setStyleSheet("color: #ffaa30;")
        self._inp_app = QLineEdit(identity.get_application_name())
        self._inp_app.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        form_lay.addWidget(lbl_app, 1, 0)
        form_lay.addWidget(self._inp_app, 1, 1)

        container = QWidget()
        container.setFixedWidth(400)
        container.setLayout(form_lay)
        lay.addWidget(container, 0, Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("CONTINUE →")
        btn.setFixedSize(160, 40)
        btn.setStyleSheet("background: rgba(255, 170, 48, 0.2); color: #ffaa30; border: 1px solid #ffaa30; border-radius: 20px;")
        btn.clicked.connect(self._save_identity_and_next)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        lay.addStretch(2)
        self._stack.addWidget(page)

    def _save_identity_and_next(self):
        identity.set_assistant_name(self._inp_ast.text().strip() or "Nexus")
        identity.set_application_name(self._inp_app.text().strip() or "Nexus Core")
        self._stack.setCurrentIndex(2)

    # ── STAGE 1.2: Owner Profile ────────────────────────────────
    def _build_stage_owner(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(2)

        title = QLabel("WHO AM I ASSISTING?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent; letter-spacing: 2px;")
        lay.addWidget(title)
        
        sub = QLabel("Tell me a little about yourself so I can work better with you.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        lay.addWidget(sub)
        lay.addSpacing(20)

        form_lay = QGridLayout()
        form_lay.setSpacing(16)
        
        lbl_own = QLabel("Your Name")
        lbl_own.setStyleSheet("color: #ffaa30;")
        self._inp_own = QLineEdit(identity.get_owner_name())
        self._inp_own.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        form_lay.addWidget(lbl_own, 0, 0)
        form_lay.addWidget(self._inp_own, 0, 1)

        lbl_role = QLabel("Your Role")
        lbl_role.setStyleSheet("color: #ffaa30;")
        self._inp_role = QLineEdit(identity.get_owner_role())
        self._inp_role.setPlaceholderText("e.g. Student, Developer")
        self._inp_role.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        form_lay.addWidget(lbl_role, 1, 0)
        form_lay.addWidget(self._inp_role, 1, 1)

        container = QWidget()
        container.setFixedWidth(400)
        container.setLayout(form_lay)
        lay.addWidget(container, 0, Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("CONTINUE →")
        btn.setFixedSize(160, 40)
        btn.setStyleSheet("background: rgba(255, 170, 48, 0.2); color: #ffaa30; border: 1px solid #ffaa30; border-radius: 20px;")
        btn.clicked.connect(self._save_owner_and_next)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        lay.addStretch(2)
        self._stack.addWidget(page)

    def _save_owner_and_next(self):
        identity.set_owner_name(self._inp_own.text().strip())
        identity.set_owner_role(self._inp_role.text().strip())
        self._stack.setCurrentIndex(3)

    # ── STAGE 1.3: Behavior ────────────────────────────────
    def _build_stage_behavior(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(2)

        title = QLabel("HOW SHOULD I ASSIST YOU?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent; letter-spacing: 2px;")
        lay.addWidget(title)
        lay.addSpacing(20)

        self._combo_mode = QComboBox()
        self._combo_mode.addItems(["professional", "casual", "technical", "minimal", "proactive"])
        self._combo_mode.setCurrentText(identity.get_behavior_mode())
        self._combo_mode.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        self._combo_mode.setFixedWidth(300)
        lay.addWidget(self._combo_mode, 0, Qt.AlignmentFlag.AlignCenter)
        
        sub = QLabel("Custom Instructions (Optional)")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #ffaa30; margin-top: 10px;")
        lay.addWidget(sub)
        
        self._inp_custom = QTextEdit(identity.get_custom_instructions())
        self._inp_custom.setFixedSize(400, 80)
        self._inp_custom.setStyleSheet("background: rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 4px;")
        lay.addWidget(self._inp_custom, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addSpacing(20)
        btn = QPushButton("CONTINUE →")
        btn.setFixedSize(160, 40)
        btn.setStyleSheet("background: rgba(255, 170, 48, 0.2); color: #ffaa30; border: 1px solid #ffaa30; border-radius: 20px;")
        btn.clicked.connect(self._save_behavior_and_next)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        lay.addStretch(2)
        self._stack.addWidget(page)

    def _save_behavior_and_next(self):
        identity.set_behavior_mode(self._combo_mode.currentText())
        identity.set_custom_instructions(self._inp_custom.toPlainText().strip())
        self._stack.setCurrentIndex(4)

    # ── STAGE 1.4: Shared Computer ────────────────────────────────
    def _build_stage_shared(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(2)

        title = QLabel("WHO USES THIS COMPUTER?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent; letter-spacing: 2px;")
        lay.addWidget(title)
        lay.addSpacing(20)
        
        btn_personal = QPushButton("THIS IS MY PERSONAL COMPUTER")
        btn_personal.setFixedSize(300, 50)
        btn_personal.setStyleSheet("background: rgba(255, 170, 48, 0.1); color: #ffaa30; border: 1px solid #ffaa30; border-radius: 8px;")
        btn_personal.clicked.connect(lambda: self._save_shared_and_next(False))
        lay.addWidget(btn_personal, 0, Qt.AlignmentFlag.AlignCenter)
        
        lay.addSpacing(10)
        
        btn_shared = QPushButton("THIS IS A SHARED COMPUTER")
        btn_shared.setFixedSize(300, 50)
        btn_shared.setStyleSheet("background: rgba(255,255,255, 0.05); color: #fff; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;")
        btn_shared.clicked.connect(lambda: self._save_shared_and_next(True))
        lay.addWidget(btn_shared, 0, Qt.AlignmentFlag.AlignCenter)
        
        lay.addStretch(2)
        self._stack.addWidget(page)
        
    def _save_shared_and_next(self, shared: bool):
        identity.set_shared_computer(shared)
        self._stack.setCurrentIndex(5)


    def _finish_stage1(self):
        if not identity.is_setup_complete():
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(5)

    def _build_stage2(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        lay.addStretch(3)

        title = QLabel("SELECT PRIMARY INTELLIGENCE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent; border: none; letter-spacing: 4px;")
        lay.addWidget(title)
        lay.addSpacing(24)

        cards_lay = QHBoxLayout()
        cards_lay.setSpacing(20)
        cards_lay.addStretch()

        # ── Gemini Card ──
        gem_card = QFrame()
        gem_card.setFixedSize(260, 160)
        gem_card.setStyleSheet("""
            QFrame {
                background: rgba(0, 229, 255, 0.06);
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 16px;
            }
            QFrame:hover {
                background: rgba(0, 229, 255, 0.12);
                border: 1px solid rgba(0, 229, 255, 0.5);
            }
        """)
        gem_card.setCursor(Qt.CursorShape.PointingHandCursor)
        glay = QVBoxLayout(gem_card)
        glay.setContentsMargins(22, 18, 22, 18)
        glay.setSpacing(4)

        gt = QLabel("Google Gemini")
        gt.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        gt.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        glay.addWidget(gt)

        gs = QLabel("★★★★★  Recommended")
        gs.setFont(QFont("Segoe UI", 9))
        gs.setStyleSheet("color: rgba(0, 229, 255,0.7); background: transparent; border: none;")
        glay.addWidget(gs)

        gd = QLabel("Primary Intelligence")
        gd.setFont(QFont("Segoe UI", 9))
        gd.setStyleSheet("color: rgba(255,255,255,0.35); background: transparent; border: none;")
        glay.addWidget(gd)

        glay.addStretch()

        gc = QLabel("Connect →")
        gc.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        gc.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        glay.addWidget(gc)

        # Make the whole card clickable via a transparent button overlay
        gem_btn = QPushButton(gem_card)
        gem_btn.setGeometry(0, 0, 260, 160)
        gem_btn.setStyleSheet("background: transparent; border: none;")
        gem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gem_btn.clicked.connect(self._goto_stage3)

        cards_lay.addWidget(gem_card)

        # ── OpenRouter Card ──
        or_card = QFrame()
        or_card.setFixedSize(260, 160)
        or_card.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }
            QFrame:hover {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        or_card.setCursor(Qt.CursorShape.PointingHandCursor)
        olay = QVBoxLayout(or_card)
        olay.setContentsMargins(22, 18, 22, 18)
        olay.setSpacing(4)

        ot = QLabel("OpenRouter")
        ot.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        ot.setStyleSheet("color: rgba(255,255,255,0.8); background: transparent; border: none;")
        olay.addWidget(ot)

        od = QLabel("Multiple Models")
        od.setFont(QFont("Segoe UI", 9))
        od.setStyleSheet("color: rgba(255,255,255,0.3); background: transparent; border: none;")
        olay.addWidget(od)

        od2 = QLabel("Optional · Secondary")
        od2.setFont(QFont("Segoe UI", 9))
        od2.setStyleSheet("color: rgba(255,255,255,0.2); background: transparent; border: none;")
        olay.addWidget(od2)

        olay.addStretch()

        oc = QLabel("Configure Later →")
        oc.setFont(QFont("Segoe UI", 11))
        oc.setStyleSheet("color: rgba(255,255,255,0.35); background: transparent; border: none;")
        olay.addWidget(oc)

        cards_lay.addWidget(or_card)
        cards_lay.addStretch()

        lay.addLayout(cards_lay)
        lay.addStretch(1)
        self._stack.addWidget(page)

    def _goto_stage3(self):
        self._call_js("if(window.triggerPulse) window.triggerPulse();")
        self._stack.setCurrentIndex(6)

    # ── STAGE 3 & 4: API Input + Auth ──────────────────────────────
    def _build_stage3(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        lay.addStretch(3)

        self._s3_box = QFrame()
        self._s3_box.setFixedSize(480, 260)
        self._s3_box.setStyleSheet("""
            QFrame {
                background: rgba(8, 10, 16, 220);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 20px;
            }
        """)
        blay = QVBoxLayout(self._s3_box)
        blay.setContentsMargins(32, 28, 32, 28)
        blay.setSpacing(6)

        self._s3_title = QLabel("Google Gemini")
        self._s3_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._s3_title.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        blay.addWidget(self._s3_title)

        self._s3_sub = QLabel("Paste your Neural Key")
        self._s3_sub.setFont(QFont("Segoe UI", 10))
        self._s3_sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent; border: none;")
        blay.addWidget(self._s3_sub)

        blay.addSpacing(16)

        # Input row
        input_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("Paste API key here...")
        self._key_input.setFont(QFont("Consolas", 12))
        self._key_input.setFixedHeight(48)
        self._key_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 229, 255, 0.04);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 12px;
                padding: 0 16px;
                letter-spacing: 1px;
                selection-background-color: rgba(0, 229, 255, 0.3);
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 229, 255, 0.6);
                background: rgba(0, 229, 255, 0.06);
            }
        """)
        self._key_input.setText((self._defaults.get("gemini_api_key") or "").strip())
        self._key_input.textChanged.connect(self._on_key_changed)
        input_row.addWidget(self._key_input)

        toggle_pw = QPushButton("👁")
        toggle_pw.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_pw.setFixedSize(36, 48)
        toggle_pw.setStyleSheet("QPushButton { background: transparent; border: none; color: rgba(255,255,255,0.3); font-size: 16px; } QPushButton:hover { color: #00e5ff; }")
        def _toggle():
            if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
                self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            else:
                self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        toggle_pw.clicked.connect(_toggle)
        input_row.addWidget(toggle_pw)
        blay.addLayout(input_row)

        # Status + link row
        status_row = QHBoxLayout()
        self._s3_status = QLabel("")
        self._s3_status.setFont(QFont("Consolas", 10))
        self._s3_status.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
        status_row.addWidget(self._s3_status)

        status_row.addStretch()

        hint = QLabel("<a href='https://aistudio.google.com/app/apikey' style='color: rgba(0, 229, 255,0.5); text-decoration: none; font-size: 10px;'>Get API Key →</a>")
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("background: transparent; border: none;")
        status_row.addWidget(hint)
        blay.addLayout(status_row)

        blay.addStretch()

        lay.addWidget(self._s3_box, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)

        # Intro page (hidden initially, will replace s3_box)
        self._intro_widget = QWidget(page)
        self._intro_widget.hide()
        intro_lay = QVBoxLayout(self._intro_widget)
        intro_lay.setContentsMargins(0, 0, 0, 0)
        intro_lay.setSpacing(12)

        self._intro_lines = []
        for txt in ["Identity confirmed.", "Hello.", "I'm Nexus Core.", "Ready whenever you are."]:
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if txt == "I'm Nexus Core.":
                lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
                lbl.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
            else:
                lbl.setFont(QFont("Segoe UI", 14))
                lbl.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent; border: none;")
            lbl.hide()
            intro_lay.addWidget(lbl)
            self._intro_lines.append(lbl)

        intro_lay.addSpacing(20)

        self._launch_btn = QPushButton("Launch Nexus Core →")
        self._launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launch_btn.setFixedSize(220, 48)
        self._launch_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._launch_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.4);
                border-radius: 24px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.25);
                border: 1px solid #00e5ff;
            }
        """)
        self._launch_btn.hide()
        self._launch_btn.clicked.connect(self._start_ignition)
        intro_lay.addWidget(self._launch_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._stack.addWidget(page)

    def _on_key_changed(self, text):
        if len(text) > 10 and not hasattr(self, "_authenticating"):
            self._authenticating = True
            self._key_input.setReadOnly(True)
            self._s3_sub.setText("Authenticating...")
            self._s3_sub.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
            self._auth_step = 0
            self._auth_timer = QTimer(self)
            self._auth_timer.timeout.connect(self._auth_tick)
            self._auth_timer.start(250)

    def _auth_tick(self):
        bars = [
            "█░░░░░░░░░░░░░░",
            "████░░░░░░░░░░░",
            "████████░░░░░░░",
            "███████████░░░░",
            "███████████████",
        ]
        if self._auth_step < len(bars):
            self._s3_status.setText(bars[self._auth_step])
            if self._auth_step % 2 == 0:
                self._call_js("if(window.triggerPulse) window.triggerPulse();")
            self._auth_step += 1
        else:
            self._auth_timer.stop()
            self._s3_status.setText("✓ Identity Verified")
            self._s3_status.setStyleSheet("color: #37ff5f; background: transparent; border: none;")
            self._s3_title.setText("✓ Google Gemini")
            self._s3_title.setStyleSheet("color: #37ff5f; background: transparent; border: none;")
            self._s3_sub.setText("Gemini 2.5 Pro  ·  Ready")
            self._s3_sub.setStyleSheet("color: rgba(55,255,95,0.6); background: transparent; border: none;")
            self._key_input.setStyleSheet("""
                QLineEdit {
                    background: rgba(55, 255, 95, 0.04);
                    color: #37ff5f;
                    border: 1px solid rgba(55, 255, 95, 0.3);
                    border-radius: 12px;
                    padding: 0 16px;
                }
            """)
            self._s3_box.setStyleSheet("""
                QFrame {
                    background: rgba(8, 10, 16, 220);
                    border: 1px solid rgba(55, 255, 95, 0.2);
                    border-radius: 20px;
                }
            """)
            QTimer.singleShot(1800, self._show_or_prompt)


    def _show_or_prompt(self):
        """After Gemini verified, ask if user wants to add OpenRouter too."""
        self._s3_box.hide()
        page = self._stack.widget(6)
        lay = page.layout()

        self._or_prompt_widget = QFrame()
        self._or_prompt_widget.setFixedSize(460, 200)
        self._or_prompt_widget.setStyleSheet("""
            QFrame {
                background: rgba(8, 10, 16, 220);
                border: 1px solid rgba(0, 229, 255, 0.15);
                border-radius: 20px;
            }
        """)
        prom_lay = QVBoxLayout(self._or_prompt_widget)
        prom_lay.setContentsMargins(32, 28, 32, 24)
        prom_lay.setSpacing(8)

        q_title = QLabel("Secondary Intelligence")
        q_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        q_title.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        prom_lay.addWidget(q_title)

        q_sub = QLabel("Would you like to configure OpenRouter as well?\nThis is optional and can be done later in Settings.")
        q_sub.setFont(QFont("Segoe UI", 10))
        q_sub.setWordWrap(True)
        q_sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent; border: none;")
        prom_lay.addWidget(q_sub)

        prom_lay.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        skip_btn = QPushButton("Skip")
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.setFixedHeight(42)
        skip_btn.setFont(QFont("Segoe UI", 11))
        skip_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255,255,255,0.4);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 0 24px;
            }
            QPushButton:hover {
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.25);
            }
        """)
        skip_btn.clicked.connect(self._skip_or)
        btn_row.addWidget(skip_btn)

        yes_btn = QPushButton("Configure OpenRouter")
        yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        yes_btn.setFixedHeight(42)
        yes_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        yes_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 12px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                border: 1px solid rgba(0, 229, 255, 0.6);
            }
        """)
        yes_btn.clicked.connect(self._show_or_input)
        btn_row.addWidget(yes_btn)

        prom_lay.addLayout(btn_row)

        lay.insertWidget(lay.count() - 1, self._or_prompt_widget, 0, Qt.AlignmentFlag.AlignCenter)

    def _skip_or(self):
        """User chose to skip OpenRouter, go to color selection."""
        self._or_key_value = ""
        self._or_prompt_widget.hide()
        self._show_color_stage()

    def _show_or_input(self):
        """User wants to add OpenRouter."""
        self._or_prompt_widget.hide()
        page = self._stack.widget(6)
        lay = page.layout()

        self._or_box = QFrame()
        self._or_box.setFixedSize(480, 230)
        self._or_box.setStyleSheet("""
            QFrame {
                background: rgba(8, 10, 16, 220);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 20px;
            }
        """)
        or_blay = QVBoxLayout(self._or_box)
        or_blay.setContentsMargins(32, 28, 32, 28)
        or_blay.setSpacing(6)

        or_title = QLabel("OpenRouter")
        or_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        or_title.setStyleSheet("color: rgba(255,255,255,0.8); background: transparent; border: none;")
        or_blay.addWidget(or_title)

        or_sub = QLabel("Paste your OpenRouter API Key")
        or_sub.setFont(QFont("Segoe UI", 10))
        or_sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent; border: none;")
        or_blay.addWidget(or_sub)

        or_blay.addSpacing(12)

        self._or_input = QLineEdit()
        self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-************************")
        self._or_input.setFont(QFont("Consolas", 12))
        self._or_input.setFixedHeight(48)
        self._or_input.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.03);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                padding: 0 16px;
                letter-spacing: 1px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0, 229, 255, 0.5);
            }
        """)
        self._or_input.setText((self._defaults.get("openrouter_api_key") or "").strip())
        or_blay.addWidget(self._or_input)

        or_blay.addStretch()

        or_btn_row = QHBoxLayout()
        or_skip = QPushButton("Skip")
        or_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        or_skip.setFixedHeight(42)
        or_skip.setFont(QFont("Segoe UI", 11))
        or_skip.setStyleSheet("""
            QPushButton { background: transparent; color: rgba(255,255,255,0.4); border: none; }
            QPushButton:hover { color: rgba(255,255,255,0.7); }
        """)
        or_skip.clicked.connect(self._skip_or)
        or_btn_row.addWidget(or_skip)

        or_save = QPushButton("Save & Continue")
        or_save.setCursor(Qt.CursorShape.PointingHandCursor)
        or_save.setFixedHeight(42)
        or_save.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        or_save.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 12px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                border: 1px solid rgba(0, 229, 255, 0.6);
            }
        """)
        or_save.clicked.connect(self._save_or_key)
        or_btn_row.addWidget(or_save)

        or_blay.addLayout(or_btn_row)

        lay.insertWidget(lay.count() - 1, self._or_box, 0, Qt.AlignmentFlag.AlignCenter)

    def _save_or_key(self):
        self._or_key_value = self._or_input.text().strip()
        self._or_box.hide()
        self._show_color_stage()

    def _show_color_stage(self):
        """Show color selection."""
        page = self._stack.widget(6)
        lay = page.layout()

        self._color_box = QFrame()
        self._color_box.setFixedSize(480, 230)
        self._color_box.setStyleSheet("""
            QFrame {
                background: rgba(8, 10, 16, 220);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 20px;
            }
        """)
        c_blay = QVBoxLayout(self._color_box)
        c_blay.setContentsMargins(32, 28, 32, 28)
        c_blay.setSpacing(6)

        c_title = QLabel("CHOOSE AESTHETIC")
        c_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        c_title.setStyleSheet("color: rgba(255,255,255,0.8); background: transparent; border: none;")
        c_blay.addWidget(c_title)

        c_sub = QLabel("Select your preferred neural color palette.")
        c_sub.setFont(QFont("Segoe UI", 10))
        c_sub.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent; border: none;")
        c_blay.addWidget(c_sub)

        c_blay.addSpacing(12)
        
        self._setup_color_btn = QPushButton("Pick Custom Color")
        self._setup_color_btn.setFixedHeight(48)
        self._setup_color_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._setup_color_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
            }}
        """)
        self._setup_color_btn.clicked.connect(self._pick_setup_color)
        c_blay.addWidget(self._setup_color_btn)

        c_blay.addStretch()

        c_btn_row = QHBoxLayout()
        c_btn_row.addStretch()
        c_continue = QPushButton("Continue →")
        c_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        c_continue.setFixedHeight(42)
        c_continue.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        c_continue.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.1);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 12px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.2);
                border: 1px solid rgba(0, 229, 255, 0.6);
            }
        """)
        c_continue.clicked.connect(self._finish_color_stage)
        c_btn_row.addWidget(c_continue)
        
        c_blay.addLayout(c_btn_row)

        lay.insertWidget(lay.count() - 1, self._color_box, 0, Qt.AlignmentFlag.AlignCenter)
        
    def _pick_setup_color(self):
        color = QColorDialog.getColor(QColor(C.PRI), self, "Select App Theme Color")
        if color.isValid():
            hex_col = color.name()
            self._setup_color_btn.setStyleSheet(f"QPushButton {{ background: {hex_col}; color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 12px; }}")
            try:
                settings = {}
                if APP_SETTINGS_FILE.exists():
                    with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                settings["app_theme"] = hex_col
                with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(settings, f, indent=4)
                C.load_theme(hex_col)
            except:
                pass
                
    def _finish_color_stage(self):
        self._color_box.hide()
        self._show_intro_final()

    def _show_intro_final(self):
        """Show the Nexus Core intro sequence."""
        page = self._stack.widget(6)
        lay = page.layout()
        self._intro_widget.setParent(None)
        lay.insertWidget(lay.count() - 1, self._intro_widget, 0, Qt.AlignmentFlag.AlignCenter)
        self._intro_widget.show()
        self._intro_reveal_idx = 0
        self._intro_timer = QTimer(self)
        self._intro_timer.timeout.connect(self._intro_tick)
        self._intro_timer.start(600)

    def _show_intro(self):
        self._s3_box.hide()
        page = self._stack.widget(6)
        lay = page.layout()
        self._intro_widget.setParent(None)
        lay.insertWidget(lay.count() - 1, self._intro_widget, 0, Qt.AlignmentFlag.AlignCenter)
        self._intro_widget.show()
        self._intro_reveal_idx = 0
        self._intro_timer = QTimer(self)
        self._intro_timer.timeout.connect(self._intro_tick)
        self._intro_timer.start(600)

    def _intro_tick(self):
        if self._intro_reveal_idx < len(self._intro_lines):
            self._intro_lines[self._intro_reveal_idx].show()
            if self._intro_reveal_idx == 2:
                self._call_js("if(window.triggerPulse) window.triggerPulse();")
            self._intro_reveal_idx += 1
        else:
            self._intro_timer.stop()
            self._launch_btn.show()

    # ── STAGE 6: Neural Link Ignition ──────────────────────────────
    def _build_stage4(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        lay.addStretch(3)

        self._s4_container = QFrame()
        self._s4_container.setFixedWidth(360)
        self._s4_container.setStyleSheet("""
            QFrame {
                background: rgba(5, 8, 12, 180);
                border: 1px solid rgba(0, 229, 255, 0.12);
                border-radius: 16px;
            }
        """)
        c4lay = QVBoxLayout(self._s4_container)
        c4lay.setContentsMargins(30, 24, 30, 24)
        c4lay.setSpacing(8)

        self._s4_title = QLabel("ESTABLISHING NEURAL LINK")
        self._s4_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._s4_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._s4_title.setStyleSheet("color: rgba(0, 229, 255,0.7); background: transparent; border: none; letter-spacing: 3px;")
        c4lay.addWidget(self._s4_title)
        c4lay.addSpacing(12)

        self._module_labels = {}
        for mod in ["MEMORY", "VOICE", "VISION", "AUTOMATION", "REASONING"]:
            row = QHBoxLayout()
            name_lbl = QLabel(mod)
            name_lbl.setFont(QFont("Consolas", 11))
            name_lbl.setStyleSheet("color: rgba(255,255,255,0.2); background: transparent; border: none;")
            name_lbl.setFixedWidth(130)
            row.addWidget(name_lbl)

            bar_lbl = QLabel("░░░░░░░░░░")
            bar_lbl.setFont(QFont("Consolas", 11))
            bar_lbl.setStyleSheet("color: rgba(0, 229, 255,0.15); background: transparent; border: none;")
            row.addWidget(bar_lbl)
            row.addStretch()

            c4lay.addLayout(row)
            self._module_labels[mod] = (name_lbl, bar_lbl)

        lay.addWidget(self._s4_container, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        self._stack.addWidget(page)

    def _start_ignition(self):
        self._stack.setCurrentIndex(7)
        self._call_js("if(window.setReactorSpeed) window.setReactorSpeed(5.0);")

        self._ignite_step = 0
        self._module_order = ["MEMORY", "VOICE", "VISION", "AUTOMATION", "REASONING"]
        self._ignite_timer = QTimer(self)
        self._ignite_timer.timeout.connect(self._ignite_tick)
        self._ignite_timer.start(600)

    def _ignite_tick(self):
        if self._ignite_step < len(self._module_order):
            mod = self._module_order[self._ignite_step]
            name_lbl, bar_lbl = self._module_labels[mod]
            name_lbl.setStyleSheet("color: #00e5ff; background: transparent; border: none; font-weight: bold;")
            bar_lbl.setText("██████████")
            bar_lbl.setStyleSheet("color: #00e5ff; background: transparent; border: none;")
            self._call_js(f"if(window.setReactorSpeed) window.setReactorSpeed({5.0 + self._ignite_step * 4});")
            self._call_js("if(window.triggerPulse) window.triggerPulse();")
            self._ignite_step += 1
        else:
            self._ignite_timer.stop()
            self._s4_title.setText("NEURAL LINK ESTABLISHED")
            self._s4_title.setStyleSheet("color: #37ff5f; background: transparent; border: none; letter-spacing: 3px; font-weight: bold;")
            self._s4_container.setStyleSheet("""
                QFrame {
                    background: rgba(5, 8, 12, 180);
                    border: 1px solid rgba(55, 255, 95, 0.2);
                    border-radius: 16px;
                }
            """)
            for mod in self._module_order:
                n, b = self._module_labels[mod]
                n.setStyleSheet("color: #37ff5f; background: transparent; border: none; font-weight: bold;")
                b.setStyleSheet("color: #37ff5f; background: transparent; border: none;")
            self._call_js("if(window.dissolveReactor) window.dissolveReactor();")
            QTimer.singleShot(1200, lambda: self.done.emit(self._key_input.text().strip(), getattr(self, "_or_key_value", ""), self._sel_os))




class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


from ui_popup_components import (BackgroundWidget, RemoteKeyOverlay, DailyBriefingOverlay, ConfirmationOverlay, MemoryInspectorOverlay)
from ui_gestures import _SysMetrics, _GestureRenderCanvas, GestureCameraPreview, _camera_available, _active_net_label
from ui_workspace import TaskDock, WorkspaceSidebar, InlineChatWorkspace
from ui_overlays import (VoiceWaveformVisualizer, CommandBar, OmniCommandPalette, DeveloperModeDialog, ScanningOverlay, BootSequenceOverlay, IncomingAlertDialog, UltronMalfunctionDialog, MeetingOverlay, FloatingLauncher, FloatingGestureCard, _ease_out_expo, _ease_in_out_sine)
from ui_settings_pages import (
    SystemConnectivitySidebar, SettingsHubPage, SystemConnectivityPage,
    SmartDevicesSection, _ConnectDeviceCard, NexusConnectDevicesPage,
)
from ui_main_window import MainWindow


class BrahmaUI:
    def __init__(self, face_path: str, size=None, *, show_immediately: bool = True):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        # Set application icon for dock/taskbar when minimized
        app_icon = _logo_icon()
        if not app_icon.isNull():
            self._app.setWindowIcon(app_icon)
        self._app.setStyleSheet("""
            QMessageBox, QDialog, QInputDialog {
                background-color: #0b0f19;
                color: #ffffff;
                border: 1.5px solid rgba(0, 229, 255, 0.35);
                border-radius: 14px;
            }
            QMessageBox QLabel, QDialog QLabel, QInputDialog QLabel {
                color: #ffffff;
                background-color: transparent;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 13px;
                padding: 4px;
            }
            QMessageBox QPushButton, QDialog QPushButton, QInputDialog QPushButton {
                background-color: #00e5ff;
                color: #050a12;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                min-width: 80px;
                min-height: 30px;
            }
            QMessageBox QPushButton:hover, QDialog QPushButton:hover, QInputDialog QPushButton:hover {
                background-color: #33ebff;
            }
            QMessageBox QPushButton:pressed, QDialog QPushButton:pressed, QInputDialog QPushButton:pressed {
                background-color: #00b3cc;
            }
            QMessageBox QPushButton:disabled, QDialog QPushButton:disabled, QInputDialog QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationDisplayName("Nexus Core")
        self._app.setWindowIcon(self._make_app_icon())
        try:
            current_store = workspace_store()
            current_store.rollover_active_conversation_on_startup()
        except Exception:
            pass
        self._win = MainWindow(face_path)
        try:
            from core.updater import UpdateChecker
            self._updater = UpdateChecker()
            self._updater.update_available_sig.connect(self._show_update_prompt)
            self._updater.start()
        except Exception as e:
            print(f"Failed to start updater: {e}")
        try:
            self._win._startup_enabled()
        except Exception:
            pass
        self._win.set_settings_bridge(self)
        self._discord_service = DiscordBotService(
            status_callback=self._win.discord_status_changed.emit,
            log_callback=self._win._log_sig.emit,
        )
        self._discord_service.bind_app_submitter(self._win.submit_command)
        self._win.discord_config_changed.connect(self._on_discord_config_changed)
        self._win.on_chat_event = self._on_chat_event
        self._app.aboutToQuit.connect(self._discord_service.stop)
        self._launcher = FloatingLauncher()
        self._command_bar = CommandBar()
        self._workspace_sidebar = WorkspaceSidebar()
        self._control_panel: LauncherControlPanel | None = None
        self._boot_overlay: BootSequenceOverlay | None = None
        self._app_settings_cache: dict | None = None
        self._launcher.single_clicked.connect(self._toggle_workspace_sidebar)
        self._launcher.double_clicked.connect(self._on_launcher_double_clicked)
        self._launcher.action_requested.connect(self._handle_launcher_action)
        self._launcher.position_changed.connect(self._save_launcher_position)
        self._command_bar.submitted.connect(self._submit_command)
        self._command_bar.attach_clicked.connect(self._browse_attachment)
        self._command_bar.mic_clicked.connect(self._toggle_mute)
        self._command_bar.developer_clicked.connect(self._open_developer_mode_dialog)
        self._workspace_sidebar.command_submitted.connect(self._submit_command)
        self._workspace_sidebar.attach_requested.connect(self._browse_attachment)
        self._workspace_sidebar.mic_requested.connect(self._toggle_mute)
        self._workspace_sidebar.close_requested.connect(self._close_workspace_sidebar)
        self._win.minimized.connect(self._on_minimized)
        self._win.restored.connect(self._on_restored)
        self._win._state_sig.connect(self._sync_launcher_state)
        self._win._audio_level_sig.connect(self._launcher.set_audio_level)
        try:
            from core.clipboard_sentry import ClipboardSentry
            self._clip_sentry = ClipboardSentry(callback=self._on_clipboard_actionable)
            self._clip_sentry.start()
        except Exception:
            pass
        self._tray = QSystemTrayIcon(self._make_app_icon(), self._app)
        self._tray.setToolTip("Nexus Core")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.setContextMenu(self._build_tray_menu())
        self._tray.show()
        self._win._log_sig.connect(self._workspace_sidebar.append_log)
        self._win._task_workspace_sig.connect(self._workspace_sidebar.apply_task_workspace)
        # Some window layouts intentionally omit the inline chat workspace.  It is
        # optional, so do not let its absence prevent the application from starting.
        inline_workspace = getattr(self._win, "_inline_workspace", None)
        if inline_workspace is not None:
            self._win._task_workspace_sig.connect(inline_workspace.apply_task_workspace)
        self._on_discord_config_changed(self._win._load_discord_settings())
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.move(int(launcher_pos[0]), int(launcher_pos[1]))
            except Exception:
                pass
        if bool(self._load_app_settings().get("show_workspace_on_startup", False)):
            self._workspace_sidebar.show_workspace(animate=False)
        else:
            self._workspace_sidebar.hide_workspace(animate=False)
        self.set_dashboard_page(getattr(self._win, "_current_page", "dashboard") == "dashboard")
        self._apply_developer_mode_ui()
        if not self._load_app_settings().get("first_run_diagnostics_complete", False):
            try:
                diagnostics = FirstRunDiagnosticsDialog(self._win)
                diagnostics.exec()
            except Exception as exc:
                print(f"First-run diagnostics could not be shown: {exc}")
            settings = self._load_app_settings()
            settings["first_run_diagnostics_complete"] = True
            self._save_app_settings(settings)
        if show_immediately:
            self._launcher.hide()
            if self._should_play_boot_sequence():
                self.play_boot_sequence()
            else:
                self.show_main()
        else:
            self._show_floating_icon()
        self.root = _RootShim(self._app)

    def _make_app_icon(self) -> QIcon:
        return _logo_icon()

    def set_nexus_connect_service(self, service):
        self._win.set_nexus_connect_service(service)


    

    def show_main(self):
        if self._boot_overlay is not None and not getattr(self._boot_overlay, "_boot_finished", False):
            return
        try:
            self._win.setWindowState(
                (self._win.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
            )
            self._win.showNormal()
        except Exception:
            self._win.show()
        self._win.raise_()
        self._win.activateWindow()
        self._launcher.hide()

    def set_dashboard_page(self, enabled: bool):
        try:
            if not enabled:
                self._command_bar.hide()
                self._workspace_sidebar.hide_workspace(animate=False)
        except Exception:
            pass

    def hide_main(self):
        self._command_bar.hide()
        self._launcher.hide()
        self._win.hide()

    def _load_app_settings(self) -> dict:
        if self._app_settings_cache is not None:
            return dict(self._app_settings_cache)
        settings = _default_app_settings()
        if APP_SETTINGS_FILE.exists():
            try:
                data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        settings[k] = v
            except Exception:
                pass
        self._app_settings_cache = dict(settings)
        return dict(settings)

    def _save_app_settings(self, settings: dict):
        _write_settings_files(settings)
        self._app_settings_cache = dict(settings)

    def _save_launcher_position(self, x: int, y: int):
        try:
            settings = self._load_app_settings()
            settings["launcher_pos"] = [int(x), int(y)]
            self._save_app_settings(settings)
        except Exception:
            pass

    def _open_developer_mode_dialog(self):
        try:
            dialog = DeveloperModeDialog(self._win, settings=self._load_app_settings())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                settings = dialog.get_settings()
                self._save_app_settings(settings)
                self._apply_developer_mode_ui()
        except Exception:
            pass

    def _apply_developer_mode_ui(self):
        try:
            settings = self._load_app_settings()
            enabled = bool(settings.get("developer_mode_enabled", False))
            workspace = str(settings.get("developer_mode_workspace", "")).strip()
            if hasattr(self._win, "_developer_card") and hasattr(self._win, "_developer_status_lbl"):
                if enabled:
                    workspace_text = workspace or "No folder selected"
                    self._win._developer_status_lbl.setText(
                        f"Developer mode is on • {workspace_text}"
                    )
                # Keep legacy card permanently hidden; modern UI integrates status inside settings
                self._win._developer_card.hide()
        except Exception:
            pass

    def _sync_launcher_state(self, state: str):
        state = (state or "idle").strip().lower()
        detail = {
            "listening": "Ready",
            "thinking": "Thinking...",
            "processing": "Executing task...",
            "speaking": "Speaking",
            "muted": "Muted",
        }.get(state, "Ready")
        try:
            self._launcher.set_state(state, detail)
        except Exception:
            pass

    def _load_discord_settings(self) -> dict:
        settings = _default_discord_settings()
        if DISCORD_SETTINGS_FILE.exists():
            try:
                data = json.loads(DISCORD_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    settings.update(data)
            except Exception:
                pass
        if (settings.get("bot_token") or "").strip():
            settings["enabled"] = True
        return dict(settings)

    def _save_discord_settings(self, settings: dict):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        DISCORD_SETTINGS_FILE.write_text(json.dumps(settings, indent=4), encoding="utf-8")

    def _emit_discord_settings(self):
        if not hasattr(self, "_discord_token_input"):
            return
        settings = {
            "bot_token": self._discord_token_input.text().strip(),
            "enabled": bool(getattr(self, "_discord_enabled", False)),
            "channel_id": self._discord_channel_input.text().strip() if hasattr(self, "_discord_channel_input") else "",
        }
        self._save_discord_settings(settings)
        self.discord_config_changed.emit(dict(settings))
        self._refresh_discord_card()

    def _refresh_discord_card(self, note: str = ""):
        if not hasattr(self, "_discord_status_lbl"):
            return
        token = self._discord_token_input.text().strip() if hasattr(self, "_discord_token_input") else ""
        enabled = bool(getattr(self, "_discord_enabled", False))
        if note:
            status = note
            color = C.PRI if "error" in note.lower() or "missing" in note.lower() else C.TEXT_MED
        elif not token:
            status = "Token required"
            color = C.PRI
        elif enabled:
            status = "Bot enabled"
            color = C.GREEN
        else:
            status = "Bot disabled"
            color = C.TEXT_MED
        self._discord_status_lbl.setText(status)
        self._discord_status_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_discord_start_btn"):
            self._discord_start_btn.setEnabled(True)
        if hasattr(self, "_discord_stop_btn"):
            self._discord_stop_btn.setEnabled(True)
        if hasattr(self, "_discord_save_btn"):
            self._discord_save_btn.setText("Save Settings")

    def _startup_animation_enabled(self) -> bool:
        if platform.system() != "Windows":
            return False
        return bool(self._load_app_settings().get("startup_animation_enabled", True))

    def _set_startup_animation_enabled(self, enabled: bool) -> bool:
        try:
            settings = self._load_app_settings()
            settings["startup_animation_enabled"] = bool(enabled)
            settings["last_boot_stamp"] = _current_boot_stamp()
            self._save_app_settings(settings)
            return True
        except Exception as e:
            self._log.append_log(f"ERR: startup animation setting failed: {e}")
            return False

    def _refresh_startup_animation_button(self):
        if not hasattr(self, "_startup_anim_btn"):
            return
        if platform.system() != "Windows":
            self._startup_anim_btn.setText("Startup Animation (Windows only)")
            self._startup_anim_btn.setEnabled(False)
            return
        if self._startup_animation_enabled():
            self._startup_anim_btn.setText("Disable Startup Animation")
        else:
            self._startup_anim_btn.setText("Enable Startup Animation")

    def _toggle_startup_animation(self):
        if platform.system() != "Windows":
            return
        enabled = not self._startup_animation_enabled()
        if self._set_startup_animation_enabled(enabled):
            self._refresh_startup_animation_button()
            state = "enabled" if enabled else "disabled"
            self._log.append_log(f"SYS: Startup animation {state}.")

    def _should_play_boot_sequence(self) -> bool:
        return True

    def _mark_boot_sequence_played(self):
        try:
            settings = self._load_app_settings()
            settings["last_boot_stamp"] = _current_boot_stamp()
            settings["boot_sequence_played"] = True
            self._save_app_settings(settings)
        except Exception:
            pass

    def play_boot_sequence(self, finished_callback=None):
        self._mark_boot_sequence_played()
        if self._boot_overlay is None:
            self._boot_overlay = BootSequenceOverlay()
            def _on_boot_finished():
                try:
                    self._win.setWindowState(
                        (self._win.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
                    )
                    self._win.showNormal()
                    self._win.raise_()
                    self._win.activateWindow()
                    self._launcher.hide()
                except Exception:
                    try:
                        self._win.show()
                    except Exception:
                        pass
                if finished_callback:
                    try:
                        finished_callback()
                    except Exception:
                        pass
            self._boot_overlay.finished.connect(_on_boot_finished)
        self._boot_overlay.start()

    # Thread-safe helpers for driving the boot overlay from background threads
    def boot_add_step(self, text: str):
        try:
            if not self._boot_overlay:
                return None
            QTimer.singleShot(0, lambda: self._boot_overlay.add_step(text))
        except Exception:
            pass

    def boot_set_step_status(self, text: str, status: str):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_step_status(text, status))
        except Exception:
            pass

    def boot_set_progress(self, percent: int, tip: str | None = None):
        try:
            if not self._boot_overlay:
                return
            QTimer.singleShot(0, lambda: self._boot_overlay.set_progress(percent, tip))
        except Exception:
            pass

    def _build_tray_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background: rgba(8, 8, 8, 245);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: rgba(255,255,255,0.08);
            }}
        """)

        open_app_action = menu.addAction("Open App")
        open_action = menu.addAction("Open Workspace")
        close_action = menu.addAction("Close Workspace")
        startup_action = menu.addAction("Show Workspace On Startup")
        startup_action.setCheckable(True)
        startup_action.setChecked(bool(self._load_app_settings().get("show_workspace_on_startup", False)))
        show_icon_action = menu.addAction("Show Floating Icon")
        hide_icon_action = menu.addAction("Hide Floating Icon")
        menu.addSeparator()
        restart_action = menu.addAction("Restart")
        quit_action = menu.addAction("Quit")

        open_app_action.triggered.connect(self.show_main)
        open_action.triggered.connect(self._show_workspace_sidebar)
        close_action.triggered.connect(self._close_workspace_sidebar)
        startup_action.triggered.connect(lambda: self._toggle_workspace_on_startup(startup_action.isChecked()))
        show_icon_action.triggered.connect(self._show_floating_icon)
        hide_icon_action.triggered.connect(self._hide_launcher_with_protection)
        restart_action.triggered.connect(self._restart_app)
        quit_action.triggered.connect(self._app.quit)
        return menu

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_workspace_sidebar()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main()

    def _on_minimized(self):
        self._command_bar.hide()
        self._show_floating_icon()

    def _on_restored(self):
        self._launcher.hide()

    def _on_launcher_double_clicked(self):
        self._workspace_sidebar.hide_workspace(animate=False)
        self.show_main()

    def _on_clipboard_actionable(self, category: str, content: str):
        label = {
            "error_traceback": "Traceback/Error copied — want an explanation?",
            "json_data": "JSON copied — format/validate?",
            "sql_query": "SQL Query copied — optimize/review?",
            "code_snippet": "Code snippet copied — review?",
        }.get(category, "Clipboard item copied")
        self._workspace_sidebar.record_chat_event({
            "role": "system",
            "text": f"💡 {label}",
            "source": "clipboard",
        })

    def _toggle_command_bar(self):
        if self._command_bar.isVisible():
            self._command_bar.hide()
        else:
            self._command_bar.show_near(self._launcher)

    def _toggle_workspace_sidebar(self):
        if self._workspace_sidebar.isVisible() and not self._workspace_sidebar.is_collapsed():
            self._close_workspace_sidebar()
        else:
            self._show_workspace_sidebar()

    def _show_workspace_sidebar(self):
        self._workspace_sidebar.show_workspace()
        self._workspace_sidebar.focus_input()
        if self._launcher.isVisible():
            self._launcher.raise_()

    def _close_workspace_sidebar(self):
        self._workspace_sidebar.hide_workspace()
        if self._launcher.isVisible():
            self._launcher.raise_()

    def _show_floating_icon(self):
        launcher_pos = self._load_app_settings().get("launcher_pos")
        if isinstance(launcher_pos, (list, tuple)) and len(launcher_pos) == 2:
            try:
                self._launcher.show_at(int(launcher_pos[0]), int(launcher_pos[1]))
                return
            except Exception:
                pass
        self._launcher.show_at()

    def _restart_app(self):
        try:
            args = _hidden_launch_args("--startup" if _launched_from_windows_startup() else "")
            args = [arg for arg in args if arg]
            kwargs = {"cwd": str(BASE_DIR)}
            if _OS == "Windows":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(args, **kwargs)
        except Exception as exc:
            self._win.write_log(f"ERR: Restart failed: {exc}")
        self._app.quit()

    def _toggle_workspace_on_startup(self, enabled: bool):
        try:
            settings = self._load_app_settings()
            settings["show_workspace_on_startup"] = bool(enabled)
            self._save_app_settings(settings)
        except Exception:
            pass

    def _hide_launcher_with_protection(self):
        self._show_hide_launcher_confirm()

    def _show_hide_launcher_confirm(self):
        panel = LauncherControlPanel(
            startup_workspace=bool(self._load_app_settings().get("show_workspace_on_startup", False)),
            on_open=self._show_workspace_sidebar,
            on_close=self._close_workspace_sidebar,
            on_toggle_startup=self._toggle_workspace_on_startup,
            on_hide_icon=self._launcher.hide,
            on_restart=self._restart_app,
            on_quit=self._app.quit,
            on_open_app=self.show_main,
            on_show_icon=self._show_floating_icon,
            on_open_dev=self._open_developer_mode_dialog,
        )
        self._control_panel = panel
        self._position_control_panel(panel)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def _position_control_panel(self, panel: LauncherControlPanel):
        try:
            geo = self._launcher.geometry()
            panel.adjustSize()
            panel.move(max(20, geo.left() - panel.width() - 16), max(20, geo.top() - 10))
        except Exception:
            screen = QApplication.primaryScreen().availableGeometry()
            panel.move(screen.center().x() - panel.width() // 2, screen.center().y() - panel.height() // 2)

    def _show_control_panel(self):
        self._show_hide_launcher_confirm()

    def _handle_launcher_action(self, action: str):
        action = (action or "").strip().lower()
        if action == "open_app":
            self.show_main()
        elif action == "open_workspace":
            self._show_workspace_sidebar()
        elif action == "close_workspace":
            self._close_workspace_sidebar()
        elif action == "show_icon":
            self._show_floating_icon()
        elif action == "hide_icon":
            self._hide_launcher_with_protection()
        elif action == "restart":
            self._restart_app()
        elif action == "quit":
            self._app.quit()
        elif action == "toggle_startup":
            current = bool(self._load_app_settings().get("show_workspace_on_startup", False))
            self._toggle_workspace_on_startup(not current)

    def _submit_command(self, text: str):
        self._win.submit_command(text)

    def _browse_attachment(self):
        self._win._browse_attachment()

    def _toggle_mute(self):
        self._win._toggle_mute()

    def _show_update_prompt(self, remote_hash: str):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self._win,
            "Update Detected!",
            f"A new update is available on GitHub!\n\nDo you want to apply the update and restart the app?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            from core.updater import apply_update_and_restart
            # Show a simple overlay while updating
            self._win._set_status("Applying update from GitHub...")
            import threading
            threading.Thread(target=apply_update_and_restart, daemon=True).start()

    def _on_chat_event(self, event: dict):
        try:
            self._discord_service.mirror_chat_event(event or {})
        except Exception:
            pass
        try:
            self._workspace_sidebar.record_chat_event(event or {})
        except Exception:
            pass
        try:
            self._win._inline_workspace.record_chat_event(event or {})
        except Exception:
            pass

    def _on_discord_config_changed(self, settings: dict):
        settings = settings or {}
        enabled = bool(settings.get("enabled", False) or (settings.get("bot_token") or "").strip())
        token = (settings.get("bot_token") or "").strip()
        channel_id = (settings.get("channel_id") or "").strip()
        self._discord_service.set_target_channel_id(channel_id)
        if not enabled or not token:
            self._discord_service.stop()
            if not token:
                self._win.discord_status_changed.emit("Token required")
            else:
                self._win.discord_status_changed.emit("Discord bot disabled")
            return
        try:
            self._discord_service.start(token)
        except Exception as exc:
            msg = f"Discord error: {exc}"
            self._win.discord_status_changed.emit(msg)
            self._win._log_sig.emit(f"ERR: {msg}")

    def _open_app(self):
        self._command_bar.hide()
        self._workspace_sidebar.hide_workspace(animate=False)
        self.show_main()

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    def set_muted(self, muted: bool):
        if bool(muted) != self._win._muted:
            self._win.set_muted_state(bool(muted))

    def set_muted_state(self, muted: bool, *, wakeword: bool = False):
        self._win.set_muted_state(bool(muted), wakeword=wakeword)

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_attention_action(self):
        return self._win.on_attention_action

    @on_attention_action.setter
    def on_attention_action(self, cb):
        self._win.on_attention_action = cb

    @property
    def on_chat_event(self):
        return self._win.on_chat_event

    @on_chat_event.setter
    def on_chat_event(self, cb):
        self._win.on_chat_event = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_audio_level(self, level: float):
        self._win.set_audio_level(level)

    def set_live_subtitles(self, speaker: str, text: str, interim: bool = False):
        try:
            self._win._subtitle_sig.emit(speaker, text, interim)
        except Exception:
            pass

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def show_confirm(self, title: str, detail: str = ""):
        self.w.show_confirm(title, detail)

    def hide_confirm(self):
        self.w.hide_confirm()

    def show_memory_inspector(self):
        self.w.show_memory_inspector()

    def hide_memory_inspector(self):
        self.w.hide_memory_inspector()

    def show_daily_briefing(self, text: str):
        self._win.show_daily_briefing(text)

    def hide_daily_briefing(self):
        self._win.hide_daily_briefing()

    def schedule_daily_briefing_hide(self):
        self._win.schedule_daily_briefing_hide()

    def submit_external_command(self, text: str, source: str = "discord"):
        self._win.submit_command(text, source=source)

    def notify_phone_connected(self):
        self._win.notify_phone_connected()

    def set_scanning(self, enabled: bool, text: str = ""):
        self._win.set_scanning(enabled, text)

    def show_circuit_hud(self, circuit_data: dict):
        self._win._circuit_hud_sig.emit(circuit_data or {})

    def show_radar_hud(self, radar_data: dict):
        self._win._radar_hud_sig.emit(radar_data or {})

    def show_space_cleaner_hud(self, data: dict = None):
        self._win._space_cleaner_sig.emit(data or {})

    def show_call_screening(self, event: dict):
        self._win._call_screening_sig.emit(event or {})

    def update_call_screening_transcript(self, speaker: str, text: str):
        self._win._call_screening_sig.emit({
            "action": "transcript",
            "speaker": speaker,
            "text": text,
        })

    def hide_call_screening(self):
        self._win._call_screening_sig.emit({"action": "hide"})

    def show_attention_alert(self, event: dict):
        self._win._attention_sig.emit(event or {})

    def set_meeting_mode(self, enabled: bool, title: str = "", summary: str = "", answer: str = "", speech: str = ""):
        self._win.set_meeting_mode(enabled, title, summary, answer, speech)

    def begin_task_workspace(self, command: str, plan: list[str] | str | None = None, source: str = "local"):
        self._win._task_workspace_sig.emit({
            "action": "start",
            "command": command or "",
            "plan": plan or [],
            "source": source or "local",
        })

    def capture_screen_bytes(self) -> bytes:
        import threading
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QBuffer, QIODevice, Qt

        if threading.current_thread() == threading.main_thread():
            screen = QApplication.primaryScreen()
            if not screen: return b""
            pixmap = screen.grabWindow(0)
            pixmap = pixmap.scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer, 'JPG', 55)
            return buffer.data().data()
        else:
            return self._win.capture_screen_threadsafe()

    def update_task_workspace(self, *, title: str | None = None, command: str | None = None, plan: list[str] | str | None = None,
                              status: str | None = None, output: str | None = None, percent: int | None = None,
                              footer: str | None = None, source: str | None = None):
        payload = {"action": "update"}
        if title is not None:
            payload["title"] = title
        if command is not None:
            payload["command"] = command
        if plan is not None:
            payload["plan"] = plan
        if status is not None:
            payload["status"] = status
        if output is not None:
            payload["output"] = output
        if percent is not None:
            payload["percent"] = percent
        if footer is not None:
            payload["footer"] = footer
        if source is not None:
            payload["source"] = source or "local"
        self._win._task_workspace_sig.emit(payload)

    def finish_task_workspace(self, result: str, status: str = "Task completed.", percent: int = 100):
        self._win._task_workspace_sig.emit({
            "action": "finish",
            "result": result or "Done.",
            "status": status or "Task completed.",
            "percent": percent,
        })

    def clear_task_workspace(self):
        self._win._task_workspace_sig.emit({"action": "clear"})

    def show_hud_operation(self, title: str, step: str, sources: list = None, tool: str = None, **kwargs):
        """Displays live operation telemetry on the right HUD wing."""
        if hasattr(self, "_win") and hasattr(self._win, "_hud_operation_sig"):
            payload = {
                "title": title,
                "step": step,
                "sources": sources or [],
                "tool": tool or ""
            }
            payload.update(kwargs)
            self._win._hud_operation_sig.emit(payload)

    def show_hud_deliverable(self, title: str, summary: str = "", bullets: list = None,
                             file_path: str = None, kind: str = "result", actions: list = None, data: dict = None, **kwargs):
        """Displays final results or file deliverables on the left HUD wing."""
        if hasattr(self, "_win") and hasattr(self._win, "_hud_deliverable_sig"):
            payload = {
                "title": title,
                "summary": summary or "",
                "bullets": bullets or [],
                "file_path": file_path or "",
                "kind": kind or "result",
                "actions": actions or [],
                "data": data or {}
            }
            payload.update(kwargs)
            self._win._hud_deliverable_sig.emit(payload)

    def show_ultron_malfunction(self, payload: dict):
        """Pops up or updates the dedicated Ultron Malfunction & Self-Repair HUD dialog window."""
        if hasattr(self, "_win") and hasattr(self._win, "_ultron_malfunction_sig"):
            self._win._ultron_malfunction_sig.emit(payload or {})

    def show_content(self, title: str, body: str):
        """Universal rich content presenter. Automatically routes to the Nexus Holographic Left Deliverable Wing."""
        import re
        file_path = None
        m = re.search(r'([A-Za-z]:\\[^\s"\'<>`\r\n]+\.(?:pdf|docx|xlsx|pptx|png|jpg|mp4|py|html|json|txt))', body)
        if m:
            cand = Path(m.group(1).strip())
            if cand.exists():
                file_path = str(cand.resolve())
        if not file_path:
            m2 = re.search(r'([^\s"\'<>`\r\n]+\.(?:pdf|docx|xlsx|pptx|png|jpg|mp4|py|html|json|txt))', body)
            if m2:
                cand2 = Path(m2.group(1).strip())
                if cand2.exists():
                    file_path = str(cand2.resolve())

        bullets = []
        for line in body.splitlines():
            line_str = line.strip()
            if (line_str.startswith(("-", "*", "•", ">")) or line_str.startswith(tuple("123456789."))) and len(line_str) > 2:
                clean_bullet = line_str.lstrip("-*•>0123456789. ").strip()
                if clean_bullet and not clean_bullet.startswith("#"):
                    bullets.append(clean_bullet)

        self.show_hud_deliverable(
            title=title,
            summary=body[:220] if not bullets else "",
            bullets=bullets[:5],
            file_path=file_path,
            kind="deliverable"
        )

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")



