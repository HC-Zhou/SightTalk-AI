from __future__ import annotations

import asyncio
from typing import Any

from PIL import Image

from sighttalk_api.agent.context import AgentSessionContext
from sighttalk_api.agent.lifecycle import AgentLifecycle
from sighttalk_api.agent.livekit_runtime import encode_jpeg_under_limit
from sighttalk_api.providers.base import ImageFrame
from sighttalk_api.schemas.livekit import MediaPolicy


def make_context() -> AgentSessionContext:
    return AgentSessionContext(
        session_id="room-1",
        user_id="user-1",
        media_policy=MediaPolicy(
            mode="balanced",
            max_video_fps=1.0,
            max_jpeg_edge=1024,
            jpeg_quality=75,
            vad_enabled=True,
        ),
    )


def test_encode_jpeg_under_limit_compresses_large_frame() -> None:
    image = Image.new("RGB", (1280, 720), color=(82, 120, 180))

    data = encode_jpeg_under_limit(image, quality=90, max_bytes=20_000)

    assert len(data) <= 20_000
    assert data.startswith(b"\xff\xd8")


async def test_lifecycle_waits_for_provider_ready_before_audio() -> None:
    context = make_context()
    tooling = FakeTooling()
    lifecycle = AgentLifecycle(context=context, tooling=tooling)  # type: ignore[arg-type]
    task = asyncio.create_task(lifecycle.handle_audio_chunk(b"audio", sample_rate=16_000))

    await asyncio.sleep(0)
    assert tooling.audio_chunks == []

    lifecycle._provider_ready.set()  # noqa: SLF001
    await task

    assert tooling.audio_chunks == [b"audio"]
    assert lifecycle._provider_audio_started.is_set()  # noqa: SLF001


async def test_lifecycle_waits_for_first_provider_audio_before_image() -> None:
    context = make_context()
    tooling = FakeTooling(context)
    lifecycle = AgentLifecycle(context=context, tooling=tooling)  # type: ignore[arg-type]
    lifecycle._provider_ready.set()  # noqa: SLF001
    frame = ImageFrame(
        data=b"image",
        mime_type="image/jpeg",
        width=10,
        height=10,
    )
    task = asyncio.create_task(lifecycle.handle_image_frame(frame))

    await asyncio.sleep(0)
    assert tooling.image_frames == []

    lifecycle._provider_audio_started.set()  # noqa: SLF001
    await task

    assert tooling.image_frames == [frame]
    assert context.image_frames_sent == 1


async def test_lifecycle_publishes_single_terminal_error() -> None:
    context = make_context()
    tooling = FakeTooling()
    execution = FakeExecution()
    lifecycle = AgentLifecycle(
        context=context,
        tooling=tooling,  # type: ignore[arg-type]
        execution=execution,  # type: ignore[arg-type]
    )

    await lifecycle._handle_terminal_error("PROVIDER_UNAVAILABLE", "first")  # noqa: SLF001
    await lifecycle._handle_terminal_error("PROVIDER_UNAVAILABLE", "second")  # noqa: SLF001

    errors = [event for event in execution.events if event["type"] == "error"]
    assert len(errors) == 1
    assert errors[0]["message"] == "first"


class FakeTooling:
    def __init__(self, context: AgentSessionContext | None = None) -> None:
        self.context = context
        self.audio_chunks: list[bytes] = []
        self.image_frames: list[ImageFrame] = []

    async def send_audio(self, data: bytes, *, sample_rate: int) -> None:
        self.audio_chunks.append(data)

    async def send_image(self, frame: ImageFrame) -> bool:
        self.image_frames.append(frame)
        if self.context is not None:
            self.context.add_image_frame()
        return True

    async def close(self) -> None:
        return None

    def events(self) -> Any:
        raise AssertionError("events should not be called")


class FakeExecution:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish_event(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)

    async def stop(self) -> None:
        return None
