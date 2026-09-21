from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from openjev.backends import LocalHeuristicBackend, MockBackend
from openjev.backends.base import BackendError
from openjev.client import OpenJev
from openjev.models import ErrorBody, EvaluateRequest, EvaluateResponse

app = FastAPI(title="OpenJev", version="0.1.0", description="Open, local-first typed decision intelligence.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "openjev"}


@app.post("/v1/evaluate", response_model=EvaluateResponse, responses={400: {"model": ErrorBody}, 502: {"model": ErrorBody}, 504: {"model": ErrorBody}})
async def evaluate(request: EvaluateRequest, http_request: Request) -> EvaluateResponse:
    try:
        selected = http_request.headers.get("X-OpenJev-Backend", "").lower()
        backend = MockBackend() if selected == "mock" else LocalHeuristicBackend() if selected == "local" else None
        return await OpenJev(backend=backend).evaluate(request)
    except BackendError as error:
        status = 504 if error.code == "backend_timeout" else 502
        body = ErrorBody(code=error.code, message=str(error))
        raise HTTPException(status_code=status, detail=body.model_dump(mode="json")) from error
    except ValueError as error:
        body = ErrorBody(code="invalid_request", message=str(error))
        raise HTTPException(status_code=400, detail=body.model_dump(mode="json")) from error


@app.get("/")
async def playground() -> FileResponse:
    return FileResponse("web/index.html")


app.mount("/assets", StaticFiles(directory="web"), name="assets")
