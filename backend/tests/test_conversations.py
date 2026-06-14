from __future__ import annotations

from fastapi.testclient import TestClient

from sighttalk_api.main import create_app


def make_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SIGHTTALK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-auth-secret-at-least-32-bytes")
    return TestClient(create_app())


def register_user(client: TestClient, *, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse"},
    )
    assert response.status_code == 200
    return response.json()


def auth_headers(auth: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def conversation_payload(session_id: str = "room-1") -> dict[str, object]:
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": "user-1",
                "speaker": "user",
                "text": "今天的天气怎么样",
                "final": True,
            },
            {
                "id": "assistant-1",
                "speaker": "assistant",
                "text": "今天适合出门散步。",
                "final": True,
            },
        ],
    }


def test_conversation_history_requires_auth(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)

    assert client.get("/api/v1/conversations").status_code == 401
    assert client.post("/api/v1/conversations", json=conversation_payload()).status_code == 401


def test_create_and_list_conversations_for_current_user(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    auth = register_user(client, email="ada@example.com")

    created = client.post(
        "/api/v1/conversations",
        json=conversation_payload(),
        headers=auth_headers(auth),
    )
    listed = client.get("/api/v1/conversations", headers=auth_headers(auth))

    assert created.status_code == 200
    assert created.json()["id"] == "room-1"
    assert created.json()["title"] == "今天的天气怎么样"
    assert [message["text"] for message in created.json()["messages"]] == [
        "今天的天气怎么样",
        "今天适合出门散步。",
    ]
    assert listed.status_code == 200
    assert listed.json()["conversations"] == [created.json()]


def test_conversation_history_is_isolated_by_user(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    ada = register_user(client, email="ada@example.com")
    grace = register_user(client, email="grace@example.com")

    response = client.post(
        "/api/v1/conversations",
        json=conversation_payload(),
        headers=auth_headers(ada),
    )

    assert response.status_code == 200
    assert client.get("/api/v1/conversations", headers=auth_headers(grace)).json() == {
        "conversations": []
    }


def test_saving_same_session_replaces_existing_conversation(monkeypatch, tmp_path) -> None:
    client = make_client(monkeypatch, tmp_path)
    auth = register_user(client, email="ada@example.com")

    first = conversation_payload()
    second = conversation_payload()
    second["messages"] = [
        {
            "id": "user-2",
            "speaker": "user",
            "text": "改成新的问题",
            "final": True,
        }
    ]

    first_response = client.post(
        "/api/v1/conversations",
        json=first,
        headers=auth_headers(auth),
    )
    second_response = client.post(
        "/api/v1/conversations",
        json=second,
        headers=auth_headers(auth),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    listed = client.get("/api/v1/conversations", headers=auth_headers(auth))

    assert listed.status_code == 200
    conversations = listed.json()["conversations"]
    assert len(conversations) == 1
    assert conversations[0]["title"] == "改成新的问题"
