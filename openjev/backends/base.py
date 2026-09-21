from __future__ import annotations

from abc import ABC, abstractmethod

from openjev.models import EvaluateRequest, EvaluateResponse


class BackendError(RuntimeError):
    code = "backend_unavailable"


class BackendTimeout(BackendError):
    code = "backend_timeout"


class MalformedBackendResponse(BackendError):
    code = "malformed_backend_response"


class DecisionBackend(ABC):
    name: str
    model: str

    @abstractmethod
    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        """Evaluate every named question against the same state."""
