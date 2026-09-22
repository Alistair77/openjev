"""Every preset must validate against the strict v1 contract."""

from openjev import presets
from openjev.models import EvaluateRequest


def _valid(questions) -> None:
    EvaluateRequest.model_validate({"state": "Charged twice, need a refund.", "questions": questions})


def test_triage_preset_is_valid():
    questions = presets.triage_questions()
    assert set(questions) == {"intent", "is_urgent", "frustration", "refund_requested", "churn_risk"}
    _valid(questions)


def test_email_preset_is_valid_with_default_and_custom_categories():
    _valid(presets.email_questions())
    _valid(presets.email_questions({"a": "team a", "b": "team b"}))


def test_guard_preset_is_valid():
    questions = presets.guard_questions()
    assert set(questions) == {"jailbreak", "prompt_injection", "sensitive_data", "harm_severity", "topic"}
    _valid(questions)


def test_moderation_preset_is_valid():
    _valid(presets.moderation_questions())


def test_router_preset_is_valid():
    questions = presets.router_questions()
    assert set(questions) == {"difficulty", "domain", "needs_tools", "is_sensitive"}
    _valid(questions)
