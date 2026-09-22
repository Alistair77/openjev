"""Voice-command intents and slot extraction (no microphone, no optional deps).

The intent set is deliberately keyword-dense: the local lexical backend decides
in ~0.07 ms, which is what makes per-utterance execution feel instant.
"""

from __future__ import annotations

import re
from typing import Any

VOICE_INTENTS: dict[str, str] = {
    "open_app": "open launch start run an application program app browser notes",
    "youtube": "youtube video watch play search youtube clip",
    "web_search": "search google web internet look up find online browse",
    "type_text": "type write enter dictate text words note say",
    "press_key": "press key shortcut hotkey copy paste enter escape tab space",
    "volume": "volume mute unmute louder quieter sound audio",
}

INTENT_QUESTION = {
    "intent": {
        "type": "choice",
        "instructions": "What does the speaker want the computer to do?",
        "criteria": VOICE_INTENTS,
    }
}

# spoken name -> macOS application name for `open -a`
APPS: dict[str, str] = {
    "brave": "Brave Browser",
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "notes": "Notes",
    "finder": "Finder",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "claude": "Claude",
    "cloudcode": "Claude",
    "slack": "Slack",
    "discord": "Discord",
    "spotify": "Spotify",
    "music": "Music",
    "mail": "Mail",
    "calendar": "Calendar",
    "settings": "System Settings",
    "photos": "Photos",
    "messages": "Messages",
}

_KEY_ALIASES = {
    "enter": "enter",
    "return": "enter",
    "escape": "esc",
    "esc": "esc",
    "tab": "tab",
    "space": "space",
    "delete": "backspace",
    "backspace": "backspace",
    "copy": "cmd+c",
    "paste": "cmd+v",
    "cut": "cmd+x",
    "undo": "cmd+z",
    "save": "cmd+s",
}

_FILLER = re.compile(
    r"\b(open|launch|start|run|please|the|a|an|app|application|browser|for|me|my|on|in|to|video|clip)\b",
    re.IGNORECASE,
)


def extract_slots(text: str, intent: str) -> dict[str, Any]:
    """Pull action parameters out of the utterance. Pure string logic, no model."""
    lowered = text.lower()
    slots: dict[str, Any] = {}
    if intent == "open_app":
        for spoken, app in APPS.items():
            if re.search(rf"\b{re.escape(spoken)}\b", lowered):
                slots["app"] = app
                break
    elif intent in ("youtube", "web_search"):
        query = _FILLER.sub(" ", lowered)
        query = re.sub(r"\b(youtube|google|web|internet|search|look|up|find|watch|play|online|browse)\b", " ", query)
        query = re.sub(r"\s+", " ", query).strip(" ,.")
        slots["query"] = query or text.strip()
    elif intent == "type_text":
        cleaned = re.sub(r"^\s*(type|write|enter|dictate|note|say)\b", "", lowered).strip()
        slots["text"] = cleaned or text.strip()
    elif intent == "press_key":
        for spoken, key in _KEY_ALIASES.items():
            if re.search(rf"\b{re.escape(spoken)}\b", lowered):
                slots["key"] = key
                break
    elif intent == "volume":
        if re.search(r"\b(mute|silent|quiet)\b", lowered):
            slots["level"] = "mute"
        elif re.search(r"\b(louder|up|higher|unmute)\b", lowered):
            slots["level"] = "up"
        elif re.search(r"\b(quieter|down|lower|softer)\b", lowered):
            slots["level"] = "down"
    return slots


def build_action(intent: str, slots: dict[str, Any], raw_text: str) -> dict[str, Any]:
    """Turn (intent, slots) into one executable action dict."""
    if intent == "open_app" and slots.get("app"):
        return {"action": "open_app", "app": slots["app"]}
    if intent == "youtube" and slots.get("query"):
        return {"action": "youtube_search", "query": slots["query"]}
    if intent == "web_search" and slots.get("query"):
        return {"action": "web_search", "query": slots["query"]}
    if intent == "type_text" and slots.get("text"):
        return {"action": "type_text", "text": slots["text"]}
    if intent == "press_key" and slots.get("key"):
        return {"action": "press_key", "key": slots["key"]}
    if intent == "volume" and slots.get("level"):
        return {"action": "volume", "level": slots["level"]}
    return {"action": "unheard", "heard": raw_text}
