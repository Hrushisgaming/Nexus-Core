import subprocess
import sys
import json
import os
from pathlib import Path


def _get_base_dir() -> Path:
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return Path(_sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = _get_base_dir()


def _prompt(prompt: str, default: str = "") -> str:
    """Prompt the user for input with an optional default value."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    try:
        value = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return value if value else default


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question."""
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        value = input(f"{prompt}{suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not value:
        return default
    return value.startswith("y")


def install_requirements():
    print("\n=== Installing Python requirements ===")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

    print("\n=== Installing Playwright browsers ===")
    subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)


def setup_api_keys():
    """Interactively collect API keys for all AI providers."""
    print("\n" + "=" * 60)
    print("  AI Provider API Key Setup")
    print("=" * 60)
    print(
        "You can enter API keys for the providers you want to use. "
        "Press Enter to skip any provider (you can always add keys later in Settings).\n"
    )

    keys = {}

    # NVIDIA is asked first so it can be picked as the primary intelligence.
    keys["nvidia_api_key"] = _prompt("  NVIDIA NIM API key (https://build.nvidia.com)", "")

    # Gemini (also powers live voice)
    keys["gemini_api_key"] = _prompt("  Google Gemini API key", "")

    # OpenRouter
    keys["openrouter_api_key"] = _prompt("  OpenRouter API key", "")

    # Groq
    keys["groq_api_key"] = _prompt("  Groq API key", "")

    # Custom (OpenAI-compatible)
    custom_key = _prompt("  Custom OpenAI-compatible API key", "")
    if custom_key:
        keys["custom_ai_api_key"] = custom_key
        keys["custom_ai_base_url"] = _prompt(
            "    Custom API base URL", "https://api.openai.com/v1"
        )
        keys["custom_ai_model"] = _prompt("    Custom model name", "gpt-4o-mini")

    # Remove empty keys
    keys = {k: v for k, v in keys.items() if v}

    # Choose the primary provider (NVIDIA is preferred when it has a key).
    names = {
        "nvidia_api_key": "NVIDIA",
        "gemini_api_key": "Gemini",
        "groq_api_key": "Groq",
        "openrouter_api_key": "OpenRouter",
        "custom_ai_api_key": "Custom",
    }
    available = [name for field, name in names.items() if keys.get(field)]
    print("\n  Available providers:", ", ".join(available) or "(none)")
    default_provider = _prompt(
        "  Primary AI provider (NVIDIA, Gemini, Groq, OpenRouter, Custom)",
        available[0] if available else "OpenRouter",
    )
    # Accept any capitalisation / "nvidia nim" / "google gemini" style answers.
    from llm_client import normalize_provider
    keys["default_ai_provider"] = normalize_provider(default_provider)

    return keys


# (menu number, engine id, label, api-key field - "" means no key needed)
VOICE_ENGINES = [
    ("1", "elevenlabs", "ElevenLabs", "elevenlabs_api_key"),
    ("2", "groq_tts", "Groq (Orpheus)", "groq_api_key"),
    ("3", "fish_audio", "Fish Audio", "fish_audio_api_key"),
    ("4", "edge_tts", "Microsoft Edge (free, no key)", ""),
]


def setup_voice(existing_keys: dict) -> tuple[dict, dict]:
    """Optional voice-engine step. Returns (api keys to save, app settings to merge).

    Skipped by default: Nexus keeps using Gemini's built-in voice. A chosen engine is
    used for Nexus's own announcements; live conversation still speaks with Gemini.
    """
    print("\n" + "=" * 60)
    print("  Voice Engine (optional)")
    print("=" * 60)
    if not _ask_yes_no("Set up an extra voice engine now? (default: keep Gemini's built-in voice)", default=False):
        return {}, {}
    for number, _engine, label, _field in VOICE_ENGINES:
        print(f"  {number}) {label}")
    choice = _prompt("  Pick one (number or name, Enter to skip)", "").strip().lower()
    picked = next(
        (e for e in VOICE_ENGINES
         if choice in (e[0], e[1], e[2].lower()) or (choice and choice in e[2].lower())),
        None,
    )
    if not picked:
        print("  Skipped - keeping Gemini's built-in voice.")
        return {}, {}
    _number, engine, label, field = picked

    keys: dict = {}
    if field:
        key = (existing_keys.get(field) or "").strip()
        if key:
            print(f"  Using the {label} key you already entered.")
        else:
            key = _prompt(f"  {label} API key (Enter to skip this voice)", "").strip()
        if not key:
            print("  No key given - skipped, keeping Gemini's built-in voice.")
            return {}, {}
        keys[field] = key

    voice = ""
    try:
        from core.tts_providers import get_tts_provider
        prov = get_tts_provider(engine)
        default_voice = str(getattr(prov, "voice_id", "") or "")
        if prov is not None and prov.get_voices():
            print("  Voices: " + ", ".join(str(v.get("id")) for v in prov.get_voices()))
        voice = _prompt("  Voice", default_voice).strip()
    except Exception:
        pass
    settings = {"tts_engine": engine}
    if voice:
        settings["tts_voices"] = {engine: voice}
    print(f"  ✓ {label} will be used for Nexus's announcements (change anytime in Settings).")
    return keys, settings


def write_config(api_keys: dict, extra_settings: dict | None = None):
    """Write api_keys.json and app_settings.json to the user data dir."""
    from core.user_paths import get_user_data_dir

    config_dir = get_user_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write api_keys.json
    api_keys_path = config_dir / "api_keys.json"
    existing = {}
    if api_keys_path.exists():
        try:
            with open(api_keys_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing.update(api_keys)
    from core.atomic_io import atomic_write_json
    atomic_write_json(api_keys_path, existing, indent=2)
    print(f"\n  ✓ API keys saved to: {api_keys_path}")

    # Write/update app_settings.json
    app_settings_path = config_dir / "app_settings.json"
    app_settings = {}
    if app_settings_path.exists():
        try:
            with open(app_settings_path, "r", encoding="utf-8") as f:
                app_settings = json.load(f)
        except Exception:
            app_settings = {}

    app_settings["default_ai_provider"] = api_keys.get(
        "default_ai_provider", "Gemini"
    )
    if "custom_ai_base_url" in api_keys:
        app_settings["custom_ai_base_url"] = api_keys["custom_ai_base_url"]
    if "custom_ai_model" in api_keys:
        app_settings["custom_ai_model"] = api_keys["custom_ai_model"]
    if extra_settings:
        from core.voice_settings import merge_setup_result
        app_settings = merge_setup_result(app_settings, extra_settings)

    from core.atomic_io import atomic_write_json
    atomic_write_json(app_settings_path, app_settings, indent=2)
    print(f"  ✓ App settings saved to: {app_settings_path}")


def main():
    print("Nexus Core - Setup")
    print("=" * 40)

    # 1. Install requirements
    install_requirements()

    # 2. API key setup
    print("\n=== AI Provider Configuration ===")
    setup_keys = _ask_yes_no("Configure AI provider API keys now?", default=True)
    api_keys = {}
    voice_settings_extra = {}
    if setup_keys:
        api_keys = setup_api_keys()
        voice_keys, voice_settings_extra = setup_voice(api_keys)
        api_keys.update(voice_keys)

    # 3. Write config
    if api_keys:
        write_config(api_keys, voice_settings_extra)
    else:
        print("\n  ⚠ No API keys configured. You can add them later in Settings → AI Providers.")

    # 4. Done
    print("\n" + "=" * 40)
    print("✅ Setup complete!")
    print("=" * 40)
    print("\nTo start Nexus Core:")
    print("  macOS/Linux: python3 main.py")
    print("  Windows:     python main.py  or  start_nexus.bat")
    print("\nManage API keys anytime in Settings → AI Providers.")


if __name__ == "__main__":
    main()
