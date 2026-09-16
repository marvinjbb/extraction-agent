from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(response.headers["x-request-id"]) == 32


def test_caller_supplied_request_id_is_not_trusted() -> None:
    response = client.get("/health", headers={"X-Request-ID": "caller-value"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "caller-value"
    assert len(response.headers["x-request-id"]) == 32
