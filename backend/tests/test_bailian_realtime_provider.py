from __future__ import annotations

import json

import pytest

from sighttalk_api.providers.bailian import (
    BailianRealtimeProvider,
    normalize_realtime_model,
    normalize_realtime_url,
    realtime_url_with_model,
)
from sighttalk_api.providers.base import AudioChunk, ImageFrame, ProviderSessionConfig


class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        return None


def make_provider() -> BailianRealtimeProvider:
    return BailianRealtimeProvider(
        api_key="key",
        realtime_url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        region="cn-beijing",
        workspace_id="",
        model="qwen3-omni-flash-realtime",
    )


async def test_bailian_connect_uses_session_update(monkeypatch) -> None:
    fake_connection = FakeConnection()
    calls: list[dict[str, object]] = []

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        calls.append({"url": url, **kwargs})
        return fake_connection

    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = make_provider()

    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="qwen3-omni-flash-realtime",
            workspace_id="",
            system_prompt="你是视觉语音助手。",
        )
    )

    assert calls[0]["url"] == (
        "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
        "?model=qwen3-omni-flash-realtime"
    )
    first_payload = fake_connection.sent[0]
    assert first_payload["type"] == "session.update"
    assert first_payload["session"]["modalities"] == ["text", "audio"]  # type: ignore[index]
    assert first_payload["session"]["input_audio_format"] == "pcm"  # type: ignore[index]
    turn_detection = first_payload["session"]["turn_detection"]  # type: ignore[index]
    assert turn_detection["type"] == "server_vad"  # type: ignore[index]
    assert turn_detection["silence_duration_ms"] == 2000  # type: ignore[index]
    assert turn_detection["create_response"] is True  # type: ignore[index]
    assert turn_detection["interrupt_response"] is True  # type: ignore[index]


async def test_bailian_connect_uses_custom_turn_silence_duration(monkeypatch) -> None:
    fake_connection = FakeConnection()

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        return fake_connection

    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = BailianRealtimeProvider(
        api_key="key",
        realtime_url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        region="cn-beijing",
        workspace_id="",
        model="qwen3-omni-flash-realtime",
        turn_silence_duration_ms=2500,
    )

    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="qwen3-omni-flash-realtime",
            workspace_id="",
            system_prompt="test",
        )
    )

    first_payload = fake_connection.sent[0]
    turn_detection = first_payload["session"]["turn_detection"]  # type: ignore[index]
    assert turn_detection["silence_duration_ms"] == 2500  # type: ignore[index]


async def test_bailian_connect_retries_transient_failures(monkeypatch) -> None:
    fake_connection = FakeConnection()
    attempts = 0

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary outage")
        return fake_connection

    monkeypatch.setattr("sighttalk_api.providers.bailian.CONNECT_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = make_provider()

    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="qwen3-omni-flash-realtime",
            workspace_id="",
            system_prompt="test",
        )
    )

    assert attempts == 2
    assert fake_connection.sent[0]["type"] == "session.update"


async def test_bailian_connect_reports_underlying_failure(monkeypatch) -> None:
    attempts = 0

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        nonlocal attempts
        attempts += 1
        raise OSError("network down")

    monkeypatch.setattr("sighttalk_api.providers.bailian.CONNECT_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = make_provider()

    with pytest.raises(RuntimeError, match="network down"):
        await provider.connect(
            ProviderSessionConfig(
                session_id="room-1",
                model="qwen3-omni-flash-realtime",
                workspace_id="",
                system_prompt="test",
            )
        )

    assert attempts == 3


async def test_bailian_media_events_match_realtime_protocol(monkeypatch) -> None:
    fake_connection = FakeConnection()

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        return fake_connection

    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = make_provider()
    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="qwen3-omni-flash-realtime",
            workspace_id="",
            system_prompt="test",
        )
    )

    await provider.send_audio(AudioChunk(data=b"pcm", sample_rate=16_000))
    await provider.send_image(
        ImageFrame(data=b"jpeg", mime_type="image/jpeg", width=320, height=240)
    )

    audio_payload = fake_connection.sent[1]
    image_payload = fake_connection.sent[2]
    assert audio_payload == {
        "event_id": audio_payload["event_id"],
        "type": "input_audio_buffer.append",
        "audio": "cGNt",
    }
    assert image_payload == {
        "event_id": image_payload["event_id"],
        "type": "input_image_buffer.append",
        "image": "anBlZw==",
    }


async def test_bailian_skips_images_before_audio(monkeypatch) -> None:
    fake_connection = FakeConnection()

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        return fake_connection

    monkeypatch.setattr("sighttalk_api.providers.bailian.websockets.connect", fake_connect)
    provider = make_provider()
    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="qwen3-omni-flash-realtime",
            workspace_id="",
            system_prompt="test",
        )
    )

    await provider.send_image(
        ImageFrame(data=b"jpeg", mime_type="image/jpeg", width=320, height=240)
    )
    await provider.send_audio(AudioChunk(data=b"pcm", sample_rate=16_000))

    assert [payload["type"] for payload in fake_connection.sent] == [
        "session.update",
        "input_audio_buffer.append",
    ]


def test_realtime_url_with_model_preserves_existing_query() -> None:
    assert realtime_url_with_model("wss://example.test/realtime?foo=bar", "qwen") == (
        "wss://example.test/realtime?foo=bar&model=qwen"
    )


def test_realtime_normalizers_handle_legacy_defaults() -> None:
    assert normalize_realtime_url("") == "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    assert normalize_realtime_url("wss://dashscope.aliyuncs.com/api-ws/v1/inference") == (
        "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    assert normalize_realtime_model("multimodal-dialog") == "qwen3-omni-flash-realtime"


def test_bailian_maps_nested_error() -> None:
    provider = make_provider()

    event = provider._map_event(  # noqa: SLF001
        {
            "type": "error",
            "error": {
                "code": "invalid_request_error",
                "message": "Invalid payload",
            },
        }
    )

    assert event is not None
    assert event.type == "error"
    assert event.code == "invalid_request_error"
    assert event.message == "Invalid payload"


def test_bailian_maps_assistant_audio_transcript_done_as_final_text() -> None:
    provider = make_provider()

    event = provider._map_event(  # noqa: SLF001
        {
            "type": "response.audio_transcript.done",
            "response_id": "assistant-1",
            "transcript": "完整回答",
        }
    )

    assert event is not None
    assert event.type == "transcript_done"
    assert event.speaker == "assistant"
    assert event.text == "完整回答"
    assert event.message_id == "assistant-1"
