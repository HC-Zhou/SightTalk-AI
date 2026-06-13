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


def test_create_session_returns_livekit_contract(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/livekit/session",
        json={"display_name": "Ada", "media_mode": "accurate"},
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


def test_create_session_reports_missing_bailian_config(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "bailian")
    monkeypatch.setenv("BAILIAN_API_KEY", "")
    client = TestClient(create_app())

    response = client.post("/api/v1/livekit/session", json={})

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "CONFIGURATION_ERROR"
    assert "BAILIAN_API_KEY" in payload["error"]["message"]


def test_end_session_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    client = TestClient(create_app())
    created = client.post("/api/v1/livekit/session", json={}).json()

    first = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/end",
        json={"participant_identity": created["participant_identity"]},
    )
    second = client.post(
        f"/api/v1/livekit/session/{created['room_name']}/end",
        json={"participant_identity": created["participant_identity"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert get_session_registry().get(created["room_name"]) is None


def test_mock_events_endpoint_sends_agent_events(monkeypatch) -> None:
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
    client = TestClient(create_app())
    created = client.post("/api/v1/livekit/session", json={}).json()

    response = client.post(f"/api/v1/livekit/session/{created['room_name']}/mock-events")

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert [event["topic"] for event in sent] == ["sighttalk.agent"] * 3


def test_agent_start_endpoint_enters_listening(monkeypatch) -> None:
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
            started.append(str(kwargs["room_name"]))

        async def stop(self, room_name: str) -> None:
            return None

    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitRoomService", FakeRoomService)
    monkeypatch.setattr("sighttalk_api.api.v1.livekit.LiveKitMessenger", FakeMessenger)
    monkeypatch.setattr(
        "sighttalk_api.api.v1.livekit.get_agent_manager",
        lambda: FakeAgentManager(),
    )
    client = TestClient(create_app())
    created = client.post("/api/v1/livekit/session", json={}).json()

    response = client.post(f"/api/v1/livekit/session/{created['room_name']}/agent/start")

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert started == [created["room_name"]]
    payloads = [event["payload"] for event in sent]
    assert payloads[0]["type"] == "agent.status"
    assert payloads[0]["status"] == "listening"
    assert payloads[1]["type"] == "cost.estimate"
    assert payloads[2]["type"] == "transcript.done"
