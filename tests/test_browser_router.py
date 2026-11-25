import json

import pytest

from actions import browser_router as br


class FakeExtension:
    """Stands in for connect_execute and records calls."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, parameters):
        action = parameters["action"]
        self.calls.append((action, parameters.get("parameters", {})))
        reply = self.responses.get(action, {"success": True, "data": {"message": f"{action} ok"}})
        if callable(reply):
            reply = reply(parameters.get("parameters", {}))
        return reply


@pytest.fixture
def ext(monkeypatch):
    fake = FakeExtension()
    monkeypatch.setattr(br, "_execute", fake)
    monkeypatch.setattr(br, "find_browser_device", lambda: {"device_id": "chrome_1", "platform": "browser", "online": True})
    return fake


SNAPSHOT = {
    "success": True,
    "data": {"elements": [
        {"ref": "n1", "tag": "a", "text": "Sign in"},
        {"ref": "n2", "tag": "input", "type": "search", "text": "Search"},
        {"ref": "n3", "tag": "button", "text": "Search"},
    ]},
}


def test_no_extension_means_playwright(monkeypatch):
    monkeypatch.setattr(br, "find_browser_device", lambda: None)
    assert br.try_extension({"action": "navigate", "url": "https://example.com"}) is None


def test_playwright_can_be_forced(ext):
    assert br.try_extension({"action": "navigate", "url": "https://example.com", "browser": "playwright"}) is None
    assert ext.calls == []


def test_navigate_opens_tab_when_none_exists(ext):
    ext.responses["browser_list_tabs"] = {"success": True, "data": {"tabs": []}}
    out = br.try_extension({"action": "go_to", "url": "example.com"})
    assert out == "browser_open_url ok"
    assert ("browser_open_url", {"url": "https://example.com"}) in ext.calls


def test_navigate_reuses_existing_tab(ext):
    ext.responses["browser_list_tabs"] = {"success": True, "data": {"tabs": [{"tab_id": 7}]}}
    br.try_extension({"action": "navigate", "url": "https://example.com"})
    assert ext.calls[-1][0] == "browser_navigate"


def test_click_by_text_resolves_ref_from_snapshot(ext):
    ext.responses["browser_snapshot"] = SNAPSHOT
    br.try_extension({"action": "click", "text": "sign in"})
    assert ext.calls[-1] == ("browser_click", {"ref": "n1"})


def test_type_defaults_to_first_text_field(ext):
    ext.responses["browser_snapshot"] = SNAPSHOT
    br.try_extension({"action": "type", "text": "hello"})
    assert ext.calls[-1] == ("browser_type", {"text": "hello", "ref": "n2"})


def test_type_uses_description_to_find_field(ext):
    ext.responses["browser_snapshot"] = SNAPSHOT
    br.try_extension({"action": "type", "text": "hello", "description": "search"})
    assert ext.calls[-1][1]["ref"] == "n2"


@pytest.mark.parametrize("code", sorted(br.REFUSAL_CODES))
def test_refusals_are_final_and_never_fall_back(ext, code):
    ext.responses["browser_open_url"] = {"success": False, "error": "no", "error_code": code}
    out = br.try_extension({"action": "go_to", "url": "https://bank.example"})
    assert out is not None and code in out and "another browser" in out


def test_offline_extension_falls_back(ext):
    ext.responses["browser_list_tabs"] = {"success": False, "error": "x", "error_code": "DEVICE_OFFLINE"}
    assert br.try_extension({"action": "navigate", "url": "https://example.com"}) is None


def test_ordinary_failure_is_reported_not_retried_elsewhere(ext):
    ext.responses["browser_click"] = {"success": False, "error": "Element is covered", "error_code": "ACTION_FAILED"}
    out = br.try_extension({"action": "click", "selector": "#buy"})
    assert out is not None and "ACTION_FAILED" in out


def test_unsupported_action_explains_how_to_force_playwright(ext):
    out = br.try_extension({"action": "hover", "selector": "#x"})
    assert "playwright" in out


def test_tab_switch_maps_index_to_tab_id(ext):
    ext.responses["browser_list_tabs"] = {"success": True, "data": {"tabs": [{"tab_id": 11}, {"tab_id": 22}]}}
    br.try_extension({"action": "switch_tab", "tab": 2})
    assert ext.calls[-1] == ("browser_activate_tab", {"tab_id": 22})


def test_browser_control_returns_extension_result(ext, monkeypatch):
    pytest.importorskip("playwright")
    from actions import browser_control as bc

    ext.responses["browser_snapshot"] = SNAPSHOT
    out = bc.browser_control({"action": "snapshot"})
    assert "Sign in" in out
