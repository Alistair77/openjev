from __future__ import annotations

import os

from openjev.backends import (
    DecisionBackend,
    LocalHeuristicBackend,
    MockBackend,
    OpenAICompatibleBackend,
    RemoteBackend,
)
from openjev.models import EvaluateRequest, EvaluateResponse


class OpenJev:
    """Small provider-neutral SDK facade."""

    def __init__(self, backend: DecisionBackend | None = None) -> None:
        self.backend = backend or self._backend_from_environment()

    @staticmethod
    def _backend_from_environment() -> DecisionBackend:
        backend = os.getenv("OPENJEV_BACKEND", "local")
        if backend == "mock":
            return MockBackend()
        if backend == "local":
            return LocalHeuristicBackend()
        if backend == "openai-compatible":
            return OpenAICompatibleBackend()
        if backend == "remote":
            return RemoteBackend()
        if backend == "research":
            from openjev.research.backend import ResearchBackend
            return ResearchBackend.from_environment()
        raise ValueError(f"unknown OpenJev backend: {backend}")

    async def evaluate(self, request: EvaluateRequest | dict) -> EvaluateResponse:
        parsed = request if isinstance(request, EvaluateRequest) else EvaluateRequest.model_validate(request)
        return await self.backend.evaluate(parsed)
