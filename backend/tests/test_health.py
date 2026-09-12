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


def test_readiness_endpoint_returns_diagnostic_checks() -> None:
    with TestClient(app) as client:
        response = client.get("/api/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert {
        "database",
        "discovery",
        "network_identity",
        "technitium",
        "router_control",
    } <= set(body["checks"])
    for check in body["checks"].values():
        assert check["status"] in {
            "ready",
            "degraded",
            "unavailable",
            "not_configured",
            "unsupported",
        }
        assert check["message"]
