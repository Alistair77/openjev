from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx

from openjev.backends.base import (
    BackendError,
    BackendTimeout,
    DecisionBackend,
    MalformedBackendResponse,
)
from openjev.math import concentration_confidence, normalize_mapping
from openjev.models import (
    Alternative,
    ChoiceAnswer,
    ChoiceQuestion,
    EvaluateRequest,
    EvaluateResponse,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
    TraceEvent,
    Usage,
)


class OpenAICompatibleBackend(DecisionBackend):
    name = "openai-compatible"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OPENJEV_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENJEV_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENJEV_MODEL", "gpt-4o-mini")
        if not self.api_key:
            raise ValueError("openai-compatible backend requires OPENJEV_API_KEY or OPENAI_API_KEY")

    async def _ask(self, client: httpx.AsyncClient, state: Any, candidate: str, description: Any) -> tuple[float, dict[str, int]]:
        prompt = {
            "role": "typed decision scorer",
            "task": "Return a JSON object with only p, a number from 0 to 1. p is the support in state for this candidate. Do not explain.",
            "state": state,
            "candidate": candidate,
            "description": description,
        }
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": json.dumps(prompt)}]},
            )
            response.raise_for_status()
            payload = response.json()
            parsed = json.loads(payload["choices"][0]["message"]["content"])
            probability = float(parsed["p"])
            if not 0 <= probability <= 1:
                raise ValueError("p outside [0, 1]")
            usage = payload.get("usage", {})
            return probability, {"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)}
        except httpx.TimeoutException as error:
            raise BackendTimeout("provider request timed out") from error
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise MalformedBackendResponse("provider did not return {p: number}") from error
        except httpx.HTTPError as error:
            raise BackendError(f"provider request failed: {error}") from error

    @staticmethod
    def _extras(probabilities: dict[str, float], top_k: int) -> tuple[float, list[Alternative], float]:
        ordered = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        confidence = concentration_confidence(list(probabilities.values()))
        margin = ordered[0][1] - ordered[1][1] if len(ordered) > 1 else 1.0
        return confidence, [Alternative(key=key, probability=value) for key, value in ordered[:top_k]], margin

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        started = time.perf_counter()
        tasks: list[tuple[str, object, dict[str, object]]] = []
        for question_id, question in request.questions.items():
            if isinstance(question, ChoiceQuestion):
                tasks.append((question_id, question, question.criteria))
            elif isinstance(question, ScoreQuestion):
                tasks.append((question_id, question, {str(index): value for index, value in enumerate(question.criteria)}))
            elif isinstance(question, NoulQuestion):
                tasks.append((question_id, question, {"true": question.instructions, "false": "The statement is not supported by the state."}))
        async with httpx.AsyncClient(timeout=request.options.timeout_seconds) as client:
            raw = await asyncio.gather(*[self._score_question(client, request.state, question_id, candidates) for question_id, _, candidates in tasks])
        answers = {}
        trace = []
        total_input = total_output = 0
        for (question_id, question, candidates), (probabilities, usage, latency) in zip(tasks, raw):
            total_input += usage["input_tokens"]
            total_output += usage["output_tokens"]
            confidence, alternatives, margin = self._extras(probabilities, request.options.top_k)
            abstained = bool(request.options.abstain_below is not None and confidence < request.options.abstain_below)
            common = {
                "probabilities": probabilities,
                "confidence": confidence,
                "abstained": abstained,
                "abstention_reason": "distribution is too diffuse" if abstained else None,
                "alternatives": alternatives,
                "margin": margin,
                "calibration": {"method": "uncalibrated provider micro-sampling"},
            }
            if isinstance(question, ChoiceQuestion):
                answers[question_id] = ChoiceAnswer(choice=max(probabilities, key=probabilities.get), **common)
            elif isinstance(question, ScoreQuestion):
                answers[question_id] = ScoreAnswer(score=sum(int(key) * value for key, value in probabilities.items()), legend=candidates, **common)
            else:
                answers[question_id] = NoulAnswer(noul=probabilities["true"], **common)
            trace.append(TraceEvent(question_id=question_id, backend=self.name, latency_ms=latency, detail={"parallel_candidates": len(candidates)}))
        return EvaluateResponse(model=self.model, backend=self.name, answers=answers, usage=Usage(input_tokens=total_input, output_tokens=total_output), latency_ms=(time.perf_counter() - started) * 1000, trace=trace if request.options.trace else [])

    async def _score_question(self, client: httpx.AsyncClient, state: Any, question_id: str, candidates: dict[str, object]) -> tuple[dict[str, float], dict[str, int], float]:
        started = time.perf_counter()
        values = await asyncio.gather(*[self._ask(client, state, key, value) for key, value in candidates.items()])
        probabilities = normalize_mapping({key: value[0] for key, value in zip(candidates, values)})
        usage = {"input_tokens": sum(value[1]["input_tokens"] for value in values), "output_tokens": sum(value[1]["output_tokens"] for value in values)}
        return probabilities, usage, (time.perf_counter() - started) * 1000
