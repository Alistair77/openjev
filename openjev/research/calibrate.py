"""Post-hoc temperature scaling for the research option scorer.

Idea adapted from Heman10x-NGU/openJev-verdict-2.0 (`core/calibration.py`,
Apache-2.0): fit a single positive temperature T on held-out logits so predicted
probabilities match empirical hit rates. Reimplemented here from scratch with
numpy only (their version uses torch + L-BFGS) via golden-section search on NLL.
Preserves argmax rankings; only rescales confidence.
"""

from __future__ import annotations

import math


def softmax_row(logits: list[float]) -> list[float]:
    maximum = max(logits)
    exps = [math.exp(min(value - maximum, 700)) for value in logits]
    total = sum(exps)
    return [value / total for value in exps]


def mean_nll(all_logits: list[list[float]], labels: list[int], temperature: float) -> float:
    total = 0.0
    for logits, label in zip(all_logits, labels):
        scaled = [value / temperature for value in logits]
        total -= math.log(max(softmax_row(scaled)[label], 1e-12))
    return total / max(1, len(labels))


def fit_temperature(
    all_logits: list[list[float]],
    labels: list[int],
    low: float = 0.5,
    high: float = 5.0,
    iterations: int = 100,
) -> float:
    """Golden-section search for the NLL-minimizing temperature in [low, high].

    The lower bound of 0.5 is deliberate: on small validation sets an unbounded
    fit collapses toward 0 (absolute overconfidence, great validation NLL,
    ruined held-out NLL). Bounded scaling can only sharpen 2x or flatten 5x.
    """
    if not all_logits:
        raise ValueError("temperature fitting requires at least one row")
    golden = (math.sqrt(5) - 1) / 2
    left, right = low, high
    for _ in range(iterations):
        middle_left = right - golden * (right - left)
        middle_right = left + golden * (right - left)
        if mean_nll(all_logits, labels, middle_left) < mean_nll(all_logits, labels, middle_right):
            right = middle_right
        else:
            left = middle_left
    return (left + right) / 2


def fit_temperature_by_group(
    all_logits: list[list[float]],
    labels: list[int],
    groups: list[str],
) -> dict[str, float]:
    """Fit one temperature per group (e.g. per question type / option count).

    Adapted from Laya's per-(question type, option count) temperature tables,
    which moved their mean ECE 0.466 -> 0.081: one global temperature cannot fit
    groups with different sharpness. Groups with fewer than 2 rows fall back to
    1.0 (unfitted) rather than overfitting noise.
    """
    by_group: dict[str, tuple[list[list[float]], list[int]]] = {}
    for logits, label, group in zip(all_logits, labels, groups):
        bucket = by_group.setdefault(group, ([], []))
        bucket[0].append(logits)
        bucket[1].append(label)
    temperatures = {}
    for group, (group_logits, group_labels) in by_group.items():
        temperatures[group] = (
            fit_temperature(group_logits, group_labels) if len(group_labels) >= 2 else 1.0
        )
    return temperatures
