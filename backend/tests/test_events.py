import pytest
from pydantic import ValidationError

from sighttalk_api.core.events import (
    AudioChunkEvent,
    CostSnapshotEvent,
    ErrorEvent,
    SessionReadyEvent,
    VideoFrameEvent,
    parse_client_event,
)


def test_parse_audio_chunk_event() -> None:
    event = parse_client_event(
        {
            "type": "audio.chunk",
            "seq": 3,
            "mime": "audio/webm",
            "data": "abc123",
        }
    )

    assert isinstance(event, AudioChunkEvent)
    assert event.seq == 3
    assert event.mime == "audio/webm"


def test_parse_video_frame_event() -> None:
    event = parse_client_event(
        {
            "type": "video.frame",
            "seq": 8,
            "mime": "image/jpeg",
            "captured_at": 1781320000,
            "data": "image-data",
        }
    )

    assert isinstance(event, VideoFrameEvent)
    assert event.captured_at == 1781320000


def test_parse_unknown_client_event_fails() -> None:
    with pytest.raises(ValueError, match="Unsupported client event type"):
        parse_client_event({"type": "unknown.event"})


def test_server_event_serialization_uses_type_field() -> None:
    ready = SessionReadyEvent()
    error = ErrorEvent(stage="asr", message="Speech recognition failed.", retryable=True)
    cost = CostSnapshotEvent(
        frames_captured=4,
        frames_sent_to_model=2,
        asr_calls=1,
        vision_llm_calls=1,
        tts_calls=1,
        policy="normal",
    )

    assert ready.model_dump()["type"] == "session.ready"
    assert error.model_dump()["stage"] == "asr"
    assert cost.model_dump()["frames_sent_to_model"] == 2


def test_audio_chunk_rejects_negative_sequence() -> None:
    with pytest.raises(ValidationError):
        AudioChunkEvent(type="audio.chunk", seq=-1, mime="audio/webm", data="x")

