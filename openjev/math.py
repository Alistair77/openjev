from __future__ import annotations

import math


def clamp(value: float, lower: float = 1e-6, upper: float = 1 - 1e-6) -> float:
    return min(max(value, lower), upper)


def softmax(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("softmax requires values")
    maximum = max(values)
    exps = [math.exp(min(value - maximum, 700)) for value in values]
    total = sum(exps)
    return [value / total for value in exps]


def logit(probability: float) -> float:
    probability = clamp(probability)
    return math.log(probability / (1 - probability))


def normalized_entropy(probabilities: list[float]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    entropy = -sum(probability * math.log(probability) for probability in probabilities if probability)
    return entropy / math.log(len(probabilities))


def concentration_confidence(probabilities: list[float]) -> float:
    """One for a single peak, zero for an exactly uniform distribution."""
    return round(1 - normalized_entropy(probabilities), 6)


def normalize_mapping(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        raise ValueError("cannot normalize an empty mapping")
    safe = {key: max(0.0, float(value)) for key, value in raw.items()}
    total = sum(safe.values())
    if total <= 0:
        uniform = 1 / len(safe)
        return {key: uniform for key in safe}
    return {key: value / total for key, value in safe.items()}
