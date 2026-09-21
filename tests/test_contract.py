import pytest
from pydantic import ValidationError

from openjev.models import EvaluateRequest


def test_choice_requires_two_options():
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate({"state": "x", "questions": {"route": {"type": "choice", "instructions": "route", "criteria": {"only": "only option"}}}})


def test_score_requires_descriptive_levels():
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate({"state": "x", "questions": {"severity": {"type": "score", "instructions": "severity", "criteria": ["low"]}}})


def test_empty_question_set_is_rejected():
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate({"state": "x", "questions": {}})
