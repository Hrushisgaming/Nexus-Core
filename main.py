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


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = get_user_data_dir() / "config" / "api_keys.json"
APP_SETTINGS_FILE = get_user_data_dir() / "config" / "app_settings.json"
logger = logging.getLogger("NexusCore")
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
STARTUP_LOG     = get_user_data_dir() / "logs" / "startup.log"
# Live (bidiGenerateContent) needs a native-audio Live model; text models such as
# gemini-3.5-flash-lite are rejected with a 1008 error. Order = preference.
# Override the first choice with:  NEXUS_LIVE_MODEL=models/gemini-3.1-flash-live-preview
LIVE_MODEL_FALLBACKS = (
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
    "models/gemini-3.1-flash-live-preview",
)
LIVE_MODEL_OVERRIDE = os.environ.get("NEXUS_LIVE_MODEL", "").strip()
LIVE_MODEL          = LIVE_MODEL_OVERRIDE or LIVE_MODEL_FALLBACKS[0]
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
LIVE_CONNECT_TIMEOUT = 12
_SINGLE_INSTANCE_MUTEX = None


def _live_model_candidates(client=None) -> list:
    """Prefer native-audio Live models advertised by this API key.

    Model discovery is best-effort: if the API does not expose model
    capabilities (or discovery is unavailable), retain known fallbacks.
    """
    discovered = []
    if client is not None:
        try:
            for model_info in client.models.list():
                name = str(getattr(model_info, "name", "") or "").strip()
                if not name:
                    continue
                lowered = name.lower()
                if "live" not in lowered and "native-audio" not in lowered:
                    continue
                actions = getattr(model_info, "supported_actions", None)
                if actions and not any("bidi" in str(action).lower() for action in actions):
                    continue
                if not name.startswith("models/"):
                    name = f"models/{name}"
                if name not in discovered:
                    discovered.append(name)
        except Exception as exc:
            _startup_log(f"Gemini model discovery unavailable; using fallbacks: {exc}")

    out = []
    preferred = (LIVE_MODEL_OVERRIDE,) if LIVE_MODEL_OVERRIDE else ()
    for model in (*preferred, *discovered, *LIVE_MODEL_FALLBACKS):
        if model and model not in out:
            out.append(model)
    _startup_log(f"Gemini Live model candidates: {', '.join(out)}")
    return out


async def _connect_live_with_fallback(client, build_config, models, timeout):
    """Try each Live model in order. Returns (connect_cm, session, model).

    build_config(model) -> LiveConnectConfig. If every model fails, the last
    error is re-raised so the caller's reconnect loop still applies.
    """
    last_exc = None
    for model in models:
        connect_cm = None
        try:
            connect_cm = client.aio.live.connect(model=model, config=build_config(model))
            session = await asyncio.wait_for(connect_cm.__aenter__(), timeout=timeout)
            return connect_cm, session, model
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            _startup_log(f"Gemini Live model {model} failed: {exc}")
            print(f"[NEXUS CORE] ⚠️ Live model {model} unavailable: {str(exc)[:160]}")
    raise last_exc if last_exc is not None else RuntimeError("No Live models configured")


def _get_api_key() -> str:
    """Get Gemini API key from either settings file location."""
    for path in [APP_SETTINGS_FILE, API_CONFIG_PATH]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("gemini_api_key", "")
            if key:
                return key
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
    return ""


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _startup_log(message: str) -> None:
    try:
        STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(STARTUP_LOG, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def _ensure_desktop_shortcut() -> None:
    if os.name != "nt":
        return

    marker_path = get_user_data_dir() / "config" / ".desktop_shortcut_created"
    if marker_path.exists():
        return

    try:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            desktop_raw, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            desktop_dir = Path(os.path.expandvars(desktop_raw))
        except Exception:
            desktop_dir = Path(os.path.expanduser("~")) / "Desktop"
            
        desktop_dir.mkdir(parents=True, exist_ok=True)
        shortcut_path = desktop_dir / "Nexus Core.lnk"
        script_path = BASE_DIR / "main.py"
        icon_path = BASE_DIR / "assets" / "nexus_app_icon.ico"

        if not icon_path.exists():
            icon_path = None

        python_exe = sys.executable
        if not python_exe:
            python_exe = shutil.which("python") or shutil.which("py") or "python"

        shortcut_target = python_exe
        shortcut_args = f'"{script_path}"'
        if getattr(sys, "frozen", False):
            shortcut_target = python_exe
            shortcut_args = ""

        powershell_exe = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell_exe is None:
            raise RuntimeError("PowerShell is not available")

        def _ps_escape(value: str) -> str:
            return value.replace("'", "''")

        icon_value = str(icon_path) if icon_path and icon_path.exists() else ""
        ps1_path = get_user_data_dir() / "config" / "create_desktop_shortcut.ps1"
        ps1_script = "\n".join([
            "$WshShell = New-Object -ComObject WScript.Shell",
            f"$Shortcut = $WshShell.CreateShortcut('{_ps_escape(str(shortcut_path))}')",
            f"$Shortcut.TargetPath = '{_ps_escape(shortcut_target)}'",
            f"$Shortcut.Arguments = '{_ps_escape(shortcut_args)}'",
            f"$Shortcut.WorkingDirectory = '{_ps_escape(str(BASE_DIR))}'",
            "$Shortcut.WindowStyle = 1",
            "$Shortcut.Description = 'Launch Nexus Core'",
            f"if ('{_ps_escape(icon_value)}') {{ $Shortcut.IconLocation = '{_ps_escape(icon_value)},0' }}",
            "$Shortcut.Save()",
        ])
        ps1_path.write_text(ps1_script, encoding="utf-8")

        subprocess.run(
            [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        marker_path.write_text("created", encoding="utf-8")
        _startup_log(f"desktop shortcut created at {shortcut_path}")
    except Exception as exc:
        _startup_log(f"desktop shortcut creation skipped: {exc}")


def _load_system_prompt() -> str:
    try:
        base_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        base_prompt = (
            "You are Nexus Core, a calm, direct, and professional AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool. "
            "If the user asks to create, build, launch, or open a website, always use the selected workspace folder."
        )
        
    try:
        from core.identity import identity
        ast_name = identity.get_assistant_name() or "Nexus Core"
        own_name = identity.get_owner_name() or "the user"
        role = identity.get_owner_role()
        mode = identity.get_behavior_mode()
        
        identity_str = f"You are {ast_name}. You are assisting {own_name}"
        if role:
            identity_str += f" (Role: {role}).\n"
        else:
            identity_str += ".\n"
            
        identity_str += f"Your current behavior mode is: {mode}.\n"
        
        custom = identity.get_custom_instructions()
        if custom:
            identity_str += f"Custom Instructions: {custom}\n\n"

        # Inject long-term memory cortex facts
        try:
            from core.memory_cortex import MemoryCortex
            recalled_facts = MemoryCortex.get_instance().build_context_prompt("user preferences identity hardware")
            if recalled_facts:
                identity_str += f"{recalled_facts}\n\n"
        except Exception as e_mem:
            print(f"[MemoryCortex] Error injecting memory into prompt: {e_mem}")

        # Inject continuously learned rules and behavioral directives
        try:
            from core.learned_rules import LearnedRulesEngine
            learned_directives = LearnedRulesEngine.get_prompt_injections()
            if learned_directives:
                identity_str += f"{learned_directives}\n\n"
        except Exception as e_rules:
            print(f"[LearnedRules] Error injecting rules into prompt: {e_rules}")

        return identity_str + base_prompt
    except Exception as e:
        print(f"Error injecting identity: {e}")
        try:
            from core.learned_rules import LearnedRulesEngine
            learned_directives = LearnedRulesEngine.get_prompt_injections()
            if learned_directives:
                return f"{learned_directives}\n\n" + base_prompt
        except Exception:
            pass
        return base_prompt


def _speak_daily_briefing(ui=None, speak=None) -> None:
    try:
        from actions.daily_briefing import compile_unified_briefing
        data, narrative = compile_unified_briefing()
        if ui:
            ui.show_daily_briefing(data)
            ui.write_log(f"Nexus Core: {narrative}")
        (speak or speak_native)(narrative)
    except Exception as e:
        print(f"[DailyBriefing] Error: {e}")
    
def _extract_gemini_text(response) -> str:
    text_parts: list[str] = []
    try:
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    text_parts.append(part_text)
    except Exception:
        pass

    text = "".join(text_parts).strip()
    if text:
        return text

    try:
        return (getattr(response, "text", "") or "").strip()
    except Exception:
        return ""


def _gemini_text_reply(prompt: str) -> str:
    client = genai.Client(
        api_key=_get_api_key(),
        http_options={"api_version": "v1beta"},
    )
    system_prompt = (
        "You are Nexus Core, a concise, helpful desktop assistant. "
        "Reply naturally and briefly. Do not mention internal implementation details."
    )
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"{system_prompt}\n\nUser: {prompt}",
        config={"temperature": 0.6},
    )
    return _extract_gemini_text(response)


def _ig_gemini_reply(username: str, text: str) -> str:
    system_prompt = (
        "You are Nexus Core, an AI personal assistant acting on behalf of your user. "
        "You have taken over their Instagram chat with the user's permission. "
        "Reply naturally, briefly, and conversationally to the incoming message. "
        "Do not sound like a bot. Keep your replies under 2 sentences."
    )
    prompt = f"Instagram DM from {username}: {text}"
    
    try:
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"},
        )
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"{system_prompt}\n\nUser: {prompt}",
            config={"temperature": 0.6},
        )
        return _extract_gemini_text(response)
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or _is_gemini_limit_error(e):
            print("[InstagramChat] Gemini Rate Limit hit, falling back to OpenRouter...")
            try:
                from or_client import client as openrouter_client
                return openrouter_client.chat(prompt, system=system_prompt)
            except Exception as or_e:
                print(f"[InstagramChat] OpenRouter fallback failed: {or_e}")
                return "Hey, I'm currently busy. I will get back to you later!"
        print(f"[InstagramChat] Gemini Reply Error: {e}")
        return "Hey, I'm currently busy. I will get back to you later!"


def _clipboard_gemini_reply(text: str) -> str:
    system_prompt = (
        "You are Nexus Core, a witty and helpful AI assistant. "
        "The user just copied the following text to their clipboard. "
        "Make a very short, interesting, or helpful 1-sentence comment or question about it. "
        "Do not offer to 'help' or ask 'how can I help'. Just make a standalone witty observation or summary."
    )
    prompt = text
    try:
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"},
        )
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"{system_prompt}\n\nClipboard Text: {prompt}",
            config={"temperature": 0.8},
        )
        return _extract_gemini_text(response)
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or _is_gemini_limit_error(e):
            try:
                from or_client import client as openrouter_client
                return openrouter_client.chat(prompt, system=system_prompt)
            except Exception:
                pass
        return "Interesting stuff you copied there!"


def _build_task_plan(text: str) -> list[str]:
    t = (text or "").lower()
    if any(word in t for word in ("presentation", "ppt", "slides", "deck")):
        return [
            "Understand the topic and goal",
            "Build a slide structure",
            "Generate and format the deck",
            "Open the finished presentation",
        ]
    if any(word in t for word in ("spreadsheet", "excel", "sheet", "table", "tracker", "budget")):
        return [
            "Read the data request",
            "Lay out sheets and columns",
            "Apply formulas and formatting",
            "Open the workbook",
        ]
    if any(word in t for word in ("word", "docx", "document", "report", "letter")):
        return [
            "Understand the document type",
            "Draft the structure and content",
            "Preserve formatting and polish",
            "Save the editable file",
        ]
    if any(word in t for word in ("website", "web site", "landing page", "saaS", "saas", "dashboard", "app")):
        return [
            "Interpret the brief",
            "Generate frontend and backend files",
            "Launch the local preview",
            "Debug and fix launch issues if needed",
        ]
    if any(word in t for word in ("browser", "website", "google", "search", "open url", "navigate")):
        return [
            "Open the browser",
            "Navigate to the target page",
            "Collect the needed information",
            "Return the result",
        ]
    if any(word in t for word in ("screen", "camera", "meeting", "call", "analyze", "analyse", "analyze")):
        return [
            "Capture the live screen or camera",
            "Inspect what is visible",
            "Answer with the important details",
            "Keep listening for follow-up commands",
        ]
    if any(word in t for word in ("fan", "light", "plug", "kasa", "atomberg", "smart home", "home device", "room", "bedroom", "living room", "kitchen", "office", "bathroom", "balcony")):
        return [
            "Identify the smart-home device or room",
            "Choose the correct action",
            "Send the command to the connected provider",
            "Confirm the result back to the user",
        ]
    return [
        "Understand the command",
        "Choose the right tool",
        "Execute the task",
        "Return the result",
    ]


_last_memory_input = ""

def _update_memory_async(user_text: str, brahma_text: str) -> None:
    global _last_memory_input

    user_text   = (user_text   or "").strip()
    brahma_text = (brahma_text or "").strip()

    if len(user_text) < 4 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    # Fast deterministic heuristic extraction (Pillar 5 - Living Knowledge Graph)
    try:
        learned = auto_learn_interaction(user_text, brahma_text)
        if learned:
            print(f"[Memory] 🧠 Auto-learned: {list(learned.keys())}")
    except Exception as exc:
        print(f"[Memory] ⚠️ Auto-learn error: {exc}")

    try:
        api_key = _get_api_key()
        if not should_extract_memory(user_text, brahma_text, api_key):
            return
        data = extract_memory(user_text, brahma_text, api_key)
        if data:
            update_memory(data)
            print(f"[Memory] ✅ {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")

def _memory_context_for_request(text: str) -> str:
    try:
        return workspace_store().memory_context(text, limit=5)
    except Exception:
        return ""


TOOL_DECLARATIONS = [
    {
        "name": "undo",
        "description": (
            "Roll back the last change made to the computer — reversing a file move, "
            "copy, create, or edit, a desktop organization, a volume or brightness change, "
            "or a Wi-Fi toggle. Call this whenever the user says undo, revert, take it back, "
            "put it back, restore, or says they made a mistake. "
            "Use action='list' when they ask what can be undone."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "undo (default) — reverse the last change | list — show what can be undone",
                },
            },
        },
    },
    {
        "name": "recall_memory",
        "description": (
            "Search long-term memory for stored facts, preferences, user info, projects, or history. "
            "Use this when the user asks 'do you remember', 'what is my...', or when context about "
            "past instructions or preferences is needed."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Keyword or topic to search for in memory (e.g. 'project', 'coffee', 'birthday', 'preference')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_protocol",
        "description": (
            "Activates or switches high-level macro system directives (protocols) across the PC. "
            "Call this whenever the user asks to activate, engage, start, run, or switch to a protocol: "
            "'deep_work' (deep focus mode), 'redline' (gaming / max power performance), "
            "'lockdown' (instant lock and security mute), or 'nightfall' (evening standby wrap-up)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "protocol": {
                    "type": "STRING",
                    "description": "Name of the protocol: 'deep_work', 'redline', 'lockdown', 'nightfall'",
                },
            },
            "required": ["protocol"],
        },
    },
    {
        "name": "get_sensorium_telemetry",
        "description": (
            "Read real-time situational awareness telemetry: current active application, "
            "window title, task dwell time in seconds, user idle time, CPU/RAM load, and battery health."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "manage_local_model",
        "description": (
            "Inspect, download, or switch offline local LLM models on the machine. "
            "action='status' returns available models and server health. "
            "action='pull' downloads a new model (e.g., 'qwen2.5:3b', 'llama3.2:3b'). "
            "action='toggle_offline' switches between local offline inference and cloud."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "One of: 'status', 'pull', 'toggle_offline', 'set_active'",
                },
                "model_name": {
                    "type": "STRING",
                    "description": "Model name when pulling or setting active (e.g. 'qwen2.5:3b', 'llama3.2:3b')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "dev_agent",
        "description": (
            "An autonomous coding agent that builds full projects, writes code, installs dependencies, "
            "runs the project, and automatically fixes errors. Use this when the user asks you to 'write a script', "
            "'build an app', 'code a program', or 'run a project'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {
                    "type": "STRING",
                    "description": "A very detailed description of what the project should do."
                },
                "language": {
                    "type": "STRING",
                    "description": "The programming language to use (e.g., 'python', 'javascript')"
                },
                "project_name": {
                    "type": "STRING",
                    "description": "A short, snake_case name for the project folder."
                }
            },
            "required": ["description"]
        }
    },
    {
        "name": "background_monitor",
        "description": (
            "Sets up a background monitor to check crypto prices, system RAM/CPU, or website uptime. "
            "Use this when the user asks to be alerted when a condition is met (e.g., 'tell me if RAM goes over 90%' or 'alert me if bitcoin drops below 50000')."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "'add' to create a monitor (default), 'list' to see active monitors."
                },
                "type": {
                    "type": "STRING",
                    "description": "One of: 'system', 'crypto', 'website'"
                },
                "target": {
                    "type": "STRING",
                    "description": "What to monitor (e.g. 'ram', 'cpu', 'bitcoin', 'https://example.com')"
                },
                "threshold": {
                    "type": "NUMBER",
                    "description": "The threshold value (e.g. 90 for 90%, 50000 for $50k)"
                },
                "condition": {
                    "type": "STRING",
                    "description": "'above' or 'below'"
                },
                "interval": {
                    "type": "INTEGER",
                    "description": "How often to check in seconds (default 60)"
                }
            },
            "required": []
        }
    },
    {
        "name": "system_manager",
        "description": (
            "Checks the system health (CPU, RAM, disk, battery) and lists top resource-hogging apps. "
            "Can also be used to forcefully close or kill frozen or heavy applications."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "What to do: 'status' to check system health (default), or 'kill' to close an app."
                },
                "process_name": {
                    "type": "STRING",
                    "description": "The exact name of the process to kill (if action is 'kill'), e.g. 'chrome.exe' or 'Spotify'"
                },
                "pid": {
                    "type": "INTEGER",
                    "description": "The PID of the process to kill (if action is 'kill')"
                }
            },
            "required": []
        }
    },
    {
        "name": "check_instagram_messages",
        "description": (
            "Checks your Instagram inbox for any recent unread or direct messages. "
            "Use this when the user asks 'do I have any messages', 'check my instagram', or similar."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "clipboard_processor",
        "description": (
            "Instantly reads the current text copied to the user's Windows clipboard. "
            "Use this whenever the user asks you to read, analyze, or fix what they just copied to their clipboard."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "instagram_reply",
        "description": "Replies to a pending Instagram message or takes over the Instagram chat in auto-mode.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Must be 'take_over' to handle it automatically, or 'manual_reply' to send a specific text message."
                },
                "reply_text": {
                    "type": "STRING",
                    "description": "The exact message to send to the user if action is 'manual_reply'."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "instagram_send_dm",
        "description": "Sends an Instagram direct message to a username or conversation thread, and automatically opens the chat in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient": {
                    "type": "STRING",
                    "description": "The Instagram username (e.g. 'john_doe') or numeric thread ID."
                },
                "message": {
                    "type": "STRING",
                    "description": "The message text to send."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the chat thread in your browser (default: true)."
                }
            },
            "required": ["recipient", "message"]
        }
    },
    {
        "name": "instagram_post_photo",
        "description": "Publishes a photo directly to your Instagram feed and automatically opens the live post in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {
                    "type": "STRING",
                    "description": "Absolute path to the JPG or PNG image file to publish."
                },
                "caption": {
                    "type": "STRING",
                    "description": "The caption text with optional hashtags for the post."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the published post in your browser (default: true)."
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "instagram_post_reel",
        "description": "Publishes a video or Reel directly to your Instagram account and automatically opens the live Reel in your browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "video_path": {
                    "type": "STRING",
                    "description": "Absolute path to the MP4 video file to publish."
                },
                "caption": {
                    "type": "STRING",
                    "description": "The caption text with optional hashtags."
                },
                "thumbnail_path": {
                    "type": "STRING",
                    "description": "Optional path to cover image."
                },
                "open_in_browser": {
                    "type": "BOOLEAN",
                    "description": "Whether to auto-open the published Reel in your browser (default: true)."
                }
            },
            "required": ["video_path"]
        }
    },
    {
        "name": "instagram_get_user_info",
        "description": "Looks up profile details, bio, follower count, following count, and verified badge for any Instagram handle.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "username": {
                    "type": "STRING",
                    "description": "The Instagram username to look up (e.g. 'natgeo' or 'openai')."
                }
            },
            "required": ["username"]
        }
    },
    {
        "name": "open_app",
        "description": (
            "Opens any application on the Windows computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": (
            "Fetches live real-time weather, forecast, and temperature for any city or location. "
            "Call this whenever the user asks about the weather, temperature, rain, or forecast for any city or location."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, Instagram DMs, or other messaging platform. Can also upload media to Instagram when mode=upload and media_path is supplied.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name for DMs"},
                "message_text": {"type": "STRING", "description": "The message to send or Instagram caption"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, Instagram, etc."},
                "mode":         {"type": "STRING", "description": "dm | upload (Instagram only; default: dm)"},
                "media_path":   {"type": "STRING", "description": "Optional image/video path for Instagram uploads"}
            },
            "required": ["platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."},
                "confirmed":   {"type": "STRING", "description": "Pass 'yes' if the user explicitly confirmed a dangerous action like 'shutdown' or 'restart'."}
            },
            "required": []
        }
    },
    {
        "name": "smart_home_control",
        "description": (
            "Controls connected smart-home devices such as Atomberg fans and TP-Link Kasa lights/plugs. "
            "Use when the user asks to turn devices on or off, set fan speed, change brightness, or control a room."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Natural language smart-home command"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "connect_list_devices",
        "description": (
            "Lists devices connected to Nexus Connect. Use when the user asks what devices are connected, "
            "what is online, or wants a simple inventory of paired devices."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "connect_get_device",
        "description": (
            "Gets the details for one connected device by name, id, or natural reference such as my phone, "
            "my laptop, my PC, or my tablet."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "connect_get_capabilities",
        "description": (
            "Returns the capabilities and permissions reported by a connected device. "
            "Use before trying any device command."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "connect_execute",
        "description": (
            "Routes a Nexus Connect command to a paired device through the gateway. "
            "Use for actions such as launch_app, open_url, get_battery, capture_screen, take_photo, "
            "clipboard_get, clipboard_set, send_file, receive_file, media_play, media_pause, volume_set, "
            "notification_list, get_device_info, close_app, mouse_move, keyboard_type, unlock_phone, file_list, file_read, file_write, file_delete."
            "Do not execute device operations directly anywhere else."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Target device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
                "action": {"type": "STRING", "description": "Command to execute on the device"},
                "parameters": {"type": "OBJECT", "description": "Action parameters"},
            },
            "required": ["device", "action"]
        }
    },
    {
        "name": "unlock_device",
        "description": "Unlocks a paired Android device using its saved PIN.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "Device name or ID to unlock"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "connect_pair_device",
        "description": (
            "Creates or approves Nexus Connect pairing. Use to generate a QR code / pairing code for a new device, "
            "or to approve a pending pairing request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device_name": {"type": "STRING", "description": "Optional device name shown in the pairing flow"},
                "platform": {"type": "STRING", "description": "android | windows | ios | tablet | other"},
                "pending_id": {"type": "STRING", "description": "Pending request id to approve"},
            },
            "required": []
        }
    },
    {
        "name": "connect_disconnect_device",
        "description": (
            "Disconnects a device from Nexus Connect and marks it offline. "
            "Use when the user asks to disconnect, log out, or stop a paired device."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device": {"type": "STRING", "description": "Target device name, id, or natural reference"},
                "target": {"type": "STRING", "description": "Alias for device"},
                "device_id": {"type": "STRING", "description": "Exact device id"},
                "name": {"type": "STRING", "description": "Exact device name"},
                "query": {"type": "STRING", "description": "Search query"},
                "reason": {"type": "STRING", "description": "Optional reason for disconnect"},
            },
            "required": ["device"]
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Complete browser automation powered by Microsoft Playwright MCP. "
            "Use for: opening websites, web searching, navigating, semantic accessibility snapshots, "
            "clicking elements or snapshot references, typing, form filling, hovering, executing JavaScript, "
            "taking screenshots, managing tabs, and any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | navigate | search | click | hover | type | scroll | fill_form | snapshot | find | evaluate | screenshot | press | back | forward | refresh | open_tab | new_tab | switch_tab | list_tabs | wait_for | select_option | upload | console | network | close"},
                "url":         {"type": "STRING", "description": "URL for go_to/navigate"},
                "query":       {"type": "STRING", "description": "Search query or search term for find"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type/hover"},
                "element":     {"type": "STRING", "description": "Snapshot element reference (e.g. e2)"},
                "text":        {"type": "STRING", "description": "Text to click, type, or wait for"},
                "description": {"type": "STRING", "description": "Element description for smart targeting"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action (Enter, Tab, Escape, etc.)"},
                "expression":  {"type": "STRING", "description": "JavaScript expression to evaluate in page"},
                "path":        {"type": "STRING", "description": "File path for screenshot or upload"},
                "tab":         {"type": "INTEGER", "description": "1-based tab index for switch_tab"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": (
            "Manages files and folders: open, close, list, create, delete, move, copy, rename, read, write, find, disk usage, "
            "and organizing a desktop or any folder into subfolders by type/date. Can also be used to explore and manage files on a connected Android phone."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "open | close | list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | organize_folder | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home. For android, use paths like downloads, documents, photos, movies, root."},
                "target":      {"type": "STRING", "description": "If operating on an Android device, provide the device name or ID. Leave empty for PC local files."},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
                "mode":        {"type": "STRING", "description": "by_type or by_date for organize actions"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_organizer",
        "description": (
            "Smart Desktop & Downloads Organizer MCP with safe transaction rollback (undo), "
            "dry-run previews, duplicate file detection, empty folder cleanup, and archiving. "
            "Use when the user asks to organize, preview, declutter, clean, or find duplicate files on the desktop, downloads, or any folder."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "preview | organize | undo | find_duplicates | clean_empty_folders | archive_old"},
                "target": {"type": "STRING", "description": "Target folder: 'desktop' | 'downloads' | 'documents' | 'pictures' or a custom directory path"},
                "mode":   {"type": "STRING", "description": "by_type (categorizes into Documents, Images/Screenshots, Installers, Code, Archives, etc.) or by_date (YYYY-MM)"},
                "days":   {"type": "INTEGER", "description": "Number of days for archive_old (default: 30)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, preview, clean, undo, find_duplicates, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | preview | clean | undo | find_duplicates | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "file_processor",
        "description": (
            "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
            "text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
            "ALWAYS call this tool when a non-Word file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx via word_document; txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
        }
    },
    {
        "name": "presentation_builder",
        "description": (
            "Creates editable PowerPoint presentations (.pptx) from a structured slide outline. "
            "Nexus Core automatically infers the best visual style from the topic, searches for a matching online template when available, "
            "reuses cached templates, and falls back to the built-in designer if no suitable template is found. "
            "Use when the user asks for a deck, slideshow, presentation, pitch deck, or report slides."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Presentation title"},
                "subtitle": {"type": "STRING", "description": "Optional subtitle or audience line"},
                "theme": {
                    "type": "STRING",
                    "description": "Optional presentation theme or visual direction such as neon, corporate, luxury, academic, sunset, or creative. If omitted, Nexus Core infers the best style automatically."
                },
                "outline": {
                    "type": "STRING",
                    "description": "Slide-by-slide outline. Use blank lines to separate slides if slides array is omitted."
                },
                "slides": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING", "description": "Slide title"},
                            "kicker": {"type": "STRING", "description": "Short all-caps kicker"},
                            "bullets": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Bullet points for the slide"
                            },
                            "notes": {"type": "STRING", "description": "Optional speaker note or footnote"}
                        },
                        "required": ["title"]
                    },
                    "description": "Structured slides. Preferred when the model can format the deck directly."
                },
                "output_path": {"type": "STRING", "description": "Optional output path for the .pptx"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["title"]
        }
    },
    {
        "name": "spreadsheet_builder",
        "description": (
            "Creates editable Excel workbooks (.xlsx) from structured sheet data. "
            "Use for trackers, tables, analysis workbooks, budgets, planners, and other spreadsheet requests."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Workbook title"},
                "worksheets": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING", "description": "Worksheet name"},
                            "title": {"type": "STRING", "description": "Optional sheet title row"},
                            "headers": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"},
                                "description": "Column headers"
                            },
                            "rows": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"},
                                },
                                "description": "Data rows"
                            },
                            "chart": {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {"type": "STRING", "description": "bar | line | pie"},
                                    "title": {"type": "STRING", "description": "Chart title"},
                                    "anchor": {"type": "STRING", "description": "Cell anchor such as E2"},
                                    "x_axis": {"type": "STRING", "description": "Optional x-axis title"},
                                    "y_axis": {"type": "STRING", "description": "Optional y-axis title"},
                                }
                            }
                        },
                        "required": ["name"]
                    },
                    "description": "One or more worksheets to create."
                },
                "output_path": {"type": "STRING", "description": "Optional output path for the .xlsx"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["title"]
        }
    },
    {
        "name": "word_document",
        "description": (
            "Creates, edits, reads, summarizes, extracts text from, and opens editable Word documents (.docx). "
            "Use for Word document requests, letters, reports, headings, bullets, formatting edits, and preserving existing formatting."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create | create_letter | create_report | read | summarize | extract_text | append | replace_text | add_heading | add_bullets | reformat | open"
                },
                "file_path": {"type": "STRING", "description": "Existing .docx file path for read/edit/open actions"},
                "output_path": {"type": "STRING", "description": "Optional output path for the saved .docx"},
                "title": {"type": "STRING", "description": "Document title"},
                "doc_type": {"type": "STRING", "description": "letter | report | generic"},
                "content": {"type": "STRING", "description": "Main body content or text to append"},
                "body": {"type": "STRING", "description": "Body text for letter/report creation"},
                "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Paragraphs to add"},
                "bullets": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Bullet items to add"},
                "numbered": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Numbered items to add"},
                "sections": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Structured sections with heading/body/bullets"},
                "replacements": {"type": "OBJECT", "description": "Find/replace mapping for formatting-preserving edits"},
                "find": {"type": "STRING", "description": "Text to find for simple replace_text edits"},
                "replace": {"type": "STRING", "description": "Replacement text for simple replace_text edits"},
                "heading": {"type": "STRING", "description": "Heading text to append"},
                "level": {"type": "INTEGER", "description": "Heading level 1-3"},
                "recipient": {"type": "STRING", "description": "Letter recipient"},
                "salutation": {"type": "STRING", "description": "Custom letter salutation"},
                "closing": {"type": "STRING", "description": "Custom letter closing"},
                "date": {"type": "STRING", "description": "Letter date"},
                "author": {"type": "STRING", "description": "Document author"},
                "subject": {"type": "STRING", "description": "Document subject"},
                "open_after": {"type": "BOOLEAN", "description": "Open the saved document after writing (default: true)"},
                "save": {"type": "BOOLEAN", "description": "Save large generated summaries to a text file"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "pdf_document",
        "description": (
            "Creates editable-style PDF documents (.pdf) from structured content or converts DOCX / text files into PDFs. "
            "Use for PDF creation, PDF exports, and PDF generation requests that need a direct file output."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create | create_report | create_letter | convert"
                },
                "file_path": {"type": "STRING", "description": "Existing file to convert, typically .docx or .txt"},
                "output_path": {"type": "STRING", "description": "Optional output path for the saved .pdf"},
                "title": {"type": "STRING", "description": "PDF title"},
                "subtitle": {"type": "STRING", "description": "Optional subtitle"},
                "content": {"type": "STRING", "description": "Main body content"},
                "body": {"type": "STRING", "description": "Main body content"},
                "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Paragraphs to add"},
                "bullets": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Bullet items to add"},
                "numbered": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Numbered items to add"},
                "sections": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Structured sections with heading/body/bullets"},
                "recipient": {"type": "STRING", "description": "Letter recipient"},
                "salutation": {"type": "STRING", "description": "Custom letter salutation"},
                "closing": {"type": "STRING", "description": "Custom letter closing"},
                "date": {"type": "STRING", "description": "Letter date"},
                "author": {"type": "STRING", "description": "Document author"},
                "subject": {"type": "STRING", "description": "Document subject"},
                "auto_open": {"type": "BOOLEAN", "description": "Open the file after creating it (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "shutdown_nexus",
        "description": (
            "Shuts down the assistant completely. "
        "Call this when the user expresses intent to end the conversation, "
        "close the assistant, say goodbye, or stop Nexus Core. "
        "The user can say this in ANY language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. User, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "spotify_controller",
        "description": (
            "Plays and controls music via Spotify, Spotify MCP, and Google Chrome. "
            "ALWAYS use this tool whenever the user asks to play any song, music, track, or artist "
            "(e.g. 'play Starboy', 'play music on Spotify'), or control playback "
            "('pause the music', 'resume', 'skip song', 'next track', 'volume up', 'volume down', 'mute'). "
            "Do NOT use open_app for playing songs."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "search_play | play | pause | toggle | next | previous | volume_up | volume_down | set_volume | get_now_playing | get_playlists | get_queue | get_devices | auth | mute | open_spotify (default: search_play)"
                },
                "query": {
                    "type": "STRING",
                    "description": "Song title, artist name, album, or playlist to search and play"
                },
                "volume": {
                    "type": "NUMBER",
                    "description": "Volume level (optional)"
                },
                "device_id": {
                    "type": "STRING",
                    "description": "Optional Spotify Connect playback device ID"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "calendar_scheduler",
        "description": (
            "Manages calendar events, appointments, and schedules. "
            "Use whenever the user asks to schedule a meeting, check upcoming events, "
            "view schedule for today/tomorrow, or remove an event."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "add_event | list_events | check_day | delete_event | get_upcoming | export_ics"
                },
                "title": {
                    "type": "STRING",
                    "description": "Title or summary of the meeting/event"
                },
                "date": {
                    "type": "STRING",
                    "description": "Date (YYYY-MM-DD or 'today', 'tomorrow')"
                },
                "time": {
                    "type": "STRING",
                    "description": "Time (HH:MM in 24h format, e.g. '14:30')"
                },
                "duration_minutes": {
                    "type": "NUMBER",
                    "description": "Duration in minutes (default: 30)"
                },
                "location": {
                    "type": "STRING",
                    "description": "Location or meeting link (optional)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "daily_briefing",
        "description": (
            "Delivers a complete daily briefing including time, date, today's schedule/calendar events, "
            "and top world & tech headlines. Use whenever the user asks for their daily briefing, morning update, "
            "or what's happening today."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Optional news category: all (default), tech, world"
                }
            },
            "required": []
        }
    },
    {
        "name": "google_workspace",
        "description": (
            "Full Google Workspace MCP for Gmail, Calendar, and Google Drive automation. "
            "Supports: reading unread emails, listing inbox, searching emails, sending emails; "
            "listing calendar events, adding calendar events; "
            "searching Drive files, reading Drive files, and uploading files to Google Drive."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "gmail | calendar | drive"
                },
                "action": {
                    "type": "STRING",
                    "description": "gmail actions: 'list', 'unread', 'read', 'search', 'send' | calendar actions: 'list', 'add' | drive actions: 'list', 'search', 'read', 'upload'"
                },
                "to": {
                    "type": "STRING",
                    "description": "Recipient email address for sending emails"
                },
                "subject": {
                    "type": "STRING",
                    "description": "Subject for sending or searching emails"
                },
                "body": {
                    "type": "STRING",
                    "description": "Body message for email"
                },
                "query": {
                    "type": "STRING",
                    "description": "Search query for Gmail or Drive"
                },
                "email_id": {
                    "type": "STRING",
                    "description": "ID of email to read"
                },
                "title": {
                    "type": "STRING",
                    "description": "Title/summary for calendar event"
                },
                "date": {
                    "type": "STRING",
                    "description": "Date for calendar event (YYYY-MM-DD or today/tomorrow)"
                },
                "time": {
                    "type": "STRING",
                    "description": "Time for calendar event (HH:MM)"
                },
                "duration_minutes": {
                    "type": "NUMBER",
                    "description": "Duration in minutes"
                },
                "file_path": {
                    "type": "STRING",
                    "description": "Local file path or name for Drive upload/read"
                }
            },
            "required": ["service", "action"]
        }
    },
    {
        "name": "system_diagnostics",
        "description": (
            "Local OS Hardware and System Diagnostics MCP. "
            "Checks battery health, power status, CPU usage and thermals, RAM utilization and top memory/CPU hogs, "
            "storage drive space, and controls multi-monitor display brightness. Can safely terminate frozen apps."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | ram_hogs | cpu_hogs | kill | brightness | battery | disk"
                },
                "target": {
                    "type": "STRING",
                    "description": "Application name (e.g. 'chrome', 'notepad') or numerical PID to terminate"
                },
                "level": {
                    "type": "NUMBER",
                    "description": "Display brightness level from 0 to 100"
                },
                "monitor": {
                    "type": "STRING",
                    "description": "Optional target monitor name or index"
                },
                "relative": {
                    "type": "BOOLEAN",
                    "description": "Whether brightness level is relative (+10, -10)"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maximum number of processes to return (default: 5)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "auto_heal",
        "description": (
            "Autonomous Self-Healing and Continuous Self-Improvement System. "
            "Analyzes tracebacks/exceptions in first-party codebase, synthesizes surgical code hotfixes, "
            "validates AST syntax in safety sandbox, applies hotfixes with atomic backup, or rolls back changes. "
            "Also manages learned behavioral rules and persistent user directives."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | heal | history | rollback | learn_rule | list_rules"
                },
                "error_traceback": {
                    "type": "STRING",
                    "description": "The exact exception traceback or error message to heal"
                },
                "rule_text": {
                    "type": "STRING",
                    "description": "The user preference, habit, or behavioral directive to remember permanently"
                },
                "category": {
                    "type": "STRING",
                    "description": "Category for learned rule (general, formatting, workflow, habit)"
                },
                "patch_id": {
                    "type": "STRING",
                    "description": "Specific patch ID to rollback (default: latest)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "circuit_assembler",
        "description": "Designs a safe electronic wiring schematic from component names or a screen image, then shows the interactive circuit HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "assemble_components | analyze_screen | show_schematic"},
                "components": {"type": "STRING", "description": "Electronic components, such as Arduino Uno, ESP32, DHT11, or HC-SR04."},
                "query": {"type": "STRING", "description": "Circuit goal or wiring question."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "geospatial_globe",
        "description": "Opens Nexus Core's interactive 3D map for routes, live aircraft, weather, earthquakes, nearby places, and ISS tracking.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open | route | drive | location | fly_to | weather | flights | iss | earthquakes | nearby | radar | inspect"},
                "origin": {"type": "STRING", "description": "Origin city for a route."},
                "destination": {"type": "STRING", "description": "Destination city for a route."},
                "location": {"type": "STRING", "description": "City or area to focus on."},
                "query": {"type": "STRING", "description": "Nearby place category, such as hospitals, fuel, or restaurants."},
                "min_magnitude": {"type": "NUMBER", "description": "Minimum earthquake magnitude to display."},
                "enable": {"type": "BOOLEAN", "description": "Enable or disable the weather radar overlay."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "call_screening",
        "description": "Screens an incoming call with Nexus Core as an AI attendant. Answering always waits for the user to confirm on the Echo HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | take_over | hang_up"},
                "caller": {"type": "STRING", "description": "Caller name or notification title."},
                "app": {"type": "STRING", "description": "Calling application, such as Phone Link, WhatsApp, or Teams."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "skill_forge",
        "description": "Use whenever the user explicitly asks to make, create, build, or add a new skill or feature. Starts creation immediately, validates the generated Python feature, and registers it for use. Do not use screen analysis for feature-creation requests.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "forge | list"},
                "goal": {"type": "STRING", "description": "What new capability the skill should provide."},
                "skill_name": {"type": "STRING", "description": "Optional short name for the skill."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "dynamic_skill",
        "description": "Lists and runs installed Nexus Core skills, including stock, crypto, cricket, speed-test, and ISS examples. Running a skill requires user confirmation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "list | run"},
                "skill_name": {"type": "STRING", "description": "Skill name to run."},
                "arguments": {"type": "OBJECT", "description": "Arguments for the selected skill."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "calorie_counter",
        "description": (
            "Analyzes food and meals to report calories, macronutrients (protein, carbs, fat, fiber), "
            "and dietary advice. Can capture a live snapshot via webcam, inspect an image file, "
            "or analyze a spoken/typed meal description. "
            "Use whenever the user asks about the calories or nutritional value of food."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Food or meal description (e.g. 'How many calories in this plate?', 'I had 2 eggs and toast')."
                },
                "image_path": {
                    "type": "STRING",
                    "description": "Optional local file path to a food photo."
                },
                "use_camera": {
                    "type": "BOOLEAN",
                    "description": "True to capture a live photo from the webcam."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "pushup_counter",
        "description": (
            "Live AI workout and repetition counter. Tracks reps, tempo, and calories burned "
            "for pushups, squats, and bodyweight exercises through the webcam with live HUD overlay. "
            "Use whenever the user asks to count pushups, track squats, or start a workout."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "User's request (e.g. 'count my pushups', 'track 20 squats')."
                },
                "exercise": {
                    "type": "STRING",
                    "description": "pushups | squats | general"
                },
                "target": {
                    "type": "INTEGER",
                    "description": "Target rep goal (e.g. 20)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "upload_video",
        "description": (
            "Automates video publishing to TikTok, YouTube Shorts, or Instagram. "
            "Auto-locates recent videos on Desktop/Downloads, generates viral SEO captions and tags, "
            "copies metadata to clipboard, reveals the file in Explorer, and launches the studio uploader."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {
                    "type": "STRING",
                    "description": "Video topic, caption brief, or context (in user's language)."
                },
                "platform": {
                    "type": "STRING",
                    "description": "tiktok | youtube | instagram (default: tiktok)"
                },
                "video_path": {
                    "type": "STRING",
                    "description": "Optional path to the video file to publish."
                }
            },
            "required": ["description"]
        }
    },
    {
        "name": "reverse_engineer",
        "description": (
            "Reverse engineer any website, desktop application, or native binary without source code. "
            "Extracts API surfaces, network schemas, client bundles, or native pseudocode, "
            "and can automatically remake/replicate a clean working version in your project. "
            "Supports web URLs (https://...), desktop apps (.exe, Electron .asar), and .wasm."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {
                    "type": "STRING",
                    "description": "Target website URL (e.g. 'https://example.com') or local file/folder path (e.g. 'C:/Apps/target.exe' or 'D:/electron-app')"
                },
                "action": {
                    "type": "STRING",
                    "description": "'analyze' (architectural breakdown), 'remake' (generate a working clone project), 'api_surface' (extract backend API schemas only), 'decompile' (pseudocode of native binary or JS bundle)"
                },
                "feature": {
                    "type": "STRING",
                    "description": "Specific feature, component, or behavior to investigate (e.g. 'search modal', 'auth flow', 'database query')"
                },
                "destination": {
                    "type": "STRING",
                    "description": "Optional local folder to write the remade code, assets, or extracted schemas into"
                }
            },
            "required": ["target"]
        }
    },
    {
        "name": "generate_image",
        "description": (
            "Generates stunning AI images, concept art, photorealistic photos, and 3D renders from text prompts. "
            "Saves the high-resolution image to Desktop, shows a preview on the HUD, and opens it automatically. "
            "Use whenever the user asks to generate, create, draw, paint, or visualize an image or picture."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Detailed text description of the image to generate."
                },
                "style": {
                    "type": "STRING",
                    "description": "Style: 'photorealistic', 'cyberpunk', 'anime', 'cinematic_3d', 'digital_art', 'concept_art', 'fantasy', or 'minimalist' (default: photorealistic)."
                },
                "aspect_ratio": {
                    "type": "STRING",
                    "description": "Aspect ratio: '1:1' (square), '16:9' (landscape), '9:16' (portrait) (default: 1:1)."
                },
                "destination": {
                    "type": "STRING",
                    "description": "Optional custom folder path to save the generated image."
                }
            },
            "required": ["prompt"]
        }
    },
    # =========================================================================
    # UNIVERSAL CLAUDE-CODE & OPENAI CODEX TOOL SUITE (PROJECT OMNIPOTENCE)
    # =========================================================================
    {
        "name": "bash",
        "description": "Execute a shell or PowerShell command on the local machine with captured output, timeouts, and smart truncation. Essential for compilers, package managers (npm, pip, cargo), git, and running scripts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "The exact shell or PowerShell command to execute"},
                "timeout": {"type": "INTEGER", "description": "Timeout in seconds (default 120)"},
                "cwd": {"type": "STRING", "description": "Optional working directory path"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "file_read",
        "description": "Read file contents with line numbers starting at offset up to limit lines. Line numbers help target surgical file_edit updates.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Relative or absolute path to the file"},
                "offset": {"type": "INTEGER", "description": "Line number to start reading from (1-based, default 1)"},
                "limit": {"type": "INTEGER", "description": "Maximum number of lines to read (default 2000)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "file_edit",
        "description": "Surgically edit an existing file by replacing old_string with new_string. Whitespace, indentation, and newlines must match exactly. Fails safely if old_string is not found or ambiguous.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path to the file to edit"},
                "old_string": {"type": "STRING", "description": "Exact text block to replace, including exact indentation"},
                "new_string": {"type": "STRING", "description": "Replacement text block"},
                "replace_all": {"type": "BOOLEAN", "description": "Whether to replace every occurrence (default false)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    },
    {
        "name": "file_write",
        "description": "Write or overwrite a file with full content. Automatically creates any missing parent directories.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path to the file to write"},
                "content": {"type": "STRING", "description": "Complete text content of the file"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "glob",
        "description": "Fast recursive file search by pattern (e.g. '**/*.py', 'src/**/*.tsx', '*.json'). Automatically skips .git, node_modules, .venv, dist.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Glob pattern to match"},
                "path": {"type": "STRING", "description": "Subdirectory to search inside (default '.')"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of files to return (default 100)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "grep",
        "description": "Fast regex and keyword search across file contents with line numbers and file paths. Essential for finding symbols, functions, and errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Regex pattern or literal text to search for"},
                "path": {"type": "STRING", "description": "Subdirectory to search inside (default '.')"},
                "case_sensitive": {"type": "BOOLEAN", "description": "Case sensitive matching (default true)"},
                "max_results": {"type": "INTEGER", "description": "Maximum number of matches (default 50)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "python_repl",
        "description": "Execute Python code in an isolated computational sandbox (Codex / Advanced Data Analysis). Use for math calculations, data analysis with pandas/numpy, and generating charts/plots with matplotlib.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING", "description": "Valid Python code to execute"},
                "timeout": {"type": "INTEGER", "description": "Execution timeout in seconds (default 60)"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "git_manager",
        "description": "Autonomous Git version control operations: status, diff, log, commit, branch, checkout, add, push, pull.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Git action: 'status', 'diff', 'diff_staged', 'log', 'commit', 'branch', 'checkout', 'new_branch', 'push', 'pull'"},
                "message": {"type": "STRING", "description": "Commit message (required for 'commit')"},
                "branch": {"type": "STRING", "description": "Branch name (for 'branch', 'checkout', 'new_branch')"},
                "cwd": {"type": "STRING", "description": "Optional repository path"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "test_and_heal",
        "description": "Run automated test suites (pytest, npm test, cargo test) and analyze failure stack traces to verify code functionality.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Test command to execute (default 'pytest')"},
                "cwd": {"type": "STRING", "description": "Optional working directory"}
            }
        }
    },
    {
        "name": "subagent_task",
        "description": "Spawn an autonomous child subagent (researcher, coder, tester) to perform parallel background tasks without cluttering the primary conversation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "role": {"type": "STRING", "description": "Role: 'researcher' (code survey/read-only), 'coder' (build/execution), 'tester' (test verification)"},
                "prompt": {"type": "STRING", "description": "Specific task instructions for the subagent"},
                "workspace": {"type": "STRING", "description": "Optional workspace directory path"},
                "wait": {"type": "BOOLEAN", "description": "Whether to wait for completion (default true)"}
            },
            "required": ["role", "prompt"]
        }
    },
    {
        "name": "mcp_status",
        "description": "Check the connection status and discovered tools of all configured MCP servers (Model Context Protocol).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "skill_execute",
        "description": "Execute or consult an installed community or markdown skill (e.g. 'code-review', 'test-driven-development', 'git-workflow', 'database-architect', 'docker-devops', 'web-scraper-stealth'). Returns the comprehensive guidelines, directives, and protocols for the skill.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "Name of the skill to execute/consult"},
                "task": {"type": "STRING", "description": "Specific user task or question to apply the skill to"}
            },
            "required": ["skill_name"]
        }
    },
    {
        "name": "skill_install",
        "description": "Install a new markdown skill into Nexus Core's skills/ library, allowing Nexus Core to perpetually learn new procedures and protocols from the internet or user.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "Short slug name for the skill (e.g. 'pdf-analyzer')"},
                "content": {"type": "STRING", "description": "Full Markdown/YAML SKILL.md definition"}
            },
            "required": ["skill_name", "content"]
        }
    },
    {
        "name": "skill_list",
        "description": "List all installed community and markdown skills available in Nexus Core.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "todo_write",
        "description": "Claude Code style task list tracker. Update the active multi-step plan checklist with status for each task (pending, in_progress, completed).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "todos": {
                    "type": "ARRAY",
                    "description": "List of task objects: [{'id': '1', 'task': '...', 'status': 'pending'|'in_progress'|'completed'}]",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "task": {"type": "STRING"},
                            "status": {"type": "STRING"}
                        },
                        "required": ["id", "task", "status"]
                    }
                }
            },
            "required": ["todos"]
        }
    },
    {
        "name": "todo_read",
        "description": "Read the active task checklist and current step progress.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },

]


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
        from core.live_runtime import BrahmaLive
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
