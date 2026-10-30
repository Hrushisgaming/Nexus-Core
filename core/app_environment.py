"""Application paths, startup configuration, and Gemini Live setup helpers."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from core.user_paths import get_user_data_dir

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


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
