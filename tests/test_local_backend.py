import pytest

from openjev.backends.local import LocalHeuristicBackend
from openjev.models import EvaluateRequest


@pytest.mark.asyncio
async def test_local_backend_returns_normalized_typed_results():
    request = EvaluateRequest.model_validate({"state": "I was charged twice and need a refund.", "questions": {"route": {"type": "choice", "instructions": "Who handles this?", "criteria": {"billing": "charges and refunds", "technical": "product bug"}}, "urgent": {"type": "score", "instructions": "How urgent?", "criteria": ["routine", "repeat financial problem"]}, "refund": {"type": "noul", "instructions": "The person wants a refund."}}})
    response = await LocalHeuristicBackend().evaluate(request)
    assert response.answers["route"].choice == "billing"
    assert sum(response.answers["route"].probabilities.values()) == pytest.approx(1)
    assert response.answers["urgent"].score >= 0
    assert 0 <= response.answers["refund"].noul <= 1
    assert len(response.trace) == 3


@pytest.mark.asyncio
async def test_threshold_can_abstain():
    request = EvaluateRequest.model_validate({"state": "unrelated", "questions": {"route": {"type": "choice", "instructions": "Who handles this?", "criteria": {"billing": "charges", "technical": "bugs"}}}, "options": {"abstain_below": 0.9}})
    response = await LocalHeuristicBackend().evaluate(request)
    assert response.answers["route"].abstained
