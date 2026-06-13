from __future__ import annotations

import json

from sighttalk_api.agent.worker import AgentSession
from sighttalk_api.providers.base import AudioChunk, ProviderEvent, ProviderSessionConfig
from sighttalk_api.providers.mock import MockRealtimeProvider
from sighttalk_api.schemas.livekit import MediaPolicy


def make_session() -> AgentSession:
    return AgentSession(
        session_id="room-1",
        provider=MockRealtimeProvider(),
        media_policy=MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        ),
    )


def test_agent_maps_provider_transcript_event() -> None:
    session = make_session()

    payload = session.map_provider_event(
        ProviderEvent(
            type="transcript_done",
            speaker="assistant",
            text="hello",
            message_id="msg-1",
        )
    )

    assert payload is not None
    assert payload["type"] == "transcript.done"
    assert payload["speaker"] == "assistant"
    assert payload["text"] == "hello"


def test_agent_maps_provider_audio_event() -> None:
    session = make_session()

    payload = session.map_provider_event(
        ProviderEvent(
            type="audio_delta",
            audio=b"audio",
            mime_type="audio/pcm",
            message_id="msg-1",
        )
    )

    assert payload is not None
    assert payload["type"] == "audio.delta"
    assert payload["audio"] == "YXVkaW8="
    assert payload["mime_type"] == "audio/pcm"


async def test_agent_handles_mode_update() -> None:
    session = make_session()

    payload = await session.handle_control_message(
        json.dumps(
            {
                "type": "client.mode.update",
                "session_id": "room-1",
                "timestamp": "now",
                "mode": "accurate",
            }
        )
    )

    assert payload is not None
    assert payload["type"] == "cost.estimate"
    assert payload["mode"] == "accurate"


async def test_agent_handles_interrupt() -> None:
    session = make_session()

    payload = await session.handle_control_message(
        json.dumps(
            {
                "type": "client.interrupt",
                "session_id": "room-1",
                "timestamp": "now",
            }
        )
    )

    assert payload is not None
    assert payload["type"] == "agent.status"
    assert payload["status"] == "listening"


async def test_agent_audio_updates_cost_counter() -> None:
    session = make_session()

    await session.handle_audio(b"\0" * 32_000, sample_rate=16_000)

    payload = session.cost_event()
    assert payload["audio_seconds"] == 1.0


async def test_mock_provider_emits_events() -> None:
    provider = MockRealtimeProvider()
    await provider.connect(
        ProviderSessionConfig(
            session_id="room-1",
            model="mock",
            workspace_id="mock",
            system_prompt="test",
        )
    )
    await provider.send_audio(AudioChunk(data=b"hello", sample_rate=16_000))
    event_stream = provider.events()
    event = await anext(event_stream)

    assert event.type == "status"
