from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Recursive JSON aliases currently trigger a schema-generation recursion in
# Pydantic on Python 3.14. The typed decision envelope remains strict; state
# and human-authored criteria intentionally accept any JSON-serializable value.
JsonValue = Any
Criterion = Any


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: Criterion
    criteria: dict[str, Criterion]

    @field_validator("criteria")
    @classmethod
    def validate_options(cls, value: dict[str, Criterion]) -> dict[str, Criterion]:
        if len(value) < 2:
            raise ValueError("choice criteria requires at least two named options")
        if any(not key.strip() for key in value):
            raise ValueError("choice option keys cannot be empty")
        return value


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: Criterion
    criteria: list[Criterion]

    @field_validator("criteria")
    @classmethod
    def validate_levels(cls, value: list[Criterion]) -> list[Criterion]:
        if not 2 <= len(value) <= 10:
            raise ValueError("score criteria requires between two and ten ordered levels")
        return value


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: Criterion


Question = Annotated[ChoiceQuestion | ScoreQuestion | NoulQuestion, Field(discriminator="type")]


class EvaluateOptions(BaseModel):
    abstain_below: float | None = Field(default=0.2, ge=0, le=1)
    top_k: int = Field(default=3, ge=1, le=20)
    seed: int | None = None
    trace: bool = True
    timeout_seconds: float = Field(default=20, gt=0, le=120)


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: Literal["v1"] = "v1"
    state: JsonValue
    questions: dict[str, Question]
    options: EvaluateOptions = Field(default_factory=EvaluateOptions)

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, value: dict[str, Question]) -> dict[str, Question]:
        if not value:
            raise ValueError("at least one named question is required")
        if any(not key.strip() for key in value):
            raise ValueError("question identifiers cannot be empty")
        return value


class Alternative(BaseModel):
    key: str
    probability: float = Field(ge=0, le=1)


class AnswerBase(BaseModel):
    type: Literal["choice", "score", "noul"]
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    abstained: bool
    abstention_reason: str | None = None
    alternatives: list[Alternative] = Field(default_factory=list)
    margin: float | None = Field(default=None, ge=0, le=1)
    calibration: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_distribution(self) -> AnswerBase:
        if not self.probabilities:
            raise ValueError("answer probabilities cannot be empty")
        total = sum(self.probabilities.values())
        if abs(total - 1.0) > 0.0002:
            raise ValueError("answer probabilities must sum to one")
        return self


class ChoiceAnswer(AnswerBase):
    type: Literal["choice"] = "choice"
    choice: str


class ScoreAnswer(AnswerBase):
    type: Literal["score"] = "score"
    score: float
    legend: dict[str, Criterion]


class NoulAnswer(AnswerBase):
    type: Literal["noul"] = "noul"
    noul: float = Field(ge=0, le=1)


Answer = ChoiceAnswer | ScoreAnswer | NoulAnswer


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


class TraceEvent(BaseModel):
    question_id: str
    backend: str
    latency_ms: float = Field(ge=0)
    detail: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    api_version: Literal["v1"] = "v1"
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str
    backend: str
    answers: dict[str, Answer]
    usage: Usage = Field(default_factory=Usage)
    latency_ms: float = Field(ge=0)
    trace: list[TraceEvent] = Field(default_factory=list)


class ErrorBody(BaseModel):
    code: Literal[
        "invalid_request",
        "backend_unavailable",
        "backend_timeout",
        "malformed_backend_response",
        "calibration_failure",
        "internal_error",
    ]
    message: str
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    detail: dict[str, Any] = Field(default_factory=dict)
