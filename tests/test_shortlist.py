"""Coarse-to-fine shortlisting: keeps the right labels, reports honestly."""

import pytest

from openjev.shortlist import lexical_embed_fn, reduce_questions, shortlist_choice

CRITERIA = {
    "billing": "charges invoices duplicate refunds",
    "technical": "bugs crashes errors failures",
    "sales": "pricing contracts demos",
    "hr": "hiring leave payroll",
    "security": "phishing scams compromise",
}


def test_lexical_shortlist_keeps_relevant_labels():
    result = shortlist_choice("duplicate charge, refund my invoice", CRITERIA, lexical_embed_fn(), k=2)
    assert result["passthrough"] is False
    assert result["n"] == 5 and result["k"] == 2
    assert result["labels"][0] == "billing"
    assert len(result["scores"]) == 2


def test_passthrough_when_k_covers_everything():
    calls = []

    def counting_embed(texts):
        calls.append(texts)
        return [[1.0]] * len(texts)

    result = shortlist_choice("anything", CRITERIA, counting_embed, k=5)
    assert result["passthrough"] is True
    assert result["labels"] == list(CRITERIA)
    assert result["scores"] is None
    assert calls == []


def test_reduce_questions_restricts_only_listed_choice():
    questions = {
        "route": {"type": "choice", "instructions": "route", "criteria": dict(CRITERIA)},
        "urgent": {"type": "noul", "instructions": "urgent?"},
    }
    reduced = reduce_questions(questions, {"route": ["billing", "technical"]})
    assert list(reduced["route"]["criteria"]) == ["billing", "technical"]
    assert reduced["urgent"]["instructions"] == "urgent?"
    assert list(questions["route"]["criteria"]) == list(CRITERIA)  # caller not mutated


def test_invalid_k_and_criteria_rejected():
    with pytest.raises(ValueError):
        shortlist_choice("x", CRITERIA, lexical_embed_fn(), k=0)
    with pytest.raises(ValueError):
        shortlist_choice("x", {}, lexical_embed_fn(), k=2)
    with pytest.raises(TypeError):
        shortlist_choice("x", CRITERIA, "not-callable", k=2)
