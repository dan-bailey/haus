from fastapi.testclient import TestClient

from app.main import app


def test_login_fails_closed_when_google_is_not_configured() -> None:
    response = TestClient(app).get("/auth/login")

    assert response.status_code == 503
    assert response.json() == {"detail": "Google sign-in is not configured"}