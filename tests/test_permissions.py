from fastapi.testclient import TestClient

from app.main import app


def test_current_user_requires_a_session() -> None:
    response = TestClient(app).get("/invitations/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}