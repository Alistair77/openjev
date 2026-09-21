"""Evaluate a JSON request with the local OpenJev package."""
import asyncio
import json
import sys
from pathlib import Path

from openjev import OpenJev

if len(sys.argv) != 2:
    raise SystemExit("usage: openjev_eval.py request.json")
request = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps(asyncio.run(OpenJev().evaluate(request)).model_dump(mode="json"), indent=2, default=str))
