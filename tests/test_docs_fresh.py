"""README must quote the same numbers as the committed captures.

Practice adapted from openJev-verdict-2.0's test_docs_fresh.py: documentation
drift is a test failure, not a vibe. If you regenerate docs/captures, update
README.md to match (or vice versa).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_readme_matches_captures():
    readme = (ROOT / "README.md").read_text()
    evaluation = json.loads((ROOT / "docs" / "captures" / "eval_result.json").read_text())
    training = json.loads((ROOT / "docs" / "captures" / "training_result.json").read_text())

    metrics = evaluation["metrics"]
    for key in ("top1_accuracy", "log_loss", "brier_score"):
        assert str(round(metrics[key], 3)) in readme, f"README missing eval {key}={metrics[key]}"

    history = training["history"]
    assert str(round(history[0]["loss"], 3)) in readme, "README missing first-epoch loss"
    assert str(round(history[-1]["loss"], 3)) in readme, "README missing final loss"
    checkpoint_path = ROOT / "runs" / "demo" / "model.json"
    if checkpoint_path.exists():  # runs/ is gitignored; checked when present locally
        checkpoint = json.loads(checkpoint_path.read_text())
        assert "temperature" in checkpoint, "demo checkpoint must carry fitted temperature"
