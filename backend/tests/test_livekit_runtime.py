from __future__ import annotations

import asyncio

from PIL import Image

from sighttalk_api.agent.livekit_runtime import LiveKitRoomAgent, encode_jpeg_under_limit


def test_encode_jpeg_under_limit_compresses_large_frame() -> None:
    image = Image.new("RGB", (1280, 720), color=(82, 120, 180))

    data = encode_jpeg_under_limit(image, quality=90, max_bytes=20_000)

    assert len(data) <= 20_000
    assert data.startswith(b"\xff\xd8")


async def test_audio_consumer_waits_for_provider_ready(monkeypatch) -> None:
    agent = object.__new__(LiveKitRoomAgent)
    agent._provider_ready = asyncio.Event()  # noqa: SLF001
    stream_created = False
    stream_closed = False

    class EmptyAudioStream:
        def __aiter__(self) -> EmptyAudioStream:
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        async def aclose(self) -> None:
            nonlocal stream_closed
            stream_closed = True

    def fake_from_track(**kwargs: object) -> EmptyAudioStream:
        nonlocal stream_created
        stream_created = True
        return EmptyAudioStream()

    monkeypatch.setattr(
        "sighttalk_api.agent.livekit_runtime.rtc.AudioStream.from_track",
        fake_from_track,
    )
    task = asyncio.create_task(agent._consume_audio(object()))  # noqa: SLF001

    await asyncio.sleep(0)
    assert stream_created is False

    agent._provider_ready.set()  # noqa: SLF001
    await task

    assert stream_created is True
    assert stream_closed is True


async def test_video_consumer_waits_for_first_provider_audio(monkeypatch) -> None:
    agent = object.__new__(LiveKitRoomAgent)
    agent._provider_ready = asyncio.Event()  # noqa: SLF001
    agent._provider_ready.set()  # noqa: SLF001
    agent._provider_audio_started = asyncio.Event()  # noqa: SLF001
    stream_created = False
    stream_closed = False

    class EmptyVideoStream:
        def __aiter__(self) -> EmptyVideoStream:
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

        async def aclose(self) -> None:
            nonlocal stream_closed
            stream_closed = True

    def fake_from_track(**kwargs: object) -> EmptyVideoStream:
        nonlocal stream_created
        stream_created = True
        return EmptyVideoStream()

    monkeypatch.setattr(
        "sighttalk_api.agent.livekit_runtime.rtc.VideoStream.from_track",
        fake_from_track,
    )
    task = asyncio.create_task(agent._consume_video(object()))  # noqa: SLF001

    await asyncio.sleep(0)
    assert stream_created is False

    agent._provider_audio_started.set()  # noqa: SLF001
    await task

    assert stream_created is True
    assert stream_closed is True
