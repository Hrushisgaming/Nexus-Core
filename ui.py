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

from ui_support import (
    BASE_DIR, CONFIG_DIR, API_FILE, APP_SETTINGS_FILE, DISCORD_SETTINGS_FILE,
    LOGO_FILE, LOGO_ICO, APP_ICON_PNG, BACKGROUND_IMAGE_FILE, MODEL_DOWNLOAD_URL,
    _DEFAULT_W, _DEFAULT_H, _MIN_W, _MIN_H, _LEFT_W, _RIGHT_W, _OS,
    _logo_icon, _logo_pixmap, _framed_logo, _icon_pixmap, _attach_pulse_glow,
    _quiet_run, _quote_cmd_arg, _get_pythonw_path, _hidden_launch_args,
    _startup_run_value, _startup_registry_key, _current_boot_stamp,
    _launched_from_windows_startup, _default_app_settings, _read_json_dict,
    _write_settings_files, _PROVIDER_KEY_FIELDS, _default_discord_settings, _RootShim
)

from ui_panels import (LauncherControlPanel, SmallPanelCard, BrahmaTelemetryWing, BrahmaResultWing, StatCard, LogWidget, _file_category, _fmt_size, FileDropZone, _DropCanvas)
from ui_setup import APIKeySettingsDialog, SetupOverlay
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



