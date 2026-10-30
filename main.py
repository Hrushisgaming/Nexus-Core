from core.user_paths import get_user_data_dir
from typing import Any, Optional
import logging
import os

# Hardware acceleration & WebGL flags for smooth rendering in Chromium.
# ANGLE backend must match the host OS: d3d11 on Windows, metal on macOS,
# opengl/egl on Linux. Using the wrong backend makes Qt WebEngine fail to
# initialize GPU acceleration on that platform.
import sys as _sys
_base_chromium_flags = (
    "--enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist "
    "--enable-accelerated-2d-canvas --enable-webgl --enable-webgl2-compute-context "
    "--disable-frame-rate-limit --disable-gpu-vsync --num-raster-threads=4 "
    "--disable-gpu-driver-bug-workarounds"
)
if _sys.platform == "win32":
    _base_chromium_flags += " --use-angle=d3d11"
elif _sys.platform == "darwin":
    _base_chromium_flags += " --use-angle=metal"
else:
    _base_chromium_flags += " --use-angle=egl"
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", _base_chromium_flags)

try:
    from PyQt6.QtCore import QCoreApplication, Qt
    from PyQt6.QtGui import QSurfaceFormat
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    fmt = QSurfaceFormat.defaultFormat()
    fmt.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(fmt)
except Exception:
    pass

from core import undo as undo_stack
from core import audio_devices
from core.echo import EchoGuard
from core.hotkey import PushToTalk
from memory import config_manager
from memory.memory_manager import search_memory

import core.boot_sentry
from core.sensorium import sensorium
from core.protocols import protocols
from core.local_brain import local_brain
import asyncio
import threading
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import os
import pyperclip
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sounddevice as sd
from google import genai
from google.genai import types
from ui import BrahmaUI
from core.request_intents import (
    _extract_skill_creation_goal,
    _is_gemini_limit_error,
    _looks_like_camera_request,
    _looks_like_code_request,
    _looks_like_daily_briefing_request,
    _looks_like_presentation_request,
    _looks_like_screen_request,
    _looks_like_spreadsheet_request,
    _looks_like_website_request,
    _wakeword_detected,
)
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory, auto_learn_interaction
)

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.meeting_assistant import MeetingAssistant
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.office_builder     import create_presentation, create_spreadsheet
from actions.docx_tools        import word_document
from actions.pdf_tools         import create_pdf
from actions.nexus_connect    import (
    connect_list_devices,
    connect_get_device,
    connect_get_capabilities,
    connect_execute,
    connect_pair_device,
    connect_disconnect_device,
)
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.attention_monitor import AttentionMonitor, speak_native, stop_native_speech, handle_call_action, read_event_preview, set_speech_sink
# from actions.daily_briefing import compile_daily_briefing
from or_client import client as openrouter_client
from workspace_store import store as workspace_store
from smart_home.service import SmartHomeService
from plugin_manager import PluginManager
from updater import restart_application, update_from_github

try:
    from dashboard.server import DashboardServer
except Exception:
    DashboardServer = None

try:
    from actions.instagram_mcp import start_daemon as start_ig_daemon, set_ig_prompt_callback
except ImportError:
    try:
        from actions.instagram_chat import start_daemon as start_ig_daemon, set_ig_prompt_callback
    except ImportError:
        start_ig_daemon = None

try:
    from nexus_connect.service import get_service as get_nexus_connect_service
except Exception:
    get_nexus_connect_service = None


from core.runtime_helpers import _is_port_in_use, _extract_gemini_text, _build_task_plan
from core.tool_declarations import TOOL_DECLARATIONS

from core.app_environment import (
    BASE_DIR, API_CONFIG_PATH, APP_SETTINGS_FILE, logger, PROMPT_PATH,
    STARTUP_LOG, LIVE_MODEL_FALLBACKS, LIVE_MODEL_OVERRIDE, LIVE_MODEL,
    CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
    LIVE_CONNECT_TIMEOUT, get_base_dir, _live_model_candidates,
    _connect_live_with_fallback, _get_api_key, _startup_log,
    _ensure_desktop_shortcut, _load_system_prompt,
)
_SINGLE_INSTANCE_MUTEX = None

from core.assistant_helpers import (
    _speak_daily_briefing, _gemini_text_reply, _ig_gemini_reply,
    _clipboard_gemini_reply, _update_memory_async, _memory_context_for_request,
)

# BrahmaLive is implemented in core.live_runtime to keep the entry point focused.
def main():
    _startup_log("main entered")
    global _SINGLE_INSTANCE_MUTEX
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            _MUTEX_NAME = "Global\\NexusCore_SingleInstance_AppMutex"
            _SINGLE_INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, wintypes.BOOL(True), _MUTEX_NAME)
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                _startup_log("Exiting duplicate Nexus instance (already running).")
                print("[NEXUS CORE] Another instance of Nexus Core is already running. Exiting.")
                return
        except Exception as _mex:
            _startup_log(f"Mutex check skipped: {_mex}")
    try:
        if update_from_github(BASE_DIR):
            _startup_log("updated from GitHub; restarting")
            restart_application(BASE_DIR)
            return
    except Exception as exc:
        _startup_log(f"GitHub update skipped: {exc}")
    _ensure_desktop_shortcut()
    ui = BrahmaUI(str(BASE_DIR / "assets" / "nexus_core_logo.png"), show_immediately=True)
    dashboard = None
    dashboard_enabled = DashboardServer is not None and not _is_port_in_use(8000)
    if DashboardServer is not None and not dashboard_enabled:
        _startup_log("dashboard disabled: port 8000 already in use")
        try:
            ui.write_log("SYS: Mobile Connect is already running in another Nexus Core instance.")
        except Exception:
            pass
    if dashboard_enabled:
        dashboard = DashboardServer()

    if dashboard is not None:
        def _start_dashboard_server():
            try:
                _startup_log("dashboard thread started")
                asyncio.run(dashboard.serve())
            except Exception as exc:
                _startup_log(f"dashboard thread error: {exc}")
                try:
                    ui.write_log(f"ERR: Mobile Connect server failed: {exc}")
                except Exception:
                    pass

        threading.Thread(target=_start_dashboard_server, daemon=True).start()
        _startup_log("dashboard thread spawned")

    nexus_connect = None
    nexus_connect_enabled = False
    if get_nexus_connect_service is not None:
        try:
            nexus_connect = get_nexus_connect_service(BASE_DIR)
            nexus_connect_enabled = bool(nexus_connect.gateway.config.enabled)
        except Exception as exc:
            _startup_log(f"nexus connect init failed: {exc}")
            try:
                ui.write_log(f"ERR: Nexus Connect failed to initialize: {exc}")
            except Exception:
                pass
            nexus_connect = None
    try:
        if nexus_connect is not None and hasattr(ui, "set_nexus_connect_service"):
            ui.set_nexus_connect_service(nexus_connect)
    except Exception:
        pass
    if nexus_connect is not None and nexus_connect_enabled:
        connect_port = int(getattr(nexus_connect.gateway.config, "port", 8765))
        if _is_port_in_use(connect_port):
            _startup_log(f"nexus connect disabled: port {connect_port} already in use")
            try:
                ui.write_log(f"SYS: Nexus Connect is already running on port {connect_port}.")
            except Exception:
                pass
        else:
            def _start_nexus_connect_server():
                try:
                    _startup_log("nexus connect thread started")
                    nexus_connect.start_background()
                    _startup_log("nexus connect thread spawned")
                except Exception as exc:
                    _startup_log(f"nexus connect thread error: {exc}")
                    try:
                        ui.write_log(f"ERR: Nexus Connect server failed: {exc}")
                    except Exception:
                        pass

            threading.Thread(target=_start_nexus_connect_server, daemon=True).start()



    ui.show_main()
    _startup_log("ui shown")

    # Start Nexus Passive Sensorium Engine (v2)
    try:
        def _on_sensorium_alert(alert_type: str, meta: dict):
            msg = meta.get("message", "System state change detected.")
            try:
                ui.write_log(f"🧠 SENSORIUM: {msg}")
            except Exception:
                pass
        sensorium.register_interjection_handler(_on_sensorium_alert)
        sensorium.start()
        _startup_log("passive sensorium daemon started")
    except Exception as exc:
        _startup_log(f"sensorium start failed: {exc}")

    try:
        from core.globe_window import GlobeWindow
        GlobeWindow.get_instance(parent=None)
        _startup_log("globe window initialized")
    except Exception as exc:
        _startup_log(f"globe window initialization failed: {exc}")
        try:
            ui.write_log(f"ERR: Globe window initialization failed: {exc}")
        except Exception:
            pass

    # Initialize plugin manager and load any plugins from ./plugins
    try:
        plugin_manager = PluginManager(BASE_DIR)
        plugin_manager.load_plugins()
    except Exception:
        plugin_manager = None

    def runner():
        from core.live_runtime import BrahmaLive, bind_runtime_globals
        bind_runtime_globals(globals())
        _startup_log("runner waiting api key")
        ui.wait_for_api_key()
        _startup_log("runner api key ready")
        nexus_core = BrahmaLive(
            ui,
            dashboard=dashboard,
            dashboard_started=dashboard is not None,
            enable_dashboard=dashboard_enabled,
        )

        # Wire proactive voice to Sensorium
        def _proactive_sensorium_voice(alert_type: str, meta: dict):
            # Meeting mode transitions
            if alert_type == "meeting_mode_enter":
                nexus_core._start_meeting_mode({
                    "app": meta.get("process", "Meeting"),
                    "title": meta.get("message", "Meeting Mode")
                })
            elif alert_type == "meeting_mode_exit":
                nexus_core._stop_meeting_mode("Meeting concluded. Normal audio levels restored.")

            # Morning greeting -> compile daily briefing and deliver via Charon voice
            elif alert_type == "morning_greeting":
                threading.Thread(
                    target=_speak_daily_briefing,
                    kwargs={"ui": nexus_core.ui, "speak": nexus_core.speak},
                    daemon=True,
                    name="morning-briefing-worker"
                ).start()
                return

            spoken_text = meta.get("speech")
            if spoken_text and not getattr(ui, "muted", False):
                try:
                    nexus_core.speak(spoken_text, proactive=True)
                except Exception as exc:
                    print(f"[Sensorium Speak Error]: {exc}")

        sensorium.register_interjection_handler(_proactive_sensorium_voice)
        try:
            if plugin_manager is not None:
                nexus_core.plugin_manager = plugin_manager
                plugin_manager.register_brahma(nexus_core)
                # allow plugins to run a startup hook
                try:
                    plugin_manager.dispatch("on_startup", nexus_core)
                except Exception:
                    pass
        except Exception:
            pass

        print(f"DEBUG: start_ig_daemon is {start_ig_daemon}")
        
        if start_ig_daemon:
            try:
                from actions.instagram_mcp import set_ig_prompt_callback
            except ImportError:
                from actions.instagram_chat import set_ig_prompt_callback

            def _ig_handler(thread_id, username, text, is_auto):
                if is_auto:
                    return _ig_gemini_reply(username, text)
                else:
                    nexus_core._ig_reply_mode = True
                    nexus_core._ig_pending_thread = {
                        "thread_id": thread_id,
                        "username": username,
                        "message": text
                    }
                    clean_text = (text or "").strip()
                    snippet = f": '{clean_text[:75]}...'" if len(clean_text) > 75 else (f": '{clean_text}'" if clean_text else "")
                    msg = f"You received a new Instagram message from {username}{snippet}. What should I reply, or should I take over the chat?"
                    ui.write_log(f"📱 Insta (@{username}): {clean_text or '[Media/Attachment]'}")
                    ui.write_log(f"Nexus Core: {msg}")
                    nexus_core.speak(msg)
                    return None
                
            set_ig_prompt_callback(_ig_handler)
            start_ig_daemon()

        # Background Email Watcher
        try:
            from actions.google_workspace_mcp import (
                start_email_daemon,
                set_email_prompt_callback,
                get_stored_gmail_credentials,
            )
            gmail_addr, gmail_pw = get_stored_gmail_credentials()
            if gmail_addr and gmail_pw:
                def _email_handler(sender, subject, msg_id):
                    clean_subj = (subject or "No Subject").strip()
                    subj_preview = f"'{clean_subj[:70]}...'" if len(clean_subj) > 70 else f"'{clean_subj}'"
                    msg = f"You received a new email from {sender} with subject: {subj_preview}."
                    ui.write_log(f"📧 Email ({sender}): {clean_subj}")
                    ui.write_log(f"Nexus Core: {msg}")
                    nexus_core.speak(msg)

                set_email_prompt_callback(_email_handler)
                start_email_daemon(poll_interval=25)
                print("[Nexus Core] Background email watcher started.")
        except Exception as e:
            print(f"[Nexus Core] Email daemon initialization notice: {e}")

        # Smart Clipboard Sentry
        try:
            from core.clipboard_sentry import ClipboardSentry
            _last_clipboard_speak_time = 0.0

            def _clipboard_callback(category: str, content: str):
                nonlocal _last_clipboard_speak_time
                now = time.time()
                clean = content.strip()

                if category == "error_traceback":
                    ui.write_log(f"📋 CLIPBOARD [Traceback]: {clean[:120]}...")
                    if now - _last_clipboard_speak_time > 180:
                        _last_clipboard_speak_time = now
                        msg = "I noticed an error traceback on your clipboard, sir. Would you like me to analyze and heal it?"
                        ui.write_log(f"Nexus Core: {msg}")
                        nexus_core.speak(msg, proactive=True)
                elif category == "youtube_url":
                    ui.write_log(f"📋 CLIPBOARD [YouTube]: {clean}")
                    if now - _last_clipboard_speak_time > 300:
                        _last_clipboard_speak_time = now
                        msg = "YouTube link detected. Let me know if you'd like a summary or key insights."
                        ui.write_log(f"Nexus Core: {msg}")
                        nexus_core.speak(msg, proactive=True)
                elif category == "github_url":
                    ui.write_log(f"📋 CLIPBOARD [GitHub]: {clean}")
                    if now - _last_clipboard_speak_time > 300:
                        _last_clipboard_speak_time = now
                        msg = "GitHub repository copied. I'm ready to clone or inspect the code whenever you are."
                        ui.write_log(f"Nexus Core: {msg}")
                        nexus_core.speak(msg, proactive=True)
                elif category in ("json_data", "sql_query", "code_snippet"):
                    ui.write_log(f"📋 CLIPBOARD [{category}]: {clean[:80]}...")
                    if now - _last_clipboard_speak_time > 600:
                        _last_clipboard_speak_time = now
                        reply = _clipboard_gemini_reply(clean[:1000])
                        if reply:
                            ui.write_log(f"Nexus Core (Clipboard): {reply}")
                            nexus_core.speak(reply, proactive=True)

            clip_sentry = ClipboardSentry(callback=_clipboard_callback)
            clip_sentry.start()
        except Exception as e_clip:
            logger.debug(f"[ClipboardSentry] Error: {e_clip}")

        # Ultron Autonomous Terminal Crash & Malfunction Monitor
        def _terminal_crash_monitor():
            crash_signal_path = get_user_data_dir() / "config" / "crash_signal.json"
            fatal_crash_path = BASE_DIR / "FATAL_CRASH.log"
            last_fatal_crash_mtime = fatal_crash_path.stat().st_mtime if fatal_crash_path.exists() else 0

            while True:
                time.sleep(0.5)
                try:
                    tb_to_heal = ""
                    if crash_signal_path.exists():
                        try:
                            with open(crash_signal_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            crash_signal_path.unlink(missing_ok=True)
                            tb_to_heal = data.get("traceback", "")
                        except Exception:
                            pass

                    if not tb_to_heal and fatal_crash_path.exists():
                        try:
                            curr_mtime = fatal_crash_path.stat().st_mtime
                            if curr_mtime > last_fatal_crash_mtime:
                                last_fatal_crash_mtime = curr_mtime
                                tb_to_heal = fatal_crash_path.read_text(encoding="utf-8")
                        except Exception:
                            pass

                    if tb_to_heal and tb_to_heal.strip():
                        print("[Ultron Crash Sentry] Detected unhandled terminal error! Initiating auto-repair...")
                        from actions.auto_heal_engine import AutoHealEngine
                        AutoHealEngine.record_last_error(tb_to_heal)
                        threading.Thread(
                            target=lambda: AutoHealEngine.heal_traceback(
                                tb_to_heal,
                                player=ui,
                                speak=nexus_core.speak,
                                module_name=""
                            ),
                            daemon=True,
                            name="ultron-bg-healer"
                        ).start()
                except Exception:
                    pass

        threading.Thread(target=_terminal_crash_monitor, daemon=True, name="ultron-crash-monitor").start()

        # Game Sentinel & Hardware Turbo Boost Autonomous Background Watchdog
        try:
            from core.game_sentinel import get_game_sentinel_manager
            def _game_hud_cb(title: str, pct: int, msg: str):
                try:
                    if hasattr(ui, "update_task_workspace"):
                        ui.update_task_workspace(status=title, output=msg, percent=pct)
                except Exception:
                    pass
            get_game_sentinel_manager().start_background_watchdog(
                poll_interval=3.5,
                speak_cb=nexus_core.speak,
                hud_cb=_game_hud_cb
            )
        except Exception as e_gs:
            logger.debug(f"[GameSentinel] Watchdog start error: {e_gs}")

        # Anticipatory Intelligence & Context Engine Watcher
        try:
            from core.anticipatory_watcher import get_anticipatory_watcher
            watcher = get_anticipatory_watcher()
            watcher.set_nudge_callback(lambda msg, cat: nexus_core.speak(msg))
            watcher.start()
        except Exception as e_watch:
            logger.debug(f"[AnticipatoryWatcher] Start error: {e_watch}")

        try:
            asyncio.run(nexus_core.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    def start_runner():
        threading.Thread(target=runner, daemon=True).start()

    start_runner()
    ui.show_main()
    ui.root.mainloop()


def __getattr__(name: str):
    """Lazily expose the extracted runtime class for legacy imports."""
    if name == "BrahmaLive":
        from core.live_runtime import BrahmaLive, bind_runtime_globals
        bind_runtime_globals(globals())
        globals()["BrahmaLive"] = BrahmaLive
        return BrahmaLive
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import sys
    import os
    import traceback

    # Intercept subprocess calls when running as PyInstaller .exe
    if len(sys.argv) >= 2:
        if sys.argv[1].endswith(".py") and os.path.exists(sys.argv[1]):
            # AgentExecutor is trying to run a dynamic script
            try:
                with open(sys.argv[1], 'r', encoding='utf-8') as f:
                    code = f.read()
                namespace = {"__name__": "__main__", "__file__": sys.argv[1]}
                exec(code, namespace)
                sys.exit(0)
            except Exception as e:
                traceback.print_exc()
                sys.exit(1)
        elif sys.argv[1] == "-m" and len(sys.argv) >= 3 and sys.argv[2] == "pip":
            try:
                from pip._internal.cli.main import main as pip_main
                sys.exit(pip_main(sys.argv[3:]))
            except ImportError:
                print("pip is not available in the compiled executable.")
                sys.exit(1)

    try:
        main()
    except Exception as e:
        with open("FATAL_CRASH.log", "w") as f:
            traceback.print_exc(file=f)
        raise
