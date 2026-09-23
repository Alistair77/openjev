"""Floating push-to-talk overlay: top-center pill, never steals focus.

Native AppKit NSPanel (borderless, click-through, shown with `orderFront`
instead of key-making calls, so the front app keeps focus). Visual language
follows the Thinking-Orbs / Motoko look the overlay brief asked for — dark
pill, orbiting-dot state indicator, mic-ring pulse while listening, circular
check on success, ringed X on failure — reimplemented natively in drawRect
(the React components cannot run inside this Python CLI).

All public methods are thread-safe: they enqueue messages; a dedicated UI
thread owns NSApplication and pumps the queue. Importing this module never
touches AppKit (lazy import in `available()` / controller start).
"""

from __future__ import annotations

import math
import queue
import time
from dataclasses import dataclass
from typing import Any

from openjev.voice.states import VoiceState

PANEL_WIDTH = 460
PANEL_HEIGHT = 132
SUCCESS_HOLD_SECONDS = 0.9
ERROR_HOLD_SECONDS = 1.6

_STATE_COLORS = {
    VoiceState.LISTENING: (0.50, 0.70, 1.00),
    VoiceState.TRANSCRIBING: (0.89, 0.70, 0.26),
    VoiceState.EXECUTING: (0.93, 0.62, 0.38),
    VoiceState.SUCCESS: (0.20, 0.78, 0.35),
    VoiceState.ERROR: (1.00, 0.27, 0.23),
}
_STATE_SPEEDS = {
    VoiceState.LISTENING: 1.6,
    VoiceState.TRANSCRIBING: 3.2,
    VoiceState.EXECUTING: 5.2,
}

_ORB_DOTS = 16


def available() -> bool:
    """True when AppKit can show a panel (macOS GUI session present)."""
    try:
        from AppKit import NSScreen
    except Exception:  # noqa: BLE001 - any import failure means no overlay, never crash
        return False
    try:
        return len(NSScreen.screens() or []) > 0
    except Exception:  # noqa: BLE001 - GUI probing must never raise
        return False


@dataclass
class _OverlayModel:
    state: VoiceState = VoiceState.IDLE
    status: str = ""
    transcript: str = ""
    session_active: bool = False
    hold_until: float = 0.0


def _make_view_class():
    """NSView subclass drawing the pill + orb + texts. Built on the UI thread."""
    from AppKit import (
        NSBezierPath,
        NSColor,
        NSFont,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSString,
        NSView,
    )

    class OverlayView(NSView):
        def initWithFrame_model_(self, frame, model):
            self = self.initWithFrame_(frame)  # noqa: PLW0642 - required Cocoa init pattern
            self._model = model
            self._t0 = time.monotonic()
            return self

        def isOpaque(self):
            return False

        def drawRect_(self, _rect):
            model = self._model
            t = time.monotonic() - self._t0
            bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((8, 8), (PANEL_WIDTH - 16, PANEL_HEIGHT - 16)), 22, 22)
            NSColor.colorWithCalibratedWhite_alpha_(0.08, 0.92).set()
            bg.fill()
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.14).set()
            bg.setLineWidth_(1.0)
            bg.stroke()
            self._draw_orb(model, t, 60.0, PANEL_HEIGHT / 2.0 + 4)
            attrs = {NSFontAttributeName: NSFont.systemFontOfSize_weight_(15.0, 0.3),
                     NSForegroundColorAttributeName: NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.92)}
            NSString.stringWithString_(model.status or "").drawAtPoint_withAttributes_(
                (104, 74), attrs)
            sub = model.transcript
            if len(sub) > 54:
                sub = sub[:54] + "…"
            sub_attrs = {NSFontAttributeName: NSFont.systemFontOfSize_weight_(12.5, 0.0),
                         NSForegroundColorAttributeName: NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.65)}
            NSString.stringWithString_(sub).drawAtPoint_withAttributes_((104, 50), sub_attrs)

        def _draw_orb(self, model, t, cx, cy):
            from AppKit import NSBezierPath, NSColor
            state = model.state
            color = _STATE_COLORS.get(state, _STATE_COLORS[VoiceState.LISTENING])
            paint = NSColor.colorWithCalibratedRed_green_blue_alpha_(*color, 0.95)
            if state in (VoiceState.SUCCESS, VoiceState.ERROR):
                ring = NSBezierPath.bezierPathWithOvalInRect_(((cx - 20, cy - 20), (40, 40)))
                paint.set()
                ring.setLineWidth_(3.0)
                ring.stroke()
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(3.5)
                path.setLineCapStyle_(1)
                if state is VoiceState.SUCCESS:
                    path.moveToPoint_((cx - 9, cy + 1))
                    path.lineToPoint_((cx - 2, cy + 8))
                    path.lineToPoint_((cx + 11, cy - 9))
                else:
                    path.moveToPoint_((cx - 8, cy - 8))
                    path.lineToPoint_((cx + 8, cy + 8))
                    path.moveToPoint_((cx + 8, cy - 8))
                    path.lineToPoint_((cx - 8, cy + 8))
                path.stroke()
                return
            speed = _STATE_SPEEDS.get(state, 1.6)
            pulse = 0.5 + 0.5 * math.sin(t * 2.0)
            for i in range(_ORB_DOTS):
                angle = t * speed + i * 2 * math.pi / _ORB_DOTS
                radius = 13 + 5 * math.sin(t * 2.2 + i * 0.9)
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                fade = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 3 + i))
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    color[0], color[1], color[2], fade * (0.75 + 0.25 * pulse)).set()
                NSBezierPath.bezierPathWithOvalInRect_(((x - 2.6, y - 2.6), (5.2, 5.2))).fill()
            if state is VoiceState.LISTENING:
                ring_r = 20 + 6 * pulse
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    *color, 0.35 * (1 - pulse) + 0.1).set()
                ring = NSBezierPath.bezierPathWithOvalInRect_(
                    ((cx - ring_r, cy - ring_r), (ring_r * 2, ring_r * 2)))
                ring.setLineWidth_(1.5)
                ring.stroke()

    return OverlayView


class OverlayController:
    """Owns the panel. The agent owns the state machine; this only renders.

    `render()` carries no transition guard (single writer is the agent, which
    guards with `states.transition` under a lock). When a SUCCESS/ERROR hold
    expires, the controller calls `on_return` so the agent can transition back
    to LISTENING itself — no split-brain between threads.

    AppKit requires windows on the MAIN thread: `start()` builds NSApp + panel
    on the calling thread (call it from main), and the caller drives
    `pump_once()` from its main loop. Inbox traffic may come from any thread.
    """

    def __init__(self) -> None:
        self._model = _OverlayModel()
        self._inbox: queue.Queue = queue.Queue()
        self._view: Any = None
        self._panel: Any = None
        self._built = False
        self.on_return = None  # called (main thread, via pump) when a hold expires, session active

    # -- public, thread-safe -------------------------------------------
    def start(self) -> None:
        """Build NSApp + panel. MUST run on the main thread."""
        if self._built:
            return
        self._build_ui()
        self._built = True

    def render(self, state: VoiceState, status: str = "", transcript: str = "") -> None:
        self._inbox.put(("state", state, status, transcript))

    def set_session_active(self, active: bool) -> None:
        self._model.session_active = active
        self._inbox.put(("session", active))

    def hide(self) -> None:
        self._inbox.put(("hide",))

    def stop(self) -> None:
        self._inbox.put(("hide",))

    @property
    def state(self) -> VoiceState:
        return self._model.state

    # -- main thread: build once, pump from the caller's loop ----------------
    def _build_ui(self) -> None:
        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSFloatingWindowLevel,
            NSMakeRect,
            NSPanel,
            NSScreen,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorStationary,
            NSWindowStyleMaskBorderless,
        )

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(1)  # Accessory: no Dock icon, windows allowed
        screen = NSScreen.mainScreen().frame()
        x = screen.origin.x + (screen.size.width - PANEL_WIDTH) / 2
        y = screen.origin.y + screen.size.height - PANEL_HEIGHT - 28
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, PANEL_WIDTH, PANEL_HEIGHT),
            NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
        panel.setIgnoresMouseEvents_(True)
        panel.setOpaque_(False)
        panel.setHasShadow_(True)
        panel.setBackgroundColor_(panel.backgroundColor().colorWithAlphaComponent_(0.0))
        view = _make_view_class().alloc().initWithFrame_model_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT), self._model)
        panel.setContentView_(view)
        self._view = view
        self._panel = panel

    def pump_once(self) -> None:
        """Drain inbox, expire holds, redraw. Call ~30x/sec from the main loop."""
        try:
            while True:
                self._apply(self._inbox.get_nowait())
        except queue.Empty:
            pass
        model = self._model
        expired = (
            model.state in (VoiceState.SUCCESS, VoiceState.ERROR)
            and model.hold_until
            and time.monotonic() >= model.hold_until
        )
        if expired:
            model.hold_until = 0.0
            if model.session_active and self.on_return is not None:
                self.on_return()
            elif not model.session_active:
                self._apply(("hide",))
        if self._view is not None:
            self._view.setNeedsDisplay_(True)

    def _apply(self, message: tuple) -> None:
        model = self._model
        kind = message[0]
        if kind == "state":
            _, state, status, transcript = message
            model.state = state
            model.status = status
            if transcript:
                model.transcript = transcript
            if state in (VoiceState.SUCCESS, VoiceState.ERROR):
                model.hold_until = time.monotonic() + (
                    SUCCESS_HOLD_SECONDS if state is VoiceState.SUCCESS else ERROR_HOLD_SECONDS)
            if self._panel is not None:
                self._panel.orderFrontRegardless()
        elif kind == "session":
            model.session_active = bool(message[1])
        elif kind == "hide":
            model.hold_until = 0.0
            if self._panel is not None:
                self._panel.orderOut_(None)
