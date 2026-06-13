from __future__ import annotations

import json

from fastapi.testclient import TestClient

from sighttalk_api.main import create_app


def make_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SIGHTTALK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    return TestClient(create_app())


def register_user(client: TestClient, *, email: str = "ada@example.com") -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse"},
    )
    assert response.status_code == 200
    return response.json()


def test_register_creates_user_and_token(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)

    payload = register_user(client)

    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["user"]["email"] == "ada@example.com"
    assert str(payload["user"]["user_id"]).startswith("user_")


def test_register_rejects_duplicate_email(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    register_user(client)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ADA@example.com", "password": "correct-horse"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_ALREADY_EXISTS"


def test_password_file_does_not_contain_plaintext(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)

    register_user(client)

    raw = (tmp_path / "users.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    stored_user = payload["users"][0]
    assert "correct-horse" not in raw
    assert stored_user["password_hash"]["algorithm"] == "pbkdf2_sha256"
    assert "password" not in stored_user


def test_login_success_and_failure(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    register_user(client)

    success = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "correct-horse"},
    )
    failure = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )

    assert success.status_code == 200
    assert success.json()["user"]["email"] == "ada@example.com"
    assert failure.status_code == 401
    assert failure.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_validates_bearer_token(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    registered = register_user(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == registered["user"]


def test_me_rejects_missing_and_expired_token(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    assert client.get("/api/v1/auth/me").status_code == 401

    monkeypatch.setenv("AUTH_TOKEN_TTL_SECONDS", "-1")
    from sighttalk_api.core.config import get_settings

    get_settings.cache_clear()
    expired_client = TestClient(create_app())
    registered = register_user(expired_client)

    response = expired_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )

    assert response.status_code == 401
