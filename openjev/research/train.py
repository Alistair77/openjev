from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

from openjev.research.model import OptionScorer


def records(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in rows:
        if not isinstance(row.get("context"), str) or not isinstance(row.get("options"), list):
            raise TypeError("each JSONL row requires string context and option list")
        if len(row["options"]) < 2 or not 0 <= row.get("label", -1) < len(row["options"]):
            raise ValueError("every row must contain a valid zero-based label and at least two options")
    return rows


def metrics(model: OptionScorer, rows: list[dict]) -> dict[str, float]:
    correct = top3 = 0
    log_loss = brier = ece = 0.0
    bins = [[] for _ in range(10)]
    started = time.perf_counter()
    for row in rows:
        probabilities = model.predict(row["context"], row["options"])
        values = list(probabilities.values())
        label = row["label"]
        ordered = sorted(range(len(values)), key=lambda index: values[index], reverse=True)
        correct += ordered[0] == label
        top3 += label in ordered[:3]
        log_loss -= math.log(max(values[label], 1e-9))
        brier += sum((value - (1 if index == label else 0)) ** 2 for index, value in enumerate(values))
        confidence = values[ordered[0]]
        bins[min(9, int(confidence * 10))].append((confidence, ordered[0] == label))
    for bucket in bins:
        if bucket:
            avg_confidence = sum(item[0] for item in bucket) / len(bucket)
            avg_accuracy = sum(item[1] for item in bucket) / len(bucket)
            ece += len(bucket) / len(rows) * abs(avg_confidence - avg_accuracy)
    return {"top1_accuracy": correct / len(rows), "top3_accuracy": top3 / len(rows), "log_loss": log_loss / len(rows), "brier_score": brier / len(rows), "expected_calibration_error": ece, "mean_latency_ms": ((time.perf_counter() - started) * 1000) / len(rows)}


def shuffled_context_control(model: OptionScorer, rows: list[dict]) -> dict[str, float]:
    shuffled = rows[:]
    contexts = [row["context"] for row in shuffled]
    random.Random(7).shuffle(contexts)
    control = [{**row, "context": context} for row, context in zip(shuffled, contexts)]
    return metrics(model, control)


def train_model(train_file: Path, validation_file: Path, output: Path, *, epochs: int, learning_rate: float) -> dict:
    from openjev.research.model import ARCHITECTURE

    train_rows, validation_rows = records(train_file), records(validation_file)
    model = OptionScorer(metadata={"architecture": ARCHITECTURE, "encoder": "byte-l2", "feature_size": 256, "training_file": train_file.name, "license": "MIT"})
    randomizer = random.Random(7)
    history = []
    for epoch in range(epochs):
        randomizer.shuffle(train_rows)
        loss = sum(model.update(row["context"], row["options"], row["label"], learning_rate) for row in train_rows) / len(train_rows)
        history.append({"epoch": epoch + 1, "loss": loss, "validation": metrics(model, validation_rows)})
    model.metadata["training"] = {"epochs": epochs, "learning_rate": learning_rate, "seed": 7}
    model.save(output)
    return {"checkpoint": str(output), "history": history, "shuffled_context_control": shuffled_context_control(model, validation_rows)}


def evaluate_model(checkpoint: Path, test_file: Path) -> dict:
    model, test_rows = OptionScorer.load(checkpoint), records(test_file)
    return {"metrics": metrics(model, test_rows), "shuffled_context_control": shuffled_context_control(model, test_rows), "checkpoint_metadata": model.metadata}
