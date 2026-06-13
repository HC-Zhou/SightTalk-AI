from __future__ import annotations

from typing import Any, cast

from sighttalk_api.agent.execution import LiveKitExecution
from sighttalk_api.providers.base import ImageFrame
from sighttalk_api.schemas.livekit import MediaMode, MediaPolicy


class FakePublication:
    def __init__(self, sid: str) -> None:
        self.sid = sid


class FakeAudioSource:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def aclose(self) -> None:
        self._events.append("source:close")


class FakeLocalParticipant:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def unpublish_track(self, track_sid: str) -> None:
        self._events.append(f"unpublish:{track_sid}")


class FakeRoom:
    def __init__(self, events: list[str]) -> None:
        self.local_participant = FakeLocalParticipant(events)
        self._events = events

    async def disconnect(self) -> None:
        self._events.append("room:disconnect")


def make_execution() -> LiveKitExecution:
    async def on_audio_chunk(_data: bytes, *, sample_rate: int) -> None:
        return None

    async def on_image_frame(_frame: ImageFrame) -> None:
        return None

    async def on_control_message(_data: bytes) -> None:
        return None

    return LiveKitExecution(
        room_name="room-1",
        livekit_url="ws://localhost:7880",
        assistant_token="token",
        media_policy=lambda: MediaPolicy(mode=MediaMode.BALANCED),
        on_audio_chunk=on_audio_chunk,
        on_image_frame=on_image_frame,
        on_control_message=on_control_message,
    )


async def test_livekit_execution_stop_releases_audio_track_once() -> None:
    events: list[str] = []
    execution = make_execution()
    internals = cast(Any, execution)
    internals._room = FakeRoom(events)
    internals._connected = True
    internals._assistant_audio_source = FakeAudioSource(events)
    internals._assistant_audio_publication = FakePublication("track-1")

    await execution.stop()
    await execution.stop()

    assert events == ["unpublish:track-1", "source:close", "room:disconnect"]
