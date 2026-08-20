from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_local_frontend_origin_can_post_invoice() -> None:
    response = client.options(
        "/extractions/invoice",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:3000"
    )
    assert "POST" in response.headers["access-control-allow-methods"]


def test_unapproved_origin_receives_no_cors_permission() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "https://unapproved.example"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
