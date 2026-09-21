from __future__ import annotations

import os

import httpx

from openjev.backends.base import (
    BackendError,
    BackendTimeout,
    DecisionBackend,
    MalformedBackendResponse,
)
from openjev.models import EvaluateRequest, EvaluateResponse


class RemoteBackend(DecisionBackend):
    name = "remote"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OPENJEV_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENJEV_API_KEY")
        self.model = "remote-openjev-v1"
        if not self.base_url:
            raise ValueError("remote backend requires OPENJEV_BASE_URL")

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=request.options.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/v1/evaluate", json=request.model_dump(mode="json"), headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise BackendTimeout("remote OpenJev timed out") from error
        except httpx.HTTPError as error:
            raise BackendError(f"remote OpenJev failed: {error}") from error
        try:
            return EvaluateResponse.model_validate(response.json())
        except Exception as error:
            raise MalformedBackendResponse("remote OpenJev returned an invalid response") from error
