"""A brand-new install configured with ONLY an NVIDIA key (no Gemini/OpenRouter)."""
from __future__ import annotations

import json

import llm_client as llm
import setup as nexus_setup


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        return self._payload


def _ok(text):
    return _Resp(200, {"choices": [{"message": {"content": text}}]})


def test_cli_setup_can_pick_nvidia_as_primary(monkeypatch):
    answers = iter([
        "nvapi-abc",      # NVIDIA key
        "", "", "", "",   # gemini, openrouter, groq, custom skipped
        "nvidia nim",     # primary provider (alias accepted)
    ])
    monkeypatch.setattr(nexus_setup, "_prompt", lambda *a, **k: next(answers))
    keys = nexus_setup.setup_api_keys()
    assert keys["nvidia_api_key"] == "nvapi-abc"
    assert keys["default_ai_provider"] == "NVIDIA"
    assert "gemini_api_key" not in keys


def test_cli_setup_defaults_to_nvidia_when_only_nvidia_has_a_key(monkeypatch):
    answers = iter(["nvapi-abc", "", "", "", ""])
    # empty answer on the primary prompt -> the offered default
    monkeypatch.setattr(
        nexus_setup, "_prompt",
        lambda prompt, default="": next(answers, "") or default,
    )
    assert nexus_setup.setup_api_keys()["default_ai_provider"] == "NVIDIA"


def test_memory_extraction_uses_primary_provider_not_openrouter(monkeypatch):
    """Memory used to call OpenRouter directly, so it never worked without that key."""
    from memory import memory_manager

    c = llm.UnifiedAIClient()
    state = {"settings": {"default_ai_provider": "NVIDIA"}, "keys": {"nvidia_api_key": "nvapi-x"}}

    def fake_reload():
        c._settings = dict(state["settings"])
        c._provider = llm.normalize_provider(c._settings["default_ai_provider"])

    monkeypatch.setattr(c, "reload_settings", fake_reload)
    monkeypatch.setattr(llm, "get_api_key", lambda name, env=None, explicit=None: state["keys"].get(name, ""))
    monkeypatch.setattr(llm, "client", c)
    fake_reload()

    urls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        urls.append(url)
        return _ok("YES")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert memory_manager.should_extract_memory("my name is Sam", "nice to meet you") is True
    assert urls and all("integrate.api.nvidia.com" in u for u in urls)
