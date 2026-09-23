"""Voice pipeline without a microphone: intents, slots, dry-run actions."""

import pytest

from openjev.voice.actions import MacActions
from openjev.voice.agent import VoiceAgent, classify, parse_hotkey
from openjev.voice.commands import build_action, extract_slots

INTENT_CASES = [
    ("open brave browser", "open_app", {"app": "Brave Browser"}),
    ("open the notes app", "open_app", {"app": "Notes"}),
    ("launch terminal please", "open_app", {"app": "Terminal"}),
    ("search youtube for lofi hip hop", "youtube", {"query": "lofi hip hop"}),
    ("play some jazz videos", "youtube", None),
    ("search the web for weather tomorrow", "web_search", None),
    ("type hello world this is a test", "type_text", {"text": "hello world this is a test"}),
    ("press enter", "press_key", {"key": "enter"}),
    ("copy that", "press_key", {"key": "cmd+c"}),
    ("mute the volume", "volume", {"level": "mute"}),
    ("make it louder", "volume", {"level": "up"}),
]


@pytest.mark.parametrize("utterance,expected_intent,expected_slots", INTENT_CASES)
def test_intent_classification(utterance, expected_intent, expected_slots):
    result = classify(utterance)
    assert result["intent"] == expected_intent, f"{utterance!r} -> {result}"
    assert result["action"]["action"] != "unheard"
    if expected_slots:
        slots = extract_slots(utterance, expected_intent)
        for key, value in expected_slots.items():
            assert slots.get(key) == value, f"{utterance!r} slots={slots}"


def test_gibberish_abstains_to_unheard():
    result = classify("flibberty wobble zephyr quark")
    assert result["intent"] is None
    assert result["action"]["action"] == "unheard"


def test_open_without_known_app_is_unheard():
    assert build_action("open_app", {}, "open the thingamajig")["action"] == "unheard"


def test_dry_run_never_claims_execution():
    actions = MacActions(live=False)
    assert actions.run({"action": "open_app", "app": "Notes"}) == {
        "ok": True, "dry": True, "detail": "would run: open -a Notes"}
    assert actions.run({"action": "youtube_search", "query": "cats"})["dry"] is True


def test_allowlist_blocks_unlisted_apps():
    actions = MacActions(live=True, allowed_apps={"Notes"})
    blocked = actions.run({"action": "open_app", "app": "Terminal"})
    assert blocked["ok"] is False and "allowed-apps" in blocked["detail"]


def test_text_mode_pipeline_end_to_end():
    agent = VoiceAgent(live=False)
    outcome = agent.handle_text("open brave browser")
    assert outcome["intent"] == "open_app"
    assert outcome["report"]["detail"] == "would run: open -a Brave Browser"


def test_parse_hotkey_rejects_garbage():
    assert parse_hotkey("tap:option") == ("tap", "option")
    assert parse_hotkey("<cmd>+<shift>+v") == ("combo", "<cmd>+<shift>+v")
    with pytest.raises(ValueError):
        parse_hotkey("just a key")
    with pytest.raises(ValueError):
        parse_hotkey("tap:spacebar")
