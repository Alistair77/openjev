import json

from openjev.research.model import OptionScorer
from openjev.research.train import evaluate_model, train_model


def write_rows(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows))


def test_train_and_evaluate_research_scorer(tmp_path):
    rows = [{"context": "duplicate charge refund", "options": ["billing refund", "technical bug"], "label": 0}, {"context": "application crashes with error", "options": ["billing refund", "technical bug crash"], "label": 1}] * 8
    train, validation, checkpoint = tmp_path / "train.jsonl", tmp_path / "validation.jsonl", tmp_path / "model.json"
    write_rows(train, rows); write_rows(validation, rows)
    result = train_model(train, validation, checkpoint, epochs=3, learning_rate=0.5)
    assert checkpoint.exists()
    assert result["history"]
    assert "top1_accuracy" in evaluate_model(checkpoint, validation)["metrics"]
    assert isinstance(OptionScorer.load(checkpoint).predict("refund", ["billing refund", "technical bug"]), dict)
