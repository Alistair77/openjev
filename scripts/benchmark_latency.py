"""Latency receipt: p50/p90/p99 for the local backend and research scorer.

Practice adapted from openJev-verdict-2.0's E7 latency experiment (receipt-style
benchmarks committed to the repo). Run: `.venv/bin/python scripts/benchmark_latency.py`
Writes: docs/captures/latency.json
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {
        "runs": len(ordered),
        "mean_ms": statistics.mean(ordered),
        "min_ms": ordered[0],
        "p50_ms": pick(0.50),
        "p90_ms": pick(0.90),
        "p99_ms": pick(0.99),
        "max_ms": ordered[-1],
    }


async def main() -> None:
    from openjev.backends.local import LocalHeuristicBackend
    from openjev.models import EvaluateRequest
    from openjev.research.model import OptionScorer

    request = EvaluateRequest.model_validate_json((ROOT / "examples" / "support_ticket.json").read_text())
    backend = LocalHeuristicBackend()
    await backend.evaluate(request)  # warmup
    samples = []
    for _ in range(200):
        started = time.perf_counter()
        await backend.evaluate(request)
        samples.append((time.perf_counter() - started) * 1000)

    scorer = OptionScorer()
    scorer.predict("warmup", ["billing refund", "technical bug crash"])
    research_samples = []
    for _ in range(200):
        started = time.perf_counter()
        scorer.predict("refund my duplicate payment", ["billing refund", "technical bug crash"])
        research_samples.append((time.perf_counter() - started) * 1000)

    receipt = {
        "local_3_question_request": percentiles(samples),
        "research_single_predict": percentiles(research_samples),
    }
    output = ROOT / "docs" / "captures" / "latency.json"
    output.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
