from __future__ import annotations

import os
import time
from pathlib import Path

from openjev.backends.base import DecisionBackend
from openjev.math import concentration_confidence
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
)
from openjev.research.model import OptionScorer


class ResearchBackend(DecisionBackend):
    name = "research"

    def __init__(self, model: OptionScorer, source: str) -> None:
        self.scorer, self.model = model, f"research-option-scorer:{Path(source).name}"

    @classmethod
    def from_environment(cls) -> ResearchBackend:
        source = os.getenv("OPENJEV_RESEARCH_CHECKPOINT")
        if not source:
            raise ValueError("research backend requires OPENJEV_RESEARCH_CHECKPOINT")
        return cls(OptionScorer.load(Path(source)), source)

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        started, answers, trace = time.perf_counter(), {}, []
        state = str(request.state)
        for question_id, question in request.questions.items():
            question_started = time.perf_counter()
            if isinstance(question, ChoiceQuestion):
                probabilities = self.scorer.predict(state, list(question.criteria))
                answer_type, payload = ChoiceAnswer, {"choice": max(probabilities, key=probabilities.get)}
            elif isinstance(question, ScoreQuestion):
                options = [str(value) for value in question.criteria]
                probabilities = self.scorer.predict(state, options)
                probabilities = {str(index): probabilities[option] for index, option in enumerate(options)}
                answer_type, payload = ScoreAnswer, {"score": sum(int(key) * value for key, value in probabilities.items()), "legend": {str(index): value for index, value in enumerate(question.criteria)}}
            else:
                assert isinstance(question, NoulQuestion)
                probabilities = self.scorer.predict(state, [str(question.instructions), "The statement is not supported by the state."])
                probabilities = {"true": probabilities[str(question.instructions)], "false": probabilities["The statement is not supported by the state."]}
                answer_type, payload = NoulAnswer, {"noul": probabilities["true"]}
            ordered = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
            confidence = concentration_confidence(list(probabilities.values()))
            abstained = bool(request.options.abstain_below is not None and confidence < request.options.abstain_below)
            answers[question_id] = answer_type(probabilities=probabilities, confidence=confidence, abstained=abstained, abstention_reason="distribution is too diffuse" if abstained else None, alternatives=[Alternative(key=key, probability=value) for key, value in ordered[:request.options.top_k]], margin=ordered[0][1] - ordered[1][1], calibration={"method": "uncalibrated research checkpoint"}, **payload)
            trace.append(TraceEvent(question_id=question_id, backend=self.name, latency_ms=(time.perf_counter() - question_started) * 1000, detail={"checkpoint": self.model}))
        return EvaluateResponse(model=self.model, backend=self.name, answers=answers, latency_ms=(time.perf_counter() - started) * 1000, trace=trace if request.options.trace else [])
