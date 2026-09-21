from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openjev.math import softmax


def features(text: str, size: int) -> list[float]:
    """L1-normalized byte histogram rescaled to unit L2 norm.

    v1 divided raw counts by byte length, leaving vectors with L2 norm
    ~0.25-0.35. Products context_i * option_i were then ~1e-3, so SGD
    gradients were tiny and default training (lr=0.2, 15 epochs) stayed
    at chance. L2 normalization keeps the same byte-interaction
    architecture but gives unit-norm vectors, ~12x larger interaction
    signal, and stable learning with the same hyperparameters.
    Checkpoints trained on v1 features should be retrained.
    """
    vector = [0.0] * size
    payload = text.lower().encode("utf-8", errors="ignore")
    for byte in payload:
        vector[byte % size] += 1.0
    length = max(1, len(payload))
    vector = [value / length for value in vector]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


ARCHITECTURE = "option-conditioned byte interaction v2 (l2-normalized)"


@dataclass
class OptionScorer:
    """A compact option-conditioned byte baseline, not a replica of proprietary Jev."""

    feature_size: int = 256
    weights: list[float] = field(default_factory=lambda: [0.0] * 256)
    bias: float = 0.0
    metadata: dict[str, object] = field(default_factory=lambda: {"architecture": ARCHITECTURE, "encoder": "byte-l2", "feature_size": 256, "license": "MIT"})

    def logits(self, context: str, options: list[str]) -> list[float]:
        context_features = features(context, self.feature_size)
        result = []
        for option in options:
            option_features = features(option, self.feature_size)
            interaction = sum(weight * left * right for weight, left, right in zip(self.weights, context_features, option_features))
            result.append(self.bias + interaction)
        return result

    def predict(self, context: str, options: list[str]) -> dict[str, float]:
        if len(options) < 2:
            raise ValueError("prediction requires at least two options")
        probabilities = softmax(self.logits(context, options))
        return {option: probability for option, probability in zip(options, probabilities)}

    def update(self, context: str, options: list[str], label: int, learning_rate: float) -> float:
        probabilities = softmax(self.logits(context, options))
        context_features = features(context, self.feature_size)
        for option_index, option in enumerate(options):
            option_features = features(option, self.feature_size)
            error = probabilities[option_index] - (1.0 if option_index == label else 0.0)
            for index in range(self.feature_size):
                self.weights[index] -= learning_rate * error * context_features[index] * option_features[index]
            self.bias -= learning_rate * error / len(options)
        return -math.log(max(probabilities[label], 1e-9))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> OptionScorer:
        payload = json.loads(path.read_text())
        return cls(**payload)
