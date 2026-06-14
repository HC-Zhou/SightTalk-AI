from __future__ import annotations

import json

from sighttalk_api.providers.base import AudioChunk, ControlEvent, ImageFrame, ProviderSessionConfig
from sighttalk_api.providers.gemini_live import (
    GeminiLiveProvider,
    live_url_with_key,
    model_turn_audio,
    normalize_model_name,
)


class FakeConnection:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        return None


def make_provider() -> GeminiLiveProvider:
    return GeminiLiveProvider(
        api_key="key",
        live_url="wss://generativelanguage.googleapis.com/ws/live",
        model="gemini-2.0-flash-live-001",
        voice="Zephyr",
    )


async def test_gemini_connect_sends_setup(monkeypatch) -> None:
    fake_connection = FakeConnection()
    calls: list[dict[str, object]] = []

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        calls.append({"url": url, **kwargs})
        return fake_connection

    monkeypatch.setattr(
        "sighttalk_api.providers.gemini_live.websockets.connect",
        fake_connect,
    )
    provider = make_provider()

    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="gemini-2.0-flash-live-001",
            workspace_id="",
            system_prompt="你是视觉语音助手。",
        )
    )

    assert calls[0]["url"] == "wss://generativelanguage.googleapis.com/ws/live?key=key"
    setup = fake_connection.sent[0]["setup"]  # type: ignore[index]
    assert setup["model"] == "models/gemini-2.0-flash-live-001"  # type: ignore[index]
    assert setup["generation_config"]["response_modalities"] == ["AUDIO"]  # type: ignore[index]
    assert setup["input_audio_transcription"] == {}  # type: ignore[index]
    assert setup["output_audio_transcription"] == {}  # type: ignore[index]


async def test_gemini_sends_audio_image_and_interrupt(monkeypatch) -> None:
    fake_connection = FakeConnection()

    async def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        return fake_connection

    monkeypatch.setattr(
        "sighttalk_api.providers.gemini_live.websockets.connect",
        fake_connect,
    )
    provider = make_provider()
    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="gemini-2.0-flash-live-001",
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
    audio_chunk = fake_connection.sent[1]["realtime_input"]["media_chunks"][0]  # type: ignore[index]
    image_chunk = fake_connection.sent[2]["realtime_input"]["media_chunks"][0]  # type: ignore[index]
    assert audio_chunk["mime_type"] == "audio/pcm;rate=16000"  # type: ignore[index]
    assert image_chunk["mime_type"] == "image/jpeg"  # type: ignore[index]
    assert fake_connection.sent[3] == {"realtime_input": {"activity_end": {}}}


def test_gemini_maps_server_content() -> None:
    provider = make_provider()

    setup = provider._map_event({"setupComplete": {}})  # noqa: SLF001
    input_transcript = provider._map_event(  # noqa: SLF001
        {
            "serverContent": {
                "responseId": "response-1",
                "inputTranscription": {"text": "hello"},
            }
        }
    )
    audio = provider._map_event(  # noqa: SLF001
        {
            "serverContent": {
                "responseId": "response-1",
                "modelTurn": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "audio/pcm;rate=24000",
                                "data": "cGNt",
                            }
                        }
                    ]
                },
            }
        }
    )
    done = provider._map_event(  # noqa: SLF001
        {"serverContent": {"responseId": "response-1", "generationComplete": True}}
    )

    assert setup is not None
    assert setup.type == "status"
    assert input_transcript is not None
    assert input_transcript.type == "transcript_done"
    assert input_transcript.text == "hello"
    assert audio is not None
    assert audio.type == "audio_delta"
    assert audio.audio == b"pcm"
    assert done is not None
    assert done.type == "response_done"


def test_gemini_url_model_and_audio_helpers() -> None:
    assert live_url_with_key("wss://example.test/live?alt=sse", "key") == (
        "wss://example.test/live?alt=sse&key=key"
    )
    assert normalize_model_name("gemini-live") == "models/gemini-live"
    assert normalize_model_name("models/gemini-live") == "models/gemini-live"
    assert model_turn_audio(
        {
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "audio/pcm;rate=24000",
                        "data": "cGNt",
                    }
                }
            ]
        }
    ) == b"pcm"
