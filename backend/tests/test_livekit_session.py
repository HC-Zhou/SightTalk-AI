from __future__ import annotations

import jwt
from fastapi.testclient import TestClient

from sighttalk_api.main import create_app
from sighttalk_api.services.session_registry import get_session_registry


class FakeRoomService:
    def __init__(self, **kwargs: object) -> None:
        pass

    async def ensure_room(self, *, room_name: str) -> None:
        return None


def make_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("SIGHTTALK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-auth-secret")
    return TestClient(create_app())


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_session_requires_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    client = make_client(monkeypatch, tmp_path)

    response = client.post("/api/v1/livekit/session", json={})

    assert response.status_code == 401


def test_create_session_returns_livekit_contract(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    client = make_client(monkeypatch, tmp_path)
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/livekit/session",
        json={"display_name": "Ada", "media_mode": "accurate"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_name"].startswith("sighttalk-")
    assert payload["participant_identity"].startswith("user-")
    assert payload["assistant_identity"] == f"assistant-{payload['room_name']}"
    assert payload["media_policy"]["mode"] == "accurate"
    decoded = jwt.decode(payload["participant_token"], "test-secret", algorithms=["HS256"])
    assert decoded["iss"] == "test-key"
    assert decoded["sub"] == payload["participant_identity"]
    assert decoded["video"]["room"] == payload["room_name"]
    assert decoded["video"]["roomJoin"] is True
    record = get_session_registry().get(payload["room_name"])
    assert record is not None
    assert record.user_id.startswith("user_")


def test_create_session_reports_missing_bailian_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_PROVIDER", "bailian")
    monkeypatch.setenv("BAILIAN_API_KEY", "")
    client = make_client(monkeypatch, tmp_path)
    headers = auth_headers(client)

    response = client.post("/api/v1/livekit/session", json={}, headers=headers)

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"
    assert "BAILIAN_API_KEY" in payload["error"]["message"]


def test_end_session_is_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    client = make_client(monkeypatch, tmp_path)
    headers = auth_headers(client)
    created = client.post("/api/v1/livekit/session", json={}, headers=headers).json()

    first = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/end",
        json={"participant_identity": created["participant_identity"]},
        headers=headers,
    )
    second = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/end",
        json={"participant_identity": created["participant_identity"]},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert get_session_registry().get(created["room_name"]) is None


def test_mock_events_endpoint_sends_agent_events(monkeypatch, tmp_path) -> None:
    sent: list[dict[str, object]] = []

    class FakeMessenger:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def send_json(
            self,
            *,
            room_name: str,
            topic: str,
            payload: dict[str, object],
        ) -> None:
            sent.append({"room_name": room_name, "topic": topic, "payload": payload})

    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitMessenger", FakeMessenger)
    client = make_client(monkeypatch, tmp_path)
    headers = auth_headers(client)
    created = client.post("/api/v1/livekit/session", json={}, headers=headers).json()

    response = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/mock-events",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert [event["topic"] for event in sent] == ["sighttalk.agent"] * 3


def test_agent_start_endpoint_enters_listening(monkeypatch, tmp_path) -> None:
    sent: list[dict[str, object]] = []
    started: list[str] = []

    class FakeMessenger:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def send_json(
            self,
            *,
            room_name: str,
            topic: str,
            payload: dict[str, object],
        ) -> None:
            sent.append({"room_name": room_name, "topic": topic, "payload": payload})

    class FakeAgentManager:
        def start(self, **kwargs: object) -> None:
            started.append(f"{kwargs['room_name']}:{kwargs['user_id']}")

        async def stop(self, room_name: str) -> None:
            return None

    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitMessenger", FakeMessenger)
    monkeypatch.setattr(
        "sighttalk_api.api.v1.livekit.get_agent_manager",
        lambda: FakeAgentManager(),
    )
    client = make_client(monkeypatch, tmp_path)
    headers = auth_headers(client)
    created = client.post("/api/v1/livekit/session", json={}, headers=headers).json()

    response = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/agent/start",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert len(started) == 1
    assert started[0].startswith(f"{created['room_name']}:user_")
    payloads = [event["payload"] for event in sent]
    assert payloads[0]["type"] == "agent.status"
    assert payloads[0]["status"] == "listening"
    assert payloads[1]["type"] == "cost.estimate"
    assert payloads[2]["type"] == "transcript.done"
