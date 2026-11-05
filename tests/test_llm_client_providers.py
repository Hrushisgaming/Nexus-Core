"""Provider routing / failure handling for llm_client (all HTTP is mocked)."""
from __future__ import annotations

import json

import pytest

import llm_client as llm


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _ok(text):
    return _Resp(200, {"choices": [{"message": {"content": text}}]})


@pytest.fixture()
def client(monkeypatch):
    """A fresh client whose settings/keys come from the test, never from disk."""
    c = llm.UnifiedAIClient()
    state = {"settings": {"default_ai_provider": "NVIDIA"}, "keys": {"nvidia_api_key": "nvapi-test"}}

    def fake_reload():
        c._settings = dict(state["settings"])
        c._provider = llm.normalize_provider(c._settings.get("default_ai_provider"))

    monkeypatch.setattr(c, "reload_settings", fake_reload)
    monkeypatch.setattr(llm, "get_api_key", lambda name, env=None, explicit=None: state["keys"].get(name, ""))
    fake_reload()
    c.state = state
    return c


def test_normalize_provider_aliases():
    assert llm.normalize_provider("Google Gemini") == "Gemini"
    assert llm.normalize_provider("nvidia nim") == "NVIDIA"
    assert llm.normalize_provider("NVIDIA") == "NVIDIA"
    assert llm.normalize_provider("ollama") == "Local"
    assert llm.normalize_provider("") == "OpenRouter"


def test_nvidia_primary_is_called_with_bearer_key(client, monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, payload=json)
        return _ok("hello from nvidia")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert client.chat("hi") == "hello from nvidia"
    assert seen["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer nvapi-test"
    assert seen["payload"]["model"] == llm.NVIDIA_CHAT_MODELS[0]
    assert seen["payload"]["messages"][-1] == {"role": "user", "content": "hi"}


def test_key_pasted_with_bearer_prefix_is_cleaned(client, monkeypatch):
    client.state["keys"]["nvidia_api_key"] = '  "Bearer nvapi-abc"  '
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["auth"] = headers["Authorization"]
        return _ok("x")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    client.chat("hi")
    assert seen["auth"] == "Bearer nvapi-abc"


def test_unknown_model_falls_through_to_next_nvidia_model(client, monkeypatch):
    models = []
    missing = {llm.NVIDIA_CHAT_MODELS[0]}

    def fake_post(url, headers=None, json=None, timeout=None):
        models.append(json["model"])
        if json["model"] in missing:
            return _Resp(404, text='{"detail":"Function not found for model"}')
        return _ok("second model worked")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert client.chat("hi") == "second model worked"
    assert models == llm.NVIDIA_CHAT_MODELS[:2]
    # the bad model is remembered and not retried
    models.clear()
    client.chat("again")
    assert models == [llm.NVIDIA_CHAT_MODELS[1]]


def test_user_configured_nvidia_model_is_tried_first(client, monkeypatch):
    client.state["settings"]["nvidia_model"] = "meta/llama-3.1-405b-instruct"
    seen = []
    monkeypatch.setattr(
        llm.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (seen.append(json["model"]) or _ok("ok")),
    )
    client.chat("hi")
    assert seen == ["meta/llama-3.1-405b-instruct"]


def test_bad_key_gives_actionable_error_not_empty_string(client, monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post",
        lambda *a, **k: _Resp(401, text='{"detail":"Authentication failed"}'),
    )
    client.state["settings"]["auto_provider_switch"] = False
    with pytest.raises(RuntimeError) as exc:
        client.chat("hi")
    assert "NVIDIA" in str(exc.value) and "401" in str(exc.value)


def test_falls_back_to_next_configured_provider(client, monkeypatch):
    client.state["keys"]["groq_api_key"] = "gsk_test"
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        if "nvidia" in url:
            return _Resp(500, text="boom")
        return _ok("groq answered")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert client.chat("hi") == "groq answered"
    assert any("groq.com" in u for u in calls)


def test_auto_switch_off_does_not_use_other_providers(client, monkeypatch):
    client.state["keys"]["groq_api_key"] = "gsk_test"
    client.state["settings"]["auto_provider_switch"] = False
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.requests, "post", lambda url, **k: _Resp(500, text="boom") if "nvidia" in url else _ok("nope"))
    with pytest.raises(RuntimeError):
        client.chat("hi")


def test_skip_excludes_a_provider(client, monkeypatch):
    client.state["keys"]["groq_api_key"] = "gsk_test"
    urls = []
    monkeypatch.setattr(
        llm.requests, "post",
        lambda url, headers=None, json=None, timeout=None: (urls.append(url) or _ok("g")),
    )
    assert client.chat("hi", skip=("NVIDIA",)) == "g"
    assert all("nvidia" not in u for u in urls)


def test_reasoning_blocks_are_stripped(client, monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post",
        lambda *a, **k: _ok("<think>step by step</think>The answer is 4."),
    )
    assert client.chat("2+2?") == "The answer is 4."


def test_chat_json_parses_fenced_and_wrapped_output(client, monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post",
        lambda *a, **k: _ok('Sure!\n```json\n{"a": 1}\n```'),
    )
    assert client.chat_json("give json") == {"a": 1}


def test_vision_uses_a_vision_model_for_nvidia(client, monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["model"] = json["model"]
        seen["content"] = json["messages"][1]["content"]
        return _ok("a cat")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert client.vision("what is it?", "AAAA") == "a cat"
    assert seen["model"] == llm.NVIDIA_VISION_MODELS[0]
    assert any(part.get("type") == "image_url" for part in seen["content"])


def test_no_keys_anywhere_reports_which_providers_were_skipped(client, monkeypatch):
    client.state["keys"].clear()
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: pytest.fail("no request should be made"))
    monkeypatch.setattr(client, "_local_chat_completion", lambda *a, **k: None)
    with pytest.raises(RuntimeError) as exc:
        client.chat("hi")
    assert "NVIDIA: no API key configured" in str(exc.value)


def test_provider_test_reports_missing_key(client):
    client.state["keys"].clear()
    ok, detail = client.test_provider("nvidia")
    assert ok is False and "no API key" in detail


def test_provider_chain_offline_mode_is_local_only(client):
    client.state["settings"]["offline_mode_enabled"] = True
    assert client.provider_chain() == ["Local"]
