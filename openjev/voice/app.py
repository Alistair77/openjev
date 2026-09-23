"""Native macOS menu-bar app for push-to-talk voice control. No terminal needed.

Real AppKit UI (same APIs a Swift app uses): NSStatusItem with SF Symbols icon,
dropdown menu, floating state pill. The Python engine underneath is the tested
`VoiceAgent` — intents, slots, actions, safety model all unchanged.

Run: `openjev voice-app [--live]` or double-click dist/JevVoice.app.
First launch prompts for Microphone + Accessibility (both required).
"""

from __future__ import annotations

from typing import Any

from openjev.voice.agent import DEFAULT_HOTKEY, VoiceAgent
from openjev.voice.states import VoiceState

STATE_SYMBOLS = {
    VoiceState.IDLE: "mic.fill",
    VoiceState.LISTENING: "waveform",
    VoiceState.TRANSCRIBING: "waveform.badge.mic",
    VoiceState.EXECUTING: "bolt.fill",
    VoiceState.SUCCESS: "checkmark.circle.fill",
    VoiceState.ERROR: "xmark.circle.fill",
}


def symbol_for(state: VoiceState) -> str:
    """SF Symbol name for a voice state (pure function, tested)."""
    return STATE_SYMBOLS.get(state, "mic.fill")


def status_text(listening: bool, live: bool, last_heard: str = "") -> str:
    """Menu status line (pure function, tested)."""
    mode = "LIVE — executes" if live else "dry-run — safe"
    base = f"{'Listening…' if listening else 'Idle'} · {mode}"
    return f"{base}\nLast: {last_heard}" if last_heard else base


class VoiceMenuApp:
    """Builds NSStatusItem + menu + overlay on the main thread, then NSApp.run()."""

    def __init__(self, hotkey: str = DEFAULT_HOTKEY, live: bool = False,
                 confidence: float = 0.30, stt: str = "sphinx") -> None:
        self.agent = VoiceAgent(hotkey=hotkey, live=live, confidence=confidence,
                                stt=stt, overlay=False)
        self.agent.on_heard = self.on_heard
        self.last_heard = ""
        self._status_item: Any = None
        self._status_menu: Any = None
        self._menu_items: dict[str, Any] = {}

    # -- entry point ------------------------------------------------------
    def run(self) -> None:
        from AppKit import NSApplication
        from Foundation import NSTimer

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(1)
        print("jev-voice: building menu bar…", flush=True)
        self._build_status_item()
        print("jev-voice: menu bar ready", flush=True)
        self._build_overlay()
        print("jev-voice: overlay ready", flush=True)
        self.agent.begin()  # hotkey listener, non-blocking
        print("jev-voice: hotkey armed", flush=True)
        target = _PumpTarget.alloc().initWithApp_(self)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0 / 30.0, target, "fire:", None, True)
        self._targets = [target]  # keep alive
        print("jev-voice: entering runloop (menu-bar icon should be visible)", flush=True)
        try:
            app.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.agent.end()

    # -- status bar --------------------------------------------------------
    def _build_status_item(self) -> None:
        from AppKit import NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength

        bar = NSStatusBar.systemStatusBar()
        item = bar.statusItemWithLength_(NSVariableStatusItemLength)
        self._status_item = item
        self._set_icon(VoiceState.IDLE)
        menu = NSMenu.alloc().init()
        actions = _MenuActions.alloc().initWithApp_(self)

        def add(title, selector, key=""):
            entry = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, selector, key)
            entry.setTarget_(actions)
            menu.addItem_(entry)
            return entry

        self._menu_items["status"] = add("Idle · dry-run — safe", None)
        self._menu_items["status"].setEnabled_(False)
        menu.addItem_(NSMenuItem.separatorItem())
        self._menu_items["toggle"] = add("Start Listening", "toggle:", "l")
        self._menu_items["live"] = add("Live (execute actions)", "toggleLive:")
        self._menu_items["overlay"] = add("Show overlay pill", "toggleOverlay:")
        menu.addItem_(NSMenuItem.separatorItem())
        self._menu_items["last"] = add("Last heard: —", None)
        self._menu_items["last"].setEnabled_(False)
        menu.addItem_(NSMenuItem.separatorItem())
        add("Quit Jev Voice", "quit:", "q")
        item.setMenu_(menu)
        self._actions = actions
        self.refresh_menu()

    def _set_icon(self, state: VoiceState) -> None:
        from AppKit import NSImage
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol_for(state), "voice state")
        image.setTemplate_(True)
        self._status_item.button().setImage_(image)

    def refresh_menu(self) -> None:
        live = self.agent.actions.live
        self._menu_items["status"].setTitle_(status_text(self.agent.listening, live).split("\n")[0])
        self._menu_items["toggle"].setTitle_(
            "Stop Listening" if self.agent.listening else "Start Listening")
        self._menu_items["live"].setState_(1 if live else 0)
        overlay_on = self.agent._overlay is not None
        self._menu_items["overlay"].setState_(1 if overlay_on else 0)
        if self.last_heard:
            self._menu_items["last"].setTitle_(f"Last heard: {self.last_heard[:48]}")

    # -- overlay ------------------------------------------------------------
    def _build_overlay(self) -> None:
        from openjev.voice import overlay as overlay_module
        if not overlay_module.available():
            return
        controller = overlay_module.OverlayController()
        controller.on_return = self.agent._on_overlay_return
        controller.start()
        self.agent.attach_overlay(controller)
        self._overlay = controller

    # -- callbacks from menu actions -----------------------------------------
    def on_toggle_listening(self) -> None:
        self.agent.toggle()
        self._set_icon(VoiceState.LISTENING if self.agent.listening else VoiceState.IDLE)
        self.refresh_menu()

    def on_toggle_live(self) -> None:
        self.agent.actions.live = not self.agent.actions.live
        self.refresh_menu()

    def on_toggle_overlay(self) -> None:
        if self.agent._overlay is not None:
            self.agent._overlay.hide()
            self.agent.attach_overlay(None)
        elif hasattr(self, "_overlay"):
            self.agent.attach_overlay(self._overlay)
        self.refresh_menu()

    def on_heard(self, text: str) -> None:
        self.last_heard = text
        self._set_icon(self.agent._voice_state)
        self.refresh_menu()

    def on_quit(self) -> None:
        from AppKit import NSApplication
        NSApplication.sharedApplication().terminate_(None)


class _PumpTarget:
    """NSObject subclass created on the main thread (needs AppKit at runtime)."""

    @classmethod
    def alloc(cls):
        from Foundation import NSObject

        class PumpTarget(NSObject):
            def initWithApp_(self, app):
                self = self.init()  # noqa: PLW0642 - required Cocoa init pattern
                self._app = app
                return self

            def fire_(self, _timer):
                try:
                    overlay = getattr(self._app.agent, "_overlay", None)
                    if overlay is not None:
                        overlay.pump_once()
                    self._app._set_icon(self._app.agent._voice_state)
                    self._app.refresh_menu()
                except Exception:
                    import traceback
                    traceback.print_exc()  # UI errors must never trap the runloop

        return PumpTarget.alloc()


class _MenuActions:
    """NSObject subclass routing menu clicks into the app."""

    @classmethod
    def alloc(cls):
        from Foundation import NSObject

        class MenuActions(NSObject):
            def initWithApp_(self, app):
                self = self.init()  # noqa: PLW0642 - required Cocoa init pattern
                self._app = app
                return self

            def toggle_(self, _sender):
                self._app.on_toggle_listening()

            def toggleLive_(self, _sender):
                self._app.on_toggle_live()

            def toggleOverlay_(self, _sender):
                self._app.on_toggle_overlay()

            def quit_(self, _sender):
                self._app.on_quit()

        return MenuActions.alloc()


def main(live: bool = False, **kwargs) -> None:
    VoiceMenuApp(live=live, **kwargs).run()
