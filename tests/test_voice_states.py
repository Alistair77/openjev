"""Overlay state machine: legal walks, agent wiring, hold expiry. No GUI needed."""

import pytest

from openjev.voice.agent import VoiceAgent
from openjev.voice.overlay import OverlayController, available
from openjev.voice.states import VoiceState, legal_next, transition


class FakeOverlay:
    def __init__(self):
        self.renders = []
        self.hidden = 0

    def render(self, state, status="", transcript=""):
        self.renders.append(state)

    def set_session_active(self, active):
        pass

    def hide(self):
        self.hidden += 1

    def stop(self):
        pass


def test_full_legal_walk():
    state = VoiceState.IDLE
    for nxt in (VoiceState.LISTENING, VoiceState.TRANSCRIBING, VoiceState.EXECUTING,
                VoiceState.SUCCESS, VoiceState.LISTENING, VoiceState.TRANSCRIBING,
                VoiceState.EXECUTING, VoiceState.ERROR, VoiceState.LISTENING, VoiceState.IDLE):
        state = transition(state, nxt)
    assert state is VoiceState.IDLE


@pytest.mark.parametrize("frm,to", [
    (VoiceState.IDLE, VoiceState.EXECUTING),
    (VoiceState.IDLE, VoiceState.SUCCESS),
    (VoiceState.LISTENING, VoiceState.SUCCESS),
    (VoiceState.LISTENING, VoiceState.EXECUTING),
    (VoiceState.TRANSCRIBING, VoiceState.SUCCESS),
    (VoiceState.EXECUTING, VoiceState.LISTENING),
    (VoiceState.SUCCESS, VoiceState.EXECUTING),
    (VoiceState.ERROR, VoiceState.TRANSCRIBING),
])
def test_illegal_transitions_raise(frm, to):
    with pytest.raises(ValueError):
        transition(frm, to)


def test_listening_reachable_only_from_idle_success_error():
    assert legal_next(VoiceState.IDLE) == {VoiceState.LISTENING}
    assert VoiceState.LISTENING in legal_next(VoiceState.SUCCESS)
    assert VoiceState.LISTENING in legal_next(VoiceState.ERROR)
    assert VoiceState.LISTENING not in legal_next(VoiceState.EXECUTING)


def _agent_with_fake(**kwargs):
    agent = VoiceAgent(live=False, overlay=False, **kwargs)
    fake = FakeOverlay()
    agent._overlay = fake
    agent._set_state(VoiceState.LISTENING, status="Listening…")
    return agent, fake


def test_success_path_renders_listening_transcribing_executing_success():
    agent, fake = _agent_with_fake()
    outcome = agent._handle_utterance("open the notes app")
    assert outcome["intent"] == "open_app" and outcome["report"]["ok"] is True
    assert fake.renders == [VoiceState.LISTENING, VoiceState.TRANSCRIBING,
                            VoiceState.EXECUTING, VoiceState.SUCCESS]


def test_failure_path_renders_error_and_keeps_safety_model():
    agent, fake = _agent_with_fake(allowed_apps={"Notes"})
    outcome = agent._handle_utterance("open the terminal app")
    assert outcome["report"]["ok"] is False  # allowlist still blocks
    assert fake.renders[-2:] == [VoiceState.EXECUTING, VoiceState.ERROR]


def test_unheard_returns_to_listening_without_success_or_error():
    agent, fake = _agent_with_fake()
    outcome = agent._handle_utterance("flibberty wobble zephyr")
    assert outcome["intent"] is None
    assert fake.renders == [VoiceState.LISTENING, VoiceState.TRANSCRIBING, VoiceState.LISTENING]


def test_overlay_return_goes_back_to_listening():
    agent, fake = _agent_with_fake()
    agent._handle_utterance("open the notes app")
    agent._on_overlay_return()
    assert fake.renders[-1] is VoiceState.LISTENING


def test_controller_hold_expiry_calls_on_return_or_hides():
    controller = OverlayController()  # never started: no threads, no AppKit
    calls = []
    controller.on_return = lambda: calls.append(True)
    controller._apply(("session", True))
    controller._apply(("state", VoiceState.SUCCESS, "Done ✓", "open notes"))
    assert controller._model.hold_until > 0
    controller._model.hold_until = 0.0001
    import time
    time.sleep(0.01)
    controller.pump_once()
    assert calls == [True]
    controller._apply(("session", False))
    controller._apply(("state", VoiceState.ERROR, "Failed", "x"))
    controller._model.hold_until = 0.0001
    time.sleep(0.01)
    controller.pump_once()
    assert controller._model.hold_until == 0.0


def test_available_returns_bool_without_crashing():
    assert isinstance(available(), bool)
