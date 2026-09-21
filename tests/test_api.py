from fastapi.testclient import TestClient

from openjev.api import app


def test_health_and_evaluate_endpoint():
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/v1/evaluate", json={"state": "Need a refund for duplicate charge", "questions": {"route": {"type": "choice", "instructions": "Route it", "criteria": {"billing": "charges refunds", "technical": "bugs"}}}})
    assert response.status_code == 200
    assert response.json()["answers"]["route"]["choice"] == "billing"
