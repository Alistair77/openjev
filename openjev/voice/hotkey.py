"""Push-to-talk triggers: single-modifier tap (FluidVoice-style) or key combo.

Tap detection is original code (the *idea* of tap-Option-to-talk follows
FluidVoice's UX): a press+release of the bare modifier within TAP_MS, with no
other key involved, fires the callback. Holding Option for shortcuts never
fires. Combos (`<cmd>+<shift>+v`) still work via pynput GlobalHotKeys.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

TAP_MS = 350

_MODIFIERS = {"option", "cmd", "ctrl", "shift"}


def parse_hotkey(spec: str) -> tuple[str, str]:
    """'tap:option' (default) or a pynput combo like '<cmd>+<shift>+v'."""
    text = spec.strip().lower()
    if text.startswith("tap:"):
        key = text[4:]
        if key not in _MODIFIERS:
            raise ValueError(f"tap key must be one of {sorted(_MODIFIERS)}, got {key!r}")
        return ("tap", key)
    import re
    if not re.fullmatch(r"[<>\w+ ]+", spec) or "+" not in spec:
        raise ValueError(f"hotkey must be 'tap:<name>' or like '<cmd>+<shift>+v', got {spec!r}")
    return ("combo", spec)


class TapHotkey:
    """Fires `callback` on a clean tap of one modifier key. Testable without pynput."""

    def __init__(self, key: str = "option", callback: Callable[[], None] | None = None,
                 tap_ms: int = TAP_MS, clock: Callable[[], float] | None = None) -> None:
        if key not in _MODIFIERS:
            raise ValueError(f"tap key must be one of {sorted(_MODIFIERS)}")
        self.key = key
        self.callback = callback or (lambda: None)
        self.tap_ms = tap_ms
        self._clock = clock or time.monotonic
        self._press_at: float | None = None
        self._clean = True
        self._listener: Any = None

    # -- pure state machine (unit-tested) ---------------------------------
    def press(self, name: str) -> None:
        if name == self.key and self._press_at is None:
            self._press_at = self._clock()
            self._clean = True
        elif name != self.key:
            self._clean = False

    def release(self, name: str) -> bool:
        """Returns True when a tap completed (callback already fired)."""
        if name != self.key or self._press_at is None:
            if name != self.key:
                self._clean = False
            return False
        held_ms = (self._clock() - self._press_at) * 1000
        self._press_at = None
        if self._clean and held_ms <= self.tap_ms:
            self.callback()
            return True
        return False

    # -- live pynput wiring -------------------------------------------------
    def start(self):
        from pynput import keyboard

        names = {
            "option": {"alt", "alt_r", "option"},
            "cmd": {"cmd", "cmd_r"},
            "ctrl": {"ctrl", "ctrl_r"},
            "shift": {"shift", "shift_r"},
        }[self.key]

        def canonical(k) -> str:
            try:
                return k.name.lower() if hasattr(k, "name") else str(k).strip("'").lower()
            except Exception:  # noqa: BLE001 - listener thread must never die on odd keys
                return ""

        def on_press(k):
            name = canonical(k)
            self.press(self.key if name in names else name or "unknown")

        def on_release(k):
            name = canonical(k)
            self.release(self.key if name in names else name or "unknown")

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()
        return self._listener

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
