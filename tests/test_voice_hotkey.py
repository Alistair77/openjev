"""Single-tap hotkey state machine + clipboard paste path (no GUI, no keys)."""

from openjev.voice import actions as actions_module
from openjev.voice.actions import MacActions
from openjev.voice.hotkey import TapHotkey


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_clean_tap_fires():
    clock, fired = Clock(), []
    tap = TapHotkey(key="option", callback=lambda: fired.append(True), clock=clock)
    tap.press("option")
    clock.now += 0.12
    assert tap.release("option") is True
    assert fired == [True]


def test_hold_does_not_fire():
    clock, fired = Clock(), []
    tap = TapHotkey(key="option", callback=lambda: fired.append(True), clock=clock)
    tap.press("option")
    clock.now += 1.5
    assert tap.release("option") is False
    assert fired == []


def test_other_key_dirties_tap_and_repeat_ignored():
    clock, fired = Clock(), []
    tap = TapHotkey(key="option", callback=lambda: fired.append(True), clock=clock)
    tap.press("option")
    tap.press("option")  # auto-repeat: ignored, stays clean
    tap.press("cmd")     # other key: dirty
    clock.now += 0.1
    assert tap.release("option") is False
    assert fired == []


def test_release_without_press_is_quiet():
    tap = TapHotkey(key="option", callback=lambda: None, clock=Clock())
    assert tap.release("option") is False


def test_live_type_pastes_via_clipboard_not_keystrokes(monkeypatch):
    calls: dict = {"writes": []}

    class FakeBoard:
        def stringForType_(self, _type):
            calls["read"] = True
            return "old clipboard"

        def types(self):
            return ["NSStringPboardType"]

        def declareTypes_owner_(self, _types, _owner):
            calls["declared"] = True

        def setString_forType_(self, text, _type):
            calls["writes"].append(text)

    monkeypatch.setattr(actions_module, "_pasteboard", lambda: FakeBoard())
    monkeypatch.setattr(actions_module, "_string_type", lambda: "FakeType")
    monkeypatch.setattr(actions_module, "_send_paste", lambda: calls.setdefault("pasted", True))
    monkeypatch.setattr(actions_module, "focused_target",
                        lambda: {"role": "AXTextArea", "app": "Notes", "accessible": True})
    monkeypatch.setattr("time.sleep", lambda _s: None)
    report = MacActions(live=True).run({"action": "type_text", "text": "hello there"})
    assert report == {"ok": True, "detail": "pasted 11 chars at cursor"}
    assert calls["writes"][0] == "hello there"  # pasted text written…
    assert calls["writes"][-1] == "old clipboard"  # …then clipboard restored
    assert calls.get("pasted") is True


def test_launch_flash_shows_then_hides():
    import time

    from openjev.voice.app import VoiceMenuApp
    from openjev.voice.states import VoiceState

    renders = []

    class FakeOverlay:
        def render(self, state, status="", transcript=""):
            renders.append(state)

        def set_session_active(self, _active):
            pass

        def hide(self):
            renders.append("hidden")

    app = VoiceMenuApp()
    app.agent.attach_overlay(FakeOverlay())
    app.flash_ready()
    assert VoiceState.LISTENING in renders
    time.sleep(3.0)
    assert app.agent._voice_state is VoiceState.IDLE
    assert renders[-1] == "hidden"
