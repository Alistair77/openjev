"""Focus-aware typing: refuse non-text, never crash, dry-run untouched."""

from openjev.voice import actions as actions_module
from openjev.voice.actions import MacActions
from openjev.voice.focus import delivery_decision, focused_target


def test_delivery_decision_buckets():
    assert delivery_decision("AXTextArea") == "paste"
    assert delivery_decision("AXSecureTextField") == "paste"
    assert delivery_decision("AXButton") == "refuse"
    assert delivery_decision("AXMenuItem") == "refuse"
    assert delivery_decision("AXStaticText") == "refuse"
    assert delivery_decision(None) == "unknown"
    assert delivery_decision("AXGroup") == "unknown"
    assert delivery_decision("AXWebArea") == "unknown"


def test_focused_target_never_raises_and_has_shape():
    target = focused_target()
    assert set(target) == {"role", "app", "accessible"}
    assert target["role"] is None or isinstance(target["role"], str)


def test_live_type_refuses_button_focus_without_typing(monkeypatch):
    monkeypatch.setattr(actions_module, "focused_target",
                        lambda: {"role": "AXButton", "app": "Finder", "accessible": True})
    report = MacActions(live=True).run({"action": "type_text", "text": "hello"})
    assert report["ok"] is False
    assert "not in a text field" in report["detail"]
    assert "AXButton" in report["detail"]


def test_dry_run_type_never_touches_accessibility(monkeypatch):
    def explode():
        raise AssertionError("dry-run must not query focus")

    monkeypatch.setattr(actions_module, "focused_target", explode)
    report = MacActions(live=False).run({"action": "type_text", "text": "hello"})
    assert report == {"ok": True, "dry": True, "detail": "would type: 'hello'"}


def test_utterance_report_carries_timings():
    from openjev.voice.agent import VoiceAgent
    outcome = VoiceAgent(live=False, overlay=False).handle_text("open the notes app")
    assert outcome["report"]["ok"] is True
    assert outcome["report"]["dry"] is True
    assert 0 <= outcome["timings"]["classify_ms"] < 50
    assert outcome["timings"]["execute_ms"] >= 0
