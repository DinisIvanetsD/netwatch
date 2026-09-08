from fastapi.testclient import TestClient

from main import app


def test_health_endpoint_returns_structured_status() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code in {200, 503}
    body = response.json()
    assert body["service"] == "netwatch-backend"
    assert body["status"] in {"healthy", "degraded"}
    assert body["database"] in {"ready", "unavailable"}
