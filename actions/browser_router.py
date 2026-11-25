"""Routes browser_control actions to the paired Chrome extension when it is connected.

The extension drives the user's real Chrome (their sign-ins, tabs and cookies) and
enforces the user's own rules: site block/allow list, a dedicated "Nexus" tab group,
confirmation prompts for risky actions, and a pause switch.

Order of preference for browser_control:
    1. Paired Chrome extension  (this module)
    2. Playwright MCP / built-in Playwright thread  (actions.browser_control)

Fallback to Playwright happens ONLY when the extension cannot be reached or does not
offer that action. It never happens after the extension refuses: if the user blocked a
site, paused control, did not share the tab or denied a prompt, Playwright must not be
used to get around that decision.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

# The user (or their rules) said no. Never retry these through another browser.
REFUSAL_CODES = {
    "SITE_BLOCKED",
    "TAB_NOT_SHARED",
    "PAUSED",
    "USER_DENIED",
    "USER_NO_RESPONSE",
    "CANNOT_SHARE",
}

# The extension is simply not there. Fallback is fine.
UNREACHABLE_CODES = {
    "DEVICE_OFFLINE",
    "DEVICE_NOT_FOUND",
    "GATEWAY_UNAVAILABLE",
    "MULTIPLE_DEVICES",
    "UNSUPPORTED_ACTION",
    "CAPABILITY_NOT_SUPPORTED",
    "MISSING_CAPABILITY",
}

_FIELD_TAGS = {"input", "textarea", "select"}
_MAX_RESULT_CHARS = 12000


class ExtensionUnavailable(Exception):
    """Raised when the extension can't be used for this call (caller falls back)."""


# ----------------------------------------------------------------- device / calls
def _execute(parameters: dict) -> dict:
    from actions.nexus_connect import connect_execute

    raw = connect_execute(parameters)
    try:
        data = json.loads(raw)
    except Exception:
        return {"success": False, "error": str(raw), "error_code": "GATEWAY_UNAVAILABLE"}
    return data if isinstance(data, dict) else {"success": True, "data": data}


def find_browser_device() -> Optional[dict]:
    """First online device with platform 'browser', or None."""
    try:
        from actions.nexus_connect import _service

        for device in _service().list_devices():
            if str(device.get("platform", "")).lower() == "browser" and device.get("online"):
                return device
    except Exception:
        return None
    return None


class _Session:
    def __init__(self, device: dict):
        self.device_id = device.get("device_id") or device.get("name")

    def call(self, action: str, **params: Any) -> dict:
        clean = {k: v for k, v in params.items() if v is not None}
        result = _execute({"device": self.device_id, "action": action, "parameters": clean})
        if result.get("success"):
            data = result.get("data")
            return data if isinstance(data, dict) else {"value": data}
        code = str(result.get("error_code") or "ACTION_FAILED")
        if code in UNREACHABLE_CODES:
            raise ExtensionUnavailable(code)
        raise ExtensionError(code, str(result.get("error") or code))


class ExtensionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ----------------------------------------------------------------- target resolving
def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _find_ref(session: _Session, text: str, *, want_field: bool = False) -> Optional[str]:
    """Look up a snapshot ref by visible text, label, placeholder or current value."""
    needle = _norm(text)
    if not needle:
        return None
    snap = session.call("browser_snapshot", max_elements=250, max_text=200)
    best_ref, best_score = None, 0
    for el in snap.get("elements") or []:
        is_field = str(el.get("tag", "")).lower() in _FIELD_TAGS
        if want_field and not is_field:
            continue
        label = _norm(el.get("text"))
        value = _norm(el.get("value"))
        score = 0
        if label == needle or value == needle:
            score = 3
        elif label.startswith(needle):
            score = 2
        elif needle in label or (value and needle in value):
            score = 1
        if score > best_score:
            best_ref, best_score = el.get("ref"), score
    return best_ref


_TEXT_INPUT_TYPES = {None, "", "text", "search", "email", "url", "tel", "number", "password"}


def _first_text_field(session: _Session) -> Optional[str]:
    snap = session.call("browser_snapshot", max_elements=250, max_text=200)
    for el in snap.get("elements") or []:
        tag = str(el.get("tag", "")).lower()
        if el.get("disabled"):
            continue
        if tag == "textarea" or (tag == "input" and el.get("type") in _TEXT_INPUT_TYPES):
            return el.get("ref")
    return None


def _target(session: _Session, p: dict, *, want_field: bool = False) -> dict:
    """Build ref/selector arguments from browser_control style parameters.

    For fields, 'text' is the text to type, so only 'description'/'field'/'label'
    name the field. For clicks, 'text' or 'description' names the element.
    """
    if p.get("element"):
        return {"ref": str(p["element"])}
    if p.get("ref"):
        return {"ref": str(p["ref"])}
    if p.get("selector"):
        return {"selector": str(p["selector"])}
    if want_field:
        hint = p.get("description") or p.get("field") or p.get("label")
    else:
        hint = p.get("text") or p.get("description")
    if hint:
        ref = _find_ref(session, str(hint), want_field=want_field)
        if ref:
            return {"ref": ref}
        raise ExtensionError(
            "ELEMENT_NOT_FOUND",
            f"No element matching '{hint}' on the page. Take a snapshot and pass its ref as 'element'.",
        )
    if want_field:
        ref = _first_text_field(session)
        if ref:
            return {"ref": ref}
    raise ExtensionError("MISSING_PARAMETERS", "Say which element to use (element ref, selector or description).")


# ----------------------------------------------------------------- formatting
def _format(data: dict) -> str:
    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(data, dict) and set(data) <= {"message", "tab_id", "url", "title", "input"} and message:
        return message
    text = json.dumps(data, ensure_ascii=False, indent=1, default=str)
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + "\n... [truncated]"
    return text


_SEARCH_URLS = {
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
}


def _has_agent_tab(session: _Session) -> bool:
    try:
        tabs = session.call("browser_list_tabs").get("tabs") or []
        return bool(tabs)
    except ExtensionError:
        return False


# ----------------------------------------------------------------- action handlers
def _go(session: _Session, url: str) -> dict:
    if not url:
        raise ExtensionError("MISSING_PARAMETERS", "A url is required.")
    if "://" not in url:
        url = "https://" + url
    if _has_agent_tab(session):
        try:
            return session.call("browser_navigate", url=url)
        except ExtensionError as exc:
            if exc.code != "NO_AGENT_TAB":
                raise
    return session.call("browser_open_url", url=url)


def _tab_id_for_index(session: _Session, index: int) -> int:
    tabs = session.call("browser_list_tabs").get("tabs") or []
    if not 1 <= index <= len(tabs):
        raise ExtensionError("TAB_NOT_FOUND", f"Tab {index} doesn't exist ({len(tabs)} shared tab(s) open).")
    return tabs[index - 1]["tab_id"]


def _handle(session: _Session, action: str, p: dict) -> Optional[str]:
    """Return a result string, or None when the extension has no equivalent."""
    if action in {"go_to", "navigate"}:
        url = str(p.get("url", "")).strip()
        if not url and p.get("query"):
            return _handle(session, "search", p)
        return _format(_go(session, url))

    if action == "search":
        query = str(p.get("query", "")).strip()
        engine = str(p.get("engine", "google")).lower()
        from urllib.parse import quote_plus

        return _format(_go(session, _SEARCH_URLS.get(engine, _SEARCH_URLS["google"]).format(q=quote_plus(query))))

    if action in {"open_tab", "new_tab"}:
        url = str(p.get("url") or "about:blank")
        if url == "about:blank":
            url = "https://www.google.com"
        return _format(session.call("browser_open_url", url=url if "://" in url else "https://" + url))

    if action in {"click", "smart_click"}:
        return _format(session.call("browser_click", **_target(session, p), double=p.get("double") or None))

    if action in {"type", "smart_type"}:
        args = _target(session, p, want_field=True)
        return _format(session.call(
            "browser_type", text=str(p.get("text", "")), submit=p.get("submit") or None,
            clear=p.get("clear"), **args,
        ))

    if action == "select_option":
        values = p.get("values") or [p.get("value")]
        value = next((str(v) for v in values if v), "")
        return _format(session.call("browser_type", text=value, **_target(session, p, want_field=True)))

    if action == "fill_form":
        fields = p.get("fields") or {}
        items = (
            [{"element": k, "value": v} for k, v in fields.items()]
            if isinstance(fields, dict) else list(fields)
        )
        done = []
        for item in items:
            key = str(item.get("element") or item.get("selector") or item.get("name") or "").strip()
            if not key:
                continue
            if re.fullmatch(r"[en]\d+", key):
                sub = {"element": key}
            elif any(ch in key for ch in "#.[]>="):
                sub = {"selector": key}
            else:
                sub = {"description": key}
            args = _target(session, sub, want_field=True)
            session.call("browser_type", text=str(item.get("value", "")), **args)
            done.append(key)
        return f"Filled {len(done)} field(s): " + ", ".join(done)

    if action == "press":
        return _format(session.call("browser_press_key", key=p.get("key", "Enter")))

    if action == "scroll":
        return _format(session.call(
            "browser_scroll", direction=p.get("direction", "down"), amount=int(p.get("amount", 500)),
        ))

    if action in {"snapshot", "inspect"}:
        return _format(session.call("browser_snapshot"))

    if action == "find":
        query = _norm(p.get("query") or p.get("text"))
        snap = session.call("browser_snapshot", max_elements=250)
        hits = [e for e in snap.get("elements") or [] if query and query in _norm(e.get("text"))]
        return _format({"query": query, "matches": hits[:30], "count": len(hits)})

    if action == "get_text":
        return _format(session.call("browser_get_text", selector=p.get("selector"), ref=p.get("element")))

    if action in {"evaluate", "eval", "run_code", "execute"}:
        code = p.get("expression") or p.get("script") or p.get("code") or p.get("snippet") or "document.title"
        return _format(session.call("browser_eval", code=code))

    if action in {"screenshot", "take_screenshot"}:
        return _format(session.call("browser_screenshot"))

    if action == "back":
        return _format(session.call("browser_back"))
    if action == "forward":
        return _format(session.call("browser_forward"))
    if action in {"refresh", "reload"}:
        return _format(session.call("browser_reload"))

    if action in {"tabs", "list_tabs"}:
        return _format(session.call("browser_list_tabs"))

    if action == "switch_tab":
        return _format(session.call("browser_activate_tab", tab_id=_tab_id_for_index(session, int(p.get("tab", 1)))))

    if action in {"wait_for", "wait"}:
        t_ms = p.get("time_ms") or p.get("time")
        return _format(session.call(
            "browser_wait_for", selector=p.get("selector"), text=p.get("text"),
            timeout=int(t_ms) if t_ms else None,
        ))

    if action in {"upload", "file_upload"}:
        paths = [str(x) for x in (p.get("paths") or [p.get("path")]) if x]
        return _format(session.call("browser_upload_file", files=paths, **_target(session, p)))

    if action == "close":
        return _format(session.call("browser_close_tab", current=True))

    # hover, dialog, console, network: the extension has no equivalent.
    return None


_UNSUPPORTED_HINT = (
    "Your paired Chrome can't do '{action}'. Pass browser='playwright' to run it in the "
    "separate automation browser instead."
)


def try_extension(parameters: dict) -> Optional[str]:
    """Run a browser_control call through the extension.

    Returns a result string when the extension handled it (success or refusal), or
    None when the caller should use Playwright.
    """
    p = dict(parameters or {})
    action = str(p.get("action", "")).lower().strip()
    engine = str(p.get("browser") or os.environ.get("NEXUS_BROWSER_ENGINE") or "").lower()
    if engine in {"playwright", "automation"} or not action:
        return None

    device = find_browser_device()
    if device is None:
        return None

    session = _Session(device)
    try:
        result = _handle(session, action, p)
    except ExtensionUnavailable:
        return None
    except ExtensionError as exc:
        if exc.code in REFUSAL_CODES:
            return (
                f"Blocked by your browser settings ({exc.code}): {exc.message} "
                "Do not retry this in another browser; tell the user and let them decide."
            )
        return f"Browser action '{action}' failed ({exc.code}): {exc.message}"

    if result is None:
        return _UNSUPPORTED_HINT.format(action=action)
    return result
