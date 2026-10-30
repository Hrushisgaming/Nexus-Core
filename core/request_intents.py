"""Pure request-intent and message classification helpers.

Kept separate from the application entry point so these routines can be
tested and reused without importing the desktop runtime.
"""

from __future__ import annotations

import re


def _looks_like_code_request(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    # If explicitly targeting a mobile device, never treat as a local code creation request
    if any(m in low for m in ("on phone", "on my phone", "on mobile", "on my mobile", "on android", "on tablet", "on iphone", "in phone", "in my phone")):
        return False
    # Action/execution commands targeting local apps or utilities are not code creation
    if any(low.startswith(p) for p in ("open ", "launch ", "start ", "run ", "close ", "kill ", "quit ", "turn on ", "turn off ", "switch on ", "switch off ", "ring ", "find ")):
        if not any(re.search(rf"\b{a}\b", low) for a in ("write", "create", "build", "code", "develop", "implement", "scaffold", "generate")):
            return False

    code_intent_verbs = (
        "build", "create", "make", "code", "develop", "program",
        "implement", "write", "scaffold", "generate", "refactor", "debug"
    )
    code_target_nouns = (
        "app", "application", "website", "web page", "webpage", "web app",
        "webapp", "script", "program", "game", "calculator", "bot",
        "api", "server", "service", "module", "component", "frontend",
        "backend", "ui", "landing page", "portfolio"
    )
    tech_markers = (
        "in python", "using python", "python script", "python code",
        "html", "css", "javascript", "react", "typescript", "flask",
        "fastapi", "django", "node.js", "nodejs", "express", "sql"
    )

    has_intent = any(re.search(rf"\b{re.escape(v)}\b", low) for v in code_intent_verbs)
    has_target = any(re.search(rf"\b{re.escape(n)}\b", low) for n in code_target_nouns)
    has_tech = any(re.search(rf"\b{re.escape(t)}\b", low) for t in tech_markers)

    return (has_intent and (has_target or has_tech)) or (has_target and has_tech)


def _looks_like_website_request(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    if any(m in low for m in ("on phone", "on my phone", "on mobile", "on android", "on tablet")):
        return False
    if any(low.startswith(p) for p in ("open ", "go to ", "visit ", "browse ", "launch ")):
        if not any(re.search(rf"\b{a}\b", low) for a in ("make", "create", "build", "design", "develop", "code", "generate")):
            return False

    website_words = (
        "website",
        "web site",
        "webpage",
        "web page",
        "landing page",
        "homepage",
        "home page",
        "portfolio",
        "product site",
        "business site",
        "marketing site",
        "web app",
        "frontend",
        "site",
        "html",
        "react",
        "web",
    )
    action_words = ("make", "create", "build", "design", "develop", "generate", "code", "edit", "update", "fix")
    has_web = any(re.search(rf"\b{re.escape(w)}\b", low) for w in website_words)
    has_action = any(re.search(rf"\b{re.escape(a)}\b", low) for a in action_words)
    return has_web and has_action


def _looks_like_presentation_request(text: str) -> bool:
    low = (text or "").lower()
    ppt_keywords = (
        "presentation", "powerpoint", "slideshow", "slides", "slide deck",
        "pitch deck", "deck", "ppt", "pptx"
    )
    action_words = ("make", "create", "build", "design", "develop", "generate", "draft", "prepare")
    has_keyword = any(re.search(rf"\b{re.escape(k)}\b", low) for k in ppt_keywords)
    has_action = any(re.search(rf"\b{re.escape(a)}\b", low) for a in action_words)
    return has_keyword and (has_action or any(k in low for k in ("slide deck", "pitch deck", "powerpoint", "pptx", "ppt")))


def _looks_like_spreadsheet_request(text: str) -> bool:
    low = (text or "").lower()
    sheet_keywords = (
        "spreadsheet", "excel", "sheet", "sheets", "workbook", "xlsx",
        "tracker", "expense tracker", "budget sheet"
    )
    action_words = ("make", "create", "build", "design", "develop", "generate", "draft", "prepare")
    has_keyword = any(re.search(rf"\b{re.escape(k)}\b", low) for k in sheet_keywords)
    has_action = any(re.search(rf"\b{re.escape(a)}\b", low) for a in action_words)
    return has_keyword and (has_action or any(k in low for k in ("spreadsheet", "excel sheet", "expense tracker", "budget sheet", "xlsx")))


def _extract_skill_creation_goal(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    match = re.match(
        r"^(?:please\s+)?(?:(?:i\s+(?:want|need|would like)\s+you\s+to|(?:can|could)\s+you)\s+)?"
        r"(?:make|create|build|develop|generate|forge|write|implement|add|design)\s+"
        r"(?:me\s+)?(?:your\s+)?(?:(?:a|an|new|custom|own)\s+)*(?:skill|feature)\b(.*)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    goal = match.group(1).strip(" \t:,-")
    goal = re.sub(r"^(?:that|which|to)\s+", "", goal, flags=re.IGNORECASE)
    goal = re.sub(
        r"^(?:(?:will|can|could|should)\s+)?(?:allow|let|enable|allows|lets|enables)\s+(?:you\s+)?(?:to\s+)?",
        "",
        goal,
        flags=re.IGNORECASE,
    )
    return goal.strip()


def _is_gemini_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in (
        "429",
        "resource_exhausted",
        "quota",
        "rate limit",
        "too many requests",
        "exceeded",
        "1008",
        "access denied",
        "permission denied",
    ))


def _looks_like_camera_request(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    cam_words = ("camera", "cam", "webcam", "see me", "look at me", "in front of the camera", "pc cam", "laptop cam", "through cam", "through camera", "through webcam")
    has_cam = any(re.search(rf"\b{re.escape(w)}\b", t) for w in cam_words)
    request_words = ("what", "check", "look", "analy", "analyse", "analyze", "read", "tell", "answer", "see", "explain", "inspect", "view", "watch", "can you see")
    has_request = any(re.search(rf"\b{re.escape(w)}\b", t) for w in request_words)
    return has_cam and has_request


def _looks_like_screen_request(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    direct_phrases = (
        "what's on my screen",
        "whats on my screen",
        "what is on my screen",
        "what's on screen",
        "check my screen",
        "look at my screen",
        "analyze my screen",
        "analyse my screen",
        "tell me what's on my screen",
        "tell me what is on my screen",
        "read my screen",
        "what does my screen say",
        "explain this error",
        "what's this error",
        "what is this error",
        "explain the error",
        "look at this error",
        "explain what's on my screen",
        "inspect my screen",
        "what am i looking at",
    )
    if any(p in t for p in direct_phrases):
        return True
    screen_words = ("screen", "display", "monitor", "window")
    request_words = ("what", "check", "look", "analy", "analyse", "analyze", "read", "tell", "answer", "see", "explain")
    has_screen_target = any(re.search(rf"\b{re.escape(word)}\b", t) for word in screen_words)
    has_screen_request = any(re.search(rf"\b{re.escape(word)}\b", t) for word in request_words)
    return has_screen_target and has_screen_request


def _looks_like_daily_briefing_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
    phrases = (
        "daily briefing", "morning briefing", "morning update", "daily update",
        "brief me", "give me a briefing", "briefing for today", "what's happening today",
        "whats happening today", "what is happening today",
    )
    return any(phrase in normalized for phrase in phrases)


def _wakeword_detected(text: str) -> bool:
    """True only when the assistant is addressed by name.

    A bare "hey/hi/hello" no longer wakes a muted mic, otherwise ordinary
    conversation in the room would keep un-muting it. "brahma" is kept as a
    legacy wake word for existing users.
    """
    t = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower())
    words = t.split()
    if not words:
        return False
    return any(word in {"nexus", "brahma"} for word in words)
