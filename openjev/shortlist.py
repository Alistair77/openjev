"""Coarse-to-fine shortlisting for high-cardinality choice questions.

Pattern adapted from NandhaKishorM/laya (`laya/shortlist.py`, Apache-2.0): when a
choice has dozens of options, score every option is wasteful and — for lexical
backends — diffuse. Embed the state and each option with a caller-supplied
`embed_fn`, keep the top-k by cosine similarity, and evaluate only those.

This repo additionally ships :func:`lexical_embed_fn`, a dependency-free
token-overlap embedding so shortlisting works offline with the local backend.
Probabilities on a shortlisted choice are over the kept labels only; the
reduction is reported in the returned metadata so the audit trace stays honest.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

from openjev.backends.local import flatten, tokens

DEFAULT_SHORTLIST_K = 20


def lexical_embed_fn() -> Callable[[Sequence[str]], list[list[float]]]:
    """Offline token-overlap embedding over a shared vocabulary.

    Vectors are L2-normalized token-count histograms over the union vocabulary
    of the embedded batch, using this repo's token normalization (so `charged`
    and `charge` share a dimension). Zero vectors stay zero and never outrank.
    """

    def embed(texts: Sequence[str]) -> list[list[float]]:
        counters = [tokens(text) for text in texts]
        vocabulary = sorted({term for counter in counters for term in counter})
        index = {term: position for position, term in enumerate(vocabulary)}
        matrix = [[0.0] * len(vocabulary) for _ in texts]
        for row, counter in enumerate(counters):
            for term, count in counter.items():
                matrix[row][index[term]] = float(count)
            norm = math.sqrt(sum(value * value for value in matrix[row]))
            if norm > 0:
                matrix[row] = [value / norm for value in matrix[row]]
        return matrix

    return embed


def shortlist_choice(
    state: Any,
    criteria: dict[str, Any],
    embed_fn: Callable[[Sequence[str]], Sequence[Sequence[float]]],
    k: int = DEFAULT_SHORTLIST_K,
) -> dict[str, Any]:
    """Keep the top-k choice labels for `state`, with audit metadata.

    Returns `{"labels", "scores", "k", "n", "passthrough"}`. When `k` covers
    every label, all labels return in original order and `embed_fn` is never
    called (`passthrough=True`, `scores=None`).
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be a positive integer, got {k!r}")
    if not isinstance(criteria, dict) or not criteria:
        raise ValueError("choice criteria must be a non-empty dict")
    labels = list(criteria)
    if k >= len(labels):
        return {"labels": labels, "scores": None, "k": k, "n": len(labels), "passthrough": True}
    if not callable(embed_fn):
        raise TypeError("embed_fn must be callable")

    query = flatten(state)
    options = [f"{label} {flatten(description)}" for label, description in criteria.items()]
    matrix = [list(map(float, row)) for row in embed_fn([query] + options)]
    if len(matrix) != len(options) + 1 or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("embed_fn must return one vector per input text")
    scored = sorted(
        range(len(labels)),
        key=lambda position: (-_cosine(matrix[0], matrix[position + 1]), position),
    )[:k]
    return {
        "labels": [labels[position] for position in scored],
        "scores": [_cosine(matrix[0], matrix[position + 1]) for position in scored],
        "k": k,
        "n": len(labels),
        "passthrough": False,
    }


def reduce_questions(
    questions: dict[str, Any],
    kept: dict[str, list[str]],
) -> dict[str, Any]:
    """Return a copy of `questions` with choice criteria restricted to kept labels."""
    reduced: dict[str, Any] = {}
    for question_id, definition in questions.items():
        if question_id in kept and isinstance(definition, dict) and definition.get("type") == "choice":
            updated = dict(definition)
            updated["criteria"] = {
                label: definition["criteria"][label] for label in kept[question_id]
            }
            reduced[question_id] = updated
        else:
            reduced[question_id] = definition
    return reduced


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
