"""Menu-bar app logic without a GUI session: symbols, menu text, wiring."""

from openjev.voice.agent import VoiceAgent
from openjev.voice.app import status_text, symbol_for
from openjev.voice.states import VoiceState


def test_symbol_for_every_state():
    assert symbol_for(VoiceState.IDLE) == "mic.fill"
    assert symbol_for(VoiceState.LISTENING) == "waveform"
    assert symbol_for(VoiceState.TRANSCRIBING) == "waveform.badge.mic"
    assert symbol_for(VoiceState.EXECUTING) == "bolt.fill"
    assert symbol_for(VoiceState.SUCCESS) == "checkmark.circle.fill"
    assert symbol_for(VoiceState.ERROR) == "xmark.circle.fill"


def test_status_text_modes():
    assert "Idle" in status_text(False, live=False)
    assert "dry-run" in status_text(False, live=False)
    assert "Listening" in status_text(True, live=True)
    assert "LIVE" in status_text(True, live=True)
    assert "open notes" in status_text(True, live=False, last_heard="open notes")


def test_attach_overlay_and_utterance_flow():
    from openjev.voice.overlay import OverlayController

    agent = VoiceAgent(live=False, overlay=False)
    controller = OverlayController()  # never started: message logic only
    agent.attach_overlay(controller)
    assert agent._overlay is controller
    agent._set_state(VoiceState.LISTENING, status="Listening…")
    outcome = agent._handle_utterance("open the notes app")
    assert outcome["intent"] == "open_app"
    agent.attach_overlay(None)
    assert agent._overlay is None
