from __future__ import annotations

import json

from sighttalk_api.providers.base import AudioChunk, ControlEvent, ImageFrame, ProviderSessionConfig
from sighttalk_api.providers.openai_realtime import (
    OpenAIRealtimeProvider,
    realtime_url_with_model,
)


class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        return None


def make_provider() -> OpenAIRealtimeProvider:
    return OpenAIRealtimeProvider(
        api_key="key",
        realtime_url="wss://api.openai.com/v1/realtime",
        model="gpt-realtime",
        voice="alloy",
    )


async def test_openai_connect_uses_session_update(monkeypatch) -> None:
    fake_connection = FakeConnection()
    calls: list[dict[str, object]] = []

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        calls.append({"url": url, **kwargs})
        return fake_connection

    monkeypatch.setattr(
        "sighttalk_api.providers.openai_realtime.websockets.connect",
        fake_connect,
    )
    provider = make_provider()

    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="gpt-realtime",
            workspace_id="",
            system_prompt="You are a visual voice assistant.",
        )
    )

    assert calls[0]["url"] == "wss://api.openai.com/v1/realtime?model=gpt-realtime"
    headers = calls[0]["additional_headers"]
    assert headers["Authorization"] == "Bearer key"  # type: ignore[index]
    first_payload = fake_connection.sent[0]
    assert first_payload["type"] == "session.update"
    session = first_payload["session"]  # type: ignore[index]
    assert session["modalities"] == ["text", "audio"]  # type: ignore[index]
    assert session["input_audio_format"] == "pcm16"  # type: ignore[index]
    assert session["output_audio_format"] == "pcm16"  # type: ignore[index]
    assert session["voice"] == "alloy"  # type: ignore[index]


async def test_openai_sends_audio_image_and_interrupt(monkeypatch) -> None:
    fake_connection = FakeConnection()

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        return fake_connection

    monkeypatch.setattr(
        "sighttalk_api.providers.openai_realtime.websockets.connect",
        fake_connect,
    )
    provider = make_provider()
    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="gpt-realtime",
            workspace_id="",
            system_prompt="test",
        )
    )

    skipped = await provider.send_image(
        ImageFrame(data=b"jpeg", mime_type="image/jpeg", width=1, height=1)
    )
    await provider.send_audio(AudioChunk(data=b"pcm", sample_rate=16_000))
    sent = await provider.send_image(
        ImageFrame(data=b"jpeg", mime_type="image/jpeg", width=1, height=1)
    )
    await provider.send_control(ControlEvent(type="interrupt"))

    assert skipped is False
    assert sent is True
    assert fake_connection.sent[1]["type"] == "input_audio_buffer.append"
    assert fake_connection.sent[2]["type"] == "conversation.item.create"
    assert fake_connection.sent[3]["type"] == "response.cancel"


def test_openai_maps_realtime_events() -> None:
    provider = make_provider()

    user_done = provider._map_event(  # noqa: SLF001
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "user-1",
            "transcript": "hello",
        }
    )
    assistant_delta = provider._map_event(  # noqa: SLF001
        {
            "type": "response.audio_transcript.delta",
            "response_id": "response-1",
            "delta": "hi",
        }
    )
    audio_delta = provider._map_event(  # noqa: SLF001
        {
            "type": "response.audio.delta",
            "response_id": "response-1",
            "delta": "cGNt",
        }
    )

    assert user_done is not None
    assert user_done.type == "transcript_done"
    assert user_done.speaker == "user"
    assert user_done.text == "hello"
    assert assistant_delta is not None
    assert assistant_delta.type == "transcript_delta"
    assert assistant_delta.text == "hi"
    assert audio_delta is not None
    assert audio_delta.type == "audio_delta"
    assert audio_delta.audio == b"pcm"


def test_openai_realtime_url_with_model_preserves_query() -> None:
    assert realtime_url_with_model("wss://example.test/realtime?foo=bar", "gpt-realtime") == (
        "wss://example.test/realtime?foo=bar&model=gpt-realtime"
    )
