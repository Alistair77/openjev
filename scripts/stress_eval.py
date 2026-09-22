"""Redline the local decision backend: find its ceiling before real use cases bet on it.

Slices: routing accuracy, urgency scoring, noul truth, paraphrases, negations,
option-order flips, missing-option behavior, out-of-scope abstention, load.
Writes: docs/captures/stress_eval.json
Run: `.venv/bin/python scripts/stress_eval.py`
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROUTE_CRITERIA = {
    "billing": "charges invoices payments duplicate refunds money",
    "technical": "bugs crashes errors outages failures broken login",
    "sales": "pricing plans demos contracts purchase",
    "other": "everything else: greetings, thanks, general chatter",
}
URGENCY_LEVELS = [
    "routine: no time pressure, whenever convenient",
    "soon: needs attention this week",
    "critical: deadline today, blocking issue, ASAP",
]
REFUND_INSTRUCTION = "The customer explicitly requests a refund."

ROUTING_CASES = [
    ("I was charged twice on my credit card", "billing"),
    ("Need a refund for the duplicate payment", "billing"),
    ("My invoice shows the wrong amount", "billing"),
    ("Please reimburse the extra fee", "billing"),
    ("Why is there a second charge on my statement?", "billing"),
    ("The app crashes every time I open it", "technical"),
    ("Getting error 500 when I try to log in", "technical"),
    ("The dashboard is broken since the update", "technical"),
    ("Our integration is down, webhook failures all morning", "technical"),
    ("The system is malfunctioning after deploy", "technical"),
    ("What does the enterprise plan cost per seat?", "sales"),
    ("Can I get a demo of the reporting module?", "sales"),
    ("Do you offer annual contracts with a discount?", "sales"),
    ("Thanks, that solved it. Have a great day!", "other"),
    ("Hello, just checking your opening hours", "other"),
]

URGENCY_CASES = [
    ("No rush, whenever you get a chance", 0),
    ("Take your time, low priority", 0),
    ("Please look at this sometime this week", 1),
    ("Needs attention soon, customers are noticing", 1),
    ("URGENT: everything is down, fix ASAP", 2),
    ("Blocking issue, hard deadline today", 2),
]

NOUL_CASES = [
    ("I want my money back right now", True),
    ("Please refund the duplicate charge", True),
    ("Give me a reimbursement for last month", True),
    ("I am not asking for a refund, just asking about my invoice", False),
    ("No refund needed, thanks for the help", False),
    ("How do I update my payment method?", False),
]

OOS_CASES = [
    "flibberty gibbet wobble zephyr quark",
    "....,,,,!!!!????",
    "ok",
]

MISSING_OPTION_CASES = [
    ("I was charged twice, refund please", {"technical": ROUTE_CRITERIA["technical"], "sales": ROUTE_CRITERIA["sales"]}),
    ("The app crashes on launch", {"billing": ROUTE_CRITERIA["billing"], "sales": ROUTE_CRITERIA["sales"]}),
]


async def evaluate(backend, state, questions, abstain_below=0.25):
    from openjev.models import EvaluateRequest

    request = EvaluateRequest.model_validate(
        {"state": state, "questions": questions, "options": {"abstain_below": abstain_below}}
    )
    return await backend.evaluate(request)


async def main() -> None:
    from openjev.backends.local import LocalHeuristicBackend

    backend = LocalHeuristicBackend()
    receipt: dict = {"slices": {}, "notes": []}
    correct = total = 0

    def route_q(criteria=None):
        return {"route": {"type": "choice", "instructions": "Route it", "criteria": criteria or ROUTE_CRITERIA}}

    # 1. routing
    for state, expected in ROUTING_CASES:
        answer = (await evaluate(backend, state, route_q())).answers["route"]
        hit = answer.choice == expected and not answer.abstained
        correct += hit
        total += 1
        if not hit:
            receipt.setdefault("routing_misses", []).append(
                {"state": state, "expected": expected, "got": answer.choice,
                 "conf": round(answer.confidence, 3), "abstained": answer.abstained}
            )
    receipt["slices"]["routing_accuracy"] = round(correct / len(ROUTING_CASES), 4)

    # 2. paraphrase: same intents, words outside the normalization map
    paraphrases = [
        ("Kindly reimburse the surplus amount billed", "billing"),
        ("The service is down and nothing loads", "technical"),
        ("Please send back my funds for the double billing", "billing"),
        ("It keeps freezing whenever I upload a file", "technical"),
    ]
    hits = 0
    for state, expected in paraphrases:
        answer = (await evaluate(backend, state, route_q())).answers["route"]
        hits += answer.choice == expected and not answer.abstained
    receipt["slices"]["paraphrase_accuracy"] = round(hits / len(paraphrases), 4)

    # 3. urgency scoring (within-one-level counts, like Laya's 0.99 metric)
    exact = within_one = 0
    for state, expected in URGENCY_CASES:
        questions = {"urgency": {"type": "score", "instructions": "How urgent?", "criteria": URGENCY_LEVELS}}
        answer = (await evaluate(backend, state, questions)).answers["urgency"]
        predicted = min(2, max(0, round(answer.score)))
        exact += predicted == expected
        within_one += abs(predicted - expected) <= 1
    receipt["slices"]["urgency_exact"] = round(exact / len(URGENCY_CASES), 4)
    receipt["slices"]["urgency_within_one"] = round(within_one / len(URGENCY_CASES), 4)

    # 4. noul incl. negations
    hits = 0
    for state, expected in NOUL_CASES:
        questions = {"refund": {"type": "noul", "instructions": REFUND_INSTRUCTION}}
        answer = (await evaluate(backend, state, questions)).answers["refund"]
        predicted = answer.noul >= 0.5
        hits += predicted == expected
    receipt["slices"]["noul_accuracy"] = round(hits / len(NOUL_CASES), 4)

    # 5. option-order flips (shuffle criteria order, count answer changes)
    flips = trials = 0
    rng = random.Random(11)
    for state, _ in ROUTING_CASES[:8]:
        base = (await evaluate(backend, state, route_q())).answers["route"].choice
        for _ in range(3):
            items = list(ROUTE_CRITERIA.items())
            rng.shuffle(items)
            other = (await evaluate(backend, state, route_q(dict(items)))).answers["route"].choice
            trials += 1
            flips += base != other
    receipt["slices"]["option_order_flip_rate"] = round(flips / trials, 4)

    # 6. missing option: correct answer removed -> must abstain, not guess
    abstained = 0
    for state, criteria in MISSING_OPTION_CASES:
        answer = (await evaluate(backend, state, route_q(criteria))).answers["route"]
        abstained += answer.abstained
    receipt["slices"]["missing_option_abstention_rate"] = round(abstained / len(MISSING_OPTION_CASES), 4)

    # 7. out-of-scope -> must abstain
    abstained = 0
    for state in OOS_CASES:
        answer = (await evaluate(backend, state, route_q())).answers["route"]
        abstained += answer.abstained
    receipt["slices"]["oos_abstention_rate"] = round(abstained / len(OOS_CASES), 4)

    # 8. load: 50 concurrent full requests
    from openjev.models import EvaluateRequest

    batch = EvaluateRequest.model_validate_json((ROOT / "examples" / "support_ticket.json").read_text())
    started = time.perf_counter()
    await asyncio.gather(*[backend.evaluate(batch) for _ in range(50)])
    elapsed = (time.perf_counter() - started) * 1000
    receipt["slices"]["load_50_concurrent_ms"] = round(elapsed, 2)
    receipt["slices"]["throughput_per_sec"] = round(50 / (elapsed / 1000), 1)

    receipt["overall_routing_style_accuracy"] = round(correct / total, 4)
    out = ROOT / "docs" / "captures" / "stress_eval.json"
    out.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
