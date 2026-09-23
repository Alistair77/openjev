from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from openjev.client import OpenJev
from openjev.models import EvaluateRequest

app = typer.Typer(help="OpenJev - open, local-first decision intelligence.", no_args_is_help=True)


def print_json(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, default=str))


@app.command()
def evaluate(
    request_file: Path,
    backend: Annotated[
        str | None, typer.Option(help="local, mock, openai-compatible, remote, or research")
    ] = None,
) -> None:
    """Evaluate a versioned OpenJev request JSON file."""
    if backend:
        import os
        os.environ["OPENJEV_BACKEND"] = backend
    request = EvaluateRequest.model_validate_json(request_file.read_text())
    response = asyncio.run(OpenJev().evaluate(request))
    print_json(response.model_dump(mode="json"))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    """Serve the API, OpenAPI schema, and local playground."""
    import uvicorn
    uvicorn.run("openjev.api:app", host=host, port=port, reload=False)


@app.command()
def train(
    train_file: Path,
    validation: Annotated[Path, typer.Option()],
    output: Annotated[Path, typer.Option()],
    epochs: int = 30,
    learning_rate: float = 1.0,
) -> None:
    """Train the independent Jev-like option scorer from JSONL."""
    from openjev.research.train import train_model
    result = train_model(train_file, validation, output, epochs=epochs, learning_rate=learning_rate)
    print_json(result)


@app.command(name="eval")
def evaluate_checkpoint(checkpoint: Path, test_file: Path) -> None:
    """Evaluate a research checkpoint against held-out JSONL."""
    from openjev.research.train import evaluate_model
    print_json(evaluate_model(checkpoint, test_file))


@app.command()
def predict(
    checkpoint: Path,
    context: Annotated[str, typer.Option()],
    option: Annotated[list[str], typer.Option()],
) -> None:
    """Score a changing menu using a trained research checkpoint."""
    from openjev.research.model import OptionScorer
    model = OptionScorer.load(checkpoint)
    print_json({"probabilities": model.predict(context, option)})


@app.command()
def voice(
    hotkey: Annotated[str, typer.Option(help="GlobalHotKeys spec, e.g. '<cmd>+<shift>+v'")] = "<cmd>+<shift>+v",
    live: Annotated[bool, typer.Option(help="Actually execute actions (default is dry-run)")] = False,
    text: Annotated[bool, typer.Option(help="Text mode: type utterances, no microphone needed")] = False,
    stt: Annotated[str, typer.Option(help="sphinx (offline) or google (needs network)")] = "sphinx",
    confidence: float = 0.30,
    overlay: Annotated[bool, typer.Option("--overlay/--no-overlay", help="Floating state overlay (live mic mode only)")] = True,
) -> None:
    """Push-to-talk Mac voice control: hotkey toggles listening, utterances execute."""
    from openjev.voice.agent import VoiceAgent
    agent = VoiceAgent(hotkey=hotkey, live=live, confidence=confidence, stt=stt, overlay=overlay)
    if text:
        agent.run_text_mode()
    else:
        agent.start()
