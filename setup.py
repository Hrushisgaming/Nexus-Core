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

    # Gemini
    keys["gemini_api_key"] = _prompt("  Google Gemini API key", "")

    # OpenRouter
    keys["openrouter_api_key"] = _prompt("  OpenRouter API key", "")

    # NVIDIA
    keys["nvidia_api_key"] = _prompt("  NVIDIA NIM API key", "")

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

    # Choose default provider
    print("\n  Available providers:", ", ".join(
        k.replace("_api_key", "") for k in keys if k.endswith("_api_key")
    ) or "(none)")
    default_provider = _prompt(
        "  Default AI provider", "Gemini" if keys.get("gemini_api_key") else "OpenRouter"
    )
    keys["default_ai_provider"] = default_provider

    return keys


def write_config(api_keys: dict):
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
    with open(api_keys_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
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

    with open(app_settings_path, "w", encoding="utf-8") as f:
        json.dump(app_settings, f, indent=2)
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
    if setup_keys:
        api_keys = setup_api_keys()

    # 3. Write config
    if api_keys:
        write_config(api_keys)
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
