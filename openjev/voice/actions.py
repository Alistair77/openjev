"""macOS action executor. Dry-run by default; nothing touches the screen
unless `live=True` is passed explicitly (CLI: `--live`).

Live execution uses only `open(1)` + `osascript(1)` (stdlib subprocess) and,
for typing/keypresses, pynput imported lazily so the base install stays lean.
"""

from __future__ import annotations

import subprocess
import urllib.parse
from typing import Any


class MacActions:
    """Execute (or describe, when dry) on-screen actions."""

    def __init__(self, live: bool = False, allowed_apps: set[str] | None = None) -> None:
        self.live = live
        self.allowed_apps = allowed_apps  # None = allow all named apps

    def run(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute one action dict from commands.build_action. Always returns a report."""
        kind = action.get("action", "unheard")
        handler = getattr(self, f"_do_{kind}", self._do_unheard)
        return handler(action)

    # -- handlers ---------------------------------------------------------
    def _do_open_app(self, action: dict[str, Any]) -> dict[str, Any]:
        app = action["app"]
        if self.allowed_apps is not None and app not in self.allowed_apps:
            return {"ok": False, "detail": f"{app} is not in the allowed-apps list"}
        return self._exec(["open", "-a", app], f"open {app}")

    def _do_youtube_search(self, action: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.quote_plus(action["query"])
        url = f"https://www.youtube.com/results?search_query={query}"
        return self._exec(["open", url], f"youtube search: {action['query']}")

    def _do_web_search(self, action: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.quote_plus(action["query"])
        url = f"https://www.google.com/search?q={query}"
        return self._exec(["open", url], f"web search: {action['query']}")

    def _do_type_text(self, action: dict[str, Any]) -> dict[str, Any]:
        if not self.live:
            return {"ok": True, "dry": True, "detail": f"would type: {action['text']!r}"}
        from pynput.keyboard import Controller

        Controller().type(action["text"])
        return {"ok": True, "detail": f"typed {len(action['text'])} chars"}

    def _do_press_key(self, action: dict[str, Any]) -> dict[str, Any]:
        if not self.live:
            return {"ok": True, "dry": True, "detail": f"would press: {action['key']}"}
        from pynput.keyboard import Controller, Key

        keyboard = Controller()
        key = action["key"]
        if "+" in key:
            combo = key.split("+")
            pressed = [Key.cmd if part == "cmd" else part for part in combo]
            for part in pressed:
                keyboard.press(part)
            for part in reversed(pressed):
                keyboard.release(part)
        else:
            named = {"enter": Key.enter, "esc": Key.esc, "tab": Key.tab, "space": Key.space,
                     "backspace": Key.backspace}.get(key, key)
            keyboard.press(named)
            keyboard.release(named)
        return {"ok": True, "detail": f"pressed {key}"}

    def _do_volume(self, action: dict[str, Any]) -> dict[str, Any]:
        level = action["level"]
        script = {"mute": "set volume with output muted",
                  "up": "set volume output volume ((output volume of (get volume settings)) + 10)",
                  "down": "set volume output volume ((output volume of (get volume settings)) - 10)"}[level]
        return self._exec(["osascript", "-e", script], f"volume {level}")

    def _do_unheard(self, action: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "detail": f"no executable action for: {action.get('heard', '')!r}"}

    # -- plumbing ---------------------------------------------------------
    def _exec(self, argv: list[str], detail: str) -> dict[str, Any]:
        if not self.live:
            return {"ok": True, "dry": True, "detail": f"would run: {' '.join(argv)}"}
        try:
            subprocess.run(argv, check=True, capture_output=True, timeout=30)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as error:
            return {"ok": False, "detail": f"{detail} failed: {error}"}
        return {"ok": True, "detail": detail}
