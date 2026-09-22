from __future__ import annotations

import json
import re
import time
from collections import Counter

from openjev.backends.base import DecisionBackend
from openjev.lang import analyse as analyse_language
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
)

TOKEN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {"the", "a", "an", "and", "or", "for", "to", "of", "in", "is", "this", "that"}
NORMALIZED_TERMS = {
    "charged": "charge",
    "charges": "charge",
    "refunds": "refund",
    "bugs": "bug",
    "crashes": "crash",
    "problems": "problem",
    "payments": "payment",
    "twice": "duplicate",
    "second": "repeated",
    "money": "refund",
    "back": "refund",
    "need": "request",
    "needs": "request",
    "requested": "request",
}


def flatten(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def tokens(value: object) -> Counter[str]:
    raw = TOKEN.findall(flatten(value).lower())
    return Counter(NORMALIZED_TERMS.get(token, token) for token in raw if token not in STOP_WORDS)


class LocalHeuristicBackend(DecisionBackend):
    """Offline lexical baseline for demos and safe development, not a general semantic model."""

    name = "local"
    model = "local-heuristic-v1"

    @staticmethod
    def _distribution(state: object, candidates: dict[str, object]) -> dict[str, float]:
        state_tokens = tokens(state)
        scores: dict[str, float] = {}
        for key, description in candidates.items():
            option_tokens = tokens(f"{key} {flatten(description)}")
            overlap = sum(min(state_tokens[token], count) for token, count in option_tokens.items())
            keyword_bonus = 0.0
            for token in option_tokens:
                if len(token) > 3 and token in state_tokens:
                    keyword_bonus += 0.4
            scores[key] = 0.15 + overlap + keyword_bonus
        return normalize_mapping(scores)

    @staticmethod
    def _alternatives(probabilities: dict[str, float], top_k: int) -> tuple[list[Alternative], float]:
        ordered = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        margin = ordered[0][1] - ordered[1][1] if len(ordered) > 1 else 1.0
        return [Alternative(key=key, probability=value) for key, value in ordered[:top_k]], margin

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        started = time.perf_counter()
        answers = {}
        trace = []
        language = analyse_language(request.state)
        strategy = {"strategy": "lexical overlap", "state_script": language["script"]}
        if not language["is_english"]:
            strategy["warning"] = "non-English state: lexical matching is unreliable, expect abstention"
        for question_id, question in request.questions.items():
            question_started = time.perf_counter()
            if isinstance(question, ChoiceQuestion):
                probabilities = self._distribution(request.state, question.criteria)
                choice = max(probabilities, key=probabilities.get)
                alternatives, margin = self._alternatives(probabilities, request.options.top_k)
                confidence = concentration_confidence(list(probabilities.values()))
                abstained = bool(request.options.abstain_below is not None and confidence < request.options.abstain_below)
                answers[question_id] = ChoiceAnswer(
                    choice=choice,
                    probabilities=probabilities,
                    confidence=confidence,
                    abstained=abstained,
                    abstention_reason="distribution is too diffuse" if abstained else None,
                    alternatives=alternatives,
                    margin=margin,
                    calibration={"method": "uncalibrated lexical baseline"},
                )
            elif isinstance(question, ScoreQuestion):
                criteria = {str(index): level for index, level in enumerate(question.criteria)}
                probabilities = self._distribution(request.state, criteria)
                score = sum(int(key) * probability for key, probability in probabilities.items())
                alternatives, margin = self._alternatives(probabilities, request.options.top_k)
                confidence = concentration_confidence(list(probabilities.values()))
                abstained = bool(request.options.abstain_below is not None and confidence < request.options.abstain_below)
                answers[question_id] = ScoreAnswer(
                    score=round(score, 6),
                    legend=criteria,
                    probabilities=probabilities,
                    confidence=confidence,
                    abstained=abstained,
                    abstention_reason="distribution is too diffuse" if abstained else None,
                    alternatives=alternatives,
                    margin=margin,
                    calibration={"method": "uncalibrated lexical baseline"},
                )
            elif isinstance(question, NoulQuestion):
                positive = self._distribution(request.state, {"true": question.instructions, "false": "The statement is not supported by the state."})
                noul = positive["true"]
                probabilities = {"true": noul, "false": 1 - noul}
                alternatives, margin = self._alternatives(probabilities, request.options.top_k)
                confidence = concentration_confidence(list(probabilities.values()))
                abstained = bool(request.options.abstain_below is not None and confidence < request.options.abstain_below)
                answers[question_id] = NoulAnswer(
                    noul=noul,
                    probabilities=probabilities,
                    confidence=confidence,
                    abstained=abstained,
                    abstention_reason="evidence is balanced" if abstained else None,
                    alternatives=alternatives,
                    margin=margin,
                    calibration={"method": "uncalibrated lexical baseline"},
                )
            trace.append(TraceEvent(question_id=question_id, backend=self.name, latency_ms=(time.perf_counter() - question_started) * 1000, detail=dict(strategy)))
        return EvaluateResponse(model=self.model, backend=self.name, answers=answers, latency_ms=(time.perf_counter() - started) * 1000, trace=trace if request.options.trace else [])
